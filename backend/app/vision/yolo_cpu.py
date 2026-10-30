"""Optional CPU-only YOLO adapter. Model weights are user supplied, never bundled."""
from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from app.config import get_settings


@lru_cache(maxsize=2)
def _load_model(model_path: str):
    path = Path(model_path).expanduser().resolve()
    model_root = Path(os.getenv("YOLO_MODEL_ROOT") or (get_settings().storage_root / "models")).expanduser().resolve()
    try:
        path.relative_to(model_root)
    except ValueError as exc:
        raise PermissionError(f"Model weights must be stored under YOLO_MODEL_ROOT={model_root}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"YOLO model weights not found: {path}")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("YOLO support is optional. Install lineguard-cv[yolo-cpu] first.") from exc
    return YOLO(str(path))


@lru_cache(maxsize=4)
def model_identity(model_path: str) -> dict[str, str]:
    path = Path(model_path).expanduser().resolve()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    fingerprint = digest.hexdigest()
    return {"model_file": path.name, "model_sha256": fingerprint, "model_version": f"yolo-cpu:{fingerprint[:12]}"}


def detect_objects_cpu(frame: np.ndarray, config: dict[str, Any]) -> list[dict[str, Any]]:
    model_path = str(config.get("model_path") or os.getenv("YOLO_MODEL_PATH", ""))
    if not model_path:
        raise RuntimeError("Set YOLO_MODEL_PATH or configure model_path for object_detection rules")
    confidence = float(config.get("confidence", 0.35))
    iou = float(config.get("iou", 0.45))
    image_size = int(config.get("image_size", 512))
    if not 0 < confidence <= 1 or not 0 < iou <= 1 or not 128 <= image_size <= 1280:
        raise ValueError("Invalid YOLO confidence, IoU or image_size configuration")
    model = _load_model(model_path)
    identity = model_identity(model_path)
    results = model.predict(
        source=frame,
        device="cpu",
        conf=confidence,
        iou=iou,
        imgsz=image_size,
        verbose=False,
    )
    detections: list[dict[str, Any]] = []
    for result in results:
        names = result.names
        boxes = result.boxes
        if boxes is None:
            continue
        for box in boxes:
            cls_id = int(box.cls.item())
            xyxy = [int(round(v)) for v in box.xyxy[0].tolist()]
            detections.append({
                "label": str(names.get(cls_id, cls_id) if isinstance(names, dict) else names[cls_id]),
                "class_id": cls_id,
                "confidence": round(float(box.conf.item()), 5),
                "bbox_xyxy": xyxy,
                **identity,
            })
    return detections
