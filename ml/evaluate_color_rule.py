"""Evaluate the HSV presence heuristic on a labeled image manifest.

The manifest must include records with relative `image`, `split`, and boolean `present` labels.
This reports heuristic metrics for the chosen labeled sample; it does not generalize to unseen factories.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def evaluate(record: dict[str, Any], root: Path, lower: np.ndarray, upper: np.ndarray, zone: list[float], threshold: float) -> tuple[bool, float]:
    image_path = (root / str(record["image"])).resolve()
    if root.resolve() not in image_path.parents:
        raise ValueError(f"Image path escapes manifest root: {record['image']}")
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image: {image_path.name}")
    h, w = image.shape[:2]
    x1, y1, x2, y2 = zone
    roi = image[max(0, int(y1*h)):min(h, max(1, int(y2*h))), max(0, int(x1*w)):min(w, max(1, int(x2*w)))]
    if roi.size == 0:
        raise ValueError(f"Empty ROI for image: {image_path.name}")
    mask = cv2.inRange(cv2.cvtColor(roi, cv2.COLOR_BGR2HSV), lower, upper)
    ratio = float(np.count_nonzero(mask) / mask.size)
    return ratio >= threshold, ratio


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON manifest with records labelled present/absent")
    parser.add_argument("--split", default="test", help="Manifest split to evaluate (default: test)")
    parser.add_argument("--root", type=Path, default=None, help="Asset root (default: manifest parent)")
    parser.add_argument("--hsv-lower", nargs=3, type=int, default=[100, 80, 50])
    parser.add_argument("--hsv-upper", nargs=3, type=int, default=[130, 255, 255])
    parser.add_argument("--zone", nargs=4, type=float, default=[0.0, 0.0, 1.0, 1.0], metavar=("X1", "Y1", "X2", "Y2"))
    parser.add_argument("--min-pixel-ratio", type=float, default=0.015)
    args = parser.parse_args()
    if not 0 <= args.min_pixel_ratio <= 1:
        parser.error("--min-pixel-ratio must be between 0 and 1")
    x1, y1, x2, y2 = args.zone
    if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
        parser.error("--zone must be normalized increasing coordinates")

    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = (args.root or args.manifest.parent).resolve()
    records = [r for r in payload.get("records", []) if r.get("split") == args.split]
    if not records:
        parser.error(f"No records found for split={args.split!r}")

    tp = fp = tn = fn = 0
    samples = []
    for record in records:
        if not isinstance(record.get("present"), bool):
            raise ValueError("Each selected record needs a boolean `present` ground-truth label")
        predicted, ratio = evaluate(record, root, np.array(args.hsv_lower, dtype=np.uint8), np.array(args.hsv_upper, dtype=np.uint8), args.zone, args.min_pixel_ratio)
        truth = record["present"]
        if predicted and truth: tp += 1
        elif predicted and not truth: fp += 1
        elif not predicted and not truth: tn += 1
        else: fn += 1
        samples.append({"image": record["image"], "ground_truth_present": truth, "predicted_present": predicted, "matching_pixel_ratio": round(ratio, 6)})

    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    accuracy = (tp + tn) / len(records) if records else None
    print(json.dumps({
        "evaluation_type": "HSV pixel-presence heuristic",
        "split": args.split,
        "records": len(records),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": precision,
        "recall": recall,
        "accuracy": accuracy,
        "thresholds": {"hsv_lower": args.hsv_lower, "hsv_upper": args.hsv_upper, "zone": args.zone, "min_pixel_ratio": args.min_pixel_ratio},
        "warning": "Metrics apply only to the supplied labeled records and do not establish factory-level reliability.",
        "samples": samples,
    }, indent=2))


if __name__ == "__main__":
    main()
