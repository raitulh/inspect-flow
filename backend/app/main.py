import csv
import json
import logging
import os
import re
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import asyncio
import cv2
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.audit import add_audit
from app.config import get_settings
from app.db import Base, engine, get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    AnalysisJob,
    AuditLog,
    CameraSource,
    DetectionEvent,
    InspectionRule,
    Organization,
    Site,
    Station,
    User,
    VideoAsset,
    now_utc,
)
from app.schemas import (
    AnalysisCreate,
    CameraCreate,
    CameraOut,
    EventOut,
    JobOut,
    LoginRequest,
    RuleCreate,
    SiteCreate,
    SiteOut,
    StationCreate,
    StationOut,
    UserOut,
)
from app.security import create_access_token, verify_password
from app.integrations import plc as plc_integration
from app.services.notifications import dispatch_event_webhook
from app.services.storage_cleanup import cleanup_expired_storage

settings = get_settings()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("lineguard.api")
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_LOCK = threading.Lock()


def _check_login_rate_limit(key: str) -> None:
    now = time.monotonic()
    with _LOGIN_LOCK:
        attempts = [stamp for stamp in _LOGIN_ATTEMPTS.get(key, []) if now - stamp < 60]
        if len(attempts) >= 10:
            _LOGIN_ATTEMPTS[key] = attempts
            raise HTTPException(429, "Too many login attempts. Wait one minute and try again.")
        attempts.append(now)
        _LOGIN_ATTEMPTS[key] = attempts


def _clear_login_attempts(key: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(key, None)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "videos").mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "evidence").mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "cache").mkdir(parents=True, exist_ok=True)
    if settings.app_env.lower() not in {"production", "prod"} and os.getenv("AUTO_CREATE_TABLES", "true").lower() == "true":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="LineGuard CV API", version="0.2.0", description="CPU-first manufacturing inspection and event monitoring API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def csrf_cookie_guard(request: Request, call_next):
    unsafe = request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    bearer = request.headers.get("authorization", "").lower().startswith("bearer ")
    token_cookie = request.cookies.get("lg_access")
    if unsafe and token_cookie and not bearer and request.url.path != "/api/v1/auth/login":
        csrf_cookie = request.cookies.get("lg_csrf")
        csrf_header = request.headers.get("x-csrf-token")
        if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
            return JSONResponse(status_code=403, content={"detail": "CSRF token missing or invalid"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


def _rule_out(rule: InspectionRule) -> dict:
    return {
        "id": rule.id,
        "station_id": rule.station_id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "config": json.loads(rule.config_json or "{}"),
        "severity": rule.severity,
        "is_enabled": rule.is_enabled,
        "version": rule.version,
        "created_at": rule.created_at,
    }


def _safe_site(db: Session, site_id: str, user: User) -> Site:
    site = db.scalar(select(Site).where(Site.id == site_id, Site.organization_id == user.organization_id))
    if not site:
        raise HTTPException(404, "Site not found")
    return site


def _safe_station(db: Session, station_id: str, user: User) -> Station:
    station = db.scalar(select(Station).where(Station.id == station_id, Station.organization_id == user.organization_id))
    if not station:
        raise HTTPException(404, "Station not found")
    return station


def _safe_event(db: Session, event_id: str, user: User) -> DetectionEvent:
    event = db.scalar(select(DetectionEvent).where(DetectionEvent.id == event_id, DetectionEvent.organization_id == user.organization_id))
    if not event:
        raise HTTPException(404, "Event not found")
    return event


@app.get("/healthz", tags=["system"])
def healthz():
    return {"status": "ok", "service": "lineguard-api", "version": "0.2.0"}


@app.get("/readyz", tags=["system"])
def readyz(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok", "storage": "ok" if settings.storage_root.exists() else "missing"}
    except Exception as exc:
        logger.exception("Readiness check failed")
        raise HTTPException(503, "Database is not ready") from exc


@app.get("/version", tags=["system"])
def version():
    return {"name": settings.app_name, "version": "0.2.0", "environment": settings.app_env}


@app.post("/api/v1/auth/login", tags=["auth"])
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    client_host = request.client.host if request.client else "unknown"
    rate_key = f"{client_host}:{email}"
    _check_login_rate_limit(rate_key)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        # One response shape avoids revealing whether an account exists.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _clear_login_attempts(rate_key)
    token = create_access_token(user.id, user.organization_id, user.role)
    csrf = secrets.token_urlsafe(32)
    response = JSONResponse(content={"user": UserOut.model_validate(user).model_dump(mode="json")})
    response.set_cookie("lg_access", token, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.access_token_minutes * 60, path="/")
    response.set_cookie("lg_csrf", csrf, httponly=False, secure=settings.cookie_secure, samesite="lax", max_age=settings.access_token_minutes * 60, path="/")
    return response


@app.post("/api/v1/auth/logout", tags=["auth"])
def logout():
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie("lg_access", path="/")
    response.delete_cookie("lg_csrf", path="/")
    return response


@app.get("/api/v1/auth/me", response_model=UserOut, tags=["auth"])
def auth_me(user: User = Depends(get_current_user)):
    return user


@app.get("/api/v1/organizations/current", tags=["organization"])
def current_organization(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    return {"id": org.id, "name": org.name, "created_at": org.created_at}


@app.patch("/api/v1/organizations/current", tags=["organization"])
def update_organization(payload: dict, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise HTTPException(422, "name must contain 1 to 160 characters")
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    org.name = name.strip()
    add_audit(db, user, "organization.updated", "organization", org.id, {"name": org.name})
    db.commit()
    return {"id": org.id, "name": org.name}


@app.get("/api/v1/sites", response_model=list[SiteOut], tags=["sites"])
def list_sites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Site).where(Site.organization_id == user.organization_id).order_by(Site.name)).all())


@app.post("/api/v1/sites", response_model=SiteOut, status_code=201, tags=["sites"])
def create_site(payload: SiteCreate, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    site = Site(organization_id=user.organization_id, **payload.model_dump())
    db.add(site)
    try:
        db.flush()
        add_audit(db, user, "site.created", "site", site.id, {"code": site.code})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A site with this code already exists") from exc
    db.refresh(site)
    return site


@app.get("/api/v1/sites/{site_id}", response_model=SiteOut, tags=["sites"])
def get_site(site_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _safe_site(db, site_id, user)


@app.patch("/api/v1/sites/{site_id}", response_model=SiteOut, tags=["sites"])
def patch_site(site_id: str, payload: dict, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    site = _safe_site(db, site_id, user)
    for key in ("name", "location"):
        if key in payload:
            value = payload[key]
            if value is not None and (not isinstance(value, str) or len(value) > (160 if key == "name" else 240)):
                raise HTTPException(422, f"Invalid {key}")
            if key == "name" and not value.strip():
                raise HTTPException(422, "name cannot be empty")
            setattr(site, key, value.strip() if isinstance(value, str) else value)
    add_audit(db, user, "site.updated", "site", site.id)
    db.commit()
    db.refresh(site)
    return site


@app.get("/api/v1/stations", response_model=list[StationOut], tags=["stations"])
def list_stations(site_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Station).where(Station.organization_id == user.organization_id)
    if site_id:
        query = query.where(Station.site_id == site_id)
    return list(db.scalars(query.order_by(Station.created_at.desc())).all())


@app.post("/api/v1/stations", response_model=StationOut, status_code=201, tags=["stations"])
def create_station(payload: StationCreate, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    _safe_site(db, payload.site_id, user)
    station = Station(organization_id=user.organization_id, **payload.model_dump())
    db.add(station)
    try:
        db.flush()
        add_audit(db, user, "station.created", "station", station.id, {"code": station.code})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A station with this code already exists for this site") from exc
    db.refresh(station)
    return station


@app.get("/api/v1/stations/{station_id}", response_model=StationOut, tags=["stations"])
def get_station(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _safe_station(db, station_id, user)


@app.patch("/api/v1/stations/{station_id}", response_model=StationOut, tags=["stations"])
def patch_station(station_id: str, payload: dict, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    station = _safe_station(db, station_id, user)
    allowed = {"name", "description", "expected_cycle_seconds", "is_active"}
    if set(payload) - allowed:
        raise HTTPException(422, f"Allowed fields: {', '.join(sorted(allowed))}")
    for key, value in payload.items():
        if key == "name" and (not isinstance(value, str) or not value.strip() or len(value) > 160):
            raise HTTPException(422, "Invalid station name")
        if key == "expected_cycle_seconds" and value is not None and (not isinstance(value, (int, float)) or not 0 < value <= 86400):
            raise HTTPException(422, "expected_cycle_seconds must be in (0, 86400]")
        if key == "is_active" and not isinstance(value, bool):
            raise HTTPException(422, "is_active must be a boolean")
        setattr(station, key, value.strip() if key == "name" and isinstance(value, str) else value)
    add_audit(db, user, "station.updated", "station", station.id)
    db.commit()
    db.refresh(station)
    return station


@app.get("/api/v1/stations/{station_id}/health", tags=["stations"])
def station_health(station_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _safe_station(db, station_id, user)
    cameras = list(db.scalars(select(CameraSource).where(CameraSource.station_id == station_id, CameraSource.organization_id == user.organization_id)).all())
    open_events = db.scalar(select(func.count()).select_from(DetectionEvent).where(
        DetectionEvent.station_id == station_id, DetectionEvent.organization_id == user.organization_id, DetectionEvent.status == "open"
    )) or 0
    return {"station_id": station_id, "camera_count": len(cameras), "online_cameras": sum(c.status == "online" for c in cameras), "open_events": open_events, "vision_health": "not_configured" if not cameras else "camera_source_status_only"}


@app.get("/api/v1/cameras", response_model=list[CameraOut], tags=["cameras"])
def list_cameras(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(CameraSource).where(CameraSource.organization_id == user.organization_id).order_by(CameraSource.created_at.desc())).all())


@app.post("/api/v1/cameras", response_model=CameraOut, status_code=201, tags=["cameras"])
def create_camera(payload: CameraCreate, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    _safe_station(db, payload.station_id, user)
    uri = payload.source_uri
    if payload.source_type == "rtsp":
        parsed = urlparse(uri or "")
        if parsed.scheme not in {"rtsp", "rtsps"} or not parsed.hostname:
            raise HTTPException(422, "RTSP camera URI must use rtsp:// or rtsps://")
        if parsed.username or parsed.password:
            raise HTTPException(422, "Embedded RTSP credentials are not supported because this build does not provide encrypted camera-secret management")
    elif payload.source_type == "webcam" and uri and not re.fullmatch(r"\d{1,3}", uri):
        raise HTTPException(422, "Webcam source URI must be a numeric device index")
    elif payload.source_type == "uploaded_video":
        uri = None
    camera = CameraSource(organization_id=user.organization_id, station_id=payload.station_id, name=payload.name, source_type=payload.source_type, source_uri=uri, status="not_tested")
    db.add(camera)
    db.flush()
    add_audit(db, user, "camera.created", "camera", camera.id, {"source_type": camera.source_type})
    db.commit()
    db.refresh(camera)
    return camera


@app.patch("/api/v1/cameras/{camera_id}", response_model=CameraOut, tags=["cameras"])
def patch_camera(camera_id: str, payload: dict, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    camera = db.scalar(select(CameraSource).where(CameraSource.id == camera_id, CameraSource.organization_id == user.organization_id))
    if not camera:
        raise HTTPException(404, "Camera not found")
    if set(payload) - {"name"}:
        raise HTTPException(422, "Only name changes are supported for a configured camera")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise HTTPException(422, "Invalid camera name")
    camera.name = name.strip()
    add_audit(db, user, "camera.updated", "camera", camera.id)
    db.commit()
    db.refresh(camera)
    return camera


@app.post("/api/v1/cameras/{camera_id}/test-connection", tags=["cameras"])
def test_camera_connection(camera_id: str, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    camera = db.scalar(select(CameraSource).where(CameraSource.id == camera_id, CameraSource.organization_id == user.organization_id))
    if not camera:
        raise HTTPException(404, "Camera not found")
    if camera.source_type == "uploaded_video" or not camera.source_uri:
        raise HTTPException(422, "This camera has no live stream source configured")
    try:
        source = int(camera.source_uri) if camera.source_type == "webcam" else camera.source_uri
        if camera.source_type == "rtsp":
            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 4000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 4000,
            ])
        else:
            cap = cv2.VideoCapture(source)
        opened = cap.isOpened()
        ok, frame = cap.read() if opened else (False, None)
        cap.release()
        if not ok or frame is None:
            raise RuntimeError("Camera opened but no frame was received")
        camera.status = "connected"
        camera.last_error = None
        camera.last_frame_at = now_utc()
        db.commit()
        return {"camera_id": camera.id, "status": camera.status, "message": "A test frame was received.", "frame_width": int(frame.shape[1]), "frame_height": int(frame.shape[0])}
    except Exception as exc:
        camera.status = "disconnected"
        camera.last_error = str(exc)[:500]
        db.commit()
        return {"camera_id": camera.id, "status": camera.status, "message": camera.last_error}


@app.get("/api/v1/cameras/{camera_id}/health", tags=["cameras"])
def camera_health(camera_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    camera = db.scalar(select(CameraSource).where(CameraSource.id == camera_id, CameraSource.organization_id == user.organization_id))
    if not camera:
        raise HTTPException(404, "Camera not found")
    return {"camera_id": camera.id, "status": camera.status, "last_error": camera.last_error, "last_frame_at": camera.last_frame_at}


@app.get("/api/v1/cameras/{camera_id}/snapshot", tags=["cameras"])
def camera_snapshot(camera_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    camera = db.scalar(select(CameraSource).where(CameraSource.id == camera_id, CameraSource.organization_id == user.organization_id))
    if not camera:
        raise HTTPException(404, "Camera not found")
    cache_path = settings.storage_root / "cache" / f"live-{camera_id}.jpg"
    if cache_path.exists():
        return FileResponse(cache_path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    if camera.source_type == "uploaded_video" or not camera.source_uri:
        raise HTTPException(422, "Camera has no stream source configured")
    try:
        source = int(camera.source_uri) if camera.source_type == "webcam" else camera.source_uri
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000]) if camera.source_type == "rtsp" else cv2.VideoCapture(source)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        cap.release()
        if not ok or frame is None:
            raise RuntimeError("Could not capture frame from camera")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(cache_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return FileResponse(cache_path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(502, f"Could not acquire camera snapshot: {str(exc)[:200]}")


@app.get("/api/v1/cameras/{camera_id}/stream", tags=["cameras"])
async def camera_stream(camera_id: str, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("lg_access")
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Authentication required for live stream")
    from app.security import decode_access_token
    payload = decode_access_token(token)
    camera = db.scalar(select(CameraSource).where(CameraSource.id == camera_id, CameraSource.organization_id == payload["org"]))
    if not camera:
        raise HTTPException(404, "Camera not found")

    cache_path = settings.storage_root / "cache" / f"live-{camera_id}.jpg"

    async def frame_stream():
        last_mtime = 0.0
        while True:
            if await request.is_disconnected():
                break
            if cache_path.exists():
                try:
                    stat = cache_path.stat()
                    if stat.st_mtime != last_mtime:
                        last_mtime = stat.st_mtime
                        frame_bytes = cache_path.read_bytes()
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: " + str(len(frame_bytes)).encode("ascii") + b"\r\n\r\n"
                            + frame_bytes + b"\r\n"
                        )
                except Exception:
                    pass
            await asyncio.sleep(0.1)

    return StreamingResponse(frame_stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/v1/events/stream", tags=["events"])
async def events_stream(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("lg_access")
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Authentication required for live event stream")
    from app.security import decode_access_token
    payload = decode_access_token(token)
    org_id = payload["org"]

    async def sse_generator():
        last_check = datetime.now(timezone.utc)
        yield "event: connected\ndata: {\"status\":\"listening\"}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                from app.db import SessionLocal
                with SessionLocal() as session:
                    recent = list(session.scalars(
                        select(DetectionEvent).where(
                            DetectionEvent.organization_id == org_id,
                            DetectionEvent.created_at >= last_check,
                        ).order_by(DetectionEvent.created_at.asc()).limit(20)
                    ).all())
                    if recent:
                        last_check = recent[-1].created_at
                        for ev in recent:
                            data = json.dumps({
                                "id": ev.id,
                                "station_id": ev.station_id,
                                "event_type": ev.event_type,
                                "severity": ev.severity,
                                "summary": ev.summary,
                                "timestamp_seconds": ev.timestamp_seconds,
                                "created_at": ev.created_at.isoformat() if ev.created_at else None,
                            })
                            yield f"event: detection_event\ndata: {data}\n\n"
            except Exception:
                pass
            await asyncio.sleep(1.2)

    return StreamingResponse(sse_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.post("/api/v1/integrations/webhook-test", tags=["integrations"])
def test_webhook(user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    if not settings.webhook_url:
        return {"configured": False, "message": "WEBHOOK_URL is not configured in environment variables."}
    success = dispatch_event_webhook({
        "source": "manual_test",
        "station_id": "test-station",
        "event_type": "webhook_verification",
        "severity": "info",
        "summary": "Manual test notification from LineGuard CV dashboard",
        "timestamp_seconds": 0.0,
    })
    return {"configured": True, "success": success, "url": settings.webhook_url, "message": "Webhook test delivered successfully!" if success else "Webhook delivery failed. Check URL or endpoint logs."}


@app.post("/api/v1/storage/cleanup", tags=["system"])
def trigger_storage_cleanup(days: int = Query(default=30, ge=1, le=365), user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    result = cleanup_expired_storage(db, max_age_days=days)
    add_audit(db, user, "storage.cleanup", "system", "local", result)
    return result


async def _save_upload(upload: UploadFile, user: User, station: Station) -> tuple[str, int, int, int, float]:
    if not upload.filename:
        raise HTTPException(422, "A filename is required")
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in settings.allowed_video_extensions:
        raise HTTPException(415, f"Unsupported video extension. Allowed: {', '.join(settings.allowed_video_extensions)}")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    video_dir = settings.storage_root / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"videos/{uuid4().hex}{suffix}"
    target = settings.storage_root / storage_key
    bytes_written = 0
    try:
        with target.open("xb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(413, f"Video exceeds configured upload limit ({settings.max_upload_mb} MB)")
                out.write(chunk)
        if bytes_written == 0:
            raise HTTPException(422, "Uploaded video is empty")
        cap = cv2.VideoCapture(str(target))
        try:
            if not cap.isOpened():
                raise HTTPException(422, "File is not a decodable video supported by this OpenCV installation")
            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                raise HTTPException(422, "Video contains no readable frames")
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or frame.shape[1])
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or frame.shape[0])
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = frame_count / fps if fps > 0 and frame_count > 0 else 0.0
        finally:
            cap.release()
        return storage_key, bytes_written, width, height, duration
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


@app.post("/api/v1/videos", status_code=201, tags=["videos"])
async def upload_video(request: Request, station_id: str, file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings.max_upload_mb * 1024 * 1024 + 2 * 1024 * 1024:
        raise HTTPException(413, f"Upload request exceeds configured limit ({settings.max_upload_mb} MB plus multipart overhead)")
    station = _safe_station(db, station_id, user)
    storage_key, size_bytes, width, height, duration = await _save_upload(file, user, station)
    original_name = Path(file.filename or "video").name[:255]
    asset = VideoAsset(
        organization_id=user.organization_id,
        station_id=station.id,
        original_filename=original_name,
        storage_key=storage_key,
        size_bytes=size_bytes,
        duration_seconds=duration or None,
        frame_width=width,
        frame_height=height,
    )
    db.add(asset)
    db.flush()
    add_audit(db, user, "video.uploaded", "video", asset.id, {"size_bytes": size_bytes, "station_id": station.id})
    db.commit()
    db.refresh(asset)
    return {
        "id": asset.id,
        "station_id": asset.station_id,
        "original_filename": asset.original_filename,
        "size_bytes": asset.size_bytes,
        "duration_seconds": asset.duration_seconds,
        "frame_width": asset.frame_width,
        "frame_height": asset.frame_height,
        "created_at": asset.created_at,
    }


@app.get("/api/v1/videos/{video_id}", tags=["videos"])
def get_video(video_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.scalar(select(VideoAsset).where(VideoAsset.id == video_id, VideoAsset.organization_id == user.organization_id))
    if not asset:
        raise HTTPException(404, "Video not found")
    return {"id": asset.id, "station_id": asset.station_id, "original_filename": asset.original_filename, "size_bytes": asset.size_bytes, "duration_seconds": asset.duration_seconds, "frame_width": asset.frame_width, "frame_height": asset.frame_height, "created_at": asset.created_at}


@app.get("/api/v1/videos/{video_id}/content", tags=["videos"])
def stream_video_content(video_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.scalar(select(VideoAsset).where(VideoAsset.id == video_id, VideoAsset.organization_id == user.organization_id))
    if not asset:
        raise HTTPException(404, "Video not found")
    target = settings.storage_root / asset.storage_key
    if not target.exists():
        raise HTTPException(404, "Video file has been purged or does not exist")
    return FileResponse(target, filename=asset.original_filename)


@app.get("/api/v1/videos", tags=["videos"])
def list_videos(limit: int = Query(default=50, ge=1, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(VideoAsset).where(VideoAsset.organization_id == user.organization_id).order_by(VideoAsset.created_at.desc()).limit(limit)).all()
    return [{"id": x.id, "station_id": x.station_id, "original_filename": x.original_filename, "size_bytes": x.size_bytes, "duration_seconds": x.duration_seconds, "frame_width": x.frame_width, "frame_height": x.frame_height, "created_at": x.created_at} for x in rows]


@app.post("/api/v1/analyses", response_model=JobOut, status_code=202, tags=["analyses"])
def create_analysis(payload: AnalysisCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    station = _safe_station(db, payload.station_id, user)
    video = db.scalar(select(VideoAsset).where(VideoAsset.id == payload.video_id, VideoAsset.organization_id == user.organization_id))
    if not video:
        raise HTTPException(404, "Video not found")
    if video.station_id != station.id:
        raise HTTPException(422, "Video and station must match")
    job = AnalysisJob(organization_id=user.organization_id, station_id=station.id, video_id=video.id, provider_name=payload.provider_name, status="queued", progress=0)
    db.add(job)
    db.flush()
    add_audit(db, user, "analysis.created", "analysis_job", job.id, {"video_id": video.id, "station_id": station.id})
    db.commit()
    db.refresh(job)
    return job


@app.get("/api/v1/analyses", response_model=list[JobOut], tags=["analyses"])
def list_analyses(status_filter: str | None = Query(default=None, alias="status"), limit: int = Query(default=50, ge=1, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(AnalysisJob).where(AnalysisJob.organization_id == user.organization_id)
    if status_filter:
        if status_filter not in {"queued", "running", "completed", "failed", "cancelled"}:
            raise HTTPException(422, "Invalid analysis status")
        query = query.where(AnalysisJob.status == status_filter)
    return list(db.scalars(query.order_by(AnalysisJob.created_at.desc()).limit(limit)).all())


@app.get("/api/v1/analyses/{job_id}", response_model=JobOut, tags=["analyses"])
def get_analysis(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.organization_id == user.organization_id))
    if not job:
        raise HTTPException(404, "Analysis job not found")
    return job


@app.post("/api/v1/analyses/{job_id}/cancel", tags=["analyses"])
def cancel_analysis(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.organization_id == user.organization_id))
    if not job:
        raise HTTPException(404, "Analysis job not found")
    if job.status != "queued":
        raise HTTPException(409, "Only queued jobs can be cancelled")
    job.status = "cancelled"
    job.completed_at = now_utc()
    add_audit(db, user, "analysis.cancelled", "analysis_job", job.id)
    db.commit()
    return {"id": job.id, "status": job.status}


@app.get("/api/v1/models", tags=["models"])
def list_models(user: User = Depends(get_current_user)):
    from importlib.util import find_spec
    yolo_installed = find_spec("ultralytics") is not None
    model_path = os.getenv("YOLO_MODEL_PATH", "")
    weights_ready = bool(model_path and Path(model_path).is_file())
    return [
        {
            "id": "opencv_rules", "name": "OpenCV Color and Motion Rules",
            "version": "opencv-color-and-motion-rules-v1", "provider_type": "deterministic_opencv_heuristics",
            "trained_weights": False, "configured": True, "device_support": ["cpu"],
            "capabilities": ["HSV color presence", "frame-difference inactivity", "ROI-based monitoring"],
            "limitations": ["heuristic only", "not semantic object recognition", "not safety-rated"],
        },
        {
            "id": "surface_defect_cpu", "name": "CPU Surface Anomaly Heuristic",
            "version": "lineguard-surface-candidate-v1", "provider_type": "opencv_morphology_heuristic",
            "trained_weights": False, "configured": True, "device_support": ["cpu"],
            "capabilities": ["scratch-like and crack-like elongated candidate regions", "evidence bounding boxes"],
            "limitations": ["not a trained classifier", "sensitive to illumination and texture", "score is not a probability"],
        },
        {
            "id": "yolo_cpu", "name": "YOLO CPU Object Detection Adapter",
            "version": "ultralytics-yolo-cpu-adapter-v1", "provider_type": "optional_user_supplied_model",
            "trained_weights": weights_ready, "configured": weights_ready and yolo_installed,
            "runtime_installed": yolo_installed, "device_support": ["cpu"],
            "capabilities": ["object detection", "target-class presence and absence rules", "custom defect classes"],
            "limitations": ["requires separately supplied model weights", "requires labeled training and validation", "no weights are bundled"],
        },
    ]


@app.get("/api/v1/models/{model_id}", tags=["models"])
def get_model(model_id: str, user: User = Depends(get_current_user)):
    models = list_models(user)
    for model in models:
        if model["id"] == model_id or model["version"] == model_id:
            return model
    raise HTTPException(404, "Model/provider not found")


@app.get("/api/v1/inspection-rules", tags=["inspection-rules"])
def list_rules(station_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(InspectionRule).where(InspectionRule.organization_id == user.organization_id)
    if station_id:
        query = query.where(InspectionRule.station_id == station_id)
    return [_rule_out(r) for r in db.scalars(query.order_by(InspectionRule.created_at.desc())).all()]


@app.post("/api/v1/inspection-rules", status_code=201, tags=["inspection-rules"])
def create_rule(payload: RuleCreate, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    _safe_station(db, payload.station_id, user)
    rule = InspectionRule(
        organization_id=user.organization_id,
        station_id=payload.station_id,
        name=payload.name,
        rule_type=payload.rule_type,
        config_json=json.dumps(payload.config, separators=(",", ":")),
        severity=payload.severity,
        is_enabled=payload.is_enabled,
        version=1,
    )
    db.add(rule)
    db.flush()
    add_audit(db, user, "inspection_rule.created", "inspection_rule", rule.id, {"rule_type": rule.rule_type})
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@app.patch("/api/v1/inspection-rules/{rule_id}", tags=["inspection-rules"])
def update_rule(rule_id: str, payload: dict, user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    rule = db.scalar(select(InspectionRule).where(InspectionRule.id == rule_id, InspectionRule.organization_id == user.organization_id))
    if not rule:
        raise HTTPException(404, "Inspection rule not found")
    if set(payload) - {"name", "config", "severity", "is_enabled"}:
        raise HTTPException(422, "Unsupported inspection rule field")
    if "name" in payload:
        if not isinstance(payload["name"], str) or not payload["name"].strip() or len(payload["name"]) > 160:
            raise HTTPException(422, "Invalid rule name")
        rule.name = payload["name"].strip()
    if "config" in payload:
        if not isinstance(payload["config"], dict):
            raise HTTPException(422, "config must be an object")
        # Re-validate using the same schema to avoid accepting malformed rule settings.
        try:
            candidate = RuleCreate(station_id=rule.station_id, name=rule.name, rule_type=rule.rule_type, config=payload["config"], severity=payload.get("severity", rule.severity), is_enabled=payload.get("is_enabled", rule.is_enabled))
        except ValidationError as exc:
            raise HTTPException(422, "Invalid inspection rule configuration") from exc
        rule.config_json = json.dumps(candidate.config, separators=(",", ":"))
    if "severity" in payload:
        if payload["severity"] not in {"info", "warning", "high", "critical"}:
            raise HTTPException(422, "Invalid severity")
        rule.severity = payload["severity"]
    if "is_enabled" in payload:
        if not isinstance(payload["is_enabled"], bool):
            raise HTTPException(422, "is_enabled must be a boolean")
        rule.is_enabled = payload["is_enabled"]
    rule.version += 1
    add_audit(db, user, "inspection_rule.updated", "inspection_rule", rule.id, {"version": rule.version})
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@app.get("/api/v1/events", response_model=list[EventOut], tags=["events"])
def list_events(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = None,
    event_type: str | None = None,
    station_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(DetectionEvent).where(DetectionEvent.organization_id == user.organization_id)
    if status_filter:
        if status_filter not in {"open", "acknowledged", "resolved", "false_positive"}:
            raise HTTPException(422, "Invalid event status")
        query = query.where(DetectionEvent.status == status_filter)
    if severity:
        if severity not in {"info", "warning", "high", "critical"}:
            raise HTTPException(422, "Invalid severity")
        query = query.where(DetectionEvent.severity == severity)
    if event_type:
        query = query.where(DetectionEvent.event_type == event_type)
    if station_id:
        _safe_station(db, station_id, user)
        query = query.where(DetectionEvent.station_id == station_id)
    return list(db.scalars(query.order_by(DetectionEvent.created_at.desc()).offset(offset).limit(limit)).all())


@app.get("/api/v1/events/{event_id}", response_model=EventOut, tags=["events"])
def get_event(event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _safe_event(db, event_id, user)


@app.post("/api/v1/events/{event_id}/acknowledge", tags=["events"])
def acknowledge_event(event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = _safe_event(db, event_id, user)
    if event.status in {"resolved", "false_positive"}:
        raise HTTPException(409, "Closed events cannot be acknowledged")
    event.status = "acknowledged"
    event.acknowledged_by = user.id
    event.acknowledged_at = now_utc()
    add_audit(db, user, "event.acknowledged", "detection_event", event.id)
    db.commit()
    return {"id": event.id, "status": event.status, "acknowledged_at": event.acknowledged_at}


@app.post("/api/v1/events/{event_id}/resolve", tags=["events"])
def resolve_event(event_id: str, payload: dict | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = _safe_event(db, event_id, user)
    if event.status == "false_positive":
        raise HTTPException(409, "False-positive events cannot be resolved")
    note = (payload or {}).get("note", "")
    if not isinstance(note, str) or len(note) > 2000:
        raise HTTPException(422, "Resolution note must be a string up to 2000 characters")
    event.status = "resolved"
    event.resolved_by = user.id
    event.resolved_at = now_utc()
    event.resolution_note = note.strip() or None
    add_audit(db, user, "event.resolved", "detection_event", event.id, {"has_note": bool(event.resolution_note)})
    db.commit()
    return {"id": event.id, "status": event.status, "resolved_at": event.resolved_at}


@app.post("/api/v1/events/{event_id}/mark-false-positive", tags=["events"])
def mark_false_positive(event_id: str, payload: dict, user: User = Depends(require_roles("owner", "admin", "engineer", "operator")), db: Session = Depends(get_db)):
    event = _safe_event(db, event_id, user)
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise HTTPException(422, "A false-positive reason is required")
    if event.status == "resolved":
        raise HTTPException(409, "Resolved events cannot be marked as false positives")
    event.status = "false_positive"
    event.false_positive_reason = reason.strip()
    event.resolved_by = user.id
    event.resolved_at = now_utc()
    add_audit(db, user, "event.marked_false_positive", "detection_event", event.id)
    db.commit()
    return {"id": event.id, "status": event.status}


@app.get("/api/v1/events/{event_id}/evidence", tags=["events"])
def event_evidence(event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = _safe_event(db, event_id, user)
    if not event.evidence_key:
        raise HTTPException(404, "No evidence is attached to this event")
    target = (settings.storage_root / event.evidence_key).resolve()
    evidence_root = (settings.storage_root / "evidence").resolve()
    if evidence_root not in target.parents or not target.is_file():
        raise HTTPException(404, "Evidence file is unavailable")
    return FileResponse(target, media_type="image/jpeg", filename=f"lineguard-evidence-{event.id}.jpg", headers={"Cache-Control": "private, no-store"})


@app.get("/api/v1/reports/summary", tags=["reports"])
def report_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event_count = db.scalar(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.organization_id == user.organization_id)) or 0
    open_count = db.scalar(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.organization_id == user.organization_id, DetectionEvent.status == "open")) or 0
    station_count = db.scalar(select(func.count()).select_from(Station).where(Station.organization_id == user.organization_id)) or 0
    camera_count = db.scalar(select(func.count()).select_from(CameraSource).where(CameraSource.organization_id == user.organization_id)) or 0
    online_cameras = db.scalar(select(func.count()).select_from(CameraSource).where(CameraSource.organization_id == user.organization_id, CameraSource.status == "online")) or 0
    queued_jobs = db.scalar(select(func.count()).select_from(AnalysisJob).where(AnalysisJob.organization_id == user.organization_id, AnalysisJob.status == "queued")) or 0
    grouped = db.execute(select(DetectionEvent.severity, func.count()).where(DetectionEvent.organization_id == user.organization_id).group_by(DetectionEvent.severity)).all()
    severity_counts = {key: value for key, value in grouped}
    return {"stations": station_count, "cameras": camera_count, "online_cameras": online_cameras, "total_events": event_count, "open_events": open_count, "queued_jobs": queued_jobs, "events_by_severity": severity_counts}


@app.get("/api/v1/reports/quality", tags=["reports"])
def report_quality(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    grouped = db.execute(select(DetectionEvent.event_type, func.count()).where(DetectionEvent.organization_id == user.organization_id).group_by(DetectionEvent.event_type)).all()
    return {"events_by_type": [{"event_type": k, "count": v} for k, v in grouped], "model_metrics": None, "note": "Model precision/recall are unavailable until a labeled evaluation set is evaluated."}


@app.get("/api/v1/reports/stations", tags=["reports"])
def report_stations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stations = db.scalars(select(Station).where(Station.organization_id == user.organization_id).order_by(Station.name)).all()
    result = []
    for station in stations:
        total = db.scalar(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.organization_id == user.organization_id, DetectionEvent.station_id == station.id)) or 0
        open_count = db.scalar(select(func.count()).select_from(DetectionEvent).where(DetectionEvent.organization_id == user.organization_id, DetectionEvent.station_id == station.id, DetectionEvent.status == "open")) or 0
        result.append({"station_id": station.id, "name": station.name, "code": station.code, "events": total, "open_events": open_count})
    return result


@app.get("/api/v1/reports/export.csv", tags=["reports"])
def export_events_csv(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = db.scalars(select(DetectionEvent).where(DetectionEvent.organization_id == user.organization_id).order_by(DetectionEvent.created_at.desc()).limit(10000)).all()
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "created_at", "station_id", "event_type", "severity", "status", "summary", "timestamp_seconds", "rule_version"])
    for event in events:
        writer.writerow([event.id, event.created_at.isoformat(), event.station_id, event.event_type, event.severity, event.status, event.summary, event.timestamp_seconds, event.rule_version])
    return Response(content=out.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=lineguard-events.csv", "Cache-Control": "private, no-store"})


@app.get("/api/v1/audit-logs", tags=["audit"])
def audit_logs(limit: int = Query(default=100, ge=1, le=500), user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.organization_id == user.organization_id).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{"id": row.id, "actor_user_id": row.actor_user_id, "action": row.action, "resource_type": row.resource_type, "resource_id": row.resource_id, "details": json.loads(row.details_json or "{}"), "created_at": row.created_at} for row in rows]


@app.get("/api/v1/users", tags=["users"])
def list_users(user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    users = db.scalars(select(User).where(User.organization_id == user.organization_id).order_by(User.created_at)).all()
    return [UserOut.model_validate(x).model_dump(mode="json") | {"is_active": x.is_active, "created_at": x.created_at.isoformat()} for x in users]


@app.patch("/api/v1/users/{user_id}", tags=["users"])
def update_user(user_id: str, payload: dict, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    from app.security import hash_password

    target = db.scalar(select(User).where(User.id == user_id, User.organization_id == user.organization_id))
    if not target:
        raise HTTPException(404, "User not found")
    allowed = {"role", "is_active", "password"}
    if not payload or set(payload) - allowed:
        raise HTTPException(422, "Allowed fields: role, is_active, password")
    if target.role == "owner":
        raise HTTPException(409, "Owner account changes must use a separate administrative recovery process")
    if "role" in payload:
        if payload["role"] not in {"admin", "engineer", "operator", "viewer"}:
            raise HTTPException(422, "Invalid role")
        if user.role == "admin" and payload["role"] == "admin" and target.id != user.id:
            # Admins may administer operators/engineers but not grant another administrator role.
            raise HTTPException(403, "Only an owner can grant administrator role")
        target.role = payload["role"]
    if "is_active" in payload:
        if not isinstance(payload["is_active"], bool):
            raise HTTPException(422, "is_active must be a boolean")
        if target.id == user.id and payload["is_active"] is False:
            raise HTTPException(409, "You cannot deactivate your own session account")
        target.is_active = payload["is_active"]
    if "password" in payload:
        password = payload["password"]
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise HTTPException(422, "Password must contain 12 to 256 characters")
        target.password_hash = hash_password(password)
    add_audit(db, user, "user.updated", "user", target.id, {"fields": sorted(payload.keys())})
    db.commit()
    db.refresh(target)
    return UserOut.model_validate(target).model_dump(mode="json") | {"is_active": target.is_active}


@app.post("/api/v1/users", status_code=201, tags=["users"])
def create_user(payload: dict, user: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    from pydantic import EmailStr, TypeAdapter, ValidationError
    from app.security import hash_password

    email = payload.get("email")
    password = payload.get("password")
    role = payload.get("role", "operator")
    if not isinstance(email, str) or len(email) > 320:
        raise HTTPException(422, "A valid email is required")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(email)).lower().strip()
    except ValidationError as exc:
        raise HTTPException(422, "A valid email is required") from exc
    if role not in {"admin", "engineer", "operator", "viewer"}:
        raise HTTPException(422, "Role must be admin, engineer, operator or viewer")
    if not isinstance(password, str) or len(password) < 12 or len(password) > 256:
        raise HTTPException(422, "Password must contain 12 to 256 characters")
    new_user = User(organization_id=user.organization_id, email=email.lower().strip(), password_hash=hash_password(password), role=role)
    db.add(new_user)
    try:
        db.flush()
        add_audit(db, user, "user.created", "user", new_user.id, {"role": role})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists") from exc
    db.refresh(new_user)
    return UserOut.model_validate(new_user).model_dump(mode="json")


# When running via `uvicorn app.main:app`, the CLI/worker handles persistent jobs separately.


@app.get("/api/v1/integrations/plc/status", tags=["integrations"])
def plc_status(user: User = Depends(get_current_user)):
    return plc_integration.status()


@app.post("/api/v1/integrations/plc/test", tags=["integrations"])
def plc_test(user: User = Depends(require_roles("owner", "admin", "engineer")), db: Session = Depends(get_db)):
    result = plc_integration.test_connection()
    add_audit(db, user, "plc.connection_tested", "plc", None, {"connected": result.get("connected", False), "mode": result.get("mode")})
    db.commit()
    return result


@app.post("/api/v1/integrations/plc/machine-stop-request", tags=["integrations"])
def plc_machine_stop_request(payload: dict, user: User = Depends(require_roles("owner", "admin", "engineer", "operator")), db: Session = Depends(get_db)):
    try:
        result = plc_integration.request_machine_stop(
            confirmation=payload.get("confirmation", ""),
            safety_acknowledged=payload.get("safety_acknowledged") is True,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        add_audit(db, user, "plc.machine_stop_request_failed", "plc", None, {"error_type": type(exc).__name__})
        db.commit()
        logger.exception("PLC stop-request adapter failed")
        raise HTTPException(503, "PLC stop-request adapter failed; verify machine state independently") from exc
    add_audit(db, user, "plc.machine_stop_requested", "plc", None, {"simulated": result.get("simulated"), "accepted": result.get("accepted")})
    db.commit()
    return result
