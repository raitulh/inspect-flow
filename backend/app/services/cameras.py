"""RTSP/webcam capture worker with reconnects, CPU throttling, live frame caching, and event deduplication."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import cv2
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import CameraSource, DetectionEvent, InspectionRule
from app.services.notifications import dispatch_event_webhook
from app.vision.frame_rules import evaluate_frame_rules

logger = logging.getLogger("lineguard.camera_worker")


def _camera_snapshot(camera_id: str):
    with SessionLocal() as db:
        camera = db.get(CameraSource, camera_id)
        if not camera or camera.source_type not in {"rtsp", "webcam"}:
            return None
        rules = list(db.scalars(select(InspectionRule).where(
            InspectionRule.organization_id == camera.organization_id,
            InspectionRule.station_id == camera.station_id,
            InspectionRule.is_enabled.is_(True),
        )).all())
        return {
            "id": camera.id,
            "organization_id": camera.organization_id,
            "station_id": camera.station_id,
            "source_uri": camera.source_uri,
            "source_type": camera.source_type,
            "rules": rules,
        }


def camera_stream_loop(camera_id: str, stop_event: threading.Event) -> None:
    settings = get_settings()
    state: dict[str, Any] = {}
    last_raised: dict[str, float] = {}
    last_rule_refresh = 0.0
    snapshot = None
    cap = None
    last_sample = 0.0
    last_heartbeat = 0.0
    last_cache_save = 0.0
    stream_time = 0.0
    while not stop_event.is_set():
        now = time.monotonic()
        if snapshot is None or now - last_rule_refresh >= 5:
            snapshot = _camera_snapshot(camera_id)
            last_rule_refresh = now
            if snapshot is None:
                break
        source = snapshot["source_uri"]
        if not source:
            break
        if cap is None or not cap.isOpened():
            try:
                if snapshot["source_type"] == "webcam":
                    source = int(source)
                    cap = cv2.VideoCapture(source)
                else:
                    timeout_params = [
                        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                        cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
                    ]
                    cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, timeout_params)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    raise RuntimeError("OpenCV could not open the configured camera stream")
                with SessionLocal() as db:
                    camera = db.get(CameraSource, camera_id)
                    if camera:
                        camera.status = "connected"
                        camera.last_error = None
                        db.commit()
                state.clear()
                logger.info("Camera %s connected", camera_id)
            except Exception as exc:
                if cap is not None:
                    cap.release()
                cap = None
                with SessionLocal() as db:
                    camera = db.get(CameraSource, camera_id)
                    if camera:
                        camera.status = "disconnected"
                        camera.last_error = str(exc)[:500]
                        db.commit()
                stop_event.wait(3)
                continue

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.release()
            cap = None
            with SessionLocal() as db:
                camera = db.get(CameraSource, camera_id)
                if camera:
                    camera.status = "reconnecting"
                    camera.last_error = "No frame received; attempting reconnect"
                    db.commit()
            stop_event.wait(1)
            continue

        now = time.monotonic()
        if now - last_cache_save >= 0.12:
            last_cache_save = now
            try:
                cache_dir = settings.storage_root / "cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                preview = frame
                h, w = preview.shape[:2]
                if w > 960:
                    preview = cv2.resize(preview, (960, int(h * 960 / w)))
                cv2.imwrite(str(cache_dir / f"live-{camera_id}.jpg"), preview, [cv2.IMWRITE_JPEG_QUALITY, 80])
            except Exception:
                pass

        if now - last_sample >= settings.live_camera_sample_seconds:
            last_sample = now
            stream_time += settings.live_camera_sample_seconds
            try:
                findings = evaluate_frame_rules(frame, snapshot["rules"], state, stream_time)
            except Exception as exc:
                logger.exception("Camera %s rule evaluation failed", camera_id)
                with SessionLocal() as db:
                    camera = db.get(CameraSource, camera_id)
                    if camera:
                        camera.last_error = f"Rule evaluation error: {str(exc)[:350]}"
                        db.commit()
                findings = []
            for finding in findings:
                rule = finding["rule"]
                dedupe_key = rule.id + ":" + finding["event_type"]
                if now - last_raised.get(dedupe_key, -1e9) < settings.live_event_dedupe_seconds:
                    continue
                last_raised[dedupe_key] = now
                evidence_dir = settings.storage_root / "evidence"
                evidence_dir.mkdir(parents=True, exist_ok=True)
                evidence_key = f"evidence/live-{camera_id}-{int(time.time())}-{rule.id[:8]}.jpg"
                annotated = frame.copy()
                bbox = finding["details"].get("bbox_xyxy")
                if isinstance(bbox, list) and len(bbox) == 4:
                    x1, y1, x2, y2 = [int(value) for value in bbox]
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (40, 190, 120), 2)
                cv2.putText(annotated, f"LineGuard LIVE | {finding['event_type']}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (30, 160, 230), 2, cv2.LINE_AA)
                if not cv2.imwrite(str(settings.storage_root / evidence_key), annotated, [cv2.IMWRITE_JPEG_QUALITY, 88]):
                    continue
                details = dict(finding["details"])
                details.update({"camera_id": camera_id, "source": "rtsp_live", "timestamp_monotonic_seconds": stream_time})
                with SessionLocal() as db:
                    db.add(DetectionEvent(
                        organization_id=snapshot["organization_id"],
                        station_id=snapshot["station_id"],
                        video_id=None,
                        job_id=None,
                        rule_id=rule.id,
                        event_type=finding["event_type"],
                        severity=rule.severity,
                        status="open",
                        summary=f"Live camera finding: {rule.name}",
                        details_json=json.dumps(details, separators=(",", ":")),
                        confidence=details.get("confidence"),
                        timestamp_seconds=stream_time,
                        evidence_key=evidence_key,
                        model_version=str(details.get("model_version") or (
                            "lineguard-surface-candidate-v1" if finding["event_type"] == "surface_defect_detected"
                            else "lineguard-live-cpu-v0.2"
                        )),
                        rule_version=rule.version,
                    ))
                    db.commit()
                try:
                    dispatch_event_webhook({
                        "source": "live_camera",
                        "camera_id": camera_id,
                        "station_id": snapshot["station_id"],
                        "rule_name": rule.name,
                        "event_type": finding["event_type"],
                        "severity": rule.severity,
                        "summary": f"Live camera finding: {rule.name}",
                        "timestamp_seconds": stream_time,
                    })
                except Exception:
                    pass

        if now - last_heartbeat >= 5.0:
            with SessionLocal() as db:
                camera = db.get(CameraSource, camera_id)
                if camera:
                    camera.status = "connected"
                    camera.last_frame_at = datetime.now(timezone.utc)
                    camera.last_error = None
                    db.commit()
            last_heartbeat = now
        stop_event.wait(0.02)

    if cap is not None:
        cap.release()
    with SessionLocal() as db:
        camera = db.get(CameraSource, camera_id)
        if camera and camera.status not in {"disconnected", "not_tested"}:
            camera.status = "stopped"
            db.commit()


def camera_worker_loop() -> None:
    logger.info("RTSP camera worker started")
    stop_events: dict[str, threading.Event] = {}
    threads: dict[str, threading.Thread] = {}
    try:
        while True:
            with SessionLocal() as db:
                camera_ids = list(db.scalars(select(CameraSource.id).where(
                    CameraSource.source_type.in_(["rtsp", "webcam"]),
                    CameraSource.source_uri.is_not(None),
                )).all())
            for camera_id in camera_ids:
                if camera_id not in threads or not threads[camera_id].is_alive():
                    event = threading.Event()
                    thread = threading.Thread(target=camera_stream_loop, args=(camera_id, event), daemon=True, name=f"camera-{camera_id[:8]}")
                    stop_events[camera_id] = event
                    threads[camera_id] = thread
                    thread.start()
            for dead_id in list(threads):
                if dead_id not in camera_ids:
                    stop_events[dead_id].set()
                    threads[dead_id].join(timeout=2)
                    threads.pop(dead_id, None)
                    stop_events.pop(dead_id, None)
            time.sleep(2)
    except KeyboardInterrupt:
        for ev in stop_events.values():
            ev.set()
