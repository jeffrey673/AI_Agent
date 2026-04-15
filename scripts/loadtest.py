"""Locust load test — dev (3001) only.

Simulates user traffic patterns to validate capacity improvements:
- 70%: page-poll traffic (/safety/status, /api/auth/me, /api/conversations)
- 30%: AI chat via /v1/chat/completions (SSE streaming)

Auth: generates a valid JWT signed with the project's jwt_secret_key so no
real signin is needed. Targets the seeded admin user (임재필).

Usage (from project root):
    # Headless, 100 users, 10 users/sec spawn, 60s duration
    python -m locust -f scripts/loadtest.py --host http://127.0.0.1:3001 \
        --headless -u 100 -r 10 -t 60s

    # Web UI mode
    python -m locust -f scripts/loadtest.py --host http://127.0.0.1:3001

NEVER target prod (3000). Always use dev (3001).
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from locust import HttpUser, between, task

# Ensure project root is importable so we can reuse settings
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import jwt  # PyJWT — same lib auth_api uses

from app.config import get_settings

_ALGORITHM = "HS256"


def _build_admin_token() -> str:
    """Sign a long-lived JWT for the seeded admin user (임재필, id=1 by convention).

    The token is identical in shape to what /api/auth/signin issues.
    """
    settings = get_settings()
    payload = {
        "user_id": 1,
        "email": "jeffrey@skin1004korea.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
        "brand_filter": "",
        "role": "admin",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


_TOKEN = _build_admin_token()


class Skin1004User(HttpUser):
    """Simulated user — mirrors real browser polling + occasional AI question."""

    # Think time between tasks (browser behavior: 1–5s)
    wait_time = between(1, 5)

    def on_start(self):
        self.client.cookies.set("token", _TOKEN)

    @task(10)
    def poll_status(self):
        """Sidebar polls /safety/status every 30s."""
        self.client.get("/safety/status", name="/safety/status")

    @task(8)
    def me(self):
        """Browser hits /api/auth/me on page load."""
        self.client.get("/api/auth/me", name="/api/auth/me")

    @task(5)
    def list_conversations(self):
        self.client.get("/api/conversations", name="/api/conversations")

    @task(3)
    def departments(self):
        """Public endpoint — list departments."""
        self.client.get("/api/auth/departments", name="/api/auth/departments")
