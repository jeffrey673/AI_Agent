"""Visual verification of the Knowledge Wiki reports tab."""

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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            await ctx.add_cookies([{"name": "token", "value": token, "url": BASE, "httpOnly": True}])
            page = await ctx.new_page()
            await page.goto(BASE + "/", wait_until="domcontentloaded")
            await page.wait_for_selector("#chat-input", timeout=10000)
            await page.wait_for_timeout(1500)
            await page.evaluate("document.getElementById('btn-wiki').click()")
            await page.wait_for_selector("#skin-wiki-drawer.open", timeout=5000)
            await page.wait_for_timeout(1500)

            # Click reports tab
            await page.evaluate("Array.from(document.querySelectorAll('.wiki-tab')).find(t => t.getAttribute('data-tab')==='reports').click()")
            await page.wait_for_timeout(2000)

            state = await page.evaluate("(function(){"
                "var n=document.querySelectorAll('.wiki-reports-needs ~ .wiki-card-report, .wiki-card-report').length;"
                "var cards=document.querySelectorAll('.wiki-card-report').length;"
                "var needsTitle=document.querySelector('.wiki-reports-needs');"
                "var resolvedTitle=document.querySelector('.wiki-reports-resolved');"
                "return {cards: cards, needs_title: needsTitle?needsTitle.textContent:'MISSING', resolved_title: resolvedTitle?resolvedTitle.textContent:'MISSING'};"
                "})()")
            print("reports state:", state)

            await page.screenshot(path=os.path.join(_SHOT_DIR, "wiki_04_reports.png"), full_page=False)
            print(f"screenshot: wiki_04_reports.png")
            await ctx.close()
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
