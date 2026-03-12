#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add 2026-03-11 update log to Notion page."""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.upload_to_notion import (
    get_token, heading2, heading3, paragraph, bulleted, callout, divider,
    toggle, table_block, append_blocks, append_blocks_get_ids,
    PAGE_ID,
)


def build_update_log():
    """Build blocks for 2026-03-11 update log."""
    blocks = []

    blocks.append(heading2("2026-03-11 Updates"))

    # 1. QA V3 Pipeline Progress
    blocks.append(heading3("QA V3 Pipeline (6,275/6,500)"))
    blocks.append(callout(
        "V3 Pipeline: 13 tables x 500 questions = 6,500 target\n"
        "Current: 6,275/6,500 (96.5%) - Shopify 276/500 remaining",
        "🧪"
    ))

    blocks.append(table_block([
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
        ["review_shopee", "499", "234", "265", "0"],
        ["review_smartstore", "499", "238", "259", "2"],
        ["sales_all", "500", "282", "218", "0"],
        ["shopify", "276", "196", "71", "9"],
    ]))

    blocks.append(paragraph(
        "Overall: OK 4,900 (78.1%) | WARN 1,362 (21.7%) | FAIL 13 (0.2%)\n"
        "Average times: OK 39.7s | WARN 70.9s | FAIL 112.9s"
    ))

    # 2. Performance Optimization
    blocks.append(heading3("WARN/FAIL Performance Optimization"))
    blocks.append(callout(
        "3 key optimizations applied to reduce WARN (60-90s) and FAIL (>90s) response times",
        "⚡"
    ))
    blocks.append(bulleted("Removed streaming delay (0.01s per chunk) in routes.py - saves 1-3s per response"))
    blocks.append(bulleted("Reduced LLM prompt preview cap: 8KB -> 5KB, text truncation 150 -> 80 chars"))
    blocks.append(bulleted("Smart preview text truncation in _build_smart_preview: 150 -> 80 chars"))
    blocks.append(paragraph(
        "Expected improvement: WARN avg 70.9s -> ~58-62s (18-22% reduction)\n"
        "Heaviest tables: review_shopee (53% WARN), review_smartstore (52% WARN), sales_all (44% WARN)"
    ))

    # 3. Google Sheet Export
    blocks.append(heading3("Google Sheet QA Export"))
    blocks.append(bulleted("All QA results exported to Google Sheet (V1+Context+V2+V3)"))
    blocks.append(bulleted("Added 시트2 tab with V3 results: No, ID, Phase, Table, Category, Question, Answer, SQL, Status, Time"))
    blocks.append(bulleted("https://docs.google.com/spreadsheets/d/14alsi_x_P7psBNjm81EMQaoPxbTi-yCoII9RYKjv3WA/edit"))

    # 4. Bottleneck Analysis
    blocks.append(heading3("Pipeline Bottleneck Analysis"))
    blocks.append(table_block([
        ["Step", "Time", "Notes"],
        ["generate_sql (Flash)", "5-10s", "SQL generation from NL query"],
        ["validate_sql", "<0.1s", "Regex/keyword safety check"],
        ["execute_sql (BigQuery)", "5-30s", "Table size dependent"],
        ["format_answer (Flash)", "8-15s", "Parallel with chart gen"],
        ["chart_gen (Flash)", "4-8s", "Runs parallel with answer"],
    ]))

    blocks.append(divider())
    return blocks


def main():
    token = get_token()
    print(f"Target page: {PAGE_ID}")

    blocks = build_update_log()
    print(f"Appending {len(blocks)} blocks...")
    append_blocks(token, PAGE_ID, blocks)
    print("Done!")


if __name__ == "__main__":
    main()
