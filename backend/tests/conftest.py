import os
import shutil
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.gettempdir()) / "lineguard-cv-pytest"
_TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["APP_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-unit-tests"
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_ROOT / 'test.db').as_posix()}"
os.environ["STORAGE_ROOT"] = str(_TEST_ROOT / "storage")
os.environ["COOKIE_SECURE"] = "false"
os.environ["DEFAULT_FRAME_STRIDE"] = "1"
os.environ["MAX_SAMPLED_FRAMES"] = "1000"
os.environ["MAX_UPLOAD_MB"] = "10"
os.environ["AUTO_CREATE_TABLES"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app, _LOGIN_ATTEMPTS
from app.models import Organization, User
from app.security import hash_password


@pytest.fixture(autouse=True)
def clean_database():
    _LOGIN_ATTEMPTS.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    shutil.rmtree(_TEST_ROOT / "storage", ignore_errors=True)
    (_TEST_ROOT / "storage" / "videos").mkdir(parents=True, exist_ok=True)
    (_TEST_ROOT / "storage" / "evidence").mkdir(parents=True, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def owner_data():
    with SessionLocal() as db:
        organization = Organization(name="Test Plant")
        db.add(organization)
        db.flush()
        user = User(organization_id=organization.id, email="owner@example.com", password_hash=hash_password("correct-horse-battery-staple"), role="owner", is_active=True)
        db.add(user)
        db.commit()
        return {"org_id": organization.id, "user_id": user.id}


def login(client: TestClient, email: str = "owner@example.com", password: str = "correct-horse-battery-staple") -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("lg_csrf")
    return {"X-CSRF-Token": token} if token else {}


def create_site_and_station(client: TestClient) -> tuple[str, str]:
    site_resp = client.post("/api/v1/sites", json={"name": "Plant A", "code": "PLANT-A", "location": "Sylhet"}, headers=csrf(client))
    assert site_resp.status_code == 201, site_resp.text
    station_resp = client.post("/api/v1/stations", json={"site_id": site_resp.json()["id"], "name": "Assembly 01", "code": "ASSY-01"}, headers=csrf(client))
    assert station_resp.status_code == 201, station_resp.text
    return site_resp.json()["id"], station_resp.json()["id"]


def make_video_bytes(color: tuple[int, int, int] = (0, 0, 0), frames: int = 16) -> bytes:
    import cv2
    import numpy as np

    path = _TEST_ROOT / f"fixture-{os.getpid()}.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10.0, (160, 120))
    assert writer.isOpened(), "OpenCV MJPG VideoWriter unavailable in test environment"
    for index in range(frames):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        frame[:] = color
        writer.write(frame)
    writer.release()
    data = path.read_bytes()
    path.unlink(missing_ok=True)
    return data
