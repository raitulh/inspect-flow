# Operations runbook

## Service health

- `GET /healthz`: process-level liveness.
- `GET /readyz`: database query readiness and storage-root presence.
- `GET /version`: application version/environment.
- `docker compose ps`: container health/restarts.
- `docker compose logs -f api worker web`: live logs.

## Analysis job stuck in `queued`

1. Check that the worker container/process is running.
2. Inspect worker logs for database connection errors.
3. Check database readiness and available disk.
4. Confirm the job references an existing video and station in the same organization.
5. Check frame settings and video size.
6. Restarting the worker is safe for queued jobs. A job stuck as `running` after an old worker crash can be requeued by the worker's stale-job recovery if it exceeds the recovery threshold.

## Analysis failed

1. Read the job's `error_message` via the authorized API.
2. Search backend logs by job UUID; logs may have more context and must remain access-controlled.
3. Confirm the file still exists in configured storage and can be decoded with the deployed OpenCV/FFmpeg build.
4. Check codec support, available disk, permissions, and frame limits.
5. Re-upload or retry through a new analysis job after correction; do not manually set status without preserving auditability.

## Camera shows `not_tested`

This build stores camera metadata but does not currently open RTSP streams. The `test-connection` endpoint explicitly returns that connection testing is not enabled. Use uploaded-video analysis, or implement and validate a stream adapter before expecting an online state.

## Upload rejected

- `415`: extension not allowed.
- `413`: file/request exceeds the configured limit.
- `422`: the backend cannot decode or read frames.
- Confirm the proxy upload limit and timeout align with backend settings.
- Do not bypass validation by renaming a corrupt/non-video file.

## Storage is filling up

- Inspect the persistent data volume usage and upload history.
- Apply an explicitly approved retention policy; deletion is not automatic in this build.
- Back up required evidence before deletion.
- Avoid deleting evidence files directly while related events remain, unless the retention/audit policy accounts for missing media.

## Database issues

- Check `GET /readyz` and PostgreSQL logs.
- Confirm connection string, user privileges, storage and migration status.
- Before a migration/restore, take coordinated backups of database and file storage.
- Never drop tables to resolve an unknown migration issue in production.

## Incident response

- Disable access or stop ingress if unauthorized access or leakage is suspected.
- Rotate `SECRET_KEY` only with an explicit session-invalidation and deployment plan; changing the signing key invalidates existing sessions.
- Rotate database credentials and revoke compromised deployment secrets.
- Preserve relevant logs under the incident response policy.
- Assess whether video, camera credentials, personal data or product designs were exposed.
