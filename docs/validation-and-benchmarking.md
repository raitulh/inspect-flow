# Validation and industrial benchmarking plan

A valid industrial benchmark needs an agreed defect taxonomy and independently labeled examples from the target line. Split by production run/date/physical item rather than adjacent frames to avoid leakage. Preserve a final blind test set.

Minimum report:

- Per-class precision, recall, F1 and box IoU; report mAP separately when using a recognized evaluator.
- False accepts and false rejects per 1,000 inspected units; missed-defect count by severity.
- Per-SKU, shift, operator, camera, lighting, material finish and operating-speed breakdown.
- End-to-end sample latency p50/p95/p99, decoded frames/second, CPU/RAM, stream reconnects and dropped frames at target camera count.
- Alert rate, review time, operator agreement and false-positive reasons.
- Good-part and difficult-negative coverage; known hard cases and dataset/model version hashes.

Use `ml/benchmark_detector.py` for a simple per-box precision/recall/F1 calculation at one IoU. For model selection and formal reporting, use a standard evaluator such as Ultralytics validation or COCO metrics on a version-controlled holdout. Record the exact confidence threshold and NMS settings. Do not tune thresholds on the final holdout. Evaluate the CPU model on the intended production computer, not only on a developer laptop.

Acceptance limits must be set with the quality owner and safety/controls engineers based on defect severity and process risk. No universal accuracy threshold is safe for all manufacturing processes. A successful unit test, demo video, or synthetic benchmark is not a substitute for factory validation.
