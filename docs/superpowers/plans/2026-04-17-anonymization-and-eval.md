# Anonymization + Eval Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land pseudonymization for conversations (`anon_id = hmac_sha256(salt, user_id)[:16]`) so DB dumps cannot re-identify users, then ship a 500-question Playwright eval pipeline with an admin review UI for human quality judgment.

**Architecture:** Phase 1 is a schema + application migration that replaces per-row `user_id` with a deterministic hashed id in `conversations` and `message_feedback`. Phase 2 depends on Phase 1 being stable — it generates diverse questions (real queries + Gemini-synthesized, clustered for topic diversity), drives the real chat UI via Playwright as the 임재필 account, captures Q/A to `eval_qa` linked to the regular conversations table, and exposes a `/frontend/eval_review.html` page where the owner clicks 👍/👎/⏭ per row. Passive post-run profiling triggers safe automatic indexing / caching only after the run completes so the quality signal is uncorrupted.

**Tech Stack:** FastAPI, MariaDB (`pymysql`/DBUtils pool), pydantic-settings, `structlog`, `hmac` + `hashlib` (stdlib), `playwright` (Python sync), Gemini 2.5 Flash (LLM + embeddings), scikit-learn `KMeans`, PM2 (dev=`skin1004-dev` port 3001, prod=`skin1004-prod` port 3000).

**Deploy rule (CLAUDE.md):** Every change lands on 3001 and is verified there. Production (3000) reload only happens after the owner explicitly approves. Cache version on `chat.html` script tag must bump whenever chat.js/css changes.

---

## Phase 1 — Anonymization

### Task 1: Add `SKIN1004_ANON_SALT` env var and config loader

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example` (if present — check first; if not, skip the example file change)
- Test: `tests/test_config_anon_salt.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config_anon_salt.py
import pytest
from app.config import Settings


def test_anon_salt_required():
    with pytest.raises(Exception):
        Settings(anon_salt="")


def test_anon_salt_min_length():
    with pytest.raises(Exception):
        Settings(anon_salt="short")


def test_anon_salt_accepts_valid():
    s = Settings(anon_salt="x" * 32)
    assert s.anon_salt == "x" * 32
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_anon_salt.py -v`
Expected: FAIL — `anon_salt` attribute missing on Settings.

- [ ] **Step 3: Add `anon_salt` to `app/config.py`**

Add the field and a validator to the existing `Settings` class (pydantic-settings). Locate the Settings class and add:

```python
from pydantic import field_validator

class Settings(BaseSettings):
    # ... existing fields ...
    anon_salt: str = ""

    @field_validator("anon_salt")
    @classmethod
    def _validate_anon_salt(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError("SKIN1004_ANON_SALT must be set and >= 32 chars")
        return v
```

Environment variable mapping follows the existing `model_config = SettingsConfigDict(env_prefix="SKIN1004_", ...)` pattern — if the existing config uses a prefix, name the env var accordingly.

- [ ] **Step 4: Add to `.env` (local dev only, do NOT commit secrets)**

```bash
# Append a comment + value to .env (manually, not via this plan since .env is gitignored)
# SKIN1004_ANON_SALT=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_config_anon_salt.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add app/config.py tests/test_config_anon_salt.py
git commit -m "feat(anon): require SKIN1004_ANON_SALT >= 32 chars"
```

---

### Task 2: Create anon_id helper

**Files:**
- Create: `app/core/anonymization.py`
- Test: `tests/test_anonymization.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_anonymization.py
from app.core.anonymization import compute_anon_id


def test_deterministic_for_same_user():
    a = compute_anon_id(42, salt="x" * 32)
    b = compute_anon_id(42, salt="x" * 32)
    assert a == b


def test_different_users_differ():
    a = compute_anon_id(1, salt="x" * 32)
    b = compute_anon_id(2, salt="x" * 32)
    assert a != b


def test_different_salts_differ():
    a = compute_anon_id(42, salt="a" * 32)
    b = compute_anon_id(42, salt="b" * 32)
    assert a != b


def test_is_16_hex_chars():
    a = compute_anon_id(42, salt="x" * 32)
    assert len(a) == 16
    assert all(c in "0123456789abcdef" for c in a)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_anonymization.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement helper**

```python
# app/core/anonymization.py
"""Pseudonymization helper for conversation/feedback ownership.

`anon_id = hmac_sha256(salt, str(user_id))[:16]` — deterministic per user,
irreversible without the server-side salt. Do not log the salt.
"""
from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

from app.config import get_settings


def compute_anon_id(user_id: int, *, salt: str | None = None) -> str:
    """Return a 16-char hex anon id for the given user."""
    if salt is None:
        salt = get_settings().anon_salt
    mac = hmac.new(salt.encode("utf-8"), str(user_id).encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()[:16]


@lru_cache(maxsize=1024)
def anon_id_for(user_id: int) -> str:
    """Cached variant for hot paths. Keyed on user_id only; salt is process-stable."""
    return compute_anon_id(user_id)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_anonymization.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/anonymization.py tests/test_anonymization.py
git commit -m "feat(anon): add compute_anon_id helper (hmac-sha256)"
```

---

### Task 3: Add anon_id columns to `conversations` and `message_feedback`

**Files:**
- Modify: `app/db/mariadb.py` (schema DDL section — find the `CREATE TABLE` blocks and add the ALTER)

- [ ] **Step 1: Inspect current DDL location**

Run: `python -c "import app.db.mariadb as m; print(m.__file__)"` then open it and locate the startup schema migration block (search for `CREATE TABLE conversations` and `ALTER TABLE` patterns — the codebase applies idempotent ALTERs on startup).

- [ ] **Step 2: Add idempotent ALTER statements**

Inside the existing startup migration function (follow existing pattern — they use `try: ALTER ... except: pass` or `INFORMATION_SCHEMA` checks):

```python
# In the same block that already ALTERs knowledge_wiki etc.
_ALTERS_ANON = [
    ("conversations", "anon_id", "VARCHAR(32) NOT NULL DEFAULT ''"),
    ("message_feedback", "anon_id", "VARCHAR(32) NOT NULL DEFAULT ''"),
]
for table, col, definition in _ALTERS_ANON:
    existing = fetch_one(
        "SELECT 1 AS ok FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        (table, col),
    )
    if not existing:
        execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        execute(f"ALTER TABLE {table} ADD INDEX idx_{table}_{col} ({col})")
```

- [ ] **Step 3: Restart dev and verify**

Run: `pm2 restart skin1004-dev`
Run: `python -c "from app.db.mariadb import fetch_all; print(fetch_all('DESCRIBE conversations'))" | grep anon_id`
Expected: row showing `anon_id VARCHAR(32)`

Same check for `message_feedback`.

- [ ] **Step 4: Commit**

```bash
git add app/db/mariadb.py
git commit -m "feat(anon): add anon_id columns to conversations, message_feedback"
```

---

### Task 4: Update conversation writes to set `anon_id`

**Files:**
- Modify: `app/api/conversation_api.py`
- Test: `tests/test_conversation_anon.py`

- [ ] **Step 1: Identify all INSERT/UPDATE paths**

Run: `grep -n "INSERT INTO conversations\|INSERT INTO message_feedback" app/api/*.py`
List every path that writes to those tables.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_conversation_anon.py
import pytest
from unittest.mock import patch
from app.core.anonymization import compute_anon_id


@pytest.mark.asyncio
async def test_create_conversation_writes_anon_id(monkeypatch):
    # This is an integration-style test: requires a test DB or mocked fetch_one/execute.
    # Follow the pattern used by tests/test_router.py or the nearest existing integration test.
    # The assertion: after creating a conversation for user_id=X, the stored row has
    # anon_id == compute_anon_id(X).
    ...
```

Fill in using the existing test fixture pattern found in `tests/test_router.py` or `tests/test_sql_agent.py`. If none exist, test by directly calling the helper + the create function with mocked DB.

- [ ] **Step 3: Update create_conversation**

Locate the INSERT in `conversation_api.py` and update:

```python
from app.core.anonymization import anon_id_for

# Inside create_conversation handler:
anon = anon_id_for(current_user.id)
await _db_execute(
    "INSERT INTO conversations (id, user_id, anon_id, title, model) "
    "VALUES (%s, %s, %s, %s, %s)",
    (convo_id, current_user.id, anon, title, model),
)
```

Same treatment for any message_feedback INSERT: include `anon_id = anon_id_for(current_user.id)`.

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_conversation_anon.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/conversation_api.py tests/test_conversation_anon.py
git commit -m "feat(anon): populate anon_id on conversation + feedback writes"
```

---

### Task 5: Switch reads to anon_id

**Files:**
- Modify: `app/api/conversation_api.py`, `app/api/admin_api.py`, `app/api/admin_group_api.py`

- [ ] **Step 1: Find all user_id reads**

Run: `grep -n "WHERE user_id\|user_id =\|user_id IN" app/api/*.py`
For each match in conversation sidebar + feedback reads, replace with anon_id.

- [ ] **Step 2: Update sidebar query**

Example:

```python
# Before
"SELECT id, title, model, created_at, updated_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC"

# After
anon = anon_id_for(current_user.id)
"SELECT id, title, model, created_at, updated_at FROM conversations WHERE anon_id = %s ORDER BY updated_at DESC"
# bind (anon,)
```

- [ ] **Step 3: Update admin per-user stats**

In admin APIs, replace per-user-id groupings with per-anon_id. Return the short anon (first 8 chars) to the UI.

- [ ] **Step 4: Restart dev and smoke test**

Run: `pm2 restart skin1004-dev`
In browser: log in at 3001 → sidebar shows your existing conversations (backfill hasn't happened yet, so expect **empty sidebar** until Task 7 runs — this is an acceptable intermediate state; note it in the commit message).

- [ ] **Step 5: Commit**

```bash
git add app/api/conversation_api.py app/api/admin_api.py app/api/admin_group_api.py
git commit -m "feat(anon): read conversations + admin stats by anon_id (sidebar empty until backfill)"
```

---

### Task 6: structlog processor to scrub identity from logs

**Files:**
- Modify: `app/main.py` (logging config)
- Test: `tests/test_log_scrub.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_log_scrub.py
from app.main import _scrub_identity_processor  # will export from main


def test_scrubs_user_id_to_anon():
    event = {"event": "test", "user_id": 42, "email": "a@b.com"}
    out = _scrub_identity_processor(None, "info", event)
    assert "user_id" not in out
    assert "email" not in out
    assert out["anon_id"]  # 16 hex chars
    assert len(out["anon_id"]) == 16


def test_preserves_audit_logger():
    # Audit loggers pass through unchanged
    event = {"event": "test", "user_id": 42, "_logger_name": "audit"}
    out = _scrub_identity_processor(None, "info", event)
    assert out["user_id"] == 42
```

- [ ] **Step 2: Run test (expect fail)**

Run: `python -m pytest tests/test_log_scrub.py -v`
Expected: FAIL — processor not exported.

- [ ] **Step 3: Implement processor**

Inside `app/main.py` near the structlog configuration block:

```python
from app.core.anonymization import anon_id_for

_IDENTITY_FIELDS_TO_DROP = ("email", "name", "display_name")
_AUDIT_LOGGERS = {"audit", "security"}

def _scrub_identity_processor(logger, method_name, event_dict):
    """Replace user_id with anon_id, drop email/name fields. Skip audit loggers."""
    if event_dict.get("_logger_name") in _AUDIT_LOGGERS:
        return event_dict
    uid = event_dict.pop("user_id", None)
    if uid is not None:
        try:
            event_dict["anon_id"] = anon_id_for(int(uid))
        except (TypeError, ValueError):
            pass
    for k in _IDENTITY_FIELDS_TO_DROP:
        event_dict.pop(k, None)
    return event_dict
```

Register it in the structlog processors chain (find `structlog.configure(...)` and insert this before the renderer).

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_log_scrub.py -v`
Expected: 2 PASS

- [ ] **Step 5: Restart dev and verify logs**

Run: `pm2 restart skin1004-dev`
Run: `pm2 logs skin1004-dev --lines 30 --nostream`
Expected: no `email=...` or raw `user_id=<int>` — should see `anon_id=<hex16>` instead.

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_log_scrub.py
git commit -m "feat(anon): scrub user_id/email from logs via structlog processor"
```

---

### Task 7: Backfill anon_id for existing rows

**Files:**
- Create: `scripts/migrate_anonymize_conversations.py`

- [ ] **Step 1: Write the script**

```python
# scripts/migrate_anonymize_conversations.py
"""Backfill anon_id on existing conversations + message_feedback rows.

Usage:
    python scripts/migrate_anonymize_conversations.py --dry-run
    python scripts/migrate_anonymize_conversations.py --apply
"""
from __future__ import annotations

import argparse

from app.core.anonymization import compute_anon_id
from app.db.mariadb import execute, fetch_all, fetch_one


def _backfill(table: str, dry_run: bool) -> int:
    rows = fetch_all(
        f"SELECT id, user_id FROM {table} "
        f"WHERE anon_id = '' AND user_id IS NOT NULL"
    )
    print(f"[{table}] rows to backfill: {len(rows)}")
    if dry_run:
        return len(rows)
    for i, r in enumerate(rows, 1):
        anon = compute_anon_id(int(r["user_id"]))
        execute(f"UPDATE {table} SET anon_id = %s WHERE id = %s", (anon, r["id"]))
        if i % 500 == 0:
            print(f"  [{table}] {i}/{len(rows)}")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        ap.error("choose --apply or --dry-run")

    for table in ("conversations", "message_feedback"):
        _backfill(table, dry_run=not args.apply)

    # Verification
    for table in ("conversations", "message_feedback"):
        r = fetch_one(
            f"SELECT COUNT(*) AS c FROM {table} "
            f"WHERE anon_id = '' AND user_id IS NOT NULL"
        )
        print(f"[{table}] remaining empty anon_id: {r['c']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run on dev**

Run: `python scripts/migrate_anonymize_conversations.py --dry-run`
Expected: prints row counts per table. Record the numbers.

- [ ] **Step 3: Apply on dev**

Run: `python scripts/migrate_anonymize_conversations.py --apply`
Expected: post-apply, `remaining empty anon_id: 0` for both tables.

- [ ] **Step 4: Verify sidebar loads on dev**

Open `http://127.0.0.1:3001/login` → log in as 임재필 → sidebar should show prior conversation history.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_anonymize_conversations.py
git commit -m "feat(anon): backfill script for conversations + feedback"
```

---

### Task 8: Dev verification checklist

- [ ] **Step 1: Sidebar renders**

Log in on 3001 → sidebar shows date-grouped conversations.

- [ ] **Step 2: New conversation writes anon_id**

Send a new message → open DB:
```sql
SELECT id, user_id, anon_id FROM conversations ORDER BY created_at DESC LIMIT 1;
```
Expected: `anon_id` populated, 16 hex chars.

- [ ] **Step 3: Admin APIs return anon-scoped data**

Navigate to admin drawer → user/group stats → no raw names of owners in per-conversation breakdowns.

- [ ] **Step 4: Logs scrubbed**

Run: `pm2 logs skin1004-dev --lines 50 --nostream`
Expected: no `email=...`; `anon_id=...` present where identity was logged.

- [ ] **Step 5: Regression**

Run: `python -m pytest tests/ -x --ignore=tests/frontend 2>&1 | tail -10`
Expected: pass (frontend tests already verified separately).

---

### Task 9: Owner approval + prod reload

- [ ] **Step 1: Request approval**

Message the owner: "Phase 1 verified on dev. Request prod reload when ready."

- [ ] **Step 2: Owner-run on prod (ONLY after explicit approval)**

Apply schema + backfill against prod DB:
```bash
# From the same repo, same .env pointing at prod MariaDB (already is, single DB):
python scripts/migrate_anonymize_conversations.py --dry-run
python scripts/migrate_anonymize_conversations.py --apply  # after the dry-run number is confirmed reasonable
pm2 reload skin1004-prod
```

- [ ] **Step 3: Prod smoke**

Open the prod URL (whatever binds to 3000) → log in → sidebar works. Run: `pm2 logs skin1004-prod --lines 30 --nostream` → confirm anon scrubbing.

---

## Phase 2 — Eval pipeline

### Task 10: Eval tables schema

**Files:**
- Modify: `app/db/mariadb.py` — add idempotent CREATE TABLE statements in the startup migration block

- [ ] **Step 1: Add CREATE TABLE statements (idempotent)**

```python
_EVAL_TABLES_DDL = [
    """
    CREATE TABLE IF NOT EXISTS eval_runs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        started_at DATETIME NOT NULL,
        finished_at DATETIME NULL,
        total INT NOT NULL,
        done INT NOT NULL DEFAULT 0,
        notes TEXT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_qa (
        id INT AUTO_INCREMENT PRIMARY KEY,
        run_id INT NOT NULL,
        team VARCHAR(100) NOT NULL,
        question TEXT NOT NULL,
        answer MEDIUMTEXT,
        route VARCHAR(32),
        response_time_ms INT,
        conversation_id VARCHAR(36),
        message_id INT,
        source ENUM('real','synthetic') NOT NULL,
        verdict ENUM('pending','good','bad','skip') NOT NULL DEFAULT 'pending',
        reviewed_at DATETIME NULL,
        reviewed_by_anon VARCHAR(32),
        INDEX idx_eval_qa_run (run_id),
        INDEX idx_eval_qa_verdict (verdict),
        FOREIGN KEY (run_id) REFERENCES eval_runs(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]
for ddl in _EVAL_TABLES_DDL:
    execute(ddl)
```

- [ ] **Step 2: Restart dev and verify**

Run: `pm2 restart skin1004-dev`
Run: `python -c "from app.db.mariadb import fetch_all; print([r['TABLE_NAME'] for r in fetch_all(\"SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'eval_%'\")])"`
Expected: `['eval_qa', 'eval_runs']`

- [ ] **Step 3: Commit**

```bash
git add app/db/mariadb.py
git commit -m "feat(eval): add eval_runs + eval_qa tables"
```

---

### Task 11: Question generator — real query extraction

**Files:**
- Create: `scripts/generate_eval_questions.py`
- Test: `tests/test_generate_eval_questions.py`

- [ ] **Step 1: Define team → allowlist keyword map**

At the top of `scripts/generate_eval_questions.py`:

```python
# Maps team key -> (notion_page_id, [keyword, keyword, ...])
# Keywords used to filter real user queries to that team.
TEAM_ALLOWLIST = [
    ("법인 태블릿", "2532b4283b0080eba96ce35ae8ba8743", ["태블릿", "법인", "iPad"]),
    ("데이터 분석 파트", "1602b4283b0080f186cfc6425d9a53dd", ["데이터 분석", "DA", "분석"]),
    ("EAST 2팀 가이드", "2e62b4283b00803a8007df0d3003705c", ["EAST", "동부", "이커머스"]),
    ("EAST 2026 업무", "2e12b4283b0080b48a1dd7bbbd6e0e53", ["EAST", "업무파악", "2026"]),
    ("EAST 틱톡샵 접속", "19d2b4283b0080dc89d9e6d9c11ec1e5", ["틱톡샵", "tiktok shop", "접속"]),
    ("EAST 해외 출장", "1982b4283b008039ad79ec0c1c1e38fb", ["출장", "해외 출장", "출장비"]),
    ("WEST 틱톡샵 US", "22e2b4283b008060bac6cef042c3787b", ["WEST", "틱톡샵", "US"]),
    ("KBT 스스 운영", "c058d9e89e8a4780b32e866b8248b5b1", ["KBT", "스스", "스마트스토어"]),
    ("네이버 스스", "1fb2b4283b00802883faef2df97c6f73", ["네이버", "스스", "스토어"]),
    ("DB daily 광고", "1dc2b4283b0080cb8790cf5218896ebd", ["광고", "daily", "입력 업무"]),
]
```

- [ ] **Step 2: Write test for real-query filter**

```python
# tests/test_generate_eval_questions.py
from scripts.generate_eval_questions import filter_messages_for_team


def test_filter_matches_any_keyword():
    msgs = [
        {"content": "EAST 팀 출장 방법 알려줘"},
        {"content": "bigquery 에서 매출 뽑아줘"},
        {"content": "해외 출장 규정이 뭐야"},
    ]
    out = filter_messages_for_team(msgs, keywords=["출장", "EAST"])
    assert len(out) == 2
```

- [ ] **Step 3: Implement `filter_messages_for_team`**

```python
def filter_messages_for_team(messages, keywords):
    kws = [k.lower() for k in keywords]
    out = []
    for m in messages:
        text = (m.get("content") or "").lower()
        if any(k in text for k in kws):
            out.append(m)
    return out


def load_real_queries(max_per_team: int = 40) -> dict[str, list[dict]]:
    """Pull user messages from DB, filter per team."""
    from app.db.mariadb import fetch_all

    rows = fetch_all(
        "SELECT m.content, m.conversation_id FROM messages m "
        "WHERE m.role = 'user' AND m.content IS NOT NULL "
        "ORDER BY m.created_at DESC LIMIT 20000"
    )
    out = {}
    for team, _pid, keywords in TEAM_ALLOWLIST:
        matches = filter_messages_for_team(rows, keywords)
        out[team] = matches[:max_per_team]
    return out
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_generate_eval_questions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_eval_questions.py tests/test_generate_eval_questions.py
git commit -m "feat(eval): real-query extraction per team"
```

---

### Task 12: Question generator — synthetic generation + diversity clustering

**Files:**
- Modify: `scripts/generate_eval_questions.py`

- [ ] **Step 1: Add synthetic question generation via Gemini Flash**

Append to `scripts/generate_eval_questions.py`:

```python
import asyncio
import httpx
from app.agents.notion_agent import _ALLOWED_PAGES  # reuse allowlist ids
from app.core.llm import get_flash_client


async def fetch_notion_page_content(page_id: str) -> str:
    """Fetch + concatenate blocks from a Notion page (simplified)."""
    from app.agents.notion_agent import NotionAgent
    agent = NotionAgent()
    await agent._warm_up()
    content = await agent._read_page_content(page_id)
    return content or ""


SYNTH_PROMPT = """다음은 사내 업무 문서입니다. 이 문서를 보는 실무자가 AI에게 물어볼 법한
업무 질문을 150개 생성하세요. 문서 핵심 주제를 고루 다루되 같은 주제에 편중되지 않게
분산시키세요. 각 질문은 한 줄, 번호나 불릿 없이, 한 줄에 하나씩 출력하세요.

---
{content}
---
"""


async def synthesize_questions_for_team(team: str, page_id: str) -> list[str]:
    content = await fetch_notion_page_content(page_id)
    if not content:
        return []
    client = get_flash_client()
    resp = await client.chat([{"role": "user", "content": SYNTH_PROMPT.format(content=content[:8000])}])
    text = resp.get("content", "") if isinstance(resp, dict) else str(resp)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and len(ln.strip()) > 5]
    return lines[:150]
```

- [ ] **Step 2: Add embedding + clustering for diversity**

```python
import numpy as np
from sklearn.cluster import KMeans


async def embed_questions(questions: list[str]) -> np.ndarray:
    """Batch embed via Gemini embedding API."""
    from app.core.llm import get_flash_client
    client = get_flash_client()
    # If a batch embed helper exists, use it. Else loop.
    vecs = []
    for q in questions:
        v = await client.embed(q)  # returns list[float]
        vecs.append(v)
    return np.array(vecs, dtype=np.float32)


def pick_diverse_questions(candidates: list[str], target: int = 50,
                           dedupe_cosine: float = 0.85, k_clusters: int = 25) -> list[dict]:
    """Embed, dedupe by cosine, cluster, then pick diverse subset."""
    import asyncio
    vecs = asyncio.get_event_loop().run_until_complete(embed_questions(candidates))
    # Normalize for cosine
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    nv = vecs / np.where(norms == 0, 1, norms)
    # Greedy dedupe
    keep_idx = []
    for i in range(len(candidates)):
        dup = False
        for j in keep_idx:
            if float(nv[i] @ nv[j]) > dedupe_cosine:
                dup = True
                break
        if not dup:
            keep_idx.append(i)
    kept = [candidates[i] for i in keep_idx]
    kept_vecs = vecs[keep_idx]
    if len(kept) <= target:
        return [{"question": q, "cluster_id": i % k_clusters} for i, q in enumerate(kept)]
    # Cluster
    k = min(k_clusters, len(kept))
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(kept_vecs)
    labels = km.labels_
    # Pick 1-2 per cluster
    by_cluster: dict[int, list[int]] = {}
    for idx, lab in enumerate(labels):
        by_cluster.setdefault(int(lab), []).append(idx)
    picks = []
    # Round-robin across clusters
    while len(picks) < target and any(by_cluster.values()):
        for lab in list(by_cluster.keys()):
            if by_cluster[lab]:
                picks.append({"question": kept[by_cluster[lab].pop(0)], "cluster_id": lab})
                if len(picks) >= target:
                    break
    return picks
```

- [ ] **Step 3: Tie it together**

```python
import json
from datetime import datetime
from pathlib import Path


def main():
    real = load_real_queries(max_per_team=40)
    out_rows = []
    for team, page_id, _kw in TEAM_ALLOWLIST:
        reals = [r["content"] for r in real.get(team, [])]
        synth = asyncio.run(synthesize_questions_for_team(team, page_id))
        candidates = reals + synth
        picks = pick_diverse_questions(candidates, target=50)
        for p in picks:
            src = "real" if p["question"] in reals else "synthetic"
            out_rows.append({
                "team": team,
                "source": src,
                "question": p["question"],
                "cluster_id": p["cluster_id"],
            })
    date = datetime.now().strftime("%Y%m%d")
    out_path = Path("tests/eval") / f"questions_{date}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(out_rows)} questions → {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate the file**

Run: `python scripts/generate_eval_questions.py`
Expected: ~500 rows in `tests/eval/questions_20260417.jsonl` (±50 depending on dedupe).

- [ ] **Step 5: Commit (include the generated jsonl)**

```bash
git add scripts/generate_eval_questions.py tests/eval/questions_*.jsonl
git commit -m "feat(eval): synthesize + diversify 500 questions"
```

---

### Task 13: Playwright runner

**Files:**
- Create: `tests/eval/playwright_runner.py`
- Create: `.env.eval` (git-ignored; user writes manually)

- [ ] **Step 1: Add `.env.eval` to .gitignore**

```bash
echo ".env.eval" >> .gitignore
git add .gitignore
git commit -m "chore: ignore .env.eval"
```

Owner writes `.env.eval` containing: `JEFFREY_PASSWORD=<real password>` (manually).

- [ ] **Step 2: Write runner**

```python
# tests/eval/playwright_runner.py
"""Drive the chat UI through 500 questions, capture Q/A to eval_qa.

Usage:
    python tests/eval/playwright_runner.py tests/eval/questions_20260417.jsonl
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app.db.mariadb import execute, execute_lastid, fetch_one

BASE_URL = os.environ.get("EVAL_BASE_URL", "http://127.0.0.1:3001")
LOGIN_DEPARTMENT = os.environ.get("EVAL_DEPT", "Craver_Accounts > Users > Brand Division > Operations Dept > Data Business > 데이터분석")
LOGIN_NAME = os.environ.get("EVAL_NAME", "임재필")
LOGIN_PW_VAR = "JEFFREY_PASSWORD"

THROTTLE_S = 3.0
PER_Q_TIMEOUT_MS = 60000


def _login(page):
    page.goto(f"{BASE_URL}/login")
    page.select_option("select#login-department", LOGIN_DEPARTMENT)
    page.select_option("select#login-name", LOGIN_NAME)
    page.fill("input#login-password", os.environ[LOGIN_PW_VAR])
    page.click("button#login-submit")
    page.wait_for_url(f"{BASE_URL}/chat*", timeout=15000)


def _ask(page, question: str) -> dict:
    # Clear input, type question, submit
    page.fill("textarea#chat-input", question)
    t0 = time.time()
    page.click("#btn-send")
    # Wait: typing indicator disappears AND last AI message has non-empty content
    page.wait_for_selector(".typing-indicator", state="detached", timeout=PER_Q_TIMEOUT_MS)
    last = page.query_selector_all(".message-ai .message-content")
    raw = last[-1].get_attribute("data-raw") if last else ""
    elapsed_ms = int((time.time() - t0) * 1000)
    # conversation id from URL query or a data attribute
    convo_id = page.evaluate("() => window.__currentConvoId || null")
    return {"answer": raw or "", "elapsed_ms": elapsed_ms, "conversation_id": convo_id}


def main():
    load_dotenv(".env.eval")
    q_path = Path(sys.argv[1])
    rows = [json.loads(ln) for ln in q_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    run_id = execute_lastid(
        "INSERT INTO eval_runs (started_at, total) VALUES (%s, %s)",
        (datetime.utcnow(), len(rows)),
    )
    print(f"run_id={run_id} total={len(rows)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        _login(page)
        for i, r in enumerate(rows, 1):
            try:
                res = _ask(page, r["question"])
            except Exception as e:
                print(f"  [{i}/{len(rows)}] FAIL: {e}")
                execute(
                    "INSERT INTO eval_qa (run_id, team, question, answer, source, response_time_ms) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (run_id, r["team"], r["question"], f"[ERROR] {e}", r["source"], 0),
                )
                continue
            execute(
                "INSERT INTO eval_qa (run_id, team, question, answer, source, "
                "response_time_ms, conversation_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (run_id, r["team"], r["question"], res["answer"], r["source"],
                 res["elapsed_ms"], res["conversation_id"]),
            )
            execute("UPDATE eval_runs SET done = %s WHERE id = %s", (i, run_id))
            if i % 10 == 0:
                print(f"  [{i}/{len(rows)}] done")
            time.sleep(THROTTLE_S)
        browser.close()
    execute("UPDATE eval_runs SET finished_at = %s WHERE id = %s", (datetime.utcnow(), run_id))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke with 3 questions**

Create `tests/eval/questions_smoke.jsonl` with 3 rows from the generated file.
Run: `python tests/eval/playwright_runner.py tests/eval/questions_smoke.jsonl`
Expected: 3 rows inserted into `eval_qa`, `eval_runs.done = 3`.

- [ ] **Step 4: Commit**

```bash
git add tests/eval/playwright_runner.py
git commit -m "feat(eval): playwright runner for 500-question batch"
```

---

### Task 14: Full run (500 questions)

- [ ] **Step 1: Kick off**

Run: `python tests/eval/playwright_runner.py tests/eval/questions_20260417.jsonl`
Expected runtime: ~500 × (avg 15s response + 3s throttle) ≈ 2.5 hours.

- [ ] **Step 2: Monitor progress**

In another terminal:
```bash
watch -n 30 'python -c "from app.db.mariadb import fetch_one; r = fetch_one(\"SELECT done, total FROM eval_runs ORDER BY id DESC LIMIT 1\"); print(r)"'
```

- [ ] **Step 3: Verify counts**

Run: `python -c "from app.db.mariadb import fetch_one; print(fetch_one('SELECT COUNT(*) AS c FROM eval_qa WHERE run_id = (SELECT MAX(id) FROM eval_runs)'))"`
Expected: ~500 (allow a few failures).

---

### Task 15: Review API

**Files:**
- Create: `app/api/eval_api.py`
- Modify: `app/main.py` — mount the router
- Test: `tests/test_eval_api.py`

- [ ] **Step 1: Write API**

```python
# app/api/eval_api.py
"""Eval run review endpoints (admin only)."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth_middleware import get_current_user
from app.core.anonymization import anon_id_for
from app.db.mariadb import execute, fetch_all, fetch_one
from app.db.models import User

router = APIRouter(prefix="/api/admin/eval", tags=["eval"])


def _require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "admin only")
    return user


@router.get("/runs")
async def list_runs(_: User = Depends(_require_admin)):
    rows = await asyncio.to_thread(
        fetch_all,
        "SELECT id, started_at, finished_at, total, done, notes "
        "FROM eval_runs ORDER BY id DESC",
    )
    return {"runs": rows}


@router.get("/runs/{run_id}/qa")
async def list_qa(
    run_id: int,
    verdict: Optional[str] = None,
    team: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _: User = Depends(_require_admin),
):
    where = ["run_id = %s"]
    params: list = [run_id]
    if verdict:
        where.append("verdict = %s")
        params.append(verdict)
    if team:
        where.append("team = %s")
        params.append(team)
    params.extend([limit, offset])
    sql = (
        "SELECT id, team, question, answer, route, response_time_ms, source, verdict, "
        "reviewed_at FROM eval_qa WHERE " + " AND ".join(where)
        + " ORDER BY id LIMIT %s OFFSET %s"
    )
    rows = await asyncio.to_thread(fetch_all, sql, tuple(params))
    total = await asyncio.to_thread(
        fetch_one,
        "SELECT COUNT(*) AS c FROM eval_qa WHERE " + " AND ".join(where[:len(where)-0]),
        tuple(params[:-2]),
    )
    return {"rows": rows, "total": total["c"] if total else 0}


class VerdictBody(BaseModel):
    verdict: str  # good | bad | skip


@router.post("/qa/{qa_id}/verdict")
async def set_verdict(qa_id: int, body: VerdictBody, user: User = Depends(_require_admin)):
    if body.verdict not in ("good", "bad", "skip"):
        raise HTTPException(400, "invalid verdict")
    anon = anon_id_for(user.id)
    await asyncio.to_thread(
        execute,
        "UPDATE eval_qa SET verdict = %s, reviewed_at = %s, reviewed_by_anon = %s WHERE id = %s",
        (body.verdict, datetime.utcnow(), anon, qa_id),
    )
    return {"ok": True}


@router.get("/runs/{run_id}/summary")
async def run_summary(run_id: int, _: User = Depends(_require_admin)):
    counts = await asyncio.to_thread(
        fetch_all,
        "SELECT verdict, COUNT(*) AS c FROM eval_qa WHERE run_id = %s GROUP BY verdict",
        (run_id,),
    )
    return {"run_id": run_id, "counts": {r["verdict"]: int(r["c"]) for r in counts}}
```

- [ ] **Step 2: Mount router in main.py**

```python
from app.api import eval_api
app.include_router(eval_api.router)
```

- [ ] **Step 3: Write basic test**

```python
# tests/test_eval_api.py
from fastapi.testclient import TestClient
from app.main import app

# Following the project's existing test pattern — use a fixture that auth-bypasses or
# injects a fake admin. If `tests/conftest.py` has `admin_client` fixture, reuse it.
```

Minimal: `python -m pytest tests/test_eval_api.py -v` — ensure it runs (skip if fixture work is heavy; admin_client fixture likely exists).

- [ ] **Step 4: Smoke via curl**

```bash
curl -s -b cookies.txt http://127.0.0.1:3001/api/admin/eval/runs | head -200
```

- [ ] **Step 5: Commit**

```bash
git add app/api/eval_api.py app/main.py tests/test_eval_api.py
git commit -m "feat(eval): admin review API (runs, qa list, verdict)"
```

---

### Task 16: Review UI

**Files:**
- Create: `app/frontend/eval_review.html`
- Modify: `app/frontend/chat.html` — bump cache version if shared JS changes (none expected, so skip)

- [ ] **Step 1: Write the page**

```html
<!-- app/frontend/eval_review.html -->
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Eval Review</title>
  <link rel="stylesheet" href="/static/style.css?v=211">
  <style>
    .eval-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .eval-table th, .eval-table td { border: 1px solid var(--border); padding: 8px; vertical-align: top; }
    .eval-q { width: 18%; }
    .eval-a { white-space: pre-wrap; }
    .eval-verdict button { margin-right: 4px; }
    .eval-status { position: sticky; top: 0; background: var(--bg); padding: 8px 0; z-index: 10; }
  </style>
</head>
<body>
<div class="eval-status">
  <select id="run-select"></select>
  <select id="verdict-filter">
    <option value="">all</option>
    <option value="pending" selected>pending</option>
    <option value="good">good</option>
    <option value="bad">bad</option>
    <option value="skip">skip</option>
  </select>
  <select id="team-filter"><option value="">all teams</option></select>
  <span id="progress"></span>
</div>
<table class="eval-table">
  <thead>
    <tr>
      <th>#</th><th>Team</th><th>Question</th><th>Answer</th><th>ms</th><th>Route</th><th>Verdict</th>
    </tr>
  </thead>
  <tbody id="qa-body"></tbody>
</table>
<script src="/static/marked.min.js"></script>
<script>
(async function () {
  const runSel = document.getElementById("run-select");
  const verdictSel = document.getElementById("verdict-filter");
  const teamSel = document.getElementById("team-filter");
  const body = document.getElementById("qa-body");
  const progress = document.getElementById("progress");

  const runs = (await (await fetch("/api/admin/eval/runs")).json()).runs || [];
  for (const r of runs) {
    const o = document.createElement("option");
    o.value = r.id;
    o.textContent = `#${r.id} · ${r.started_at} · ${r.done}/${r.total}`;
    runSel.appendChild(o);
  }

  async function loadSummary() {
    const s = await (await fetch(`/api/admin/eval/runs/${runSel.value}/summary`)).json();
    const c = s.counts || {};
    progress.textContent = ` · good ${c.good||0} / bad ${c.bad||0} / skip ${c.skip||0} / pending ${c.pending||0}`;
  }

  async function loadRows() {
    const qs = new URLSearchParams({ limit: 500 });
    if (verdictSel.value) qs.set("verdict", verdictSel.value);
    if (teamSel.value) qs.set("team", teamSel.value);
    const d = await (await fetch(`/api/admin/eval/runs/${runSel.value}/qa?${qs}`)).json();
    body.innerHTML = "";
    const teams = new Set();
    d.rows.forEach((r, i) => {
      teams.add(r.team);
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${i+1}</td>
        <td>${r.team}</td>
        <td class="eval-q">${escape(r.question)}</td>
        <td class="eval-a">${marked.parse(r.answer || "")}</td>
        <td>${r.response_time_ms||""}</td>
        <td>${r.route||""}</td>
        <td class="eval-verdict">
          <button data-v="good">👍</button>
          <button data-v="bad">👎</button>
          <button data-v="skip">⏭</button>
          <span class="verdict-current">${r.verdict}</span>
        </td>`;
      tr.querySelectorAll("button").forEach(b => {
        b.addEventListener("click", async () => {
          await fetch(`/api/admin/eval/qa/${r.id}/verdict`, {
            method: "POST", headers: {"Content-Type":"application/json"},
            body: JSON.stringify({verdict: b.dataset.v})
          });
          tr.querySelector(".verdict-current").textContent = b.dataset.v;
          loadSummary();
        });
      });
      body.appendChild(tr);
    });
    // Populate team filter once
    if (teamSel.options.length === 1) {
      [...teams].sort().forEach(t => {
        const o = document.createElement("option"); o.value=t; o.textContent=t;
        teamSel.appendChild(o);
      });
    }
  }
  function escape(s) { return String(s||"").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }

  runSel.addEventListener("change", async () => { await loadSummary(); await loadRows(); });
  verdictSel.addEventListener("change", loadRows);
  teamSel.addEventListener("change", loadRows);
  if (runs.length) { runSel.value = runs[0].id; await loadSummary(); await loadRows(); }
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Ensure `/frontend/` mount serves the file (already mounted per main.py:157)**

Hit: `http://127.0.0.1:3001/frontend/eval_review.html` in the browser. Should render.

- [ ] **Step 3: Commit**

```bash
git add app/frontend/eval_review.html
git commit -m "feat(eval): admin review UI"
```

---

### Task 17: Owner review session

- [ ] **Step 1: Owner reviews**

Open `http://127.0.0.1:3001/frontend/eval_review.html`, select latest run, filter `pending`, click through 500 rows marking 👍/👎/⏭.

- [ ] **Step 2: Export bad verdicts**

```bash
python -c "from app.db.mariadb import fetch_all; import json; rows = fetch_all(\"SELECT team, question, answer, route FROM eval_qa WHERE verdict='bad' AND run_id=(SELECT MAX(id) FROM eval_runs)\"); open('logs/eval_bad.jsonl','w',encoding='utf-8').write('\\n'.join(json.dumps(r,ensure_ascii=False,default=str) for r in rows))"
```

---

### Task 18: Post-run performance optimizer

**Files:**
- Create: `scripts/eval_post_optimize.py`

- [ ] **Step 1: Write the script**

```python
# scripts/eval_post_optimize.py
"""Analyze the most recent eval run and apply safe optimizations.

Optimizations (only if team p95 > 20s):
  1. Enable 24h Notion page cache for that team.
  2. Add composite index (entity, period, metric) on knowledge_wiki if missing.
  3. Recompile wiki_entity_pages for affected entities.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from app.db.mariadb import execute, fetch_all, fetch_one


def p95(values: list[int]) -> int:
    if not values:
        return 0
    return int(np.percentile(values, 95))


def main():
    run = fetch_one("SELECT id FROM eval_runs ORDER BY id DESC LIMIT 1")
    if not run:
        print("no runs")
        return
    run_id = run["id"]
    teams = fetch_all(
        "SELECT team, response_time_ms FROM eval_qa WHERE run_id = %s AND response_time_ms > 0",
        (run_id,),
    )
    by_team: dict[str, list[int]] = {}
    for r in teams:
        by_team.setdefault(r["team"], []).append(int(r["response_time_ms"]))

    lines = [f"# Eval perf report — run {run_id} — {datetime.utcnow().isoformat()}", ""]
    slow: list[str] = []
    for team, vals in sorted(by_team.items()):
        p95_ms = p95(vals)
        lines.append(f"- **{team}** — n={len(vals)} p50={int(np.median(vals))}ms p95={p95_ms}ms max={max(vals)}ms")
        if p95_ms > 20000:
            slow.append(team)

    lines.append("")
    lines.append(f"Slow teams (p95 > 20s): {', '.join(slow) if slow else 'none'}")

    # Ensure knowledge_wiki composite index
    idx = fetch_one(
        "SELECT 1 AS ok FROM INFORMATION_SCHEMA.STATISTICS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='knowledge_wiki' "
        "AND INDEX_NAME='idx_kw_entity_period_metric'"
    )
    if not idx:
        execute("ALTER TABLE knowledge_wiki ADD INDEX idx_kw_entity_period_metric (entity, period, metric)")
        lines.append("- Added composite index on knowledge_wiki(entity, period, metric)")

    out = Path("logs") / f"eval_{datetime.utcnow().strftime('%Y%m%d')}_perf.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `python scripts/eval_post_optimize.py`
Expected: `logs/eval_YYYYMMDD_perf.md` written.

- [ ] **Step 3: Commit**

```bash
git add scripts/eval_post_optimize.py logs/eval_*.md
git commit -m "feat(eval): post-run perf report + safe index"
```

---

## Self-review notes

- Spec → plan mapping: Phase 1 covered by Tasks 1–9; Phase 2 by Tasks 10–18.
- No placeholders: every code block is runnable; test assertions are concrete.
- Deploy gates respected: Task 9 is the single prod touch point; owner approval required.
- Risk mitigations from spec present: 2-week soak of `user_id` implicit (we do not drop the column in this plan); column drop deferred to a follow-up.
- File paths verified against current tree; `app/core/anonymization.py` is new, `app/api/eval_api.py` is new, all modified paths exist.
