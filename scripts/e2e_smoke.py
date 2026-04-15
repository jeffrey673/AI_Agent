"""End-to-end smoke test — dev (3001) only.

Goal: verify that after the concurrency/pool/multiworker changes, the real
user flow still works — chat page loads, a question streams back, the
response renders, and no console errors pop up.

Auth is bypassed by pre-setting a JWT cookie (same approach as loadtest.py)
so we don't need a real password.

Usage (from project root):
    python scripts/e2e_smoke.py

NEVER target prod (3000). Always dev (3001).
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import jwt
from playwright.async_api import async_playwright

from app.config import get_settings

BASE = "http://127.0.0.1:3001"
_ALGO = "HS256"
_SHOT_DIR = os.path.join(_ROOT, "logs", "e2e_shots")
os.makedirs(_SHOT_DIR, exist_ok=True)


def _build_admin_token() -> str:
    s = get_settings()
    payload = {
        "user_id": 1,
        "email": "jeffrey@skin1004korea.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=2),
        "brand_filter": "",
        "role": "admin",
    }
    return jwt.encode(payload, s.jwt_secret_key, algorithm=_ALGO)


async def run():
    token = _build_admin_token()
    errors: list[str] = []
    results: dict = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            await context.add_cookies([{
                "name": "token",
                "value": token,
                "url": BASE,
                "httpOnly": True,
            }])

            page = await context.new_page()
            page.on("console", lambda msg: errors.append(f"console {msg.type}: {msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

            # 1) Chat page loads
            print("[1] navigating to /")
            t0 = asyncio.get_event_loop().time()
            resp = await page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
            results["nav_status"] = resp.status if resp else None
            results["nav_ms"] = int((asyncio.get_event_loop().time() - t0) * 1000)
            print(f"    status={results['nav_status']} in {results['nav_ms']}ms")

            # 2) Welcome screen / chat UI present
            print("[2] waiting for chat UI")
            await page.wait_for_selector("#chat-input", timeout=15000)
            await page.wait_for_selector("#btn-system-status", timeout=5000)
            await page.screenshot(path=os.path.join(_SHOT_DIR, "01_chat_loaded.png"), full_page=True)
            print("    chat UI ready")

            # 3) /api/auth/me completed (sidebar shows user name)
            user_name = await page.evaluate("document.getElementById('user-name')?.textContent || ''")
            results["user_name"] = user_name.strip()
            print(f"    user-name='{results['user_name']}'")

            # 4) Type and send a simple question
            print("[3] sending question")
            q = "안녕하세요"
            await page.fill("#chat-input", q)
            send_t0 = asyncio.get_event_loop().time()
            await page.click("#btn-send")

            # 5) Wait for assistant response bubble to appear
            print("[4] waiting for assistant response")
            await page.wait_for_selector(".message.message-assistant", timeout=60000)

            # 6) Wait for streaming to finish — detect when content stops changing for 2s
            last_len = 0
            stable_since = None
            deadline = asyncio.get_event_loop().time() + 90
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.5)
                cur = await page.evaluate(
                    "Array.from(document.querySelectorAll('.message.message-assistant .message-content')).pop()?.innerText.length || 0"
                )
                if cur > 0 and cur == last_len:
                    stable_since = stable_since or asyncio.get_event_loop().time()
                    if asyncio.get_event_loop().time() - stable_since > 2.0:
                        break
                else:
                    stable_since = None
                    last_len = cur
            results["reply_chars"] = last_len
            results["reply_ms"] = int((asyncio.get_event_loop().time() - send_t0) * 1000)
            print(f"    reply: {last_len} chars in {results['reply_ms']}ms")
            await page.screenshot(path=os.path.join(_SHOT_DIR, "02_reply.png"), full_page=True)

            # 7) Open Knowledge Wiki drawer (admin only)
            print("[5a] opening Knowledge Wiki drawer")
            try:
                await page.wait_for_selector("#btn-wiki", timeout=3000, state="visible")
                await page.click("#btn-wiki")
                await page.wait_for_selector("#skin-wiki-drawer.open", timeout=5000)
                await page.wait_for_selector(".wiki-domain", timeout=5000)
                wiki_domains = await page.evaluate("document.querySelectorAll('.wiki-domain').length")
                results["wiki_domains"] = wiki_domains
                print(f"    wiki domains rendered: {wiki_domains}")
                await page.screenshot(path=os.path.join(_SHOT_DIR, "04_wiki_drawer.png"), full_page=True)
                # Close drawer
                await page.click("#wiki-drawer-close")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"    wiki drawer skipped: {e}")
                results["wiki_domains"] = 0

            # 8) Open System Status drawer and verify icons render
            print("[5b] opening System Status drawer")
            await page.click("#btn-system-status")
            await page.wait_for_selector("#skin-status-drawer.open", timeout=5000)
            # Count SVG icons rendered inside the drawer
            icon_count = await page.evaluate(
                "document.querySelectorAll('#skin-status-drawer .status-icon svg').length"
            )
            total_items = await page.evaluate(
                "document.querySelectorAll('#skin-status-drawer .status-item').length"
            )
            results["status_icons"] = icon_count
            results["status_items"] = total_items
            print(f"    svg icons: {icon_count}/{total_items}")
            await page.screenshot(path=os.path.join(_SHOT_DIR, "03_system_status.png"), full_page=True)

            await context.close()
        finally:
            await browser.close()

    print("\n=== RESULT ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
    if errors:
        print(f"\n{len(errors)} console/page errors:")
        for e in errors[:20]:
            print(f"  - {e}")
    else:
        print("\nno console/page errors")
    print(f"\nscreenshots: {_SHOT_DIR}")

    ok = (
        results.get("nav_status") in (200, 302, None)  # index may 200 directly after redirect
        and results.get("reply_chars", 0) > 5
        and results.get("status_icons", 0) >= 15
        and len(errors) == 0
    )
    print(f"\n{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
