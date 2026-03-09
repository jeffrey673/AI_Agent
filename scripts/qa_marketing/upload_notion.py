"""Upload Marketing QA 3,300 results to Notion.

Reads per-table result files and report markdown, then uploads to the
existing Notion report page as a new QA section.
"""

import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent.parent
RESULTS_DIR = BASE_DIR / "results"
REPORT_FILE = BASE_DIR / "marketing_qa_report.md"

PAGE_ID = "3032b428-3b00-80ae-8241-cedef71fc3be"
NOTION_VERSION = "2022-06-28"
MAX_TEXT_LEN = 1900
MAX_BLOCKS_PER_CALL = 100


def get_token():
    sys.path.insert(0, str(PROJECT_DIR))
    from app.config import get_settings
    return get_settings().notion_mcp_token


def headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def rich_text(text: str, bold=False, code=False, color="default") -> list:
    chunks = []
    while text:
        chunk = text[:MAX_TEXT_LEN]
        text = text[MAX_TEXT_LEN:]
        chunks.append({
            "type": "text",
            "text": {"content": chunk},
            "annotations": {"bold": bold, "code": code, "color": color},
        })
    return chunks if chunks else [{"type": "text", "text": {"content": ""}}]


def paragraph(text: str, bold=False) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": rich_text(text, bold=bold)}}


def heading2(text: str) -> dict:
    return {"object": "block", "type": "heading_2",
            "heading_2": {"rich_text": rich_text(text)}}


def heading3(text: str) -> dict:
    return {"object": "block", "type": "heading_3",
            "heading_3": {"rich_text": rich_text(text)}}


def callout(text: str, emoji: str = "📌") -> dict:
    return {"object": "block", "type": "callout",
            "callout": {"rich_text": rich_text(text),
                        "icon": {"type": "emoji", "emoji": emoji}}}


def bulleted(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": rich_text(text)}}


def divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def toggle(text: str, children: list = None) -> dict:
    block = {"object": "block", "type": "toggle",
             "toggle": {"rich_text": rich_text(text, bold=True)}}
    if children:
        block["toggle"]["children"] = children[:MAX_BLOCKS_PER_CALL]
    return block


def table_block(rows: list) -> dict:
    width = len(rows[0]) if rows else 1
    table_rows = []
    for row in rows:
        cells = [rich_text(str(c)[:MAX_TEXT_LEN]) for c in row]
        while len(cells) < width:
            cells.append(rich_text(""))
        table_rows.append({"object": "block", "type": "table_row",
                           "table_row": {"cells": cells}})
    return {"object": "block", "type": "table",
            "table": {"table_width": width, "has_column_header": True,
                      "has_row_header": False, "children": table_rows}}


def append_blocks(token: str, parent_id: str, blocks: list):
    hdrs = headers(token)
    for start in range(0, len(blocks), MAX_BLOCKS_PER_CALL):
        batch = blocks[start:start + MAX_BLOCKS_PER_CALL]
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{parent_id}/children",
            headers=hdrs, json={"children": batch}, timeout=60,
        )
        if r.status_code != 200:
            print(f"  ERROR: {r.status_code} {r.text[:300]}")
            return False
        time.sleep(0.3)
    return True


def get_children(token: str, block_id: str) -> list:
    hdrs = headers(token)
    results = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = httpx.get(url, headers=hdrs, timeout=15)
        if r.status_code != 200:
            break
        data = r.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def build_marketing_qa_blocks():
    """Build Notion blocks from Marketing QA 3300 results."""
    blocks = []
    all_data = {}

    # Load per-table results
    for f in sorted(RESULTS_DIR.glob("results_*.json")):
        table_name = f.stem.replace("results_", "")
        data = json.loads(f.read_text(encoding="utf-8"))
        all_data[table_name] = data

    if not all_data:
        return [paragraph("No results found")]

    total_q = sum(len(v) for v in all_data.values())
    all_results = [r for v in all_data.values() for r in v]
    ok = sum(1 for r in all_results if r["status"] == "OK")
    warn = sum(1 for r in all_results if r["status"] == "WARN")
    fail = sum(1 for r in all_results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
    times = [r["time"] for r in all_results]
    avg_t = sum(times) / len(times) if times else 0
    p50 = sorted(times)[len(times) // 2] if times else 0
    p95 = sorted(times)[int(len(times) * 0.95)] if times else 0

    # Summary callout
    blocks.append(callout(
        f"Marketing QA: {ok + warn}/{total_q} PASS ({(ok + warn) / total_q * 100:.1f}%) | "
        f"OK: {ok} | WARN: {warn} | FAIL: {fail} | "
        f"Avg: {avg_t:.1f}s | P50: {p50:.1f}s | P95: {p95:.1f}s | "
        f"Tables: {len(all_data)}",
        "📊"
    ))

    # Per-table summary table
    header = ["Table", "Total", "OK", "WARN", "FAIL", "Pass%", "Avg(s)", "P50(s)"]
    rows = [header]
    for table_name in sorted(all_data.keys()):
        results = all_data[table_name]
        t_total = len(results)
        t_ok = sum(1 for r in results if r["status"] == "OK")
        t_warn = sum(1 for r in results if r["status"] == "WARN")
        t_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_pass = (t_ok + t_warn) / t_total * 100 if t_total else 0
        t_times = [r["time"] for r in results]
        t_avg = sum(t_times) / len(t_times) if t_times else 0
        t_p50 = sorted(t_times)[len(t_times) // 2] if t_times else 0
        rows.append([
            table_name, str(t_total), str(t_ok), str(t_warn), str(t_fail),
            f"{t_pass:.1f}%", f"{t_avg:.1f}", f"{t_p50:.1f}",
        ])
    rows.append(["TOTAL", str(total_q), str(ok), str(warn), str(fail),
                  f"{(ok + warn) / total_q * 100:.1f}%", f"{avg_t:.1f}", f"{p50:.1f}"])
    blocks.append(table_block(rows))

    # Per-table toggles — only FAIL/WARN items (not all 300)
    for table_name in sorted(all_data.keys()):
        results = all_data[table_name]
        t_ok = sum(1 for r in results if r["status"] == "OK")
        t_warn = sum(1 for r in results if r["status"] == "WARN")
        t_fail = sum(1 for r in results if r["status"] in ("FAIL", "ERROR", "EMPTY"))
        t_avg = sum(r["time"] for r in results) / len(results) if results else 0

        # Only include non-OK results to stay under block limits
        non_ok = [r for r in results if r["status"] != "OK"]
        children = []
        for r in sorted(non_ok, key=lambda x: -x["time"]):
            icon = {"WARN": "⚠️", "FAIL": "❌", "ERROR": "❌", "EMPTY": "⭕"}.get(r["status"], "❓")
            q = r["query"][:50]
            children.append(bulleted(f"{icon} [{r['id']}] {q} ({r['time']:.1f}s) — {r['status']}"))

        if not children:
            children = [paragraph("All 300 queries passed (OK)")]

        blocks.append(toggle(
            f"{table_name}: {t_ok + t_warn}/{len(results)} PASS "
            f"(OK={t_ok} W={t_warn} F={t_fail}, avg {t_avg:.1f}s)",
            children[:MAX_BLOCKS_PER_CALL]
        ))

    # Failures detail
    fails = [r for r in all_results if r["status"] in ("FAIL", "ERROR", "EMPTY")]
    if fails:
        fail_children = []
        for r in sorted(fails, key=lambda x: -x["time"]):
            fail_children.append(bulleted(
                f"❌ [{r['id']}] [{r.get('table', '?')}] {r['query'][:40]} "
                f"({r['time']:.1f}s) — {r['status']}"
            ))
        blocks.append(toggle(f"Failures ({len(fails)}건)", fail_children[:MAX_BLOCKS_PER_CALL]))

    return blocks


def main():
    token = get_token()
    now = datetime.now().strftime("%Y-%m-%d")

    print(f"Building Marketing QA 3,300 blocks...")
    mkt_blocks = build_marketing_qa_blocks()

    if not mkt_blocks:
        print("No blocks to upload!")
        return

    print(f"Uploading to Notion page {PAGE_ID}...")

    # Find QA Test Reports section and append after it
    # Strategy: append at the end of the page (after existing content)
    section_blocks = [
        heading2(f"{now} Marketing QA 3,300 테스트 (13 tables × 300) — v7.2"),
    ]
    section_blocks.extend(mkt_blocks)

    # Find the right position — look for "🧪 QA Test Reports" heading
    children = get_children(token, PAGE_ID)

    # Find QA section heading
    qa_section_id = None
    for child in children:
        if child.get("type") == "heading_1":
            rt = child.get("heading_1", {}).get("rich_text", [])
            text = "".join(t.get("text", {}).get("content", "") for t in rt)
            if "QA Test Reports" in text:
                qa_section_id = child["id"]
                break

    if qa_section_id:
        # Insert after QA Test Reports heading
        # Find the block after it
        found = False
        insert_after = qa_section_id
        for i, child in enumerate(children):
            if child["id"] == qa_section_id:
                found = True
                # The next block after the heading's description paragraph
                if i + 1 < len(children):
                    # Check if next is a paragraph (description)
                    if children[i + 1].get("type") == "paragraph":
                        insert_after = children[i + 1]["id"]
                break

        # Append blocks after the insert point
        print(f"  Inserting after QA section (after block {insert_after[:8]}...)")
        r = httpx.patch(
            f"https://api.notion.com/v1/blocks/{PAGE_ID}/children",
            headers=headers(token),
            json={"children": section_blocks[:MAX_BLOCKS_PER_CALL], "after": insert_after},
            timeout=60,
        )
        if r.status_code == 200:
            print(f"  OK: {len(section_blocks)} blocks inserted")
            # Handle overflow
            if len(section_blocks) > MAX_BLOCKS_PER_CALL:
                remaining = section_blocks[MAX_BLOCKS_PER_CALL:]
                append_blocks(token, PAGE_ID, remaining)
        else:
            print(f"  Insert failed ({r.status_code}), falling back to append...")
            append_blocks(token, PAGE_ID, section_blocks)
    else:
        print("  QA section not found, appending to end...")
        append_blocks(token, PAGE_ID, section_blocks)

    print(f"\nDone! {len(mkt_blocks)} blocks uploaded.")
    print(f"Check: https://www.notion.so/{PAGE_ID.replace('-', '')}")


if __name__ == "__main__":
    main()
