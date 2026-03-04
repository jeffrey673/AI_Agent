"""Markdown to PDF converter using fpdf2 + markdown.

Converts Korean-heavy markdown documents to styled PDF.
Uses 맑은 고딕 (Malgun Gothic) for full Korean support.
"""

import html
import re
import sys
from pathlib import Path

from fpdf import FPDF

# ── Constants ──

FONT_DIR = "C:/Windows/Fonts"
FONT_REGULAR = f"{FONT_DIR}/malgun.ttf"
FONT_BOLD = f"{FONT_DIR}/malgunbd.ttf"

PAGE_W = 210  # A4 mm
MARGIN_L = 15
MARGIN_R = 15
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

# Colors
COLOR_H1 = (30, 58, 138)       # Dark blue
COLOR_H2 = (37, 99, 235)       # Blue
COLOR_H3 = (59, 130, 246)      # Light blue
COLOR_H4 = (107, 114, 128)     # Gray
COLOR_TEXT = (31, 41, 55)       # Dark gray
COLOR_CODE_BG = (243, 244, 246) # Light gray
COLOR_TABLE_HEADER = (37, 99, 235)
COLOR_TABLE_ALT = (248, 250, 252)
COLOR_LINK = (37, 99, 235)
COLOR_QUOTE_BAR = (234, 179, 8) # Amber
COLOR_QUOTE_BG = (254, 252, 232)


class MarkdownPDF(FPDF):
    """PDF generator that renders markdown with Korean font support."""

    def __init__(self, title: str = ""):
        super().__init__()
        self.doc_title = title
        self.set_auto_page_break(auto=True, margin=20)

        # Register Korean fonts
        self.add_font("MalgunGothic", "", FONT_REGULAR)
        self.add_font("MalgunGothic", "B", FONT_BOLD)

        # Code font — use Malgun Gothic for Unicode support (box-drawing, Korean)
        self.add_font("CodeFont", "", FONT_REGULAR)

    def header(self):
        if self.page_no() > 1:
            self.set_font("MalgunGothic", "", 7)
            self.set_text_color(156, 163, 175)
            self.cell(0, 6, self.doc_title, align="L")
            self.cell(0, 6, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(229, 231, 235)
            self.line(MARGIN_L, self.get_y(), PAGE_W - MARGIN_R, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("MalgunGothic", "", 7)
        self.set_text_color(156, 163, 175)
        self.cell(0, 10, f"{self.page_no()}", align="C")


def _clean(text: str) -> str:
    """Remove markdown inline formatting for plain text output."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    return text.strip()


def _parse_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """Parse markdown table lines into headers + rows."""
    if len(lines) < 2:
        return [], []

    def split_row(line: str) -> list[str]:
        line = line.strip()
        if line.startswith('|'):
            line = line[1:]
        if line.endswith('|'):
            line = line[:-1]
        return [c.strip() for c in line.split('|')]

    headers = split_row(lines[0])
    rows = []
    for line in lines[2:]:  # Skip separator line
        if '|' in line and not re.match(r'^\s*\|[-:\s|]+\|\s*$', line):
            rows.append(split_row(line))
    return headers, rows


def render_markdown_to_pdf(md_path: str, pdf_path: str):
    """Convert a markdown file to PDF."""
    md_text = Path(md_path).read_text(encoding="utf-8")
    lines = md_text.split('\n')

    # Extract title from first H1
    title = "Document"
    for line in lines:
        if line.startswith('# ') and not line.startswith('## '):
            title = line[2:].strip()
            break

    pdf = MarkdownPDF(title=title)
    pdf.set_left_margin(MARGIN_L)
    pdf.set_right_margin(MARGIN_R)
    pdf.add_page()

    # ── Cover / Title ──
    pdf.ln(30)
    pdf.set_font("MalgunGothic", "B", 24)
    pdf.set_text_color(*COLOR_H1)

    # Word-wrap title
    title_clean = _clean(title)
    pdf.multi_cell(CONTENT_W, 12, title_clean, align="C")
    pdf.ln(8)

    # Subtitle (first blockquote lines)
    subtitle_lines = []
    for line in lines:
        if line.startswith('> '):
            subtitle_lines.append(line[2:].strip())
        elif subtitle_lines and not line.startswith('>'):
            break

    if subtitle_lines:
        pdf.set_font("MalgunGothic", "", 9)
        pdf.set_text_color(107, 114, 128)
        for sl in subtitle_lines:
            pdf.cell(0, 5, _clean(sl), align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    pdf.ln(10)
    pdf.set_draw_color(37, 99, 235)
    pdf.set_line_width(0.5)
    center_x = PAGE_W / 2
    pdf.line(center_x - 30, pdf.get_y(), center_x + 30, pdf.get_y())
    pdf.ln(15)

    # ── Parse and Render ──
    i = 0
    in_code_block = False
    code_lines = []
    table_lines = []
    skip_initial_meta = True  # Skip title and initial blockquote

    while i < len(lines):
        line = lines[i]

        # Skip initial title + blockquote (already rendered as cover)
        if skip_initial_meta:
            if line.startswith('# ') and not line.startswith('## '):
                i += 1
                continue
            if line.startswith('> '):
                i += 1
                continue
            if line.strip() == '' and i < 10:
                i += 1
                continue
            if line.strip() == '---' and i < 15:
                i += 1
                continue
            skip_initial_meta = False

        # ── Code blocks ──
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block — render
                _render_code_block(pdf, code_lines)
                code_lines = []
                in_code_block = False
            else:
                # Flush any pending table
                if table_lines:
                    _render_table(pdf, table_lines)
                    table_lines = []
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # ── Table accumulation ──
        if '|' in line and re.match(r'^\s*\|', line):
            table_lines.append(line)
            i += 1
            continue
        elif table_lines:
            _render_table(pdf, table_lines)
            table_lines = []

        # ── Horizontal rule ──
        if re.match(r'^-{3,}\s*$', line.strip()):
            pdf.ln(3)
            pdf.set_draw_color(229, 231, 235)
            pdf.set_line_width(0.3)
            pdf.line(MARGIN_L, pdf.get_y(), PAGE_W - MARGIN_R, pdf.get_y())
            pdf.ln(5)
            i += 1
            continue

        # ── Headers ──
        if line.startswith('#### '):
            _render_heading(pdf, line[5:], level=4)
            i += 1
            continue
        if line.startswith('### '):
            _render_heading(pdf, line[4:], level=3)
            i += 1
            continue
        if line.startswith('## '):
            _render_heading(pdf, line[3:], level=2)
            i += 1
            continue
        if line.startswith('# '):
            _render_heading(pdf, line[2:], level=1)
            i += 1
            continue

        # ── Blockquotes ──
        if line.startswith('> '):
            quote_lines = []
            while i < len(lines) and lines[i].startswith('> '):
                quote_lines.append(lines[i][2:])
                i += 1
            _render_blockquote(pdf, quote_lines)
            continue

        # ── List items ──
        list_match = re.match(r'^(\s*)([-*]|\d+\.)\s+(.+)', line)
        if list_match:
            indent_level = len(list_match.group(1)) // 2
            bullet = list_match.group(2)
            text = list_match.group(3)
            _render_list_item(pdf, text, indent_level, bullet)
            i += 1
            continue

        # ── Empty lines ──
        if line.strip() == '':
            pdf.ln(2)
            i += 1
            continue

        # ── Regular paragraph ──
        _render_paragraph(pdf, line)
        i += 1

    # Flush remaining
    if table_lines:
        _render_table(pdf, table_lines)
    if code_lines:
        _render_code_block(pdf, code_lines)

    pdf.output(pdf_path)
    print(f"PDF saved: {pdf_path}")


def _render_heading(pdf: MarkdownPDF, text: str, level: int):
    """Render a heading with appropriate styling."""
    text = _clean(text)

    configs = {
        1: (18, COLOR_H1, 14, 8),
        2: (14, COLOR_H2, 10, 6),
        3: (11, COLOR_H3, 8, 4),
        4: (10, COLOR_H4, 6, 3),
    }
    size, color, space_before, space_after = configs.get(level, configs[4])

    # Page break check
    if pdf.get_y() > 260:
        pdf.add_page()

    pdf.ln(space_before)

    if level <= 2:
        pdf.set_draw_color(*color)
        pdf.set_line_width(0.3 if level == 2 else 0.5)
        pdf.line(MARGIN_L, pdf.get_y(), PAGE_W - MARGIN_R, pdf.get_y())
        pdf.ln(3)

    pdf.set_font("MalgunGothic", "B", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(CONTENT_W, size * 0.55, text)
    pdf.ln(space_after)


def _render_paragraph(pdf: MarkdownPDF, text: str):
    """Render a paragraph with inline formatting."""
    pdf.set_font("MalgunGothic", "", 9)
    pdf.set_text_color(*COLOR_TEXT)

    clean = _clean(text)
    pdf.multi_cell(CONTENT_W, 5, clean)
    pdf.ln(1)


def _render_list_item(pdf: MarkdownPDF, text: str, indent: int = 0, bullet: str = "-"):
    """Render a list item."""
    pdf.set_font("MalgunGothic", "", 9)
    pdf.set_text_color(*COLOR_TEXT)

    indent_mm = 5 + indent * 6
    text_w = CONTENT_W - indent_mm - 4

    x = MARGIN_L + indent_mm
    y = pdf.get_y()

    # Bullet
    if bullet in ('-', '*'):
        marker = "\u2022"  # bullet char
    else:
        marker = bullet

    pdf.set_x(x)
    pdf.cell(4, 5, marker, new_x="END")
    pdf.multi_cell(text_w, 5, _clean(text))
    pdf.ln(0.5)


def _render_code_block(pdf: MarkdownPDF, lines: list[str]):
    """Render a code block with background."""
    if not lines:
        return

    # Check if we need a page break
    block_height = len(lines) * 4.5 + 6
    if pdf.get_y() + block_height > 275:
        pdf.add_page()

    pdf.ln(2)
    start_y = pdf.get_y()

    # Draw background
    pdf.set_fill_color(*COLOR_CODE_BG)

    # Render each line
    pdf.set_font("CodeFont", "", 7)
    pdf.set_text_color(55, 65, 81)

    temp_y = start_y + 3
    for line in lines:
        if temp_y > 275:
            # Fill background up to current point
            pdf.rect(MARGIN_L, start_y, CONTENT_W, temp_y - start_y + 3, 'F')
            pdf.add_page()
            start_y = pdf.get_y()
            temp_y = start_y + 3
            pdf.set_fill_color(*COLOR_CODE_BG)

        pdf.set_xy(MARGIN_L + 3, temp_y)
        # Truncate very long lines
        display_line = line[:120] if len(line) > 120 else line
        pdf.cell(CONTENT_W - 6, 4.5, display_line)
        temp_y += 4.5

    # Fill background
    pdf.rect(MARGIN_L, start_y, CONTENT_W, temp_y - start_y + 3, 'F')

    # Re-render text on top of background
    temp_y = start_y + 3
    pdf.set_font("CodeFont", "", 7)
    pdf.set_text_color(55, 65, 81)
    for line in lines:
        if temp_y > 275:
            pdf.add_page()
            start_y = pdf.get_y()
            temp_y = start_y + 3
        pdf.set_xy(MARGIN_L + 3, temp_y)
        display_line = line[:120] if len(line) > 120 else line
        pdf.cell(CONTENT_W - 6, 4.5, display_line)
        temp_y += 4.5

    pdf.set_y(temp_y + 3)
    pdf.ln(2)


def _render_table(pdf: MarkdownPDF, lines: list[str]):
    """Render a markdown table."""
    headers, rows = _parse_table(lines)
    if not headers:
        return

    n_cols = len(headers)
    if n_cols == 0:
        return

    # Calculate column widths based on content
    col_widths = []
    for j in range(n_cols):
        max_len = len(_clean(headers[j]))
        for row in rows:
            if j < len(row):
                max_len = max(max_len, len(_clean(row[j])))
        col_widths.append(max_len)

    # Normalize widths to fit page
    total_chars = sum(col_widths) or 1
    col_widths_mm = [max(15, (w / total_chars) * CONTENT_W) for w in col_widths]

    # Adjust to exactly fill content width
    total_mm = sum(col_widths_mm)
    scale = CONTENT_W / total_mm
    col_widths_mm = [w * scale for w in col_widths_mm]

    row_height = 6

    # Check page space
    table_height = (len(rows) + 1) * row_height + 4
    if pdf.get_y() + min(table_height, 50) > 270:
        pdf.add_page()

    pdf.ln(2)

    # Header row
    pdf.set_fill_color(*COLOR_TABLE_HEADER)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("MalgunGothic", "B", 8)

    x_start = MARGIN_L
    for j, hdr in enumerate(headers):
        if j < len(col_widths_mm):
            pdf.set_xy(x_start + sum(col_widths_mm[:j]), pdf.get_y())
            pdf.cell(col_widths_mm[j], row_height, _clean(hdr), border=1, fill=True, align="C")

    pdf.ln(row_height)

    # Data rows
    pdf.set_font("MalgunGothic", "", 8)
    for ri, row in enumerate(rows):
        # Page break check
        if pdf.get_y() > 270:
            pdf.add_page()

        if ri % 2 == 1:
            pdf.set_fill_color(*COLOR_TABLE_ALT)
            fill = True
        else:
            fill = False
            pdf.set_fill_color(255, 255, 255)

        pdf.set_text_color(*COLOR_TEXT)

        y_before = pdf.get_y()
        for j in range(n_cols):
            cell_text = _clean(row[j]) if j < len(row) else ""
            pdf.set_xy(x_start + sum(col_widths_mm[:j]), y_before)
            pdf.cell(col_widths_mm[j], row_height, cell_text, border=1, fill=fill or (ri % 2 == 1))

        pdf.ln(row_height)

    pdf.ln(3)


def _render_blockquote(pdf: MarkdownPDF, lines: list[str]):
    """Render a blockquote with amber left bar."""
    pdf.ln(2)
    text = " ".join(_clean(l) for l in lines)

    start_y = pdf.get_y()

    # Text
    pdf.set_font("MalgunGothic", "", 9)
    pdf.set_text_color(107, 114, 128)
    pdf.set_x(MARGIN_L + 6)
    pdf.multi_cell(CONTENT_W - 8, 5, text)

    end_y = pdf.get_y()

    # Left bar
    pdf.set_draw_color(*COLOR_QUOTE_BAR)
    pdf.set_line_width(1.0)
    pdf.line(MARGIN_L + 2, start_y - 1, MARGIN_L + 2, end_y + 1)

    pdf.ln(3)


# ── Main ──

if __name__ == "__main__":
    base = Path("C:/Users/DB_PC/Desktop/python_bcj/AI_Agent/docs")

    files = [
        ("SKIN1004_AI_Technical_Architecture.md", "SKIN1004_AI_Technical_Architecture_2026-02-26.pdf"),
        ("SKIN1004_AI_Update_History.md", "SKIN1004_AI_Update_History_2026-02-26.pdf"),
        ("SKIN1004_Enterprise_AI_PRD_v6.md", "SKIN1004_Enterprise_AI_PRD_v6_2026-02-26.pdf"),
    ]

    for md_name, pdf_name in files:
        md_path = base / md_name
        pdf_path = base / pdf_name
        if md_path.exists():
            print(f"Converting: {md_name} ...")
            render_markdown_to_pdf(str(md_path), str(pdf_path))
        else:
            print(f"Not found: {md_path}")

    print("\nDone!")
