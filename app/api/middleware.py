"""Middleware for CORS, authentication, and request logging."""

import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the FastAPI app.

    Args:
        app: The FastAPI application instance.
    """
    # CORS - allow Open WebUI and local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Open WebUI needs this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs request/response details."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Log request
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)

            # Log response
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "request_completed",
                request_id=request_id,
                status_code=response.status_code,
                latency_ms=elapsed_ms,
            )

            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Latency-Ms"] = str(elapsed_ms)

            return response

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "request_failed",
                request_id=request_id,
                error=str(e),
                latency_ms=elapsed_ms,
            )
            raise
