# Limitations and field validation plan

## Current implementation limits

- HSV color presence and low frame-difference rules are pixel-level heuristics, not semantic part recognition or machine-state telemetry.
- Surface-defect processing emits scratch/crack-like image candidates from morphology and connected components. It is not a validated trained classifier; finish, lighting, focus, oil, vibration and camera movement can dominate its output.
- YOLO object detection is an optional CPU adapter only. No weights, classes or defect-specific data are bundled. User-supplied models need independent licensing, validation and CPU profiling.
- RTSP/webcam capture has a reconnecting worker and live-event path, but physical cameras, network paths, multi-camera load and reconnect edge cases have not been field tested in this package.
- Modbus TCP integration is optional and defaults to simulation/output disabled. Its manual stop-request coil is not a certified safety controller and AI events do not initiate stop requests.
- Assembly order, part orientation, dimensional tolerance, worker safety, robotics control and line balancing are not inferred by generic video.
- No target-production precision, recall, false acceptance/rejection, throughput, FPS, uptime or safety performance has been measured.
- No factory safety certification, regulatory conformity or machine risk acceptance is provided.

## Before a pilot

1. Select one physical station and one narrowly defined part/condition.
2. Agree on true-positive criteria and the cost of false positives/false negatives with the quality owner.
3. Fix camera position, focus, lighting, exposure and acceptable variation.
4. Collect good and bad examples across shifts, normal variation, product lots and edge cases.
5. Obtain footage rights and approval; protect worker privacy and confidential process data.
6. Independently label a held-out evaluation set. Split by run/date/physical item, not adjacent frames.
7. Evaluate per-class precision/recall, false accepts/rejects and severity-weighted missed defects.
8. Run in shadow mode next to existing quality checks. Do not gate production or safety functions initially.
9. Review every false alarm and missed condition; adjust rules/model and revalidate.
10. Revalidate whenever camera, lighting, SKU, material, supplier, process or model changes.
11. Measure target CPU throughput, per-camera latency, queue growth, dropped frames, storage and restart recovery.
12. Obtain qualified industrial, controls and safety engineering approval for any PLC integration.

## Acceptance evidence for a production trial

- Versioned dataset, annotation guide and frozen blind holdout set.
- Documented rule/model versions, class map and thresholds.
- Per-class confusion matrix and false-positive/false-negative review.
- CPU/RAM/latency measurements on the deployment computer and target camera count.
- Shadow-mode operator review, escalation and manual fallback process.
- Storage retention, backup, security, privacy and access-control review.
- Failure-mode test for camera loss, worker stoppage, overload, database failure and PLC/network loss.
- Independent machine risk assessment and formal approvals. Completing this list is not itself certification.
