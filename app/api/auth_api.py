"""Authentication endpoints: signup, signin, me, logout."""

from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.auth_middleware import get_current_user
from app.config import get_settings
from app.db.database import get_db
from app.db.models import User

logger = structlog.get_logger(__name__)

auth_api_router = APIRouter(prefix="/api/auth", tags=["auth"])

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = 7


class SignupRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class SigninRequest(BaseModel):
    email: EmailStr
    password: str


_ALL_MODELS = "skin1004-Analysis,skin1004-Search"


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    allowed_models: list[str]


def _user_response(user: User) -> UserResponse:
    """Build UserResponse with resolved allowed_models."""
    if user.role == "admin":
        models = [m.strip() for m in _ALL_MODELS.split(",") if m.strip()]
    else:
        raw = getattr(user, "allowed_models", "") or ""
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if not models:
            models = ["skin1004-Search"]
    return UserResponse(
        id=user.id, email=user.email, name=user.name,
        role=user.role, allowed_models=models,
    )


def _create_token(user_id: str, email: str = "") -> str:
    settings = get_settings()
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def _set_cookie(response: Response, token: str):
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


@auth_api_router.post("/signup")
async def signup(req: SignupRequest, response: Response, db: Session = Depends(get_db)):
    """Create a new user account."""
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    user = User(
        email=req.email,
        name=req.name,
        password=_bcrypt.hashpw(req.password.encode(), _bcrypt.gensalt()).decode(),
    )
    # First user gets admin role
    count = db.query(User).count()
    if count == 0:
        user.role = "admin"
        user.allowed_models = _ALL_MODELS

    db.add(user)
    db.commit()
    db.refresh(user)

    token = _create_token(user.id, user.email)
    _set_cookie(response, token)

    logger.info("user_signup", email=req.email, role=user.role)
    return _user_response(user)


@auth_api_router.post("/signin")
async def signin(req: SigninRequest, response: Response, db: Session = Depends(get_db)):
    """Sign in with email and password."""
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not _bcrypt.checkpw(req.password.encode(), user.password.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token(user.id, user.email)
    _set_cookie(response, token)

    logger.info("user_signin", email=req.email)
    return _user_response(user)


@auth_api_router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return _user_response(user)


@auth_api_router.post("/logout")
async def logout(response: Response):
    """Clear auth cookie."""
    response.delete_cookie(key="token", path="/")
    return {"ok": True}
