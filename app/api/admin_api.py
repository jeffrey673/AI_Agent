"""Admin endpoints: user management, model access control."""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth_middleware import get_current_user
from app.db.database import get_db
from app.db.models import User

logger = structlog.get_logger(__name__)

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

_ALL_MODELS = "skin1004-Analysis,skin1004-Search"


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class UserListItem(BaseModel):
    id: str
    email: str
    name: str
    role: str
    allowed_models: list[str]


class UpdateModelsRequest(BaseModel):
    allowed_models: list[str]


class UpdateRoleRequest(BaseModel):
    role: str


@admin_router.get("/users")
async def list_users(
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> list[UserListItem]:
    """List all users with their model permissions."""
    users = db.query(User).order_by(User.created_at).all()
    result = []
    for u in users:
        if u.role == "admin":
            models = [m.strip() for m in _ALL_MODELS.split(",") if m.strip()]
        else:
            raw = getattr(u, "allowed_models", "") or ""
            models = [m.strip() for m in raw.split(",") if m.strip()]
            if not models:
                models = ["skin1004-Search"]
        result.append(UserListItem(
            id=u.id, email=u.email, name=u.name,
            role=u.role, allowed_models=models,
        ))
    return result


@admin_router.put("/users/{user_id}/models")
async def update_user_models(
    user_id: str,
    req: UpdateModelsRequest,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Update allowed models for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot modify admin model access")

    # Validate model names
    valid = {m.strip() for m in _ALL_MODELS.split(",")}
    for m in req.allowed_models:
        if m not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid model: {m}")

    user.allowed_models = ",".join(req.allowed_models)
    db.commit()

    logger.info("admin_update_models", target=user.email, models=req.allowed_models, by=admin.email)
    return {"ok": True, "email": user.email, "allowed_models": req.allowed_models}
