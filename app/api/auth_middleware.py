"""JWT cookie-based authentication dependency for FastAPI (MariaDB)."""

import asyncio
from typing import Optional

import jwt
from fastapi import HTTPException, Request

from app.config import get_settings
from app.db.mariadb import fetch_one
from app.db.models import User

_ALGORITHM = "HS256"


def _extract_user_id(request: Request) -> int:
    """Extract user_id from JWT cookie. Raises 401 on failure."""
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Wave 1: Cache brand_filter and role from JWT claims
    request.state.jwt_brand_filter = payload.get("brand_filter", "")
    request.state.jwt_role = payload.get("role", "")

    return int(user_id)


async def get_current_user(request: Request) -> User:
    """Extract and validate JWT from httpOnly cookie, return User from MariaDB."""
    user_id = _extract_user_id(request)

    row = await asyncio.to_thread(
        fetch_one,
        "SELECT u.id, u.email, u.display_name, u.role, u.allowed_models, u.ad_user_id, "
        "a.display_name as ad_name, a.email as ad_email, a.department "
        "FROM users u LEFT JOIN ad_users a ON u.ad_user_id = a.id "
        "WHERE u.id = %s",
        (user_id,),
    )
    if not row:
        raise HTTPException(status_code=401, detail="User not found")

    user = User(
        id=row["id"],
        email=row.get("ad_email") or row.get("email") or "",
        name=row.get("ad_name") or row.get("display_name") or "",
        department=row.get("department") or "",
        role=row["role"],
        allowed_models=row.get("allowed_models") or "skin1004-Analysis",
        ad_user_id=row.get("ad_user_id"),
    )

    # Store on request.state for downstream use
    request.state.user_email = user.email
    request.state.user_id = user.id
    return user


async def get_optional_user(request: Request) -> Optional[User]:
    """Like get_current_user but returns None instead of 401."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
