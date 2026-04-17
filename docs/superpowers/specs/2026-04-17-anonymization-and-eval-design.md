# Anonymization + Eval Pipeline Design

**Date**: 2026-04-17
**Author**: Jeffrey (via Claude)
**Status**: approved
**Phases**: Phase 1 — anonymization migration (blocks Phase 2). Phase 2 — eval pipeline.

## Motivation

1. **Privacy**: Conversation history currently stores `user_id FK` on every row. A DB dump lets anyone re-identify who asked what. Policy: from now on, question/answer rows must not carry identity.
2. **Answer quality insight**: We need a way to see, per-team, whether the AI gives good answers. Current thumbs-down data is sparse because real users rarely click it. Goal: run a controlled 500-question batch (10 teams × 50), then review the answers as a human judge.

Phase 1 is a schema change that affects every writer/reader of `conversations` and `message_feedback`. It must ship and stabilize before Phase 2, because Phase 2 pumps ~500 new rows through the same path.

## Phase 1 — Anonymization (pseudonymization, not deletion)

### Threat model
- **In scope**: DB dump leak, shared read-replica access, analytics exports. After Phase 1 lands, an attacker with read-only DB access cannot link a conversation to a human without also obtaining the server-side salt.
- **Out of scope**: Full memory dump of running server (salt in process memory), cross-correlation with `ad_users` table (identity table unchanged, required for login).

### Identity model
- New env var `SKIN1004_ANON_SALT`, ≥ 32 bytes, set in `.env` (never in git, never in logs). Server fails to start if missing in production.
- Derivation: `anon_id = hmac_sha256(salt, str(user_id)).hexdigest()[:16]`. Deterministic per-user → same user's conversations stay grouped in sidebar. 16 hex chars = 64 bits of entropy, collision-resistant at our scale.
- Derivation helper: new `app/core/anonymization.py` with `compute_anon_id(user_id: int) -> str` and a cached lookup (TTL 10 min) keyed by user_id to avoid per-request HMAC cost.

### Schema changes
```sql
-- conversations
ALTER TABLE conversations
    ADD COLUMN anon_id VARCHAR(32) NOT NULL DEFAULT '' AFTER id,
    ADD INDEX idx_conversations_anon_id (anon_id);

-- message_feedback (confirmed: has user_id int(11))
ALTER TABLE message_feedback
    ADD COLUMN anon_id VARCHAR(32) NOT NULL DEFAULT '' AFTER id,
    ADD INDEX idx_message_feedback_anon_id (anon_id);
```

Kept as-is: `users`, `ad_users` (needed for login), `audit_logs` (needed for incident response — legitimate attribution use case, separate table so DB dump of `conversations` alone never leaks identity).

### Application changes
- `conversation_api.py`: every query that filters by `user_id` → filter by `compute_anon_id(current_user.id)`. Every insert writes `anon_id` only; `user_id` column stops being written on new rows (but column stays for 2-week soak).
- Admin APIs (`admin_api.py`, `admin_group_api.py`): per-user breakdowns become per-anon_id. Counts, averages, distributions unchanged. Admin UI shows a truncated anon_id (e.g. "a7f3…") instead of name.
- `structlog` processor addition in `app/main.py` logging config: before emit, scrub any `user_id`, `email`, `name`, `display_name` keys from event dict → replace `user_id` with `anon_id`, drop others. Exception: loggers under the `audit` namespace keep raw fields.

### Migration — backfill existing ~29k conversations
- New script `scripts/migrate_anonymize_conversations.py`:
  - Loads salt from env
  - `UPDATE conversations SET anon_id = ... WHERE anon_id = ''` computed per row (chunked 1000 at a time)
  - Same for `message_feedback`
  - Dry-run flag prints counts, prod-run flag writes
- Verification: post-migration invariant `COUNT(*) WHERE anon_id = '' = 0`.

### Deprecation of `user_id` column
- Week 0 (after Phase 1 ships): writes stop, reads use anon_id, column still exists.
- Week 2: if no rollback, drop `user_id` column from conversations and message_feedback.
- Config flag `SKIN1004_ANON_DROP_USER_ID_AT` (date) gates the removal.

### Deploy order
1. dev (3001): schema + app change + backfill → smoke test sidebar + admin APIs → response times under baseline
2. Owner approval
3. prod (3000): `pm2 reload` after schema change applied via a maintenance-windowed SQL run
4. Monitor for 48h → proceed to Phase 2

## Phase 2 — Eval pipeline

### Question generation
- Script: `scripts/generate_eval_questions.py`
- Per team (10 Notion allowlist topics), target 50 questions. Process:
  1. **Real queries**: pull from `messages WHERE role='user'` and `source_route='notion'` (backfilled where possible), filter by team allowlist keywords. Cap at 40 per team.
  2. **Synthetic queries**: for remaining slots (50 − real), fetch the team's Notion page content → Gemini Flash prompt: "Given this business document, generate 150 realistic work questions a team member might ask." → 150 candidates.
  3. **Diversify**: embed all candidates (real + synthetic) using Gemini embedding API → cosine similarity matrix → drop any pair > 0.85 similar (keep earlier one) → K-means (K = 25 target clusters) → pick 1–2 from each cluster until 50 reached.
  4. Output: `tests/eval/questions_YYYYMMDD.jsonl` — one row per question with `{team, source: real|synthetic, question, cluster_id, generated_at}`.

### Playwright runner
- Script: `tests/eval/playwright_runner.py`
- Python playwright sync API, chromium headless.
- Login flow: navigate `/login` → select department + name (임재필) → password from `.env.eval` (git-ignored) → submit → wait for chat.html load.
- Per question: type into `#chat-input` → click send → wait for SSE stream completion (detect by `typing-indicator` disappearing and last `.message-ai .message-content` gaining content). Hard timeout 60s per question.
- Capture: question text, final answer markdown (from `data-raw`), `response_time_ms` (send → completion), `conversation_id` (from URL or API), `message_id` (latest assistant message), used source chips, route (from a debug attribute to be added, or parsed from answer footer).
- Throttle: 3s between questions. Retry twice on timeout/error, then mark as failed.
- Runs sequentially — agent stability over parallel throughput.

### Eval storage
```sql
CREATE TABLE eval_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    total INT NOT NULL,
    done INT NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE eval_qa (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id INT NOT NULL,
    team VARCHAR(100) NOT NULL,
    question TEXT NOT NULL,
    answer MEDIUMTEXT,
    route VARCHAR(32),
    response_time_ms INT,
    conversation_id VARCHAR(36),
    message_id INT,
    source ENUM('real', 'synthetic') NOT NULL,
    verdict ENUM('pending', 'good', 'bad', 'skip') NOT NULL DEFAULT 'pending',
    reviewed_at DATETIME,
    reviewed_by_anon VARCHAR(32),
    INDEX idx_eval_qa_run (run_id),
    INDEX idx_eval_qa_verdict (verdict),
    FOREIGN KEY (run_id) REFERENCES eval_runs(id) ON DELETE CASCADE
);
```

Conversations generated by eval go through the normal route — they land in `conversations`/`messages` with Jeffrey's anon_id (per Phase 1). `eval_qa.conversation_id` keeps the reverse link.

### Speed optimization (post-hoc, opt-in)
- After run finishes, script `scripts/eval_post_optimize.py`:
  - Computes p50/p95/max response time per team
  - Writes `logs/eval_YYYYMMDD_perf.md`
  - If any team's p95 > 20s, apply automatic remediation:
    - Enable 24h local cache for that team's Notion page content
    - Add `(entity, period, metric)` composite index on `knowledge_wiki` if absent
    - Recompile wiki_entity_pages for affected entities
  - Each remediation logs before/after measurement after re-running a small probe (5 questions).
- Explicitly not automatic mid-run — too much risk of changing behavior during data collection.

### Review UI
- New file `app/frontend/eval_review.html` served at `/frontend/eval_review.html`, gated behind admin auth (reuse existing middleware).
- Layout: top bar with run selector + progress counts ("348/500 · Good 280 / Bad 52 / Skip 16") + filters (team, route, verdict, sort by response_time).
- Body: virtualized table (rendering 500 rows without virtualization lags — use intersection observer or a simple 50-row window). Columns: Team · Question · Answer (marked.parse rendered) · Response ms · Route · Actions (👍 / 👎 / ⏭).
- Click action → `POST /api/admin/eval/{qa_id}/verdict` with `{verdict}` → updates row.
- Backend: new `app/api/eval_api.py` with endpoints:
  - `GET /api/admin/eval/runs` — list runs
  - `GET /api/admin/eval/runs/{run_id}/qa?verdict=pending&team=...` — paginated
  - `POST /api/admin/eval/qa/{qa_id}/verdict` — update verdict + reviewed_at + reviewed_by_anon

## Rollout order

1. Phase 1 schema + app changes → dev → verify sidebar unchanged, admin APIs return anon_ids, logs scrubbed
2. Phase 1 backfill on dev → verify counts, spot-check sidebar for random user
3. Owner approval → prod: maintenance-windowed SQL + `pm2 reload skin1004-prod`
4. Phase 2 script + Playwright runner on dev
5. Generate 500 questions → commit questions file
6. Run Playwright → populate eval_qa
7. Open review UI → owner reviews all 500 → export verdicts
8. Analyze bad-verdict patterns → feed into next round of prompt/agent tuning

## Non-goals

- Not doing: full deletion of history, cross-user analytics redesign, migrating `audit_logs`, eval dashboard with trends (that's a follow-up).
- Not automating mid-run optimization — quality signal integrity matters more than wall-clock time.

## Risks

- **Salt rotation**: rotating the salt re-anon_ids everyone → sidebar loses history. Mitigation: don't rotate unless compromise. Document salt lifecycle.
- **Column drop regret**: if we drop `user_id` at week 2 and later need attribution, we can't recover. Mitigation: 2-week soak, keep a one-time encrypted backup of (user_id, conversation_id) pairs for 90 days in a separate vault, then destroy.
- **Playwright flakiness on SSE completion detection**: tight timeouts could produce false "timeout" captures. Mitigation: generous 60s per-question timeout, 2× retry, final failed count surfaced in run notes.

## Files touched (preview)

- New: `app/core/anonymization.py`, `scripts/migrate_anonymize_conversations.py`, `scripts/generate_eval_questions.py`, `scripts/eval_post_optimize.py`, `tests/eval/playwright_runner.py`, `app/api/eval_api.py`, `app/frontend/eval_review.html`, `docs/superpowers/specs/2026-04-17-anonymization-and-eval-design.md` (this file)
- Modified: `app/api/conversation_api.py`, `app/api/admin_api.py`, `app/api/admin_group_api.py`, `app/main.py` (logging config, route mount), `app/db/mariadb.py` (schema DDL), `app/config.py` (env var)
