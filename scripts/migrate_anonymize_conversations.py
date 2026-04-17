"""Backfill anon_id on existing conversations + message_feedback rows.

Run once after the anon_id columns are added (scripts/ensure_anon_columns.py
runs automatically on server startup). Idempotent: only fills rows where
``anon_id = ''``.

Usage:
    python scripts/migrate_anonymize_conversations.py --dry-run
    python scripts/migrate_anonymize_conversations.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from project root without `pip install -e .`
_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from app.core.anonymization import compute_anon_id  # noqa: E402
from app.db.mariadb import execute, fetch_all, fetch_one  # noqa: E402


def _backfill(table: str, dry_run: bool) -> int:
    rows = fetch_all(
        f"SELECT id, user_id FROM {table} "
        f"WHERE anon_id = '' AND user_id IS NOT NULL"
    )
    print(f"[{table}] rows to backfill: {len(rows)}", flush=True)
    if dry_run or not rows:
        return len(rows)

    # Build unique user_id -> anon_id map first (HMAC once per user, not per row)
    unique_uids = {int(r["user_id"]) for r in rows}
    anon_by_uid = {uid: compute_anon_id(uid) for uid in unique_uids}
    print(f"  unique users: {len(unique_uids)}", flush=True)

    for i, r in enumerate(rows, 1):
        anon = anon_by_uid[int(r["user_id"])]
        execute(f"UPDATE {table} SET anon_id = %s WHERE id = %s", (anon, r["id"]))
        if i % 500 == 0 or i == len(rows):
            print(f"  [{table}] {i}/{len(rows)}", flush=True)
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        ap.error("choose --apply or --dry-run")

    for table in ("conversations", "message_feedback"):
        _backfill(table, dry_run=not args.apply)

    # Post-check (always runs, harmless on dry-run)
    for table in ("conversations", "message_feedback"):
        r = fetch_one(
            f"SELECT COUNT(*) AS c FROM {table} "
            f"WHERE anon_id = '' AND user_id IS NOT NULL"
        )
        remaining = int(r["c"]) if r else -1
        status = "OK" if remaining == 0 or args.dry_run else "INCOMPLETE"
        print(f"[{table}] remaining empty anon_id: {remaining} [{status}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
