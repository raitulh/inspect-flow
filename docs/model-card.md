# Model and provider card — LineGuard CV v0.2

LineGuard contains three detection paths. Their statuses and limitations must be reported independently.

## 1. OpenCV baseline (`opencv_rules`)
- HSV ROI color-presence and grayscale frame-difference inactivity rules.
- Deterministic CPU image processing; no trained weights.
- Pixel color and motion proxies are not semantic recognition or authoritative machine state.

## 2. Surface anomaly heuristic (`surface_defect`)
- CPU Gaussian background suppression, high-pass residual, black-hat/top-hat morphology and connected components.
- Emits elongated scratch/crack-like candidate regions and a heuristic priority score.
- Score is not a calibrated probability. Results are sensitive to surface finish, illumination, focus, contamination, motion blur and thresholds.
- No learned defect classifier is bundled or trained by default.

## 3. Optional YOLO CPU adapter (`object_detection`)
- Optional Ultralytics runtime with explicit `device="cpu"`.
- User supplies model weights and class taxonomy; no model weights are bundled.
- Supports detection and target-class absence rules.
- Validate weight provenance, license, preprocessing, class map, threshold, NMS and runtime version. A model file existing does not mean it is accurate.

## Intended use

Engineering prototype, workflow integration, evidence collection and controlled offline/parallel evaluation on representative footage. Findings are advisory and require operator/quality review.

## Not intended for

- Safety-critical protection, emergency stop or certified safety functions.
- Unvalidated product release, guaranteed defect-free checks or employee monitoring.
- Autonomous PLC/machine-stop actions.

## Evaluation status

Backend tests exercise implementation behavior on generated data. No target-factory precision, recall, false accept/reject rate, latency, throughput or safety performance has been measured. Use a blind holdout with labels, per-class metrics and target-CPU profiling before any pilot.

## Licensing

OpenCV and project code are included as dependencies/source. Ultralytics, PyTorch, model architecture, checkpoint weights and datasets have separate licensing and distribution obligations. Review licenses before commercial use.
