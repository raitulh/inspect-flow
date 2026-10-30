#!/usr/bin/env python3
"""Evaluate box detections against labels and report precision/recall/F1/latency.

Input JSON:
{"samples":[{"ground_truth":[{"label":"scratch","bbox":[x1,y1,x2,y2]}],
"predictions":[{"label":"scratch","bbox":[x1,y1,x2,y2],"latency_ms":42}]}]}
Coordinates must use the same pixel frame for ground truth and predictions.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


def iou(a: list[float], b: list[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def evaluate(samples: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    tp = fp = fn = 0
    latencies: list[float] = []
    for sample in samples:
        truths = list(sample.get("ground_truth", []))
        preds = list(sample.get("predictions", []))
        used: set[int] = set()
        for pred in preds:
            if "latency_ms" in pred:
                latencies.append(float(pred["latency_ms"]))
            candidates = [
                (iou(pred["bbox"], truth["bbox"]), index)
                for index, truth in enumerate(truths)
                if index not in used and pred.get("label") == truth.get("label")
            ]
            best = max(candidates, default=(0.0, -1))
            if best[0] >= threshold:
                tp += 1
                used.add(best[1])
            else:
                fp += 1
        fn += len(truths) - len(used)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "samples": len(samples), "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6),
        "iou_threshold": threshold,
        "mean_latency_ms": round(mean(latencies), 3) if latencies else None,
        "p95_latency_ms": round(sorted(latencies)[min(len(latencies)-1, math.ceil(0.95 * len(latencies)) - 1)], 3) if latencies else None,
        "note": "This script computes box precision/recall/F1 at one IoU threshold; it is not COCO mAP and does not certify industrial performance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 < args.iou <= 1:
        parser.error("--iou must be between 0 and 1")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = evaluate(payload.get("samples", []), args.iou)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
