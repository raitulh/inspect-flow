"""CPU-only surface anomaly heuristics for scratches/crack-like marks.

This is an explainable image-processing baseline, not a trained or certified
surface-inspection model. Results are candidate regions for human review.
"""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def detect_surface_defects(frame: np.ndarray, config: dict[str, Any]) -> list[dict[str, Any]]:
    height, width = frame.shape[:2]
    zone = config.get("zone", [0.0, 0.0, 1.0, 1.0])
    if not isinstance(zone, list) or len(zone) != 4:
        raise ValueError("surface_defect zone must contain [x1,y1,x2,y2]")
    x1, y1, x2, y2 = zone
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        raise ValueError("surface_defect zone coordinates must be normalized and increasing")
    left, top = int(x1 * width), int(y1 * height)
    right, bottom = max(left + 1, int(x2 * width)), max(top + 1, int(y2 * height))
    roi = frame[top:bottom, left:right]
    if roi.size == 0:
        return []

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    if config.get("adaptive_lighting", False):
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
    # High-pass residual suppresses slow illumination changes. Black-hat emphasizes
    # dark, narrow marks; top-hat emphasizes bright hairline marks.
    blur_size = int(config.get("background_blur", 21))
    blur_size = max(3, min(101, blur_size | 1))
    background = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
    residual = cv2.absdiff(gray, background)
    kernel_size = int(config.get("morph_kernel", 9))
    kernel_size = max(3, min(31, kernel_size | 1))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    top_hat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    response = cv2.max(residual, cv2.max(blackhat, top_hat))
    threshold = int(config.get("threshold", 24))
    threshold = max(1, min(255, threshold))
    _, mask = cv2.threshold(response, threshold, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    # Mask out configured exclusion zones (e.g. mounting holes, tooling marks, stamped logos)
    exclusion_zones = config.get("exclusion_zones", [])
    if isinstance(exclusion_zones, list):
        roi_h, roi_w = roi.shape[:2]
        for ez in exclusion_zones:
            if isinstance(ez, (list, tuple)) and len(ez) == 4:
                ex1, ey1, ex2, ey2 = ez
                if 0 <= ex1 < ex2 <= 1 and 0 <= ey1 < ey2 <= 1:
                    # Convert normalized coords relative to full frame or relative to ROI
                    lx1 = max(0, min(roi_w, int(ex1 * width) - left))
                    ly1 = max(0, min(roi_h, int(ey1 * height) - top))
                    lx2 = max(0, min(roi_w, int(ex2 * width) - left))
                    ly2 = max(0, min(roi_h, int(ey2 * height) - top))
                    if lx2 > lx1 and ly2 > ly1:
                        mask[ly1:ly2, lx1:lx2] = 0

    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, 8)
    min_area = int(config.get("min_area", 8))
    max_area = int(config.get("max_area", max(100, roi.shape[0] * roi.shape[1] // 10)))
    min_aspect = float(config.get("min_aspect_ratio", 2.0))
    min_length = int(config.get("min_length_px", 8))
    findings: list[dict[str, Any]] = []
    for index in range(1, count):
        x, y, w, h, area = [int(v) for v in stats[index]]
        long_side = max(w, h)
        if area < min_area or area > max_area or long_side < min_length:
            continue
        component_mask = (labels[y:y + h, x:x + w] == index).astype(np.uint8) * 255
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        rotated = cv2.minAreaRect(max(contours, key=cv2.contourArea))
        rect_w, rect_h = rotated[1]
        long_side, short_side = max(rect_w, rect_h), max(1.0, min(rect_w, rect_h))
        rotated_aspect = long_side / short_side
        if long_side < min_length or rotated_aspect < min_aspect:
            continue
        intensity = float(np.mean(response[y:y + h, x:x + w][component_mask > 0]))
        # This score ranks candidate marks; it is not a calibrated probability.
        score = min(0.99, max(0.05, (intensity / 255.0) * 0.65 + min(rotated_aspect / 12.0, 0.34)))
        findings.append({
            "label": "scratch_or_crack_candidate",
            "bbox_xyxy": [left + x, top + y, left + x + w, top + y + h],
            "area_px": area,
            "aspect_ratio": round(rotated_aspect, 3),
            "response_mean": round(intensity, 3),
            "score": round(score, 4),
            "score_kind": "heuristic_priority_score_not_probability",
        })
    findings.sort(key=lambda item: item["score"], reverse=True)
    return findings[: int(config.get("max_detections", 20))]
