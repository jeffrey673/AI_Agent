"""SKIN1004 Enterprise AI - FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.middleware import setup_middleware
from app.api.routes import router
from app.config import get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(ensure_ascii=False),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "application_started",
            host=settings.host,
            port=settings.port,
            project=settings.gcp_project_id,
        )
        yield
        logger.info("application_shutdown")

    app = FastAPI(
        title="SKIN1004 Enterprise AI",
        description="Text-to-SQL + Agentic RAG Hybrid AI System",
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Setup middleware (CORS, logging)
    setup_middleware(app)

    # Serve static files (charts, etc.)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Include API routes
    app.include_router(router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
