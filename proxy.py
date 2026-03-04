"""
SKIN1004 AI — Reverse Proxy for Open WebUI Customization
=========================================================
aiohttp-based reverse proxy that sits in front of Open WebUI (port 8080)
and injects custom CSS/JS into HTML responses.

Architecture:
  Browser → proxy.py (:3000) → Open WebUI (:8080)
                              → FastAPI AI backend (:8100, separate)

Features:
  - HTML injection: custom.css + loader.js into </head>
  - WebSocket transparent proxy (for Open WebUI chat)
  - /skin/static/* served directly from app/static/
  - Cache-Control: no-cache for HTML responses
"""

import asyncio
import logging
import time
from pathlib import Path

import aiohttp
from aiohttp import web, WSMsgType

# ── Config ──────────────────────────────────────────────
PROXY_PORT = 3000
UPSTREAM = "http://localhost:8080"
STATIC_DIR = Path(__file__).parent / "app" / "static"
VER = int(time.time())  # cache-buster, changes on proxy restart

INJECT_SNIPPET = (
    f'<link rel="stylesheet" href="/skin/static/custom.css?v={VER}">\n'
    f'<script src="/skin/static/loader.js?v={VER}" defer></script>\n'
    '</head>'
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [proxy] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("proxy")

# ── Shared HTTP session ─────────────────────────────────
_session: aiohttp.ClientSession | None = None


async def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120),
            auto_decompress=True,
        )
    return _session


# ── Static file handler (/skin/static/*) ────────────────
async def static_handler(request: web.Request) -> web.StreamResponse:
    """Serve files from app/static/ under /skin/static/ prefix."""
    rel = request.match_info.get("path", "")
    file_path = STATIC_DIR / rel
    if not file_path.is_file() or not file_path.resolve().is_relative_to(STATIC_DIR.resolve()):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(file_path)


# ── WebSocket proxy ─────────────────────────────────────
async def ws_proxy(request: web.Request) -> web.WebSocketResponse:
    """Bidirectional WebSocket proxy to upstream Open WebUI."""
    ws_server = web.WebSocketResponse()
    await ws_server.prepare(request)

    upstream_url = f"ws://localhost:8080{request.path_qs}"
    session = await get_session()

    try:
        async with session.ws_connect(upstream_url) as ws_client:
            async def forward(src, dst, label):
                async for msg in src:
                    if msg.type == WSMsgType.TEXT:
                        await dst.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await dst.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                        break
                    elif msg.type == WSMsgType.ERROR:
                        break

            await asyncio.gather(
                forward(ws_server, ws_client, "client→upstream"),
                forward(ws_client, ws_server, "upstream→client"),
            )
    except Exception as e:
        log.warning("WebSocket proxy error: %s", e)
    finally:
        if not ws_server.closed:
            await ws_server.close()

    return ws_server


# ── HTTP proxy handler ──────────────────────────────────
def _forward_headers(request: web.Request) -> dict:
    """Build headers to forward to upstream, excluding hop-by-hop."""
    skip = {"host", "connection", "upgrade", "transfer-encoding",
            "content-encoding", "accept-encoding"}
    headers = {}
    for k, v in request.headers.items():
        if k.lower() not in skip:
            headers[k] = v
    headers["Host"] = "localhost:8080"
    headers["Accept-Encoding"] = "identity"  # no compression from upstream
    return headers


async def proxy_handler(request: web.Request) -> web.StreamResponse:
    """Proxy HTTP requests to upstream Open WebUI, injecting CSS/JS into HTML."""
    # WebSocket upgrade
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await ws_proxy(request)

    session = await get_session()
    upstream_url = f"{UPSTREAM}{request.path_qs}"

    try:
        async with session.request(
            method=request.method,
            url=upstream_url,
            headers=_forward_headers(request),
            data=await request.read(),
            allow_redirects=False,
        ) as resp:
            body = await resp.read()

            # Build response headers (skip hop-by-hop)
            skip = {"transfer-encoding", "content-encoding", "content-length", "connection"}
            resp_headers = {}
            for k, v in resp.headers.items():
                if k.lower() not in skip:
                    resp_headers[k] = v

            content_type = resp.headers.get("Content-Type", "")

            # Inject into HTML responses
            if "text/html" in content_type:
                # Decompress if needed (auto_decompress=False)
                try:
                    text = body.decode("utf-8")
                except UnicodeDecodeError:
                    text = body.decode("latin-1")

                if "</head>" in text:
                    text = text.replace("</head>", INJECT_SNIPPET, 1)

                body = text.encode("utf-8")

                # Force no-cache for HTML
                resp_headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                resp_headers["Pragma"] = "no-cache"
                resp_headers["Expires"] = "0"

            resp_headers["Content-Length"] = str(len(body))

            return web.Response(
                body=body,
                status=resp.status,
                headers=resp_headers,
            )

    except aiohttp.ClientError as e:
        log.error("Upstream error: %s", e)
        return web.Response(
            status=502,
            text=f"Proxy error: cannot reach Open WebUI at {UPSTREAM}\n{e}",
        )


# ── App setup ───────────────────────────────────────────
async def on_shutdown(app):
    global _session
    if _session and not _session.closed:
        await _session.close()


def create_app() -> web.Application:
    app = web.Application()

    # Static files: /skin/static/*
    app.router.add_get("/skin/static/{path:.*}", static_handler)

    # Everything else → upstream proxy
    app.router.add_route("*", "/{path:.*}", proxy_handler)

    app.on_shutdown.append(on_shutdown)
    return app


if __name__ == "__main__":
    log.info("Starting reverse proxy on port %d → upstream %s", PROXY_PORT, UPSTREAM)
    log.info("Static files: %s → /skin/static/", STATIC_DIR)
    web.run_app(create_app(), host="0.0.0.0", port=PROXY_PORT)
