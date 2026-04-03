"""Crawl Notion page URLs via Playwright and update team_resources description.

For pages that Notion API can't read (external/shared pages),
uses Playwright to visit the URL and extract visible text content.

Usage:
    python scripts/crawl_notion_pages.py --teams PEOPLE IT CS
    python scripts/crawl_notion_pages.py --teams PEOPLE --dry-run
"""
import os
import sys
import re
import argparse
import time
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

import structlog
logger = structlog.get_logger(__name__)


def get_pages_to_crawl(teams: List[str], min_desc_len: int = 200) -> List[Dict]:
    """Get Notion page URLs with empty/short descriptions from team_resources.

    Args:
        teams: Team names to crawl.
        min_desc_len: Pages with description shorter than this will be re-crawled.
                      Default 200 to catch pages where only toggle titles were captured.
    """
    from app.db.mariadb import fetch_all
    placeholders = ",".join(["%s"] * len(teams))
    rows = fetch_all(
        f"SELECT id, team, node_type, name, url, description FROM team_resources "
        f"WHERE team IN ({placeholders}) "
        f"AND url LIKE '%%notion.so%%' "
        f"AND node_type IN ('page','database') "
        f"AND (description IS NULL OR description = '' OR LENGTH(description) < %s) "
        f"ORDER BY team, depth, id",
        tuple(teams) + (min_desc_len,)
    )
    return rows


def crawl_page_playwright(url: str, timeout_ms: int = 15000) -> str:
    """Visit a Notion page with Playwright and extract text content."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(4000)

            # Expand all toggle blocks to reveal hidden content
            try:
                # Method 1: Click triangle/arrow icons in toggle blocks
                toggle_selectors = [
                    "div[class*='toggleTriangle']",
                    "div[role='button'][class*='triangle']",
                    "svg[class*='triangle']",
                    "div[class*='toggle'] > div:first-child",
                    "details > summary",
                ]
                expanded = 0
                for sel in toggle_selectors:
                    try:
                        els = page.query_selector_all(sel)
                        for el in els:
                            try:
                                el.click()
                                expanded += 1
                            except Exception:
                                pass
                    except Exception:
                        pass
                # Method 2: JavaScript to open all <details> elements
                page.evaluate("""() => {
                    document.querySelectorAll('details').forEach(d => d.open = true);
                    // Notion-specific: click all collapsed toggles
                    document.querySelectorAll('[aria-expanded="false"]').forEach(el => el.click());
                }""")
                if expanded > 0:
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            # Extract page title
            title = ""
            try:
                title_el = page.query_selector("[data-block-id] .notranslate, .notion-page-block .notranslate, h1")
                if title_el:
                    title = title_el.inner_text().strip()
            except:
                pass

            # Extract main content text
            content_parts = []

            # Try Notion-specific selectors
            selectors = [
                ".notion-page-content",
                ".notion-scroller",
                "[class*='notion-page-content']",
                "main",
                "article",
                ".layout-content",
            ]

            for sel in selectors:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if len(text) > 50:
                        content_parts.append(text)
                        break

            # Fallback: get all visible text
            if not content_parts:
                body = page.query_selector("body")
                if body:
                    text = body.inner_text().strip()
                    # Remove Notion chrome (sidebar, toolbar)
                    lines = text.split("\n")
                    # Skip first ~10 lines (usually nav/sidebar)
                    content_lines = [l.strip() for l in lines if l.strip() and len(l.strip()) > 2]
                    content_parts.append("\n".join(content_lines[:200]))

            full_text = "\n".join(content_parts)
            # Clean up
            full_text = re.sub(r'\n{3,}', '\n\n', full_text)
            # Truncate to reasonable size
            if len(full_text) > 5000:
                full_text = full_text[:5000] + "..."

            return title, full_text
        except Exception as e:
            logger.warning("playwright_error", url=url[:60], error=str(e)[:80])
            return "", ""
        finally:
            browser.close()


def update_description(row_id: int, title: str, description: str):
    """Update team_resources row with crawled content (always overwrite if new content is longer)."""
    from app.db.mariadb import execute
    # Update name if it was "Untitled" and we found a real title
    if title:
        execute(
            "UPDATE team_resources SET name = %s WHERE id = %s AND (name = 'Untitled' OR name = '')",
            (title[:500], row_id)
        )
    # Always update description if new content is longer than existing
    execute(
        "UPDATE team_resources SET description = %s WHERE id = %s AND (description IS NULL OR LENGTH(description) < LENGTH(%s))",
        (description[:10000], row_id, description[:10000])
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", nargs="+", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--min-desc", type=int, default=200,
                        help="Re-crawl pages with description shorter than this (default 200)")
    args = parser.parse_args()

    pages = get_pages_to_crawl(args.teams, min_desc_len=args.min_desc)
    print(f"Found {len(pages)} pages to crawl for teams: {args.teams}")

    crawled = 0
    for row in pages[:args.limit]:
        url = row["url"]
        if not url or not url.startswith("http"):
            continue

        print(f"\n[{row['team']}] {row['name'][:40]} → {url[:60]}")
        title, text = crawl_page_playwright(url)

        if text:
            preview = text[:150].replace("\n", " ")
            print(f"  ✓ title='{title[:30]}' content={len(text)}자: {preview}...")
            if not args.dry_run:
                update_description(row["id"], title, text)
                print(f"  → DB updated (id={row['id']})")
            crawled += 1
        else:
            print(f"  ✗ No content extracted")

    print(f"\nDone: {crawled}/{len(pages)} pages crawled")


if __name__ == "__main__":
    main()
