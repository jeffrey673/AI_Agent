"""Visual check of the Knowledge Wiki drawer via Playwright.

Takes screenshots of each tab (map / recent / graph) so we can see exactly
what the admin sees. Dumps the rendered DOM summary so layout bugs show up.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import jwt
from playwright.async_api import async_playwright

from app.config import get_settings

BASE = "http://127.0.0.1:3001"
_SHOT_DIR = os.path.join(_ROOT, "logs", "e2e_shots")
os.makedirs(_SHOT_DIR, exist_ok=True)


def _build_admin_token() -> str:
    s = get_settings()
    return jwt.encode({
        "user_id": 1,
        "email": "jeffrey@skin1004korea.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "brand_filter": "",
        "role": "admin",
    }, s.jwt_secret_key, algorithm="HS256")


async def run():
    token = _build_admin_token()
    errors: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            await ctx.add_cookies([{
                "name": "token", "value": token, "url": BASE, "httpOnly": True,
            }])
            page = await ctx.new_page()
            page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

            # Load chat page
            await page.goto(BASE + "/", wait_until="domcontentloaded")
            await page.wait_for_selector("#chat-input", timeout=10000)
            await page.wait_for_timeout(1500)  # let me-refresh complete

            # Check button visibility
            btn_visible = await page.evaluate(
                "(function(){var b=document.getElementById('btn-wiki'); if(!b) return 'MISSING'; var r=b.getBoundingClientRect(); return {visible: r.width>0 && r.height>0, top: r.top, left: r.left, w: r.width, h: r.height};})()"
            )
            print("btn-wiki:", btn_visible)

            wrap_visible = await page.evaluate(
                "(function(){var w=document.getElementById('wiki-btn-wrap'); if(!w) return 'MISSING'; return {display: w.style.display, computed: getComputedStyle(w).display};})()"
            )
            print("wiki-btn-wrap:", wrap_visible)

            # Force click even if hidden (via evaluate)
            await page.evaluate("document.getElementById('btn-wiki').click()")
            await page.wait_for_timeout(2500)  # wait for fetch and render

            drawer_state = await page.evaluate(
                "(function(){var d=document.getElementById('skin-wiki-drawer'); var o=document.getElementById('skin-wiki-overlay'); return {drawer_class: d?d.className:'MISSING', overlay_class: o?o.className:'MISSING', drawer_w: d?d.getBoundingClientRect().width:0, drawer_h: d?d.getBoundingClientRect().height:0};})()"
            )
            print("drawer:", drawer_state)

            stats = await page.evaluate(
                "(function(){var s=document.getElementById('wiki-stats-bar'); return s?{html_len: s.innerHTML.length, text: s.innerText.slice(0,200)}:null;})()"
            )
            print("stats-bar:", stats)

            # Map tab content
            map_state = await page.evaluate(
                "(function(){var m=document.getElementById('wiki-tab-map'); if(!m) return 'MISSING'; return {active: m.classList.contains('active'), domains: document.querySelectorAll('.wiki-domain').length, inner_len: m.innerHTML.length, visible_rect: m.getBoundingClientRect()};})()"
            )
            print("map tab:", map_state)

            await page.screenshot(path=os.path.join(_SHOT_DIR, "wiki_01_map.png"), full_page=False)

            # Switch to recent tab
            await page.evaluate("Array.from(document.querySelectorAll('.wiki-tab')).find(t => t.getAttribute('data-tab')==='recent').click()")
            await page.wait_for_timeout(2000)
            recent_state = await page.evaluate(
                "(function(){var r=document.getElementById('wiki-tab-recent'); return {active: r.classList.contains('active'), cards: document.querySelectorAll('.wiki-card').length, inner_len: r.innerHTML.length};})()"
            )
            print("recent tab:", recent_state)
            await page.screenshot(path=os.path.join(_SHOT_DIR, "wiki_02_recent.png"), full_page=False)

            # Switch to graph tab
            await page.evaluate("Array.from(document.querySelectorAll('.wiki-tab')).find(t => t.getAttribute('data-tab')==='graph').click()")
            await page.wait_for_timeout(2000)
            graph_state = await page.evaluate(
                "(function(){var g=document.getElementById('wiki-tab-graph'); return {active: g.classList.contains('active'), rows: document.querySelectorAll('.wiki-graph-table tr').length, inner_len: g.innerHTML.length};})()"
            )
            print("graph tab:", graph_state)
            await page.screenshot(path=os.path.join(_SHOT_DIR, "wiki_03_graph.png"), full_page=False)

            # Also grab the raw HTML of drawer body for debugging
            drawer_html = await page.evaluate(
                "document.getElementById('skin-wiki-drawer').outerHTML.slice(0, 1000)"
            )
            print("\ndrawer html head:", drawer_html)

            await ctx.close()
        finally:
            await browser.close()

    print("\nerrors:", errors if errors else "none")
    print(f"shots: {_SHOT_DIR}")


if __name__ == "__main__":
    asyncio.run(run())
