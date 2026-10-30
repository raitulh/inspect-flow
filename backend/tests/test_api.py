import json

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Organization, User
from app.security import hash_password
from tests.conftest import csrf, create_site_and_station, login, make_video_bytes


def test_health_and_readiness(client: TestClient):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").status_code == 200
    assert client.get("/version").json()["name"] == "LineGuard CV"


def test_protected_api_requires_authentication(client: TestClient):
    response = client.get("/api/v1/sites")
    assert response.status_code == 401


def test_login_sets_http_only_access_and_csrf_cookie(client: TestClient, owner_data):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "correct-horse-battery-staple"})
    assert response.status_code == 200
    assert "lg_access" in response.cookies
    assert "httponly" in response.headers.get("set-cookie", "").lower()
    assert "lg_csrf" in response.cookies
    assert response.json()["user"]["role"] == "owner"
    assert client.get("/api/v1/auth/me").status_code == 200


def test_invalid_login_has_generic_error(client: TestClient, owner_data):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_cookie_mutation_requires_csrf(client: TestClient, owner_data):
    login(client)
    response = client.post("/api/v1/sites", json={"name": "No CSRF", "code": "NO-CSRF"})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_create_site_station_and_rule(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post("/api/v1/inspection-rules", headers=csrf(client), json={
        "station_id": station_id, "name": "Blue cap expected", "rule_type": "color_presence", "severity": "warning",
        "config": {"zone": [0.1, 0.1, 0.9, 0.9], "hsv_lower": [100, 80, 50], "hsv_upper": [130, 255, 255], "min_pixel_ratio": 0.02, "min_consecutive": 2},
    })
    assert response.status_code == 201, response.text
    rule = response.json()
    assert rule["station_id"] == station_id
    assert rule["config"]["min_consecutive"] == 2
    assert client.get(f"/api/v1/inspection-rules?station_id={station_id}").json()[0]["id"] == rule["id"]


def test_rule_zone_validation(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post("/api/v1/inspection-rules", headers=csrf(client), json={
        "station_id": station_id, "name": "Invalid zone", "rule_type": "color_presence", "config": {"zone": [0.8, 0.8, 0.2, 0.2]},
    })
    assert response.status_code == 422


def test_rule_rejects_invalid_hsv_bounds(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post("/api/v1/inspection-rules", headers=csrf(client), json={
        "station_id": station_id,
        "name": "Invalid HSV",
        "rule_type": "color_presence",
        "config": {"hsv_lower": [180, 0, 0], "hsv_upper": [179, 255, 255]},
    })
    assert response.status_code == 422


def test_motion_rule_rejects_out_of_range_threshold(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post("/api/v1/inspection-rules", headers=csrf(client), json={
        "station_id": station_id,
        "name": "Invalid motion threshold",
        "rule_type": "motion_stall",
        "config": {"inactivity_seconds": 5, "mean_difference_threshold": 999},
    })
    assert response.status_code == 422


def test_station_and_event_tenant_isolation(client: TestClient, owner_data):
    login(client)
    site_id, station_id = create_site_and_station(client)
    with SessionLocal() as db:
        other_org = Organization(name="Other Plant")
        db.add(other_org)
        db.flush()
        other_user = User(organization_id=other_org.id, email="other@example.com", password_hash=hash_password("another-correct-horse-battery"), role="owner", is_active=True)
        db.add(other_user)
        db.commit()
    client.post("/api/v1/auth/logout", headers=csrf(client))
    login(client, "other@example.com", "another-correct-horse-battery")
    assert client.get(f"/api/v1/sites/{site_id}").status_code == 404
    assert client.get(f"/api/v1/stations/{station_id}").status_code == 404
    assert client.get("/api/v1/sites").json() == []


def test_viewer_cannot_create_site(client: TestClient, owner_data):
    with SessionLocal() as db:
        owner = db.get(User, owner_data["user_id"])
        viewer = User(organization_id=owner.organization_id, email="viewer@example.com", password_hash=hash_password("viewer-correct-horse-battery"), role="viewer", is_active=True)
        db.add(viewer)
        db.commit()
    login(client, "viewer@example.com", "viewer-correct-horse-battery")
    response = client.post("/api/v1/sites", headers=csrf(client), json={"name": "Denied", "code": "DENIED"})
    assert response.status_code == 403


def test_video_upload_rejects_bad_extension(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post(f"/api/v1/videos?station_id={station_id}", headers=csrf(client), files={"file": ("payload.exe", b"not a video", "application/octet-stream")})
    assert response.status_code == 415


def test_video_upload_rejects_corrupt_video(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post(f"/api/v1/videos?station_id={station_id}", headers=csrf(client), files={"file": ("corrupt.mp4", b"not a valid mp4 file", "video/mp4")})
    assert response.status_code == 422


def test_upload_queue_analyze_evidence_and_resolve(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    rule_response = client.post("/api/v1/inspection-rules", headers=csrf(client), json={
        "station_id": station_id, "name": "Blue component expected", "rule_type": "color_presence", "severity": "high",
        "config": {"zone": [0, 0, 1, 1], "hsv_lower": [100, 80, 50], "hsv_upper": [130, 255, 255], "min_pixel_ratio": 0.02, "min_consecutive": 2},
    })
    assert rule_response.status_code == 201, rule_response.text
    upload = client.post(f"/api/v1/videos?station_id={station_id}", headers=csrf(client), files={"file": ("fixture.avi", make_video_bytes(), "video/x-msvideo")})
    assert upload.status_code == 201, upload.text
    video_id = upload.json()["id"]
    created = client.post("/api/v1/analyses", headers=csrf(client), json={"station_id": station_id, "video_id": video_id, "provider_name": "opencv_rules"})
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]
    assert created.json()["status"] == "queued"
    from app.services.jobs import run_analysis_job
    run_analysis_job(job_id)
    job = client.get(f"/api/v1/analyses/{job_id}")
    assert job.status_code == 200
    assert job.json()["status"] == "completed", job.text
    summary = json.loads(job.json()["result_summary"])
    assert summary["rules_evaluated"] == 1
    assert summary["events_created"] == 1
    events = client.get(f"/api/v1/events?station_id={station_id}")
    assert events.status_code == 200
    assert len(events.json()) == 1
    event = events.json()[0]
    assert event["event_type"] == "potential_missing_component"
    assert event["severity"] == "high"
    evidence = client.get(f"/api/v1/events/{event['id']}/evidence")
    assert evidence.status_code == 200
    assert evidence.headers["content-type"].startswith("image/jpeg")
    acknowledged = client.post(f"/api/v1/events/{event['id']}/acknowledge", headers=csrf(client))
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"
    resolved = client.post(f"/api/v1/events/{event['id']}/resolve", headers=csrf(client), json={"note": "Inspected manually"})
    assert resolved.status_code == 200
    refreshed = client.get(f"/api/v1/events/{event['id']}")
    assert refreshed.json()["status"] == "resolved"
    assert refreshed.json()["resolution_note"] == "Inspected manually"


def test_station_mismatch_rejected_for_video_analysis(client: TestClient, owner_data):
    login(client)
    site_resp = client.post("/api/v1/sites", headers=csrf(client), json={"name": "Plant", "code": "PLANT"})
    site_id = site_resp.json()["id"]
    st1 = client.post("/api/v1/stations", headers=csrf(client), json={"site_id": site_id, "name": "Station 1", "code": "S1"}).json()["id"]
    st2 = client.post("/api/v1/stations", headers=csrf(client), json={"site_id": site_id, "name": "Station 2", "code": "S2"}).json()["id"]
    upload = client.post(f"/api/v1/videos?station_id={st1}", headers=csrf(client), files={"file": ("fixture.avi", make_video_bytes(), "video/x-msvideo")})
    assert upload.status_code == 201
    response = client.post("/api/v1/analyses", headers=csrf(client), json={"station_id": st2, "video_id": upload.json()["id"]})
    assert response.status_code == 422


def test_queued_job_can_be_cancelled_once(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    upload = client.post(f"/api/v1/videos?station_id={station_id}", headers=csrf(client), files={"file": ("fixture.avi", make_video_bytes(), "video/x-msvideo")})
    job = client.post("/api/v1/analyses", headers=csrf(client), json={"station_id": station_id, "video_id": upload.json()["id"]}).json()
    response = client.post(f"/api/v1/analyses/{job['id']}/cancel", headers=csrf(client))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert client.post(f"/api/v1/analyses/{job['id']}/cancel", headers=csrf(client)).status_code == 409


def test_false_positive_requires_reason(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    rule_response = client.post("/api/v1/inspection-rules", headers=csrf(client), json={"station_id": station_id, "name": "Color", "rule_type": "color_presence", "config": {"hsv_lower": [100, 80, 50], "hsv_upper": [130, 255, 255]}})
    assert rule_response.status_code == 201, rule_response.text
    upload = client.post(f"/api/v1/videos?station_id={station_id}", headers=csrf(client), files={"file": ("fixture.avi", make_video_bytes(), "video/x-msvideo")}).json()
    job = client.post("/api/v1/analyses", headers=csrf(client), json={"station_id": station_id, "video_id": upload["id"]}).json()
    from app.services.jobs import run_analysis_job
    run_analysis_job(job["id"])
    event = client.get(f"/api/v1/events?station_id={station_id}").json()[0]
    empty = client.post(f"/api/v1/events/{event['id']}/mark-false-positive", headers=csrf(client), json={"reason": "   "})
    assert empty.status_code == 422
    marked = client.post(f"/api/v1/events/{event['id']}/mark-false-positive", headers=csrf(client), json={"reason": "Reflections caused the heuristic to trigger"})
    assert marked.status_code == 200
    assert marked.json()["status"] == "false_positive"


def test_reports_are_scoped_and_do_not_fake_model_metrics(client: TestClient, owner_data):
    login(client)
    assert client.get("/api/v1/reports/summary").json()["stations"] == 0
    quality = client.get("/api/v1/reports/quality").json()
    assert quality["model_metrics"] is None
    assert "labeled evaluation" in quality["note"]
    csv_response = client.get("/api/v1/reports/export.csv")
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert csv_response.text.startswith("id,created_at")


def test_camera_uri_validation(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post("/api/v1/cameras", headers=csrf(client), json={"station_id": station_id, "name": "Bad RTSP", "source_type": "rtsp", "source_uri": "https://example.com/video"})
    assert response.status_code == 422
    good = client.post("/api/v1/cameras", headers=csrf(client), json={"station_id": station_id, "name": "Plant camera", "source_type": "rtsp", "source_uri": "rtsp://camera.local/stream"})
    assert good.status_code == 201, good.text
    assert good.json()["status"] == "not_tested"


def test_audit_log_records_created_resource_ids(client: TestClient, owner_data):
    login(client)
    site_resp = client.post("/api/v1/sites", headers=csrf(client), json={"name": "Traceable Plant", "code": "TRACE"})
    assert site_resp.status_code == 201
    site_id = site_resp.json()["id"]
    logs = client.get("/api/v1/audit-logs")
    assert logs.status_code == 200
    matching = [row for row in logs.json() if row["action"] == "site.created"]
    assert len(matching) == 1
    assert matching[0]["resource_id"] == site_id


def test_duplicate_email_is_rejected_across_organizations(client: TestClient, owner_data):
    with SessionLocal() as db:
        other_org = Organization(name="Another Organization")
        db.add(other_org)
        db.flush()
        duplicate = User(organization_id=other_org.id, email="owner@example.com", password_hash=hash_password("another-owner-password-123"), role="owner")
        db.add(duplicate)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("Global email uniqueness must prevent ambiguous email login")


def test_malformed_rule_patch_returns_422_not_500(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    rule = client.post("/api/v1/inspection-rules", headers=csrf(client), json={"station_id": station_id, "name": "Presence", "rule_type": "color_presence", "config": {"zone": [0, 0, 1, 1]}})
    assert rule.status_code == 201, rule.text
    response = client.patch(f"/api/v1/inspection-rules/{rule.json()['id']}", headers=csrf(client), json={"config": {"zone": [0.9, 0.9, 0.1, 0.1]}})
    assert response.status_code == 422


def test_login_attempts_are_throttled(client: TestClient, owner_data):
    responses = [client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong-password"}) for _ in range(11)]
    assert all(response.status_code == 401 for response in responses[:10])
    assert responses[10].status_code == 429


def test_worker_requeues_stale_job(client: TestClient, owner_data):
    from datetime import datetime, timedelta, timezone
    from app.models import AnalysisJob
    from app.services.jobs import recover_stale_jobs

    login(client)
    _, station_id = create_site_and_station(client)
    upload = client.post(f"/api/v1/videos?station_id={station_id}", headers=csrf(client), files={"file": ("fixture.avi", make_video_bytes(), "video/x-msvideo")})
    assert upload.status_code == 201
    queued = client.post("/api/v1/analyses", headers=csrf(client), json={"station_id": station_id, "video_id": upload.json()["id"]})
    assert queued.status_code == 202
    with SessionLocal() as db:
        job = db.get(AnalysisJob, queued.json()["id"])
        job.status = "running"
        job.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()
    assert recover_stale_jobs(max_age_minutes=60) == 1
    refreshed = client.get(f"/api/v1/analyses/{queued.json()['id']}").json()
    assert refreshed["status"] == "queued"
    assert refreshed["progress"] == 0


def test_model_registry_is_honest_about_baseline(client: TestClient, owner_data):
    login(client)
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    model = response.json()[0]
    assert model["trained_weights"] is False
    assert "not semantic object recognition" in model["limitations"]
    assert client.get("/api/v1/models/not-a-model").status_code == 404


def test_rtsp_credentials_are_not_stored_in_plaintext(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    response = client.post("/api/v1/cameras", headers=csrf(client), json={
        "station_id": station_id, "name": "Credentialed camera", "source_type": "rtsp",
        "source_uri": "rtsp://operator:plain-secret@camera.local/stream",
    })
    assert response.status_code == 422
    assert "encrypted camera-secret management" in response.json()["detail"]


def test_video_detail_is_tenant_scoped(client: TestClient, owner_data):
    login(client)
    _, station_id = create_site_and_station(client)
    upload = client.post(f"/api/v1/videos?station_id={station_id}", headers=csrf(client), files={"file": ("fixture.avi", make_video_bytes(), "video/x-msvideo")})
    assert upload.status_code == 201
    video_id = upload.json()["id"]
    assert client.get(f"/api/v1/videos/{video_id}").status_code == 200
    with SessionLocal() as db:
        other_org = Organization(name="Different Tenant")
        db.add(other_org)
        db.flush()
        db.add(User(organization_id=other_org.id, email="different-tenant@example.com", password_hash=hash_password("different-tenant-password-123"), role="owner"))
        db.commit()
    client.post("/api/v1/auth/logout", headers=csrf(client))
    login(client, "different-tenant@example.com", "different-tenant-password-123")
    assert client.get(f"/api/v1/videos/{video_id}").status_code == 404


def test_user_admin_update_and_password_validation(client: TestClient, owner_data):
    login(client)
    create = client.post("/api/v1/users", headers=csrf(client), json={"email": "operator2@example.com", "password": "operator-password-123", "role": "operator"})
    assert create.status_code == 201, create.text
    user_id = create.json()["id"]
    bad = client.patch(f"/api/v1/users/{user_id}", headers=csrf(client), json={"password": "short"})
    assert bad.status_code == 422
    update = client.patch(f"/api/v1/users/{user_id}", headers=csrf(client), json={"role": "engineer", "is_active": False})
    assert update.status_code == 200, update.text
    assert update.json()["role"] == "engineer"
    assert update.json()["is_active"] is False
    assert client.post("/api/v1/auth/login", json={"email": "operator2@example.com", "password": "operator-password-123"}).status_code == 401


def test_live_camera_event_can_be_returned_without_video_or_job(client: TestClient, owner_data):
    from app.models import DetectionEvent

    login(client)
    _, station_id = create_site_and_station(client)
    with SessionLocal() as db:
        db.add(DetectionEvent(
            organization_id=owner_data["org_id"], station_id=station_id,
            video_id=None, job_id=None, rule_id=None,
            event_type="surface_defect_detected", severity="warning", status="open",
            summary="Live camera scratch candidate", details_json='{"camera_id":"camera-1"}',
            confidence=None, timestamp_seconds=1.0, evidence_key=None,
            model_version="lineguard-live-cpu-v0.2", rule_version=None,
        ))
        db.commit()
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    assert response.json()[0]["video_id"] is None
    assert response.json()[0]["job_id"] is None


def test_plc_routes_are_simulation_first_and_require_stop_confirmation(client: TestClient, owner_data, monkeypatch):
    monkeypatch.setenv("PLC_MODE", "simulation")
    monkeypatch.setenv("PLC_OUTPUTS_ENABLED", "false")
    login(client)
    status = client.get("/api/v1/integrations/plc/status")
    assert status.status_code == 200
    assert status.json()["mode"] == "simulation"
    tested = client.post("/api/v1/integrations/plc/test", headers=csrf(client))
    assert tested.status_code == 200
    assert tested.json()["connected"] is True
    invalid = client.post("/api/v1/integrations/plc/machine-stop-request", headers=csrf(client), json={"confirmation": "STOP", "safety_acknowledged": False})
    assert invalid.status_code == 422
    simulated = client.post("/api/v1/integrations/plc/machine-stop-request", headers=csrf(client), json={"confirmation": "REQUEST_STOP", "safety_acknowledged": True})
    assert simulated.status_code == 200
    assert simulated.json()["simulated"] is True


def test_camera_connection_test_reads_a_frame(client: TestClient, owner_data, monkeypatch):
    import numpy as np
    import app.main as main_module

    class FakeCapture:
        def __init__(self, *_args):
            pass
        def set(self, *_args):
            return True
        def isOpened(self):
            return True
        def read(self):
            return True, np.zeros((60, 80, 3), dtype=np.uint8)
        def release(self):
            return None

    monkeypatch.setattr(main_module.cv2, "VideoCapture", FakeCapture)
    login(client)
    _, station_id = create_site_and_station(client)
    camera = client.post("/api/v1/cameras", headers=csrf(client), json={
        "station_id": station_id, "name": "Test RTSP", "source_type": "rtsp", "source_uri": "rtsp://camera.local/stream",
    })
    assert camera.status_code == 201
    result = client.post(f"/api/v1/cameras/{camera.json()['id']}/test-connection", headers=csrf(client))
    assert result.status_code == 200
    assert result.json()["status"] == "connected"
    assert result.json()["frame_width"] == 80
