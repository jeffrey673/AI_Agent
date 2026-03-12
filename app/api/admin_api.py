"""Admin endpoints: user management, model access control (MariaDB)."""

import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth_middleware import get_current_user
from app.db.mariadb import fetch_all, execute
from app.db.models import User

logger = structlog.get_logger(__name__)

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

_ALL_MODELS = "skin1004-Analysis"


# ── Async DB wrappers ──

async def _db_fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    return await asyncio.to_thread(fetch_all, sql, params)

async def _db_execute(sql: str, params: tuple = ()) -> int:
    return await asyncio.to_thread(execute, sql, params)


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class UserListItem(BaseModel):
    id: int
    email: str
    name: str
    department: str
    role: str
    allowed_models: list[str]


class UpdateModelsRequest(BaseModel):
    allowed_models: list[str]


@admin_router.get("/users")
async def list_users(
    user: User = Depends(get_current_user),
) -> list[UserListItem]:
    """List all users with their model permissions."""
    users = await _db_fetch_all("""
        SELECT u.id, u.email, u.display_name, u.role, u.allowed_models,
               a.display_name as ad_name, a.email as ad_email, a.department
        FROM users u
        LEFT JOIN ad_users a ON u.ad_user_id = a.id
        ORDER BY u.created_at
    """)
    result = []
    for u in users:
        if u["role"] == "admin":
            models = [m.strip() for m in _ALL_MODELS.split(",") if m.strip()]
        else:
            raw = u.get("allowed_models") or ""
            models = [m.strip() for m in raw.split(",") if m.strip()]
            if not models:
                models = ["skin1004-Analysis"]
        result.append(UserListItem(
            id=u["id"],
            email=u.get("ad_email") or u.get("email") or "",
            name=u.get("ad_name") or u.get("display_name") or "",
            department=u.get("department") or "",
            role=u["role"],
            allowed_models=models,
        ))
    return result


@admin_router.put("/users/{user_id}/models")
async def update_user_models(
    user_id: int,
    req: UpdateModelsRequest,
    admin: User = Depends(_require_admin),
):
    """Update allowed models for a user."""
    from app.db.mariadb import fetch_one
    user = await asyncio.to_thread(
        fetch_one, "SELECT id, role, email FROM users WHERE id = %s", (user_id,)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["role"] == "admin":
        raise HTTPException(status_code=400, detail="Cannot modify admin model access")

    valid = {m.strip() for m in _ALL_MODELS.split(",")}
    for m in req.allowed_models:
        if m not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid model: {m}")

    await _db_execute(
        "UPDATE users SET allowed_models = %s WHERE id = %s",
        (",".join(req.allowed_models), user_id),
    )

    logger.info("admin_update_models", target=user["email"], models=req.allowed_models, by=admin.email)
    return {"ok": True, "email": user["email"], "allowed_models": req.allowed_models}
