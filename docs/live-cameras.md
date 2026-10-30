# RTSP / webcam live camera service

The `camera-worker` is a separate process from the video-analysis worker. It polls registered RTSP/RTSPS or local webcam sources, reconnects on stream failure, samples frames at `LIVE_CAMERA_SAMPLE_SECONDS`, executes enabled station rules and creates normal reviewable `DetectionEvent` records with evidence images. Live events intentionally have nullable `video_id` and `job_id`; their `details_json` identifies the camera and source. Event review, acknowledgement, resolution, audit logging and CSV export remain shared with uploaded-video events.

## Setup

1. Register a camera using `/api/v1/cameras` or the Integrations page. RTSP URLs with embedded username/password are rejected. Configure the camera with a LAN route accessible from the worker host/container.
2. Create enabled rules for its station. CPU color/motion/surface rules run without additional packages. YOLO rules need optional CPU dependencies and a model file mounted into the worker.
3. Start the camera worker: `python -m app.cli camera-worker`, or use `docker compose up --build -d camera-worker`.
4. Use `POST /api/v1/cameras/{id}/test-connection` to receive one test frame and inspect `/api/v1/cameras/{id}/health`.
5. Check the camera `status`, `last_frame_at`, and `last_error`, then review generated events.

The worker uses a reconnect loop and event dedupe window. A single worker process is intended initially. For many cameras, shard camera IDs across separately provisioned worker processes and measure CPU and decode capacity first. Camera count/FPS is host-specific. Containers need correct network access to the camera subnet; host webcams require explicit device passthrough or native execution. RTSP transport is not a substitute for encrypted credential management; use a secured network or credential vault before deployment.

A stream disconnect or no event does not indicate that a station is safe or defect-free. The service is not a PLC heartbeat, machine telemetry source, video recorder or safety controller.
