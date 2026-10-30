# CPU vision, defect models and training

LineGuard remains CPU-first. The default runtime needs OpenCV only. No CUDA, GPU or cloud inference API is required.

## Included inspection paths

| Rule type | CPU implementation | Output / limits |
|---|---|---|
| `color_presence` | HSV threshold in configured ROI | Pixel-color presence proxy; not part identity |
| `motion_stall` | Grayscale frame difference | Vision-derived inactivity estimate; not PLC state |
| `surface_defect` | Background suppression, morphology, connected components and elongation filters | Scratch/crack-like candidates; heuristic score, not probability |
| `object_detection` | Optional Ultralytics YOLO inference with `device="cpu"` | Uses your trained class taxonomy and supplied model weights |

All rules are evaluated on bounded frame samples. Tune `DEFAULT_FRAME_STRIDE`, `MAX_SAMPLED_FRAMES` and `LIVE_CAMERA_SAMPLE_SECONDS` for the actual CPU and camera count. Higher input resolution, more cameras and more rules increase latency. Measure the target host; no generic FPS guarantee is made.

## Install optional CPU YOLO support

The base install intentionally omits the large PyTorch/Ultralytics dependency. In `backend`:

```bash
pip install -e '.[yolo-cpu]'
```

Put a trained `.pt` model in a protected local model directory and set `YOLO_MODEL_PATH` to its absolute path, or specify `model_path` in a rule config. Model weights are not bundled. Keep class names aligned with the trained dataset.

Example rule:

```json
{
  "station_id": "<station UUID>",
  "name": "Inspect scratch and crack classes",
  "rule_type": "object_detection",
  "severity": "high",
  "config": {
    "mode": "detect",
    "model_path": "/app/data/models/lineguard-best.pt",
    "confidence": 0.35,
    "iou": 0.45,
    "image_size": 512,
    "target_classes": ["scratch", "crack", "missing_component"]
  }
}
```

For component absence monitoring, set `mode` to `missing`, supply `target_classes`, and set `min_consecutive`. A configured object detector failing to load will fail the analysis job visibly; it does not silently pretend the model ran.

## Scratch/crack CPU heuristic

`surface_defect` requires no learned weights. It applies a normalized ROI, Gaussian background estimate, high-pass residual, black-hat/top-hat morphology, thresholding and connected-component filters. Tune `threshold`, `min_area`, `max_area`, `min_length_px`, `min_aspect_ratio`, and `score_threshold`. It is appropriate for controlled experiments under fixed optics/lighting, not a replacement for a validated surface-inspection model. Brushed metal, texture, glare, oil, shadows and camera movement can trigger false detections.

## Custom training on CPU

Create a YOLO-format dataset following [ml/datasets/README.md](../ml/datasets/README.md). Separate production runs or physical parts between train/validation/test to avoid near-identical-frame leakage. Label good and defective examples. Run:

```bash
python ml/validate_yolo_dataset.py /path/to/lineguard-dataset
pip install -e '.[yolo-cpu]'
python ml/train_yolo_cpu.py --data /path/to/lineguard-dataset/data.yaml --base-model /path/to/yolov8n.pt --epochs 30 --batch 2 --imgsz 512 --export-onnx
```

The base weights must be present locally; the training script does not download them. Training is CPU-only, with `workers=0`, no CUDA and small default batches. On a low-end CPU this may take a long time. For modest CPU resources, begin with fewer epochs, `imgsz=320` or `416`, and `batch=1`. Do not confuse successful training with industrial fitness.

Copy the selected best checkpoint into protected storage and configure `YOLO_MODEL_PATH`. The event metadata records the model file name and SHA-256 fingerprint. Keep a record of dataset version, model hash, class names, training settings, validation metrics and approval. Model updates should be versioned and rollbackable.

## Evaluation

`ml/benchmark_detector.py` reports box precision, recall and F1 at one IoU threshold and optional mean/p95 per-image latency from a JSON record. This is not COCO mAP. Use a held-out, production-representative set and also report per-class counts, false rejects, false accepts, missed-defect severity, shift/lighting breakdowns and operator adjudication. Never quote the benchmark from a small synthetic sample as factory accuracy.
