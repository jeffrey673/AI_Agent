"""SQLAlchemy engine and session factory for SQLite."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        db_path = settings.sqlite_db_path
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def get_db():
    """FastAPI dependency that yields a DB session."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (idempotent) and run lightweight migrations."""
    import app.db.models  # noqa: F401 — ensure models are registered
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate(engine)


def _migrate(engine):
    """Add missing columns to existing tables (SQLite ALTER TABLE)."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "users" in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns("users")]
        if "allowed_models" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN allowed_models TEXT DEFAULT 'skin1004-Analysis'"
                ))
