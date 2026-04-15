"""Full visual check of the Knowledge Wiki drawer (all 5 tabs + entity modal)."""

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


def _tok():
    s = get_settings()
    return jwt.encode({"user_id": 1, "email": "jeffrey@skin1004korea.com",
                       "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                       "brand_filter": "", "role": "admin"},
                      s.jwt_secret_key, algorithm="HS256")


async def run():
    token = _tok()
    errors: list[str] = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        try:
            c = await b.new_context(viewport={"width": 1440, "height": 900})
            await c.add_cookies([{"name": "token", "value": token, "url": BASE, "httpOnly": True}])
            page = await c.new_page()
            page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

            await page.goto(BASE + "/", wait_until="domcontentloaded")
            await page.wait_for_selector("#chat-input", timeout=10000)
            await page.wait_for_timeout(1500)
            await page.evaluate("document.getElementById('btn-wiki').click()")
            await page.wait_for_selector("#skin-wiki-drawer.open", timeout=5000)
            await page.wait_for_timeout(1500)

            async def click_tab(name, wait_ms=2500):
                await page.evaluate(
                    f"Array.from(document.querySelectorAll('.wiki-tab')).find(t => t.getAttribute('data-tab')==='{name}').click()"
                )
                await page.wait_for_timeout(wait_ms)

            # 1) Map
            state = await page.evaluate("document.querySelectorAll('.wiki-domain').length")
            print(f"map domains: {state}")
            await page.screenshot(path=os.path.join(_SHOT_DIR, "full_01_map.png"))

            # 2) Insights
            await click_tab("insights", 3000)
            ins = await page.evaluate("(function(){return {"
                "sections: document.querySelectorAll('.insight-section').length,"
                "gods: document.querySelectorAll('.insight-list li').length,"
                "communities: document.querySelectorAll('.insight-community').length"
                "};})()")
            print(f"insights: {ins}")
            await page.screenshot(path=os.path.join(_SHOT_DIR, "full_02_insights.png"), full_page=True)

            # 3) Reports (now with conflicts section visible only if any)
            await click_tab("reports", 2500)
            rep = await page.evaluate("(function(){return {"
                "needs: document.querySelectorAll('.wiki-reports-needs').length,"
                "resolved: document.querySelectorAll('.wiki-reports-resolved').length,"
                "conflicts: document.querySelectorAll('.wiki-card-conflict').length,"
                "cards: document.querySelectorAll('.wiki-card-report').length"
                "};})()")
            print(f"reports: {rep}")
            await page.screenshot(path=os.path.join(_SHOT_DIR, "full_03_reports.png"))

            # 4) Graph
            await click_tab("graph", 3500)
            gr = await page.evaluate("(function(){var v=document.getElementById('wiki-graph-visual'); return {"
                "has_visual: !!v,"
                "rows: document.querySelectorAll('.wiki-graph-table tr').length,"
                "canvas: document.querySelectorAll('canvas').length"
                "};})()")
            print(f"graph: {gr}")
            await page.screenshot(path=os.path.join(_SHOT_DIR, "full_04_graph.png"))

            # 5) Entity modal — pick a known entity
            await click_tab("map", 1500)
            await page.evaluate("document.querySelector('.wiki-domain').setAttribute('open','')")
            await page.wait_for_timeout(400)
            # Click first entity row
            await page.evaluate("var r=document.querySelector('.wiki-entity-row'); if (r) r.click();")
            await page.wait_for_selector("#wiki-entity-modal.open", timeout=5000)
            await page.wait_for_timeout(2000)
            modal = await page.evaluate("(function(){return {"
                "open: document.getElementById('wiki-entity-modal').className,"
                "content: document.getElementById('wiki-entity-modal-content').innerText.slice(0,200)"
                "};})()")
            print(f"entity modal: {modal}")
            await page.screenshot(path=os.path.join(_SHOT_DIR, "full_05_entity_modal.png"))

            await c.close()
        finally:
            await b.close()

    print(f"\nerrors: {errors if errors else 'none'}")


if __name__ == "__main__":
    asyncio.run(run())
