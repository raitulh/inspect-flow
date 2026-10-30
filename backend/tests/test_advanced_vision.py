import numpy as np
import cv2
import pytest

from app.schemas import RuleCreate
from app.vision.surface_defects import detect_surface_defects


def test_surface_heuristic_finds_elongated_dark_mark():
    frame = np.full((180, 220, 3), 180, dtype=np.uint8)
    cv2.line(frame, (35, 35), (175, 120), (25, 25, 25), 2)
    findings = detect_surface_defects(frame, {
        "threshold": 18, "min_area": 5, "min_length_px": 8,
        "score_threshold": 0.0,
    })
    assert findings
    assert all(item["label"] == "scratch_or_crack_candidate" for item in findings)
    assert all(len(item["bbox_xyxy"]) == 4 for item in findings)


def test_surface_heuristic_does_not_flag_uniform_image():
    frame = np.full((120, 160, 3), 128, dtype=np.uint8)
    assert detect_surface_defects(frame, {}) == []


def test_rule_schema_accepts_surface_defect_rule():
    rule = RuleCreate.model_validate({
        "station_id": "station-1", "name": "Scratch inspection",
        "rule_type": "surface_defect", "config": {"threshold": 24, "min_area": 8},
    })
    assert rule.rule_type == "surface_defect"


def test_rule_schema_accepts_cpu_yolo_rule():
    rule = RuleCreate.model_validate({
        "station_id": "station-1", "name": "Defect YOLO",
        "rule_type": "object_detection", "config": {
            "mode": "detect", "target_classes": ["scratch", "crack"], "confidence": 0.4,
        },
    })
    assert rule.config["confidence"] == 0.4


def test_invalid_surface_zone_is_rejected():
    with pytest.raises(ValueError):
        RuleCreate.model_validate({
            "station_id": "station-1", "name": "Bad zone",
            "rule_type": "surface_defect", "config": {"zone": [0.8, 0.8, 0.2, 0.2]},
        })
