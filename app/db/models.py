"""Data models: User (simple dataclass, backed by MariaDB)."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    """User model populated from MariaDB users + ad_users tables."""
    id: int = 0
    email: str = ""
    name: str = ""
    department: str = ""
    role: str = "user"
    allowed_models: str = "skin1004-Analysis"
    ad_user_id: Optional[int] = None
    password_hash: str = ""
