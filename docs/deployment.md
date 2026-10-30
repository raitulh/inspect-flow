# Deployment guide

## Local Compose

1. Copy `.env.example` to `.env`.
2. Set a non-default `POSTGRES_PASSWORD` and `SECRET_KEY`, even for a shared LAN.
3. Run `docker compose up --build -d`.
4. Wait for PostgreSQL, API and web health to settle with `docker compose ps`.
5. Create an owner with `docker compose exec api python -m app.cli create-admin --email admin@example.com --password 'long-unique-password' --organization 'Plant'`.
6. Open the frontend on port 3000.

Database migrations are applied by the API container command before Uvicorn begins. The worker uses the same backend image and the shared persistent video/evidence volume.

## Production Compose overlay

The production overlay removes the default API, frontend and database host port mappings and requires explicit production secrets. Use it behind a TLS-terminating reverse proxy that is attached to the Compose application network or otherwise has a secure route to the frontend/API services.

```bash
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```

Before starting remotely:

- Put actual secrets in a secure environment or secret manager.
- Set `APP_ENV=production`, `COOKIE_SECURE=true` and exact CORS origin(s).
- Set `NEXT_PUBLIC_API_BASE_URL` at frontend build time to the public HTTPS API origin. This value is public configuration, not a secret.
- Set trusted reverse-proxy host and TLS configuration.
- Ensure the reverse proxy can route to web and API containers; do not expose PostgreSQL directly.
- Configure upload size and timeout limits to match `MAX_UPLOAD_MB` and video-processing expectations.
- Restrict access to the monitoring UI and API through network controls where practical.

The supplied Compose overlay is a hardening starting point, not a full public internet ingress solution: it does not provision certificates, configure a reverse proxy, or implement shared distributed rate limiting.

## Native backend

From `backend/` in an activated virtual environment:

```bash
pip install -e '.[dev]'
export APP_ENV=development
export SECRET_KEY='local-development-only-change-before-deployment'
python -m app.cli init-db
python -m app.cli create-admin --email admin@example.com --password 'long-unique-password' --organization 'Plant'
uvicorn app.main:app --reload --port 8000
```

Run the worker separately in another process using the same environment and database/storage paths:

```bash
python -m app.cli worker
```

PowerShell environment variables use `$env:NAME = 'value'` instead of `export NAME=value`.

## Migrations and rollback

- Apply schema migrations with `alembic upgrade head` from `backend/`.
- Review new migration scripts and test against a fresh database plus a copy of the current schema before upgrading production.
- Back up PostgreSQL and the video/evidence volume before upgrade.
- Roll back only after reviewing the downgrade and restore plan; data-loss risk depends on the migration.
- Never use the development `init-db` command as a substitute for production migrations.

## Backups and restore

Database and evidence files form one logical data set. Back up both, record the backup timestamp, and test restoring to an isolated environment. A sample PostgreSQL backup command (run from a container with credentials configured):

```bash
pg_dump --format=custom --no-owner --file=lineguard.dump "$DATABASE_URL"
```

The container volume must be archived or backed up using your platform's supported volume procedure. Restoring the database without evidence may leave event links pointing to missing files; restoring files without the database may leave orphaned files.

## Resource sizing

No single CPU/RAM requirement guarantees acceptable throughput. Benchmark the exact video codec/resolution, sampled-frame settings, rules and machine. Keep one worker for SQLite. Start with bounded frame sampling; increase worker concurrency only after measuring CPU, memory, queue depth and tail latency.

## Optional camera, YOLO and PLC workers

Compose includes a `camera-worker` process for RTSP/webcam sources. Ensure its network can reach authorized camera IPs. For YOLO, set `BACKEND_EXTRAS=yolo-cpu` or `industrial`, place model files in the persistent `/app/data/models` directory, and configure `YOLO_MODEL_PATH`. Model files are user supplied and should not be committed to source control. The default Compose build omits optional PyTorch/Modbus dependencies to keep the base CPU image lean.

PLC mode remains `simulation` and outputs disabled by default. Read [PLC integration and safety](plc-and-machine-control.md) before changing those settings.
