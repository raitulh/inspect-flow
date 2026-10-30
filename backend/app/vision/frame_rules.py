"""Shared single-frame evaluators used by uploaded-video and RTSP pipelines."""
from __future__ import annotations

import json
import os
from typing import Any

import cv2
import numpy as np

from app.models import InspectionRule
from app.vision.surface_defects import detect_surface_defects
from app.vision.yolo_cpu import detect_objects_cpu, model_identity


def normalized_roi(frame: np.ndarray, zone: list[float]):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = zone
    return max(0, int(x1 * w)), max(0, int(y1 * h)), min(w, int(x2 * w)), min(h, int(y2 * h))


def evaluate_frame_rules(
    frame: np.ndarray,
    rules: list[InspectionRule],
    state: dict[str, Any] | None = None,
    timestamp_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    state = state if state is not None else {}
    findings: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.is_enabled:
            continue
        config = json.loads(rule.config_json or "{}")
        rid = rule.id
        if rule.rule_type == "surface_defect":
            detections = detect_surface_defects(frame, config)
            minimum = float(config.get("score_threshold", 0.25))
            for detection in detections:
                if detection["score"] >= minimum:
                    findings.append({"rule": rule, "event_type": "surface_defect_detected", "details": detection, "timestamp": timestamp_seconds})
        elif rule.rule_type == "object_detection":
            detections = detect_objects_cpu(frame, config)
            target_classes = config.get("target_classes", [])
            if target_classes:
                detections = [d for d in detections if d["label"] in target_classes]
            mode = config.get("mode", "detect")
            model_path = str(config.get("model_path") or os.getenv("YOLO_MODEL_PATH", ""))
            identity = model_identity(model_path) if model_path else {"model_version": "yolo-cpu:unconfigured"}
            if mode == "missing":
                present = bool(detections)
                state.setdefault(rid, {})["absence_count"] = 0 if present else state.setdefault(rid, {}).get("absence_count", 0) + 1
                required = int(config.get("min_consecutive", 3))
                if not present and state[rid]["absence_count"] >= required:
                    findings.append({"rule": rule, "event_type": "potential_missing_component", "details": {"observation": "target_class_not_detected", "target_classes": target_classes, "frames_absent": state[rid]["absence_count"], "detector": "YOLO CPU", **identity}, "timestamp": timestamp_seconds})
            else:
                for detection in detections:
                    findings.append({"rule": rule, "event_type": "object_detection_alert", "details": detection, "timestamp": timestamp_seconds})
        elif rule.rule_type == "color_presence":
            zone = config.get("zone", [0.0, 0.0, 1.0, 1.0])
            left, top, right, bottom = normalized_roi(frame, zone)
            roi = frame[top:bottom, left:right]
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
            ratio = float(np.count_nonzero(mask) / max(1, mask.size))
            present = ratio >= float(config.get("min_pixel_ratio", 0.015))
            item = state.setdefault(rid, {})
            item["absence_count"] = 0 if present else item.get("absence_count", 0) + 1
            required = int(config.get("min_consecutive", 3))
            if not present and item["absence_count"] == required:
                findings.append({"rule": rule, "event_type": "potential_missing_component", "details": {"observation": "component_color_not_observed", "pixel_ratio": round(ratio, 6), "minimum_pixel_ratio": config.get("min_pixel_ratio", 0.015), "note": "HSV threshold only; not semantic recognition."}, "timestamp": timestamp_seconds})
        elif rule.rule_type == "motion_stall":
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            previous = state.setdefault(rid, {}).get("previous_gray")
            item = state[rid]
            if previous is None:
                item["last_motion_at"] = timestamp_seconds
            else:
                if previous.shape != gray.shape:
                    previous = cv2.resize(previous, (gray.shape[1], gray.shape[0]))
                difference = float(np.mean(cv2.absdiff(gray, previous)))
                if difference >= float(config.get("mean_difference_threshold", 2.0)):
                    item["last_motion_at"] = timestamp_seconds
                elapsed = timestamp_seconds - float(item.get("last_motion_at", timestamp_seconds))
                seconds = float(config.get("inactivity_seconds", 5.0))
                if elapsed >= seconds and not item.get("stall_raised"):
                    item["stall_raised"] = True
                    findings.append({"rule": rule, "event_type": "possible_station_stall", "details": {"mean_frame_difference": round(difference, 4), "inactivity_seconds": round(elapsed, 3), "note": "Vision estimate only; not PLC telemetry."}, "timestamp": timestamp_seconds})
                elif difference >= float(config.get("mean_difference_threshold", 2.0)):
                    item["stall_raised"] = False
            item["previous_gray"] = gray
    return findings
