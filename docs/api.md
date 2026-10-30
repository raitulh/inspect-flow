# API guide

Base path: `/api/v1`. API docs are served by FastAPI at `/docs`.

## Authentication

`POST /auth/login` accepts JSON `email` and `password`. A successful login sets the `lg_access` HttpOnly cookie and a `lg_csrf` cookie. Browser-side mutating calls must echo `lg_csrf` in `X-CSRF-Token`. `POST /auth/logout` clears the cookies. `GET /auth/me` returns the authenticated user.

For automated API tests and trusted scripts, an Authorization Bearer token is also accepted; do not store production session tokens in browser localStorage. Bearer clients should protect tokens as secrets.

## Main resources

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/sites` | List/create sites |
| GET / PATCH | `/sites/{id}` | Read/update an organization-owned site |
| GET / POST | `/stations` | List/create stations |
| GET / PATCH | `/stations/{id}` | Read/update a station |
| GET | `/stations/{id}/health` | Station metadata and alert counts |
| GET / POST | `/cameras` | List/create camera metadata |
| POST | `/cameras/{id}/test-connection` | Opens the source and attempts to receive one frame |
| GET | `/cameras/{id}/health` | Camera stream status and last-frame time |
| POST / GET | `/videos` | Upload/list validated videos |
| POST / GET | `/analyses` | Create/list persisted analysis jobs |
| GET | `/analyses/{id}` | Poll job status |
| POST | `/analyses/{id}/cancel` | Cancel a queued job |
| GET / POST | `/inspection-rules` | List/create explicit station rules |
| PATCH | `/inspection-rules/{id}` | Update rule configuration/version |
| GET | `/integrations/plc/status` | Read PLC adapter configuration and output state |
| POST | `/integrations/plc/test` | Test simulation/Modbus connection without writing outputs |
| POST | `/integrations/plc/machine-stop-request` | Role-restricted manually confirmed request bit; simulation by default |
| GET | `/models` | Report baseline, surface heuristic and optional YOLO readiness |
| GET | `/events` | Filter/paginate uploaded-video and live-camera events |
| GET | `/events/{id}` | Read event details |
| POST | `/events/{id}/acknowledge` | Acknowledge an open event |
| POST | `/events/{id}/resolve` | Resolve with optional note |
| POST | `/events/{id}/mark-false-positive` | Record a required reason |
| GET | `/events/{id}/evidence` | Authenticated evidence image download |
| GET | `/reports/summary` | Dashboard summary |
| GET | `/reports/quality` | Event counts and model-metric caveat |
| GET | `/reports/stations` | Station event summaries |
| GET | `/reports/export.csv` | Export up to 10,000 recent events |
| GET | `/audit-logs` | Admin/owner audit history |
| GET / POST | `/users` | List/create organization users |

## Error handling

Errors use JSON with a `detail` field and conventional HTTP status codes. Common statuses:

- `401`: authentication required or invalid session.
- `403`: insufficient role or invalid CSRF token.
- `404`: resource not found within the caller's organization scope.
- `409`: duplicate key or invalid lifecycle transition.
- `413`: upload too large.
- `415`: unsupported extension.
- `422`: invalid input or undecodable video.
- `429`: login throttling threshold reached.
- `500`: unexpected server error.

The API intentionally returns `404` for many cross-tenant resource lookups rather than confirming another organization's resource exists.

## Upload

`POST /videos?station_id=<UUID>` is multipart with the `file` field. An allowed extension is required, and OpenCV must be able to open and read a frame. Returned metadata includes resolution and duration when decodable. It does not return an arbitrary local file path.

## Analysis

`POST /analyses` JSON:

```json
{
  "station_id": "<station UUID>",
  "video_id": "<video UUID>",
  "provider_name": "opencv_rules"
}
```

A `202 Accepted` response represents a queued job. A separate worker must be running. Poll `GET /analyses/{job_id}` until `completed`, `failed` or `cancelled`.

## Rule examples

`color_presence`, `motion_stall`, `surface_defect` and optional CPU `object_detection` examples are in [the README](../README.md) and [CPU vision guide](cpu-vision-and-training.md). Rule versions are incremented when a rule is updated. Events retain the version used at analysis time. An unavailable YOLO runtime or missing weight file fails visibly.

## Live camera events

The `camera-worker` service processes registered RTSP/webcam sources. Live events have `video_id=null` and `job_id=null`; inspect `details_json.camera_id` to identify the source. Evidence retrieval and event lifecycle routes remain the same.

## PLC control boundary

The PLC adapter defaults to simulation. The manual machine-stop request endpoint requires an exact phrase and safety acknowledgement, and physical output writes remain disabled unless deployment configuration explicitly enables them. See the [PLC safety guide](plc-and-machine-control.md); the endpoint is not a safety-rated function.

## Security guidance

- Every organization-owned read and write must be scoped to the caller's organization.
- Evidence downloads repeat the event ownership check.
- RTSP URLs containing embedded credentials are rejected. Use controlled camera networks and secure credential management before deployment.
- In production use HTTPS, explicit CORS origins, secure cookies, robust secret storage, reverse-proxy limits and coordinated rate limiting.
