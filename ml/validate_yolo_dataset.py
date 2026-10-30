#!/usr/bin/env python3
"""Basic validation for a YOLO detection dataset directory."""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Dataset root containing images/ and labels/ splits")
    args = parser.parse_args()
    root = args.dataset.resolve()
    errors: list[str] = []
    image_ext = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    totals = {"images": 0, "label_files": 0, "boxes": 0, "empty_labels": 0}
    for split in ("train", "val", "test"):
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        if not image_dir.exists():
            if split in {"train", "val"}:
                errors.append(f"Missing {image_dir}")
            continue
        images = [p for p in image_dir.rglob("*") if p.suffix.lower() in image_ext]
        totals["images"] += len(images)
        for image in images:
            label = label_dir / image.relative_to(image_dir).with_suffix(".txt")
            if not label.is_file():
                errors.append(f"Missing label for {image.relative_to(root)}")
                continue
            totals["label_files"] += 1
            lines = [line.strip() for line in label.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not lines:
                totals["empty_labels"] += 1
            for line_no, line in enumerate(lines, 1):
                parts = line.split()
                if len(parts) != 5:
                    errors.append(f"{label}:{line_no}: expected class x_center y_center width height")
                    continue
                try:
                    cls, x, y, w, h = int(parts[0]), *[float(v) for v in parts[1:]]
                except ValueError:
                    errors.append(f"{label}:{line_no}: non-numeric value")
                    continue
                if cls < 0 or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    errors.append(f"{label}:{line_no}: class must be >= 0 and normalized box values within range")
                totals["boxes"] += 1
    print(f"Dataset: {root}")
    print(f"Totals: {totals}")
    print(f"Validation errors: {len(errors)}")
    for error in errors[:100]:
        print(f"- {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
