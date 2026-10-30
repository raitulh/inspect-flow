"""Outbound event webhook notifications for factory MES, Slack, or webhook integrations."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("lineguard.notifications")


def dispatch_event_webhook(event_data: dict[str, Any]) -> bool:
    """Send an asynchronous webhook notification if WEBHOOK_URL is configured."""
    settings = get_settings()
    url = settings.webhook_url
    if not url:
        return False

    payload = {
        "event": "lineguard.inspection_alert",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": event_data,
    }
    body = json.dumps(payload, default=str)
    headers = {"Content-Type": "application/json", "User-Agent": "LineGuard-CV/0.2.0"}

    if settings.webhook_secret:
        signature = hmac.new(
            settings.webhook_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers["X-LineGuard-Signature"] = signature

    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.post(url, content=body, headers=headers)
            if resp.status_code < 400:
                logger.info("Webhook delivered successfully to %s (HTTP %s)", url, resp.status_code)
                return True
            logger.warning("Webhook endpoint %s returned status %s: %s", url, resp.status_code, resp.text[:200])
            return False
    except Exception as exc:
        logger.error("Failed to deliver webhook to %s: %s", url, exc)
        return False
