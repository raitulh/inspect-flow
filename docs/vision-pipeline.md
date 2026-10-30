# Vision pipeline and rule providers

LineGuard samples decoded video frames at a configured stride and bounds the maximum number of samples. The same frame evaluators are used by uploaded-video analysis and RTSP camera monitoring.

## `color_presence`

HSV threshold within a normalized ROI. Emits a potential missing-component event when matching pixels remain below `min_pixel_ratio` for `min_consecutive` samples. It tests pixel color only, not object identity or assembly sequence.

## `motion_stall`

Uses grayscale mean frame difference to estimate inactivity. Static scenes, normal pauses, exposure, vibration and camera movement can mislead it. Trusted PLC telemetry is preferable for machine state.

## `surface_defect`

CPU OpenCV baseline: normalized ROI, Gaussian background estimate, absolute residual, black-hat/top-hat morphology, binary threshold, connected components and elongation/area filters. Emits a scratch/crack-like candidate region with a heuristic rank score. Tune threshold, min/max area, min length, aspect ratio and score threshold on examples. Brushed textures, glare, oil, scratches in backgrounds and uneven illumination can cause false alerts. It is not a trained crack classifier.

## `object_detection`

Optional Ultralytics YOLO adapter. A local model file is required; inference passes `device="cpu"`. `mode=detect` emits an event for matching detections. `mode=missing` monitors configured `target_classes` and raises after consecutive sampled frames with no matching class. Confidence threshold, IoU and image size are configurable. No pretrained weights are included; class mapping must match the user's trained model. Missing runtime/weights fail visibly.

## Evidence and event lifecycle

Events record rule/version, provider version, event type, severity, time offset, details and optional JPEG evidence. `confidence` stays null for heuristic paths unless an actual detector confidence is available. A surface anomaly score is not a probability. Live-camera events do not refer to an uploaded video or analysis job; they carry the camera ID in their details.

## Validation

Collect representative good and bad examples across part variation, shifts, lighting, camera placements and operating speeds. Split by production run or physical unit. Freeze a blind test set. Report per-class precision, recall, false positives and false negatives, latency, dropped frames and CPU/RAM usage. Use the dedicated CPU training and benchmark documentation for model workflows. A unit test or clean result does not prove defect-free output.
