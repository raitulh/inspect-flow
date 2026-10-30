import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def add_audit(db: Session, user: User | None, action: str, resource_type: str, resource_id: str | None = None, details: dict[str, Any] | None = None) -> None:
    if not user:
        return
    db.add(AuditLog(
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=json.dumps(details or {}, separators=(",", ":")),
    ))
