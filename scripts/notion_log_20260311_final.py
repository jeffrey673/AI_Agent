#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add 2026-03-11 FINAL update log to Notion page."""

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
    """Build blocks for 2026-03-11 final update log."""
    blocks = []

    blocks.append(heading2("2026-03-11 Final Updates"))

    # 1. QA V3 Pipeline - COMPLETE
    blocks.append(heading3("QA V3 Pipeline (6,500/6,500) - COMPLETE"))
    blocks.append(callout(
        "V3 Pipeline: 13 tables x 500 questions = 6,500 target\n"
        "COMPLETE: 6,500/6,500 (100%) - All tables done\n"
        "FAIL: 13 -> 0 (eliminated after optimization)",
        "✅"
    ))

    blocks.append(table_block([
        ["Table", "Done", "OK", "WARN", "FAIL", "SQL"],
        ["advertising", "500", "473", "27", "0", "500"],
        ["amazon_search", "500", "440", "60", "0", "496"],
        ["influencer", "500", "470", "30", "0", "500"],
        ["marketing_cost", "500", "419", "81", "0", "500"],
        ["meta_ads", "500", "447", "53", "0", "500"],
        ["platform", "500", "414", "86", "0", "496"],
        ["product", "500", "464", "36", "0", "500"],
        ["review_amazon", "500", "434", "66", "0", "500"],
        ["review_qoo10", "500", "390", "110", "0", "500"],
        ["review_shopee", "500", "235", "265", "0", "498"],
        ["review_smartstore", "500", "240", "260", "0", "499"],
        ["sales_all", "500", "282", "218", "0", "500"],
        ["shopify", "500", "424", "76", "0", "500"],
    ]))

    blocks.append(paragraph(
        "Overall: OK 5,132 (79.0%) | WARN 1,368 (21.0%) | FAIL 0 (0.0%)\n"
        "SQL Generated: 6,489/6,500 (99.8%)"
    ))

    # 2. Performance Optimization Results
    blocks.append(heading3("WARN/FAIL Performance Optimization - Results"))
    blocks.append(callout(
        "3 optimizations applied -> FAIL 13 -> 0 eliminated",
        "⚡"
    ))
    blocks.append(bulleted("Streaming delay 제거 (routes.py) - 응답당 1-3s 절감"))
    blocks.append(bulleted("LLM prompt preview cap 축소: 8KB -> 5KB"))
    blocks.append(bulleted("Text truncation 축소: 150 -> 80 chars (_truncate_row, _build_smart_preview)"))
    blocks.append(paragraph(
        "Before: OK 4,900 (78.1%) | WARN 1,362 (21.7%) | FAIL 13 (0.2%)\n"
        "After:  OK 5,132 (79.0%) | WARN 1,368 (21.0%) | FAIL 0 (0.0%)\n"
        "WARN heavy tables: review_shopee (53%), review_smartstore (52%), sales_all (44%)"
    ))

    # 3. SQL Generation (used_sql)
    blocks.append(heading3("SQL Query Generation (used_sql)"))
    blocks.append(callout(
        "6,489/6,500 results now have generated SQL stored\n"
        "Gemini Flash direct call, 3 concurrent workers, ~3-5s per query",
        "🔧"
    ))
    blocks.append(bulleted("generate_sql_only.py: Flash LLM으로 SQL만 생성 (BQ 실행 없이)"))
    blocks.append(bulleted("ThreadPoolExecutor 3 workers, ~28 queries/min"))
    blocks.append(bulleted("results_v3_{table}.json에 used_sql 필드 저장"))

    # 4. Google Sheet Export
    blocks.append(heading3("Google Sheet Export - Updated"))
    blocks.append(callout(
        "14,560 total Q&A across all tabs\n"
        "시트2: V3 6,500 results with SQL query column",
        "📊"
    ))
    blocks.append(table_block([
        ["Tab", "Count", "Notes"],
        ["시트1 (Combined)", "14,560", "V1+Context+V2+V3 all"],
        ["V1-Original", "3,900", "13 tables x 300"],
        ["V2-Variation", "3,900", "13 tables x 300"],
        ["Context", "260", "20 per table"],
        ["V3-Pipeline", "6,500", "13 tables x 500"],
        ["시트2", "6,500", "V3 + SQL query column"],
    ]))
    blocks.append(bulleted("시트2 columns: No, ID, Phase, 테이블, 카테고리, 질문, 답변(요약), 사용쿼리, 상태, 응답시간"))
    blocks.append(bulleted("https://docs.google.com/spreadsheets/d/14alsi_x_P7psBNjm81EMQaoPxbTi-yCoII9RYKjv3WA/edit"))

    # 5. Pipeline Bottleneck Analysis
    blocks.append(heading3("Pipeline Bottleneck Analysis"))
    blocks.append(table_block([
        ["Step", "Time", "Notes"],
        ["generate_sql (Flash)", "5-10s", "SQL generation from NL query"],
        ["validate_sql", "<0.1s", "Regex/keyword safety check"],
        ["execute_sql (BigQuery)", "5-30s", "Table size dependent"],
        ["format_answer (Flash)", "8-15s", "Parallel with chart gen"],
        ["chart_gen (Flash)", "4-8s", "Runs parallel with answer"],
    ]))

    # 6. Total QA Coverage Summary
    blocks.append(heading3("Total QA Coverage Summary"))
    blocks.append(table_block([
        ["Phase", "Questions", "Purpose"],
        ["V1 Original", "3,900", "Base coverage (13 tables x 300)"],
        ["V2 Variation", "3,900", "Rephrased queries"],
        ["Context", "260", "Context-dependent queries"],
        ["V3 Pipeline", "6,500", "Full pipeline test (13 x 500)"],
        ["TOTAL", "14,560", "All phases combined"],
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
