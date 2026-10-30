# Roadmap

## Implemented foundation in v0.1

- Multi-tenant API, stations, jobs, event review, audit, reports and dashboard.
- Uploaded video processing with CPU OpenCV HSV color and motion-stall rules.

## Added in v0.2

- Surface anomaly candidate heuristic for scratch/crack-like marks.
- Optional user-supplied YOLO CPU inference and CPU training utility.
- RTSP/webcam camera worker with reconnect, status and live evidence events.
- Modbus TCP integration boundary, simulation default, disabled outputs, and manually confirmed request bit.
- Expanded integration UI, dataset validation, benchmark utility and safety commissioning documentation.

## Next research / production work

1. Build target-line datasets with independent annotation and locked holdout sets.
2. Validate defect taxonomies, class balance and per-class false-negative rates.
3. Evaluate CPU inference latency and stream scaling on the actual industrial computer.
4. Add structured metrics/observability, stream backpressure and stronger camera credential storage.
5. Integrate read-only PLC telemetry and compare visual state with authoritative machine signals.
6. Perform formal machine risk assessment, independent safety design and applicable certification outside this software scope.
7. Harden backup/restore, distributed rate limits, object storage, deployment secrets and multi-site operations.

No roadmap item should be represented as industrially validated until it has measured evidence and approval.
