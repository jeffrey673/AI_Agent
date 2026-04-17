"""Drive 500 eval questions through the real chat UI, capture Q/A to eval_qa.

Login: hits /api/auth/signin via page.request to mint the JWT cookie, then
navigates to chat.html — faster and less flaky than driving the login form.

Per question: type → click send → wait until the typing indicator disappears
and the last assistant bubble has non-empty data-raw. Capture:
  answer (markdown), response_time_ms, conversation_id (from URL or global),
  message_id (best-effort by querying DB for latest assistant message).

Usage:
    python tests/eval/playwright_runner.py tests/eval/questions_20260417.jsonl
    python tests/eval/playwright_runner.py tests/eval/questions_smoke.jsonl --smoke

Env (via .env.eval — git-ignored):
    JEFFREY_PASSWORD=<real password>
Optional:
    EVAL_BASE_URL (default http://127.0.0.1:3001)
    EVAL_DEPT (default: 임재필의 AD department)
    EVAL_NAME (default: 임재필)
    EVAL_THROTTLE_S (default: 3)
    EVAL_Q_TIMEOUT_S (default: 90)
    EVAL_HEADLESS (default: 1)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

_PROJ_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright  # noqa: E402

from app.db.mariadb import execute, execute_lastid, fetch_one  # noqa: E402


DEFAULT_DEPT = (
    "Craver_Accounts > Users > Brand Division > Operations Dept > "
    "Data Business > 데이터분석"
)
DEFAULT_NAME = "임재필"
DEFAULT_BASE = "http://127.0.0.1:3001"


def _signin(page_ctx, base_url: str, department: str, name: str, password: str) -> None:
    """POST to /api/auth/signin so the cookie is minted on the context."""
    resp = page_ctx.request.post(
        f"{base_url}/api/auth/signin",
        data={"department": department, "name": name, "password": password},
        headers={"Content-Type": "application/json"},
    )
    if not resp.ok:
        body = resp.text()[:500]
        raise RuntimeError(f"signin failed {resp.status}: {body}")


def _wait_answer_done(page: Page, timeout_ms: int) -> str:
    """Wait until streaming finishes.

    The chat frontend signals completion by REMOVING the `stop-mode` class
    from `#btn-send` (see chat.js:_resetSendBtn). The `.typing-indicator`
    is NOT a good proxy — it disappears on the first streamed token, not at
    stream end, so waiting for its detach returns ~2s early with an empty
    bubble.
    """
    # 1. Wait for send to enter stop mode (confirms a stream started)
    try:
        page.wait_for_function(
            "() => document.getElementById('btn-send')?.classList.contains('stop-mode')",
            timeout=10000,
        )
    except PWTimeout:
        # No stream started — maybe error or throttled; fall through and
        # report whatever bubble text exists.
        pass

    # 2. Wait for stop-mode to clear (stream finished, success or error)
    page.wait_for_function(
        "() => !document.getElementById('btn-send')?.classList.contains('stop-mode')",
        timeout=timeout_ms,
    )

    # 3. Small settle delay for contentEl.dataset.raw to be written
    page.wait_for_timeout(200)

    raw = page.evaluate(
        """() => {
            const els = document.querySelectorAll('.message-assistant .message-content');
            if (!els.length) return '';
            const last = els[els.length - 1];
            return last.getAttribute('data-raw') || last.innerText || '';
        }"""
    )
    return raw or ""


def _current_convo_id(page: Page) -> str | None:
    """The app keeps currentConvoId as an IIFE closure var; best-effort DOM probe."""
    # Try URL query / path first (if the app mirrors it)
    url = page.url
    m = re.search(r"[?&]convo=([0-9a-f-]{36})", url)
    if m:
        return m.group(1)
    # Fallback: ask the page directly via a getter we inject
    try:
        return page.evaluate("() => window.__currentConvoId || null")
    except Exception:
        return None


def _latest_assistant_message_id(conversation_id: str | None) -> int | None:
    if not conversation_id:
        return None
    row = fetch_one(
        "SELECT id FROM messages WHERE conversation_id = %s AND role = 'assistant' "
        "ORDER BY id DESC LIMIT 1",
        (conversation_id,),
    )
    return int(row["id"]) if row else None


def _parse_route_from_answer(answer: str) -> str | None:
    """Heuristic: route is commonly noted in the answer footer, e.g.
    'AI 생성 답변', '분석 기준: ... 내부 데이터 + Google 검색', or table markers."""
    if not answer:
        return None
    a = answer[-600:]
    if "분석 기준: SKIN1004 내부 데이터 + Google" in a:
        return "multi"
    if "내부 데이터 + Google 검색" in a or "외부 맥락" in a:
        return "multi"
    if re.search(r"📊|\| ---+ \|", answer):
        return "bigquery"
    if "AI 생성 답변" in a:
        return "direct"
    if "Notion" in a or "노션" in a[-200:]:
        return "notion"
    return None


def run(questions_path: Path, smoke: bool) -> int:
    load_dotenv(".env.eval")
    password = os.environ.get("JEFFREY_PASSWORD", "")
    if not password:
        print("ERROR: JEFFREY_PASSWORD missing. Put it in .env.eval.", file=sys.stderr)
        return 2

    base_url = os.environ.get("EVAL_BASE_URL", DEFAULT_BASE)
    dept = os.environ.get("EVAL_DEPT", DEFAULT_DEPT)
    name = os.environ.get("EVAL_NAME", DEFAULT_NAME)
    throttle_s = float(os.environ.get("EVAL_THROTTLE_S", "3"))
    q_timeout_ms = int(float(os.environ.get("EVAL_Q_TIMEOUT_S", "90")) * 1000)
    headless = os.environ.get("EVAL_HEADLESS", "1") not in ("0", "false", "no")

    rows = [
        json.loads(ln)
        for ln in questions_path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    if smoke:
        rows = rows[:5]
    if not rows:
        print("no questions loaded", file=sys.stderr)
        return 2

    run_id = execute_lastid(
        "INSERT INTO eval_runs (started_at, total, notes) VALUES (%s, %s, %s)",
        (datetime.utcnow(), len(rows), f"questions_file={questions_path.name} smoke={smoke}"),
    )
    print(f"run_id={run_id} total={len(rows)}  base={base_url}  headless={headless}", flush=True)

    fail_count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context()
        _signin(ctx, base_url, dept, name, password)
        page = ctx.new_page()
        page.goto(f"{base_url}/frontend/chat.html", wait_until="domcontentloaded")
        page.wait_for_selector("#chat-input", timeout=10000)

        for i, r in enumerate(rows, 1):
            q = r["question"]
            team = r.get("team", "unknown")
            source = r.get("source", "synthetic")
            t0 = time.time()
            try:
                page.fill("#chat-input", q)
                page.click("#btn-send")
                answer = _wait_answer_done(page, q_timeout_ms)
                elapsed_ms = int((time.time() - t0) * 1000)
                convo_id = _current_convo_id(page)
                msg_id = _latest_assistant_message_id(convo_id)
                route = _parse_route_from_answer(answer)
                execute(
                    "INSERT INTO eval_qa (run_id, team, question, answer, route, "
                    "response_time_ms, conversation_id, message_id, source) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (run_id, team, q, answer, route, elapsed_ms,
                     convo_id, msg_id, source),
                )
                execute("UPDATE eval_runs SET done = %s WHERE id = %s", (i, run_id))
                if i % 10 == 0 or smoke:
                    print(f"  [{i}/{len(rows)}] {team} {elapsed_ms}ms route={route}", flush=True)
            except Exception as e:
                fail_count += 1
                elapsed_ms = int((time.time() - t0) * 1000)
                print(f"  [{i}/{len(rows)}] {team} FAIL after {elapsed_ms}ms: {e}", flush=True)
                execute(
                    "INSERT INTO eval_qa (run_id, team, question, answer, source, "
                    "response_time_ms) VALUES (%s, %s, %s, %s, %s, %s)",
                    (run_id, team, q, f"[ERROR] {e}", source, elapsed_ms),
                )
                execute("UPDATE eval_runs SET done = %s WHERE id = %s", (i, run_id))
                # If login/cookie died, try to rehydrate once
                if "401" in str(e) or "Unauthorized" in str(e):
                    _signin(ctx, base_url, dept, name, password)
                    page.goto(f"{base_url}/frontend/chat.html", wait_until="domcontentloaded")
            time.sleep(throttle_s)

        browser.close()

    execute(
        "UPDATE eval_runs SET finished_at = %s, notes = CONCAT(COALESCE(notes,''), %s) WHERE id = %s",
        (datetime.utcnow(), f" | failed={fail_count}", run_id),
    )
    print(f"DONE. run_id={run_id} failed={fail_count}/{len(rows)}", flush=True)
    return 0 if fail_count < len(rows) // 2 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("questions", type=Path)
    ap.add_argument("--smoke", action="store_true", help="Only run first 5 questions")
    args = ap.parse_args()
    if not args.questions.exists():
        print(f"questions file not found: {args.questions}", file=sys.stderr)
        return 2
    return run(args.questions, smoke=args.smoke)


if __name__ == "__main__":
    sys.exit(main())
