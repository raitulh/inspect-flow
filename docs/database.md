# Database model

The schema is managed by Alembic. The initial migration is in `backend/alembic/versions/`.

## Entities

- **Organization**: tenant boundary.
- **User**: email, scrypt password hash, role and active state; unique email per organization.
- **Site**: organization-owned physical/logical manufacturing location.
- **Station**: belongs to a site and organization; has station code, activity and optional expected cycle time.
- **CameraSource**: RTSP/webcam/uploaded-video source metadata plus connection health and last-frame timestamp.
- **VideoAsset**: metadata and private storage key for an uploaded, validated video.
- **AnalysisJob**: durable job state, provider identifier, progress, timestamps and result summary.
- **InspectionRule**: station-specific type, JSON configuration, severity, enabled flag and version.
- **DetectionEvent**: organization/station plus optional video/job references (nullable for live camera events), optional rule, event type, severity, lifecycle state, timecode, provider/rule version and evidence key.
- **AuditLog**: append-oriented record of important changes.

## Important constraints and indexes

- Site code is unique within an organization.
- Station code is unique within a site.
- User email is globally unique because login identifies accounts by email without an organization selector.
- Foreign keys enforce parent references.
- Tenant IDs are indexed on organization-owned tables.
- Event time, event status/type, analysis status and resource foreign keys are indexed for common list views.

## Tenant isolation

The API derives the tenant from the authenticated user/session and does not accept an organization ID from the caller for ordinary operations. Queries for sites, stations, cameras, videos, jobs, rules, events and reports are scoped by `organization_id`. For parent-child references (for example, station within site), both IDs are checked before the child is created.

## Data and evidence

Large binary content is not stored in relational rows. A `VideoAsset` has a generated storage key and metadata. An event stores an evidence key such as `evidence/<job-id>-<rule-id>.jpg` or a live-camera evidence key; the API resolves that key under the configured evidence root and verifies the resolved path remains beneath the root before returning it. Live-camera events use null video/job references and carry camera identity in their JSON details.

## Operational notes

- Run `alembic upgrade head` during deployment.
- SQLite foreign-key enforcement is not explicitly enabled in the starter engine; SQLite is a local/single-worker development option. PostgreSQL is the recommended deployment database.
- Back up database contents and referenced files together.
- The initial migration is a starting point; future schema changes require new reviewed Alembic revisions. Do not edit an applied migration in production.
