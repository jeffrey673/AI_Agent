#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Clean up Notion page: move raw blocks into toggles."""

import sys
import time
import httpx
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.upload_to_notion import (
    get_token, heading3, paragraph, bulleted, callout, divider,
    toggle, table_block, append_blocks,
    PAGE_ID, rich_text,
)


def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }


def get_all_blocks(token):
    blocks = []
    url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100"
    while url:
        resp = httpx.get(url, headers=headers(token), timeout=30)
        data = resp.json()
        blocks.extend(data.get("results", []))
        if data.get("has_more"):
            url = f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100&start_cursor={data['next_cursor']}"
        else:
            url = None
    return blocks


def delete_block(token, block_id):
    for attempt in range(3):
        try:
            resp = httpx.delete(
                f"https://api.notion.com/v1/blocks/{block_id}",
                headers=headers(token), timeout=30,
            )
            return resp.status_code == 200
        except Exception:
            import time as t
            t.sleep(1)
    return False


def insert_after(token, block_id, children):
    """Append children blocks after a specific block."""
    resp = httpx.patch(
        f"https://api.notion.com/v1/blocks/{PAGE_ID}/children",
        headers=headers(token),
        json={"children": children, "after": block_id},
        timeout=30,
    )
    return resp.status_code == 200, resp.text[:200]


def build_0310_toggle():
    """Build 2026-03-10 toggle with children."""
    children = [
        callout("MariaDB migration + AD login + Group management + QA V3 pipeline", "🔧"),
        heading3("1. MariaDB Migration (SQLite -> MariaDB)"),
        paragraph("SQLite + SQLAlchemy ORM 완전 제거, MariaDB + pymysql raw SQL 전환 완료."),
        bulleted("DB Layer: DBUtils PooledDB (max=10, cached=2-5)"),
        bulleted("Models: SQLAlchemy ORM -> Python dataclass (User)"),
        bulleted("Auth: email login -> AD department+name autocomplete"),
        bulleted("All DB calls: asyncio.to_thread() wrapping"),
        bulleted("Conversations, Admin API: MariaDB raw SQL"),
        heading3("2. AD Login System"),
        bulleted("Login flow: name input -> autocomplete (AD cache) -> team select -> password"),
        bulleted("Signup: AD user verify -> password set, users.ad_user_id FK link"),
        bulleted("Public API: /api/auth/departments, /api/auth/users-by-dept"),
        bulleted("Password change: /api/auth/change-password"),
        heading3("3. Admin Group Management"),
        bulleted("Group CRUD: /api/admin/groups"),
        bulleted("AD Users: /api/admin/ad/users (dept filter, group filter, search)"),
        bulleted("AD Sync: /api/admin/ad/sync (LDAPS -> MariaDB, 328 users)"),
        heading3("4. Frontend"),
        bulleted("login.html: name autocomplete + team dropdown"),
        bulleted("chat.html: Admin drawer - groups/AD tabs, password change"),
        bulleted("chat.js: Group CRUD, AD user assign, password change modal"),
        heading3("5. QA V3 Pipeline"),
        paragraph("13 tables x 500 = 6,500 target, 4,330/6,500 (67%) at time of log"),
        heading3("6. Google Sheet Export"),
        bulleted("12,374 Q&A uploaded (5 tabs)"),
        bulleted("https://docs.google.com/spreadsheets/d/14alsi_x_P7psBNjm81EMQaoPxbTi-yCoII9RYKjv3WA/edit"),
        paragraph("14 files changed, +1,429 / -400 lines. All API tests passed."),
    ]
    return toggle("2026-03-10 | MariaDB + AD + Groups + QA V3", children)


def build_0311_toggle():
    """Build 2026-03-11 toggle with children."""
    children = [
        callout(
            "QA V3 Pipeline COMPLETE: 6,500/6,500 (100%)\n"
            "FAIL 13 -> 0 eliminated | SQL 6,489/6,500 generated",
            "✅"
        ),
        heading3("QA V3 Results"),
        table_block([
            ["Table", "Done", "OK", "WARN", "FAIL"],
            ["advertising", "500", "473", "27", "0"],
            ["amazon_search", "500", "440", "60", "0"],
            ["influencer", "500", "470", "30", "0"],
            ["marketing_cost", "500", "419", "81", "0"],
            ["meta_ads", "500", "447", "53", "0"],
            ["platform", "500", "414", "86", "0"],
            ["product", "500", "464", "36", "0"],
            ["review_amazon", "500", "434", "66", "0"],
            ["review_qoo10", "500", "390", "110", "0"],
            ["review_shopee", "500", "235", "265", "0"],
            ["review_smartstore", "500", "240", "260", "0"],
            ["sales_all", "500", "282", "218", "0"],
            ["shopify", "500", "424", "76", "0"],
        ]),
        paragraph("OK 5,132 (79.0%) | WARN 1,368 (21.0%) | FAIL 0 (0.0%)"),
        heading3("Performance Optimization"),
        bulleted("Streaming delay removed (routes.py) - 1-3s savings"),
        bulleted("LLM prompt preview cap: 8KB -> 5KB"),
        bulleted("Text truncation: 150 -> 80 chars"),
        paragraph("Before: FAIL 13 (0.2%) -> After: FAIL 0 (0.0%)"),
        heading3("SQL Generation (used_sql)"),
        bulleted("6,489/6,500 results with SQL (Gemini Flash, 3 workers, ~28/min)"),
        bulleted("generate_sql_only.py: Flash LLM direct call, no BQ execution"),
        heading3("Google Sheet Export"),
        table_block([
            ["Tab", "Count", "Notes"],
            ["Combined", "14,560", "V1+Context+V2+V3"],
            ["V3-Pipeline", "6,500", "13 tables x 500"],
            ["Sheet2", "6,500", "V3 + SQL query column"],
        ]),
        bulleted("Sheet2: No, ID, Phase, Table, Category, Question, Answer, SQL, Status, Time"),
        bulleted("https://docs.google.com/spreadsheets/d/14alsi_x_P7psBNjm81EMQaoPxbTi-yCoII9RYKjv3WA/edit"),
        heading3("Total QA Coverage"),
        table_block([
            ["Phase", "Questions", "Purpose"],
            ["V1 Original", "3,900", "Base coverage"],
            ["V2 Variation", "3,900", "Rephrased queries"],
            ["Context", "260", "Context-dependent"],
            ["V3 Pipeline", "6,500", "Full pipeline test"],
            ["TOTAL", "14,560", "All phases"],
        ]),
    ]
    return toggle("2026-03-11 | QA V3 Complete + SQL Gen + Optimization", children)


def main():
    token = get_token()
    print(f"Target page: {PAGE_ID}")

    # Step 1: Get current blocks
    blocks = get_all_blocks(token)
    print(f"Current blocks: {len(blocks)}")

    # Step 2: Find and delete raw 3/10 blocks (heading_2 "2026-03-10" through divider before 3/11)
    # and raw 3/11 blocks (heading_2 "2026-03-11 Final" through end divider)
    delete_indices = []
    in_0310 = False
    in_0311 = False

    for i, b in enumerate(blocks):
        btype = b["type"]
        text = ""
        if btype in ("heading_2",):
            rt = b.get(btype, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in rt])

        if "2026-03-10" in text:
            in_0310 = True
            in_0311 = False
        elif "2026-03-11" in text:
            in_0310 = False
            in_0311 = True

        if in_0310 or in_0311:
            delete_indices.append(i)

    print(f"Blocks to delete: {len(delete_indices)} (indices {delete_indices[0]}..{delete_indices[-1]})")

    # Step 3: Delete raw blocks (reverse order to preserve indices)
    for idx, i in enumerate(reversed(delete_indices)):
        bid = blocks[i]["id"]
        ok = delete_block(token, bid)
        if not ok:
            print(f"  FAILED to delete block {i}")
        if (idx + 1) % 10 == 0:
            print(f"  Deleted {idx + 1}/{len(delete_indices)}...")
            time.sleep(0.5)

    print(f"Deleted {len(delete_indices)} raw blocks")
    time.sleep(1)

    # Step 4: Find insertion point (after the last toggle in Update Log section, before divider)
    blocks = get_all_blocks(token)
    print(f"Blocks after deletion: {len(blocks)}")

    # Find the position: after block index 3 ("새로운 업데이트가 위에 추가됩니다.")
    # Insert new toggles at top of Update Log (after "새로운 업데이트가..." paragraph)
    insert_after_id = None
    for i, b in enumerate(blocks):
        btype = b["type"]
        if btype == "paragraph":
            rt = b.get(btype, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in rt])
            if "새로운 업데이트" in text:
                insert_after_id = b["id"]
                print(f"Insert after block {i}: '{text[:50]}'")
                break

    if not insert_after_id:
        print("ERROR: Could not find insertion point")
        return

    # Step 5: Insert toggles (3/11 first, then 3/10, so 3/11 ends up on top)
    toggle_0310 = build_0310_toggle()
    toggle_0311 = build_0311_toggle()

    # Insert 3/10 first (it will be below)
    ok, msg = insert_after(token, insert_after_id, [toggle_0310])
    print(f"Insert 3/10 toggle: {'OK' if ok else 'FAILED'} {msg[:100] if not ok else ''}")
    time.sleep(0.5)

    # Insert 3/11 after same point (it pushes 3/10 down, so 3/11 is on top)
    ok, msg = insert_after(token, insert_after_id, [toggle_0311])
    print(f"Insert 3/11 toggle: {'OK' if ok else 'FAILED'} {msg[:100] if not ok else ''}")

    # Verify
    time.sleep(1)
    blocks = get_all_blocks(token)
    print(f"\nFinal blocks: {len(blocks)}")
    for i, b in enumerate(blocks[:20]):
        btype = b["type"]
        text = ""
        if btype in ("heading_1", "heading_2", "heading_3", "paragraph", "callout", "toggle"):
            rt = b.get(btype, {}).get("rich_text", [])
            text = "".join([t.get("plain_text", "") for t in rt])[:60]
        elif btype == "divider":
            text = "---"
        print(f"  [{i:3d}] {btype:20s} | {text}")

    print("\nDone!")


if __name__ == "__main__":
    main()
