"""CPU-first video inspection based on explicit station rules.

This is a configurable image-processing baseline, not a general object detector.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AnalysisJob, DetectionEvent, InspectionRule, VideoAsset
from app.services.notifications import dispatch_event_webhook
from app.vision.frame_rules import evaluate_frame_rules


@dataclass
class InspectionFinding:
    rule_id: str
    rule_version: int
    event_type: str
    severity: str
    summary: str
    timestamp_seconds: float
    evidence_frame: np.ndarray
    details: dict[str, Any]


def _normalized_roi(frame: np.ndarray, zone: list[float]) -> tuple[int, int, int, int]:
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = zone
    left = max(0, min(width - 1, int(x1 * width)))
    top = max(0, min(height - 1, int(y1 * height)))
    right = max(left + 1, min(width, int(x2 * width)))
    bottom = max(top + 1, min(height, int(y2 * height)))
    return left, top, right, bottom


def _evaluate_color_presence(rule: InspectionRule, frame: np.ndarray) -> tuple[bool, dict[str, Any]]:
    config = json.loads(rule.config_json or "{}")
    zone = config.get("zone", [0.0, 0.0, 1.0, 1.0])
    left, top, right, bottom = _normalized_roi(frame, zone)
    roi = frame[top:bottom, left:right]
    if roi.size == 0:
        return False, {"reason": "empty_inspection_zone"}
    if config.get("adaptive_lighting", False):
        hsv_pre = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv_pre)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        v = clahe.apply(v)
        hsv = cv2.merge([h, s, v])
    else:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower = np.array(config.get("hsv_lower", [0, 0, 0]), dtype=np.uint8)
    upper = np.array(config.get("hsv_upper", [179, 255, 255]), dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    pixel_ratio = float(np.count_nonzero(mask) / mask.size)
    min_ratio = float(config.get("min_pixel_ratio", 0.015))
    present = pixel_ratio >= min_ratio
    return present, {
        "observation": "component_color_present" if present else "component_color_not_observed",
        "pixel_ratio": round(pixel_ratio, 6),
        "minimum_pixel_ratio": min_ratio,
        "zone_normalized": zone,
        "hsv_lower": lower.tolist(),
        "hsv_upper": upper.tolist(),
        "note": "Color-threshold evidence only; not semantic component recognition.",
    }


def _overlay_evidence(frame: np.ndarray, rule: InspectionRule, details: dict[str, Any]) -> np.ndarray:
    output = frame.copy()
    try:
        config = json.loads(rule.config_json or "{}")
        zone = config.get("zone", [0.0, 0.0, 1.0, 1.0])
        x1, y1, x2, y2 = _normalized_roi(output, zone)
        cv2.rectangle(output, (x1, y1), (x2, y2), (70, 139, 197), 2)
    except Exception:
        pass
    bbox = details.get("bbox_xyxy")
    if isinstance(bbox, list) and len(bbox) == 4:
        x1, y1, x2, y2 = [int(value) for value in bbox]
        cv2.rectangle(output, (x1, y1), (x2, y2), (40, 190, 120), 2)
    caption = f"LineGuard rule: {rule.name[:50]}"
    cv2.rectangle(output, (0, 0), (output.shape[1], min(36, output.shape[0])), (30, 37, 36), -1)
    cv2.putText(output, caption, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (246, 240, 230), 1, cv2.LINE_AA)
    return output


def analyze_video(db: Session, job: AnalysisJob, video: VideoAsset, rules: list[InspectionRule], root: Path) -> dict[str, Any]:
    """Evaluate configured rules on a video and persist reviewable findings.

    It uses bounded frame sampling. A missing-part finding is produced only when an
    enabled color_presence rule observes the configured color below its threshold for
    min_consecutive sampled frames. This behavior is deterministic but is not a trained CV model.
    """
    storage_path = root / video.storage_key
    cap = cv2.VideoCapture(str(storage_path))
    if not cap.isOpened():
        raise ValueError("Video cannot be decoded by the configured OpenCV backend")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 25.0
    reported_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_stride = get_settings().default_frame_stride
    if reported_frames > 0:
        frame_stride = max(frame_stride, int(np.ceil(reported_frames / get_settings().max_sampled_frames)))

    enabled_rules = [r for r in rules if r.is_enabled]
    counts: dict[str, int] = {rule.id: 0 for rule in enabled_rules}
    first_missing: dict[str, tuple[float, np.ndarray, dict[str, Any]]] = {}
    last_motion_at: dict[str, float] = {}
    stall_findings: dict[str, tuple[float, np.ndarray, dict[str, Any]]] = {}
    previous_gray_by_rule: dict[str, np.ndarray] = {}
    sampled_frames = 0
    frame_index = 0
    latest_frame: np.ndarray | None = None
    advanced_state: dict[str, Any] = {}
    advanced_first: dict[str, tuple[InspectionRule, str, float, np.ndarray, dict[str, Any]]] = {}
    advanced_rules = [r for r in enabled_rules if r.rule_type in {"surface_defect", "object_detection"}]

    try:
        while sampled_frames < get_settings().max_sampled_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % frame_stride != 0:
                frame_index += 1
                continue
            sampled_frames += 1
            timestamp = frame_index / fps
            latest_frame = frame

            for rule in enabled_rules:
                config = json.loads(rule.config_json or "{}")
                if rule.rule_type == "color_presence":
                    present, details = _evaluate_color_presence(rule, frame)
                    required = int(config.get("min_consecutive", 3))
                    if required < 1 or required > 100:
                        required = 3
                    counts[rule.id] = 0 if present else counts[rule.id] + 1
                    if not present and counts[rule.id] >= required and rule.id not in first_missing:
                        first_missing[rule.id] = (timestamp, frame.copy(), details)
                elif rule.rule_type == "motion_stall":
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    threshold = float(config.get("mean_difference_threshold", 2.0))
                    previous_gray = previous_gray_by_rule.get(rule.id)
                    if previous_gray is None:
                        last_motion_at[rule.id] = timestamp
                    else:
                        resized_prev = cv2.resize(previous_gray, (gray.shape[1], gray.shape[0])) if previous_gray.shape != gray.shape else previous_gray
                        difference = float(np.mean(cv2.absdiff(gray, resized_prev)))
                        if difference >= threshold:
                            last_motion_at[rule.id] = timestamp
                        elif rule.id not in last_motion_at:
                            last_motion_at[rule.id] = timestamp
                        elapsed = timestamp - last_motion_at[rule.id]
                        threshold_seconds = float(config.get("inactivity_seconds", 5.0))
                        if elapsed >= threshold_seconds and rule.id not in stall_findings:
                            stall_findings[rule.id] = (timestamp, frame.copy(), {
                                "observation": "low_frame_difference_persistence",
                                "mean_frame_difference": round(difference, 4),
                                "inactivity_seconds": round(elapsed, 3),
                                "configured_threshold_seconds": threshold_seconds,
                                "note": "Vision-derived inactivity estimate; not authoritative machine telemetry.",
                            })
                    previous_gray_by_rule[rule.id] = gray

            if advanced_rules:
                for item in evaluate_frame_rules(frame, advanced_rules, advanced_state, timestamp):
                    rule = item["rule"]
                    if rule.id not in advanced_first:
                        advanced_first[rule.id] = (rule, item["event_type"], item["timestamp"], frame.copy(), item["details"])
            frame_index += 1
    finally:
        cap.release()

    if sampled_frames == 0 or latest_frame is None:
        raise ValueError("Video contains no decodable frames")

    evidence_dir = root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    findings: list[InspectionFinding] = []
    for rule in enabled_rules:
        if rule.id in first_missing:
            timestamp, frame, details = first_missing[rule.id]
            findings.append(InspectionFinding(
                rule_id=rule.id,
                rule_version=rule.version,
                event_type="potential_missing_component",
                severity=rule.severity,
                summary=f"Potential missing component: {rule.name}",
                timestamp_seconds=timestamp,
                evidence_frame=_overlay_evidence(frame, rule, details),
                details=details,
            ))
        if rule.id in stall_findings:
            timestamp, frame, details = stall_findings[rule.id]
            findings.append(InspectionFinding(
                rule_id=rule.id,
                rule_version=rule.version,
                event_type="possible_station_stall",
                severity=rule.severity,
                summary=f"Possible station inactivity: {rule.name}",
                timestamp_seconds=timestamp,
                evidence_frame=_overlay_evidence(frame, rule, details),
                details=details,
            ))
        if rule.id in advanced_first:
            _, event_type, timestamp, frame, details = advanced_first[rule.id]
            findings.append(InspectionFinding(
                rule_id=rule.id,
                rule_version=rule.version,
                event_type=event_type,
                severity=rule.severity,
                summary=f"{event_type.replace('_', ' ').title()}: {rule.name}",
                timestamp_seconds=timestamp,
                evidence_frame=_overlay_evidence(frame, rule, details),
                details=details,
            ))

    for finding in findings:
        key = f"evidence/{job.id}-{finding.rule_id}.jpg"
        target = root / key
        ok = cv2.imwrite(str(target), finding.evidence_frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            raise RuntimeError("Could not write inspection evidence image")
        db.add(DetectionEvent(
            organization_id=job.organization_id,
            station_id=job.station_id,
            video_id=job.video_id,
            job_id=job.id,
            rule_id=finding.rule_id,
            event_type=finding.event_type,
            severity=finding.severity,
            status="open",
            summary=finding.summary,
            details_json=json.dumps(finding.details, separators=(",", ":")),
            confidence=(
                float(finding.details["confidence"])
                if isinstance(finding.details.get("confidence"), (int, float)) else None
            ),
            timestamp_seconds=max(0.0, finding.timestamp_seconds),
            evidence_key=key,
            model_version=str(finding.details.get("model_version") or (
                "lineguard-surface-candidate-v1" if finding.event_type == "surface_defect_detected"
                else "lineguard-cpu-vision-v0.2"
            )),
            rule_version=finding.rule_version,
        ))
        created += 1
        try:
            dispatch_event_webhook({
                "source": "video_analysis",
                "job_id": job.id,
                "station_id": job.station_id,
                "event_type": finding.event_type,
                "severity": finding.severity,
                "summary": finding.summary,
                "timestamp_seconds": max(0.0, finding.timestamp_seconds),
            })
        except Exception:
            pass

    summary = {
        "provider": "lineguard_cpu_vision",
        "model_version": "lineguard-cpu-vision-v0.2",
        "frames_sampled": sampled_frames,
        "source_frame_count": reported_frames or None,
        "effective_frame_stride": frame_stride,
        "fps_reported": round(fps, 3),
        "rules_evaluated": len(enabled_rules),
        "events_created": created,
        "limitations": [
            "Color-presence inspection is a configured HSV heuristic, not semantic object recognition.",
            "Motion-stall is a vision-derived estimate and may be affected by static scenes or camera movement.",
            "Scratch/crack heuristic detections are candidate regions, not calibrated defect probabilities.",
            "YOLO requires a separately supplied, correctly licensed model weight file and CPU runtime.",
            "No finding does not prove that an item is defect-free.",
        ],
    }
    return summary
