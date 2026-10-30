# Validation report — LineGuard CV v0.2

Validation date: 2026-10-30

## Checks completed in this environment

- `cd backend && pytest -q`: **40 tests passed**. The suite covers authentication, CSRF, roles, tenant isolation, video/job workflow, events, camera metadata and mocked one-frame connection checks, live-camera events with nullable video/job IDs, PLC simulation and confirmation, model registry and report routes, surface-heuristic candidate/blank-image behavior, advanced rule schemas and migration metadata.
- `python -m compileall -q backend/app backend/tests ml`: passed.
- `DATABASE_URL=sqlite:////tmp/lineguard-migration-test.db alembic upgrade head`: passed against a fresh SQLite database; Alembic reported revision `7c91a6d8e2f4 (head)`.
- TypeScript/TSX syntax transpilation using the globally available TypeScript compiler: **11 files checked, 0 syntax diagnostics**.
- `node --check frontend/scripts/prepare-standalone.mjs`: passed.
- `frontend/package.json` JSON parse: passed.
- Main `compose.yaml` parsed with PyYAML; it contains db, api, uploaded-video worker, camera-worker and web services.

## Checks not completed

- `npm install`, `npm run typecheck`, `npm run lint` and `npm run build` were **not verified**. `npm install --no-audit --no-fund` timed out while trying to access the package registry. TS/TSX syntax transpilation does not replace strict type checking or a Next.js production build.
- `ruff check app tests` was not run because Ruff was not installed and package access was unavailable.
- Docker image builds, Docker Compose startup and production overlay validation were not run because the Docker CLI was unavailable. The production overlay uses Docker Compose's `!reset` extension, which standard PyYAML does not parse.
- PostgreSQL runtime, multi-worker concurrency, live RTSP streams, physical cameras, a real Modbus PLC, actual PLC writes, CPU YOLO inference/training and model quality were not tested.
- No industrial precision/recall, false-accept/false-reject, throughput, FPS, latency, production uptime or machine safety performance has been measured.

## Interpretation

The passing tests demonstrate API and algorithm behavior on local SQLite/generated or mocked inputs. They do not establish industrial reliability or factory readiness. Surface-defect detection is a candidate-generating OpenCV heuristic. YOLO requires optional dependencies, user-provided weights and representative labeled data. RTSP processing is implemented but not validated on real cameras. PLC hardware output is disabled by default and must be independently commissioned. No safety certification is included.

Before a field pilot, complete [validation and benchmarking](validation-and-benchmarking.md), [live camera commissioning](live-cameras.md), and the [safety commissioning checklist](safety/commissioning-checklist.md) with qualified plant personnel.
