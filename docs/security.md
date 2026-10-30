# Security and privacy

## Threat model

| Threat | Controls in this build | Remaining deployment work |
|---|---|---|
| Password guessing | Scrypt password hashes; per-process login attempt throttling | Add shared/distributed throttling or enforce at reverse proxy before horizontal API scaling |
| CSRF with cookie sessions | HttpOnly access cookie; CSRF cookie/header equality check for unsafe cookie-authenticated requests; SameSite=Lax | Enforce HTTPS and review cross-site topology, proxy headers and origin validation |
| Cross-tenant object access | Backend organization scope for core resources and evidence | Expand adversarial authorization tests as endpoints grow |
| Malicious/oversized video | Extension allowlist, streaming copy limit, OpenCV decode check, request content-length check | Configure proxy body-size and time limits; isolate codec parsing for hostile internet inputs |
| Filename/path traversal | Generated UUID storage keys, path containment check for evidence | Keep storage directories writable only by application user |
| Secret leakage | `.env` excluded; production secret validation | Use deployment secret manager and rotation process |
| Camera URL abuse | Current build stores URI and does not open an RTSP stream | Before implementing streams, enforce network allowlists, SSRF defenses, DNS/IP checks and credential encryption |
| Cross-organization evidence download | Evidence route re-checks event tenant and resolves within evidence root | Add cross-tenant negative tests for every future binary endpoint |
| Resource exhaustion | Upload size limit; bounded sampled frames; DB-backed job queue | Add reverse-proxy limits, worker resource limits, storage quotas, request timeouts and monitoring |
| Dependency vulnerability | Pinned version ranges, CI dependency installation | Add automated dependency/SBOM scanning and review findings before releases |
| Sensitive factory footage exposure | Auth-required endpoints, local storage default, retention/storage docs | Define factory-specific retention, backups, encryption at rest, access reviews and worker consent/privacy obligations |

## Authentication and roles

The app stores password hashes using Python's `hashlib.scrypt`, signs short-lived JWT claims and uses an HttpOnly `lg_access` cookie for browser sessions. A readable `lg_csrf` cookie is sent in `X-CSRF-Token` on mutating browser requests. The application accepts bearer tokens for trusted API clients; protect those as secrets and never put them in browser localStorage.

Roles are `owner`, `admin`, `engineer`, `operator` and `viewer`. Role checks are enforced server-side, not only in navigation. Tenant ownership is derived from the current user/session.

## Production checklist

- HTTPS enabled from the public edge to the browser.
- `APP_ENV=production`.
- `COOKIE_SECURE=true`.
- `SECRET_KEY` is a unique random secret of at least 32 characters and not committed to source control.
- Strong unique PostgreSQL password.
- Exact JSON array for trusted CORS origins; no wildcard.
- Reverse proxy request size, connection and response timeouts set.
- Shared login rate limit or reverse-proxy throttling enabled.
- Database/worker/internal service ports are not publicly exposed.
- Secrets are rotated on a documented schedule.
- Video/evidence volumes are access-controlled and backed up.
- Production logs are redacted and have a defined retention period.
- Model artifacts, datasets and source video have traceable licensing/permission.
- No real factory footage is used as a public demo fixture.

## Privacy

The application intentionally does not implement facial recognition, biometric identity, covert worker profiling or employee productivity scoring. Consider optional face blurring only as a separately validated privacy utility. Define data-minimization and retention policies with the factory and relevant stakeholders before storing employee-visible footage.

## Security status

This project contains useful baseline controls, but it has not undergone a third-party penetration test or a formal security audit. Do not describe it as audited or certified.
