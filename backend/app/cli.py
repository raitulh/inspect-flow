import argparse

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Organization, User
from app.config import get_settings
from app.security import hash_password


def create_admin(email: str, password: str, organization: str):
    if get_settings().app_env.lower() not in {"production", "prod"}:
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.name == organization))
        if not org:
            org = Organization(name=organization)
            db.add(org)
            db.flush()
        normalized = email.strip().lower()
        existing = db.scalar(select(User).where(User.email == normalized))
        if existing:
            raise SystemExit("An account with this email already exists")
        user = User(organization_id=org.id, email=normalized, password_hash=hash_password(password), role="owner", is_active=True)
        db.add(user)
        db.commit()
        print(f"Created owner account {normalized} for organization '{org.name}' (organization_id={org.id}).")


def main():
    parser = argparse.ArgumentParser(description="LineGuard CV admin and worker utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="Create the first owner account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", required=True)
    admin.add_argument("--organization", default="LineGuard Demo Plant")
    sub.add_parser("init-db", help="Create database tables for local development")
    sub.add_parser("worker", help="Run the database-backed analysis worker")
    sub.add_parser("camera-worker", help="Run RTSP/webcam capture and live inspection workers")
    cleanup = sub.add_parser("cleanup-storage", help="Purge expired raw videos and evidence files")
    cleanup.add_argument("--days", type=int, default=30, help="Maximum age in days (default: 30)")
    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.password, args.organization)
    elif args.command == "init-db":
        if get_settings().app_env.lower() in {"production", "prod"}:
            raise SystemExit("Do not use init-db in production; run `alembic upgrade head`.")
        Base.metadata.create_all(bind=engine)
        print("Database tables created.")
    elif args.command == "worker":
        from app.services.jobs import worker_loop
        worker_loop()
    elif args.command == "camera-worker":
        from app.services.cameras import camera_worker_loop
        camera_worker_loop()
    elif args.command == "cleanup-storage":
        from app.services.storage_cleanup import cleanup_expired_storage
        with SessionLocal() as db:
            result = cleanup_expired_storage(db, max_age_days=args.days)
            print(f"Storage cleanup complete: freed {result['freed_mb']} MB ({result['videos_removed']} videos, {result['evidence_removed']} evidence files removed).")


if __name__ == "__main__":
    main()
