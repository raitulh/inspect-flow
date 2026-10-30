#!/usr/bin/env python3
"""Train a small YOLO model on CPU using a YOLO-format dataset YAML.

Example: python ml/train_yolo_cpu.py --data ml/datasets/lineguard.yaml --epochs 30
No weights or datasets are downloaded by this script. The user supplies both.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="YOLO data.yaml with train/val paths and names")
    parser.add_argument("--base-model", default="yolov8n.pt", help="Small base model; provide a local file to avoid downloads")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=512)
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--project", default="runs/lineguard")
    parser.add_argument("--name", default="cpu-yolo")
    parser.add_argument("--export-onnx", action="store_true")
    args = parser.parse_args()
    data_path = Path(args.data).expanduser().resolve()
    if not data_path.is_file():
        parser.error(f"Dataset YAML not found: {data_path}")
    if not 1 <= args.epochs <= 1000 or not 128 <= args.imgsz <= 1280 or not 1 <= args.batch <= 16:
        parser.error("Use epochs 1-1000, imgsz 128-1280 and batch 1-16 for CPU-first training")
    try:
        from ultralytics import YOLO
    except ImportError:
        parser.error("Install CPU training extras: pip install -e '.[yolo-cpu]'")
    base_model = Path(args.base_model).expanduser().resolve()
    if not base_model.is_file():
        parser.error(f"Base model weights must exist locally; no automatic download is performed: {base_model}")
    model = YOLO(str(base_model))
    model.train(
        data=str(data_path), epochs=args.epochs, imgsz=args.imgsz,
        batch=args.batch, device="cpu", workers=0, cache=False,
        amp=False, project=args.project, name=args.name,
        patience=12, plots=True, verbose=True,
    )
    best = Path(model.trainer.save_dir) / "weights" / "best.pt"
    if not best.is_file():
        raise RuntimeError(f"Training finished but best weights were not found: {best}")
    print(f"Best CPU model: {best.resolve()}")
    if args.export_onnx:
        export_model = YOLO(str(best))
        exported = export_model.export(format="onnx", imgsz=args.imgsz, device="cpu", simplify=False)
        print(f"ONNX export: {exported}")
    print("Set YOLO_MODEL_PATH to the best.pt file (or configure model_path in an object_detection rule).")
    print("Review validation metrics and false negatives on a held-out, factory-representative dataset before use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
