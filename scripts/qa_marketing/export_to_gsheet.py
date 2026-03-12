#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export ALL QA results (V1 + Context + V2 + V3) to Google Sheet.

Reads all 4 result sets and writes Q&A pairs to the specified Google Sheet,
each phase on a separate tab.
"""

import json
import sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Config ──
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from app.config import get_settings

BASE_DIR = Path(__file__).resolve().parent
SPREADSHEET_ID = "14alsi_x_P7psBNjm81EMQaoPxbTi-yCoII9RYKjv3WA"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TABLE_LABELS = {
    "advertising": "광고비", "amazon_search": "아마존검색",
    "influencer": "인플루언서", "marketing_cost": "마케팅비용",
    "meta_ads": "메타광고", "platform": "플랫폼매출",
    "product": "제품", "review_amazon": "리뷰-아마존",
    "review_qoo10": "리뷰-큐텐", "review_shopee": "리뷰-쇼피",
    "review_smartstore": "리뷰-스마트스토어", "sales_all": "통합매출",
    "shopify": "쇼피파이",
}


def get_service():
    settings = get_settings()
    creds = Credentials.from_service_account_file(
        settings.google_application_credentials, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)


def load_results(directory: Path, prefix: str) -> list[dict]:
    """Load result files from a directory matching prefix."""
    results = []
    for f in sorted(directory.glob(f"{prefix}*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        results.extend(data)
    return results


def build_rows(results: list[dict], phase: str) -> list[list[str]]:
    """Convert results to spreadsheet rows (9 columns)."""
    rows = []
    for i, r in enumerate(results, 1):
        table = r.get("table", "")
        rows.append([
            str(i),
            r.get("id", ""),
            phase,
            TABLE_LABELS.get(table, table),
            r.get("category", ""),
            r.get("query", ""),
            r.get("answer_preview", ""),
            r.get("status", ""),
            str(r.get("time", "")),
        ])
    return rows


def build_rows_v2(results: list[dict], phase: str) -> list[list[str]]:
    """Convert results to spreadsheet rows (10 columns, with 사용쿼리)."""
    rows = []
    for i, r in enumerate(results, 1):
        table = r.get("table", "")
        rows.append([
            str(i),
            r.get("id", ""),
            phase,
            TABLE_LABELS.get(table, table),
            r.get("category", ""),
            r.get("query", ""),
            r.get("answer_preview", ""),
            r.get("used_sql", ""),  # 사용쿼리 (stored if available)
            r.get("status", ""),
            str(r.get("time", "")),
        ])
    return rows


def ensure_sheet(service, spreadsheet_id: str, title: str, sheet_id: int):
    """Create a sheet tab if it doesn't exist."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if title not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title, "sheetId": sheet_id}}}]},
        ).execute()
        print(f"  Created tab: {title}")
    return sheet_id


def write_to_tab(service, spreadsheet_id: str, tab_name: str, sheet_id: int, header: list, rows: list):
    """Write header + rows to a specific tab."""
    all_rows = [header] + rows
    needed_rows = len(all_rows) + 10

    # Expand grid
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"rowCount": needed_rows, "columnCount": 12},
                },
                "fields": "gridProperties(rowCount,columnCount)",
            }
        }]},
    ).execute()

    # Clear
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=tab_name,
    ).execute()

    # Write in batches
    BATCH_SIZE = 1000
    written = 0
    for start in range(0, len(all_rows), BATCH_SIZE):
        batch = all_rows[start:start + BATCH_SIZE]
        range_str = f"'{tab_name}'!A{start + 1}"
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_str,
            valueInputOption="RAW",
            body={"values": batch},
        ).execute()
        written += len(batch)

    # Format header
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    }},
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]},
    ).execute()

    print(f"  [{tab_name}] {written} rows written")
    return written


def main():
    service = get_service()

    # ── Load all results ──
    print("Loading all QA results...")

    v1_results = load_results(BASE_DIR / "results", "results_")
    print(f"  V1 Original:    {len(v1_results):5d}")

    ctx_results = load_results(BASE_DIR / "results_context", "context_")
    print(f"  Context:        {len(ctx_results):5d}")

    v2_results = load_results(BASE_DIR / "results_v2", "results_v2_")
    print(f"  V2 Variation:   {len(v2_results):5d}")

    v3_results = load_results(BASE_DIR / "results_v3", "results_v3_")
    print(f"  V3 Pipeline:    {len(v3_results):5d}")

    grand_total = len(v1_results) + len(ctx_results) + len(v2_results) + len(v3_results)
    print(f"  Grand Total:    {grand_total}")

    # ── Build rows per phase ──
    header = ["No", "ID", "Phase", "테이블", "카테고리", "질문", "답변 (요약)", "상태", "응답시간(초)"]

    v1_rows = build_rows(v1_results, "V1-Original")
    ctx_rows = build_rows(ctx_results, "Context")
    v2_rows = build_rows(v2_results, "V2-Variation")
    v3_rows = build_rows(v3_results, "V3-Pipeline")

    # ── Combined tab (all in one) on 시트1 ──
    print("\nWriting combined tab (시트1)...")
    all_rows = v1_rows + ctx_rows + v2_rows + v3_rows
    # Re-number
    for i, row in enumerate(all_rows):
        row[0] = str(i + 1)

    write_to_tab(service, SPREADSHEET_ID, "시트1", 0, header, all_rows)

    # ── Per-phase tabs ──
    phases = [
        ("V1-Original (3900)", 1, v1_rows),
        ("V2-Variation (3900)", 2, v2_rows),
        ("Context (260)", 3, ctx_rows),
        ("V3-Pipeline", 4, v3_rows),
    ]

    for tab_name, sid, rows in phases:
        if not rows:
            continue
        print(f"\nWriting {tab_name}...")
        ensure_sheet(service, SPREADSHEET_ID, tab_name, sid)
        # Re-number within tab
        for i, row in enumerate(rows):
            row[0] = str(i + 1)
        write_to_tab(service, SPREADSHEET_ID, tab_name, sid, header, rows)

    # ── 시트2: V3 results with 사용쿼리 column ──
    print("\nWriting 시트2 (V3 with 사용쿼리)...")
    header_v2 = ["No", "ID", "Phase", "테이블", "카테고리", "질문", "답변 (요약)", "사용쿼리", "상태", "응답시간(초)"]
    v3_rows_v2 = build_rows_v2(v3_results, "V3-Pipeline")
    for i, row in enumerate(v3_rows_v2):
        row[0] = str(i + 1)
    ensure_sheet(service, SPREADSHEET_ID, "시트2", 1496744476)
    write_to_tab(service, SPREADSHEET_ID, "시트2", 1496744476, header_v2, v3_rows_v2)

    print(f"\nDone! {len(all_rows)} total Q&A written across tabs.")
    print(f"  https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")


if __name__ == "__main__":
    main()
