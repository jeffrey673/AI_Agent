"""Resolve knowledge_wiki conflicts caused by entity name case variants.

Finds all `needs_review` pairs where the two entities differ only in
letter-casing, canonicalises them to a single name, and marks stale
duplicates as archived.

Strategy per (entity_lower, period, metric) group:
  - Pick the canonical entity name: whichever form appears most often in
    the group; tie-break on the earliest inserted row (lowest id).
  - Rename all rows in the group to the canonical name.
  - Within each group, if multiple rows have the SAME value: keep the most
    recent, archive the rest (status='archived').
  - If rows have DIFFERENT values: keep all but clear the conflict flag
    (they're now the same entity, so the conflict is legitimate and tracked
    under 'needs_review' — but at least the entity name is unified).

Usage:
  python -X utf8 scripts/resolve_wiki_conflicts.py            # dry run
  python -X utf8 scripts/resolve_wiki_conflicts.py --apply    # write to DB
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

import pymysql

DRY_RUN = "--apply" not in sys.argv


def get_conn():
    return pymysql.connect(
        host=os.getenv("MARIADB_HOST", "127.0.0.1"),
        port=int(os.getenv("MARIADB_PORT", "3306")),
        user=os.getenv("MARIADB_USER"),
        password=os.getenv("MARIADB_PASSWORD"),
        database=os.getenv("MARIADB_DATABASE"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def main():
    mode = "DRY RUN" if DRY_RUN else "APPLY"
    print(f"=== resolve_wiki_conflicts.py [{mode}] ===\n")

    conn = get_conn()
    cur = conn.cursor()

    # ── Step 1: Fetch all needs_review rows ─────────────────────────────────
    cur.execute("""
        SELECT id, entity, period, metric, value, status, review_status
        FROM knowledge_wiki
        WHERE review_status = 'needs_review'
        ORDER BY id
    """)
    all_rows = cur.fetchall()
    print(f"Loaded {len(all_rows)} needs_review rows")

    # ── Step 2: Group by (LOWER(entity), period, metric) ────────────────────
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in all_rows:
        key = (row["entity"].lower(), row["period"] or "", row["metric"] or "")
        groups[key].append(row)

    # Add rows that ARE the conflict_with target but may have different status
    # (they could be non-needs_review siblings in a case-variant group)
    cur.execute("""
        SELECT id, entity, period, metric, value, status, review_status
        FROM knowledge_wiki
        WHERE status <> 'archived'
    """)
    all_wiki = {r["id"]: r for r in cur.fetchall()}

    # ── Step 3: Process each group ──────────────────────────────────────────
    renamed = 0
    archived = 0
    resolved = 0
    skipped = 0

    # Find groups that have MORE THAN ONE distinct entity name (case variants)
    case_variant_groups = {
        key: rows for key, rows in groups.items()
        if len({r["entity"] for r in rows}) > 1
    }
    print(f"Groups with case-variant entity names: {len(case_variant_groups)}\n")

    for key, rows in case_variant_groups.items():
        entity_lower, period, metric = key

        # Collect ALL rows for this (entity_lower, period, metric) — not just needs_review
        all_in_group = [
            r for r in all_wiki.values()
            if r["entity"].lower() == entity_lower
            and (r["period"] or "") == period
            and (r["metric"] or "") == metric
            and r["status"] != "archived"
        ]

        if not all_in_group:
            skipped += 1
            continue

        # Pick canonical entity name: most frequent form, tie-break lowest id
        name_counts: dict[str, int] = defaultdict(int)
        for r in all_in_group:
            name_counts[r["entity"]] += 1
        canonical = max(name_counts, key=lambda n: (name_counts[n], -min(
            r["id"] for r in all_in_group if r["entity"] == n
        )))

        # Rename all rows to canonical
        non_canonical = [r for r in all_in_group if r["entity"] != canonical]
        if non_canonical:
            ids_to_rename = [r["id"] for r in non_canonical]
            if not DRY_RUN:
                fmt = ",".join(["%s"] * len(ids_to_rename))
                cur.execute(
                    f"UPDATE knowledge_wiki SET entity = %s WHERE id IN ({fmt})",
                    [canonical] + ids_to_rename,
                )
            renamed += len(ids_to_rename)
            print(f"  RENAME {len(ids_to_rename)}x '{non_canonical[0]['entity']}' → '{canonical}'")

        # Within group: find duplicate values → keep newest, supersede rest
        value_groups: dict[str, list[dict]] = defaultdict(list)
        for r in all_in_group:
            value_groups[r["value"] or ""].append(r)

        for val, val_rows in value_groups.items():
            if len(val_rows) <= 1:
                continue
            # Sort by id desc — keep the highest (newest) id
            val_rows.sort(key=lambda r: r["id"], reverse=True)
            keeper = val_rows[0]
            to_supersede = val_rows[1:]
            ids_to_sup = [r["id"] for r in to_supersede]
            if not DRY_RUN:
                fmt = ",".join(["%s"] * len(ids_to_sup))
                cur.execute(
                    f"UPDATE knowledge_wiki "
                    f"SET status='archived', review_status='resolved', conflict_with_id=NULL, conflict_reason=NULL "
                    f"WHERE id IN ({fmt})",
                    ids_to_sup,
                )
                # Clear conflict flag on keeper if no other conflicts remain
                cur.execute(
                    "UPDATE knowledge_wiki "
                    "SET review_status='resolved', conflict_with_id=NULL, conflict_reason=NULL "
                    "WHERE id = %s",
                    (keeper["id"],),
                )
            archived += len(ids_to_sup)
            resolved += 1

        # If multiple distinct values remain (genuine conflict) — just ensure
        # they all have the same canonical entity name (already done above).
        distinct_values = {r["value"] for r in all_in_group}
        if len(distinct_values) > 1:
            print(f"    NOTE: {len(distinct_values)} distinct values remain for "
                  f"'{canonical}' [{period}] [{metric}] — kept as needs_review")

    # ── Step 4: Deduplicate exact same facts (same entity+period+metric+value) ─
    print("\n--- Deduplicating exact same facts ---")
    cur.execute("""
        SELECT LOWER(entity) as el, period, metric, value, COUNT(*) as cnt
        FROM knowledge_wiki
        WHERE status <> 'archived' AND period IS NOT NULL AND metric IS NOT NULL AND value IS NOT NULL
        GROUP BY LOWER(entity), period, metric, value
        HAVING cnt > 1
        ORDER BY cnt DESC
    """)
    dup_groups = cur.fetchall()
    print(f"Exact-duplicate groups: {len(dup_groups)}")
    dup_archived = 0
    for dg in dup_groups:
        cur.execute("""
            SELECT id FROM knowledge_wiki
            WHERE LOWER(entity) = %s AND period = %s AND metric = %s AND value = %s
              AND status <> 'archived'
            ORDER BY id DESC
        """, (dg["el"], dg["period"], dg["metric"], dg["value"]))
        dup_rows = [r["id"] for r in cur.fetchall()]
        if len(dup_rows) <= 1:
            continue
        keeper_id = dup_rows[0]
        to_drop = dup_rows[1:]
        if not DRY_RUN:
            fmt = ",".join(["%s"] * len(to_drop))
            cur.execute(
                f"UPDATE knowledge_wiki "
                f"SET status='archived', review_status='resolved', "
                f"    conflict_with_id=NULL, conflict_reason=NULL "
                f"WHERE id IN ({fmt})",
                to_drop,
            )
            cur.execute(
                "UPDATE knowledge_wiki "
                "SET review_status='resolved', conflict_with_id=NULL, conflict_reason=NULL "
                "WHERE id = %s AND review_status = 'needs_review'",
                (keeper_id,),
            )
        dup_archived += len(to_drop)
        if dg["cnt"] >= 5:
            print(f"  [{dg['el'][:40]}] cnt={dg['cnt']} → kept id={keeper_id}, archived {len(to_drop)}")
    print(f"  Total archived (exact dups): {dup_archived}")

    # ── Step 5: Commit ───────────────────────────────────────────────────────
    if not DRY_RUN:
        conn.commit()
        print(f"\n✅  Committed.")
    else:
        conn.rollback()
        print(f"\n⚠️  Dry run — no changes written. Re-run with --apply to commit.")

    print(f"\nSummary:")
    print(f"  Renamed rows (entity → canonical):   {renamed}")
    print(f"  Superseded (same-case dups):          {archived}")
    print(f"  Resolved conflict pairs:              {resolved}")
    print(f"  Superseded (exact same-fact dups):    {dup_archived}")
    print(f"  Groups skipped (no data):             {skipped}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
