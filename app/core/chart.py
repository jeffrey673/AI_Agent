"""Chart generation module using matplotlib.

Generates charts styled after Looker Studio dark theme.
Saves as PNG files served via FastAPI static endpoint.
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# --- Looker Studio Dark Theme Constants ---
DARK_BG = "#1e1e1e"
GRID_COLOR = "#333333"
TEXT_COLOR = "#cccccc"
TITLE_COLOR = "#ffffff"
LABEL_COLOR = "#999999"

# Line chart: solid primary, dashed comparisons (Gross/MoM/YoY style)
LINE_COLORS = ["#4285F4", "#EA4335", "#34A853", "#FBBC04", "#FF6D01", "#46BDC6"]
LINE_STYLES = ["-", "--", "--", "-.", "-.", ":"]

# Bar/Donut chart colors - vibrant on dark bg
BAR_COLORS = [
    "#EA4335", "#4285F4", "#FBBC04", "#34A853", "#FF6D01",
    "#46BDC6", "#7BAAF7", "#F07B72", "#57BB8A", "#FFD54F",
]


def _setup_korean_font():
    """Configure matplotlib to render Korean text."""
    from matplotlib import font_manager

    korean_fonts = [
        "Malgun Gothic",
        "\ub9d1\uc740 \uace0\ub515",
        "NanumGothic",
        "AppleGothic",
        "NanumBarunGothic",
    ]
    for font_name in korean_fonts:
        fonts = font_manager.findSystemFonts()
        for f in fonts:
            try:
                fp = font_manager.FontProperties(fname=f)
                if font_name.lower() in fp.get_name().lower():
                    plt.rcParams["font.family"] = fp.get_name()
                    plt.rcParams["axes.unicode_minus"] = False
                    logger.info("korean_font_set", font=fp.get_name())
                    return
            except Exception:
                continue

    plt.rcParams["axes.unicode_minus"] = False
    logger.warning("korean_font_not_found")


_setup_korean_font()


def _format_number(val: float) -> str:
    """Format large numbers with Korean units."""
    if abs(val) >= 1e8:
        return f"{val / 1e8:,.1f}\uc5b5"
    elif abs(val) >= 1e4:
        return f"{val / 1e4:,.0f}\ub9cc"
    else:
        return f"{val:,.0f}"


def _apply_dark_theme(fig, ax, chart_type="default"):
    """Apply Looker Studio dark theme to figure and axes."""
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)

    for spine in ax.spines.values():
        spine.set_visible(False)

    if chart_type != "pie":
        ax.grid(axis="y", color=GRID_COLOR, linewidth=0.5, alpha=0.6)
        ax.set_axisbelow(True)

    ax.tick_params(colors=LABEL_COLOR, which="both", labelsize=9)
    ax.xaxis.label.set_color(LABEL_COLOR)
    ax.yaxis.label.set_color(LABEL_COLOR)


CHARTS_DIR = Path(__file__).resolve().parent.parent / "static" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_chart(
    chart_config: Dict[str, Any],
    data: List[Dict[str, Any]],
) -> Optional[str]:
    """Generate a chart and save as PNG file.

    Returns:
        Filename of saved PNG, or None if generation fails.
    """
    try:
        chart_type = chart_config.get("chart_type", "bar")
        x_col = chart_config.get("x_column", "")
        y_col = chart_config.get("y_column", "")
        title = chart_config.get("title", "")
        x_label = chart_config.get("x_label", "")
        y_label = chart_config.get("y_label", "")

        if not data or not x_col or not y_col:
            return None

        # Readability guard: skip chart if too many categories
        max_items = {"bar": 15, "horizontal_bar": 20, "pie": 10, "line": 36}
        limit = max_items.get(chart_type, 20)
        if len(data) > limit:
            logger.info("chart_skipped_too_many_items", chart_type=chart_type, items=len(data), limit=limit)
            return None

        x_values = [str(row.get(x_col, "")) for row in data]

        if isinstance(y_col, list):
            y_series = {}
            for col in y_col:
                y_series[col] = [float(row.get(col, 0) or 0) for row in data]
        else:
            y_values = [float(row.get(y_col, 0) or 0) for row in data]

        fig, ax = plt.subplots(figsize=(12, 5))
        _apply_dark_theme(fig, ax, chart_type)

        # --- Line Chart ---
        if chart_type == "line":
            if isinstance(y_col, list):
                for i, col in enumerate(y_col):
                    style = LINE_STYLES[i % len(LINE_STYLES)]
                    lw = 2.5 if i == 0 else 1.5
                    ms = 6 if i == 0 else 4
                    ax.plot(
                        x_values, y_series[col],
                        linestyle=style, marker="o", markersize=ms,
                        color=LINE_COLORS[i % len(LINE_COLORS)],
                        label=col, linewidth=lw, zorder=3 - i,
                    )
                ax.legend(
                    facecolor=DARK_BG, edgecolor=GRID_COLOR,
                    labelcolor=TEXT_COLOR, fontsize=9, loc="upper left",
                )
            else:
                ax.plot(
                    x_values, y_values,
                    marker="o", markersize=6, color=LINE_COLORS[0],
                    linewidth=2.5, zorder=3, label=y_col,
                )
                ax.legend(
                    facecolor=DARK_BG, edgecolor=GRID_COLOR,
                    labelcolor=TEXT_COLOR, fontsize=9, loc="upper left",
                )
                # Data labels on each point
                for i, val in enumerate(y_values):
                    ax.annotate(
                        _format_number(val),
                        (x_values[i], val),
                        textcoords="offset points",
                        xytext=(0, 12),
                        ha="center", fontsize=8.5,
                        color=TEXT_COLOR, fontweight="bold",
                    )
            if len(x_values) > 8:
                plt.xticks(rotation=45, ha="right")

        # --- Bar Chart ---
        elif chart_type == "bar":
            colors = BAR_COLORS[: len(x_values)]
            bars = ax.bar(
                x_values, y_values,
                color=colors,
                edgecolor="none", width=0.6,
            )
            for bar, val in zip(bars, y_values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    _format_number(val),
                    ha="center", va="bottom",
                    fontsize=9, fontweight="bold", color=TEXT_COLOR,
                )
            # Legend with per-item colors
            from matplotlib.patches import Patch
            legend_handles = [Patch(facecolor=colors[i % len(colors)], label=x_values[i]) for i in range(len(x_values))]
            ax.legend(
                handles=legend_handles,
                facecolor=DARK_BG, edgecolor=GRID_COLOR,
                labelcolor=TEXT_COLOR, fontsize=9, loc="upper right",
            )
            if len(x_values) > 6:
                plt.xticks(rotation=45, ha="right")

        # --- Horizontal Bar Chart ---
        elif chart_type == "horizontal_bar":
            colors = BAR_COLORS[: len(x_values)]
            bars = ax.barh(
                x_values, y_values,
                color=colors,
                edgecolor="none", height=0.6,
            )
            for bar, val in zip(bars, y_values):
                ax.text(
                    bar.get_width(),
                    bar.get_y() + bar.get_height() / 2,
                    " " + _format_number(val),
                    ha="left", va="center",
                    fontsize=9, fontweight="bold", color=TEXT_COLOR,
                )
            # Legend with per-item colors
            from matplotlib.patches import Patch
            legend_handles = [Patch(facecolor=colors[i % len(colors)], label=x_values[i]) for i in range(len(x_values))]
            ax.legend(
                handles=legend_handles,
                facecolor=DARK_BG, edgecolor=GRID_COLOR,
                labelcolor=TEXT_COLOR, fontsize=9, loc="lower right",
            )
            ax.grid(axis="y", visible=False)
            ax.grid(axis="x", color=GRID_COLOR, linewidth=0.5, alpha=0.6)

        # --- Donut Chart (Looker Studio style) ---
        elif chart_type == "pie":
            filtered = [(x, y) for x, y in zip(x_values, y_values) if y > 0]
            if not filtered:
                return None
            pie_labels, pie_values = zip(*filtered)
            wedges, texts, autotexts = ax.pie(
                pie_values,
                labels=pie_labels,
                autopct="%1.1f%%",
                colors=BAR_COLORS[: len(pie_values)],
                startangle=90,
                pctdistance=0.78,
                wedgeprops=dict(width=0.4, edgecolor=DARK_BG, linewidth=2),
            )
            for text in texts:
                text.set_color(TEXT_COLOR)
                text.set_fontsize(9)
            for text in autotexts:
                text.set_color(TITLE_COLOR)
                text.set_fontsize(8)
                text.set_fontweight("bold")

        # --- Stacked Bar ---
        elif chart_type == "stacked_bar" and isinstance(y_col, list):
            import numpy as np

            x_pos = np.arange(len(x_values))
            bottom = np.zeros(len(x_values))
            bar_width = 0.6
            for i, col in enumerate(y_col):
                vals = y_series[col]
                ax.bar(
                    x_pos, vals, bar_width, bottom=bottom,
                    label=col, color=BAR_COLORS[i % len(BAR_COLORS)],
                    edgecolor="none",
                )
                bottom += np.array(vals)
            ax.set_xticks(x_pos)
            ax.set_xticklabels(x_values)
            ax.legend(
                facecolor=DARK_BG, edgecolor=GRID_COLOR,
                labelcolor=TEXT_COLOR, fontsize=9,
            )
            if len(x_values) > 6:
                plt.xticks(rotation=45, ha="right")

        # --- Grouped Bar ---
        elif chart_type == "grouped_bar" and isinstance(y_col, list):
            import numpy as np

            x_pos = np.arange(len(x_values))
            n_groups = len(y_col)
            bar_width = 0.8 / n_groups
            for i, col in enumerate(y_col):
                offset = (i - n_groups / 2 + 0.5) * bar_width
                ax.bar(
                    x_pos + offset, y_series[col], bar_width,
                    label=col, color=BAR_COLORS[i % len(BAR_COLORS)],
                    edgecolor="none",
                )
            ax.set_xticks(x_pos)
            ax.set_xticklabels(x_values)
            ax.legend(
                facecolor=DARK_BG, edgecolor=GRID_COLOR,
                labelcolor=TEXT_COLOR, fontsize=9,
            )
            if len(x_values) > 6:
                plt.xticks(rotation=45, ha="right")

        # --- Common Formatting ---
        if title:
            ax.set_title(title, fontsize=14, fontweight="bold", color=TITLE_COLOR, pad=15)
        if x_label and chart_type != "pie":
            ax.set_xlabel(x_label, fontsize=11, color=LABEL_COLOR)
        if y_label and chart_type not in ("pie", "horizontal_bar"):
            ax.set_ylabel(y_label, fontsize=11, color=LABEL_COLOR)

        if chart_type not in ("pie",):
            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda x, _: _format_number(x))
            )

        plt.tight_layout()

        filename = f"{uuid.uuid4().hex}.png"
        filepath = CHARTS_DIR / filename
        fig.savefig(
            filepath, format="png", dpi=150,
            bbox_inches="tight", facecolor=DARK_BG, edgecolor="none",
        )
        plt.close(fig)
        logger.info("chart_generated", chart_type=chart_type, data_points=len(data), file=filename)
        return filename

    except Exception as e:
        logger.error("chart_generation_failed", error=str(e))
        plt.close("all")
        return None


def get_chart_config_prompt(query: str, sql: str, results_preview: str, row_count: int) -> str:
    """Build a prompt for the LLM to decide chart configuration."""
    return f"""\uc0ac\uc6a9\uc790\uc758 \uc9c8\ubb38\uacfc SQL \uacb0\uacfc\ub97c \ubd84\uc11d\ud574\uc11c \uc2dc\uac01\ud654\uac00 \uc801\uc808\ud55c\uc9c0 \ud310\ub2e8\ud558\uace0, \ucc28\ud2b8 \uc124\uc815\uc744 JSON\uc73c\ub85c \ubc18\ud658\ud558\uc138\uc694.

## \uc0ac\uc6a9\uc790 \uc9c8\ubb38
{query}

## SQL
{sql}

## \uacb0\uacfc ({row_count}\ud589)
{results_preview}

## \ud310\ub2e8 \uae30\uc900
- \uc0ac\uc6a9\uc790\uac00 "\uc2dc\uac01\ud654", "\ucc28\ud2b8", "\uadf8\ub798\ud504", "\ubcf4\uc5ec\uc918", "\ube44\uad50", "\ucd94\uc774", "\ud2b8\ub80c\ub4dc" \ub4f1\uc744 \uc694\uccad\ud558\uba74 \ucc28\ud2b8\ub97c \uc0dd\uc131
- \ube44\uad50 \ub370\uc774\ud130(\uad6d\uac00\ubcc4, \uc6d4\ubcc4, \ud50c\ub7ab\ud3fc\ubcc4 \ub4f1)\ub294 \ucc28\ud2b8\uac00 \ud6a8\uacfc\uc801
- \ub2e8\uc77c \uc22b\uc790 \uacb0\uacfc(\ucd1d \ub9e4\ucd9c 1\uac1c)\ub294 \ucc28\ud2b8 \ubd88\ud544\uc694
- \uacb0\uacfc\uac00 2\ud589 \uc774\uc0c1\uc774\uace0 \uc22b\uc790 \ucef4\ub7fc\uc774 \uc788\uc73c\uba74 \ucc28\ud2b8 \uad8c\uc7a5

## \u26a0\ufe0f \uac00\ub3c5\uc131 \ud310\ub2e8 \u2014 \uc544\ub798 \uacbd\uc6b0 needs_chart: false
- bar \ucc28\ud2b8: \uce74\ud14c\uace0\ub9ac\uac00 15\uac1c \ucd08\uacfc \u2192 \uc77d\uae30 \uc5b4\ub824\uc6c0
- horizontal_bar: \ud56d\ubaa9\uc774 20\uac1c \ucd08\uacfc
- pie/donut: \ud56d\ubaa9\uc774 10\uac1c \ucd08\uacfc
- line: \ub370\uc774\ud130 \ud3ec\uc778\ud2b8 36\uac1c \ucd08\uacfc (3\ub144\uce58 \uc6d4\ubcc4 \uc774\uc0c1)
- \ub77c\ubca8\uc774 \ub9e4\uc6b0 \uae38\uc5b4\uc11c(30\uc790+) \uacb9\uce60 \uacbd\uc6b0
- \uc0ac\ub78c\uc774 \ud55c\ub208\uc5d0 \ud30c\uc545\ud558\uae30 \uc5b4\ub824\uc6b4 \ubcf5\uc7a1\ud55c \ub370\uc774\ud130\ub294 \ucc28\ud2b8\ub97c \uc0dd\uc131\ud558\uc9c0 \ub9c8\uc138\uc694

## \ucc28\ud2b8 \ud0c0\uc785 \uc120\ud0dd (\uc911\uc694!)
- **line**: \uc6d4\ubcc4/\uc77c\ubcc4 \ub9e4\ucd9c \ucd94\uc774, \uc2dc\uacc4\uc5f4 \ub370\uc774\ud130. \ud2b9\ud788 "\uc6d4\ubcc4 \ub9e4\ucd9c", "\ucd94\uc774", "\ud2b8\ub80c\ub4dc", "\ubcc0\ud654" \uc694\uccad \uc2dc \ubc18\ub4dc\uc2dc line \uc0ac\uc6a9. x\ucd95=\uc6d4(\ub610\ub294 \uc77c\uc790), y\ucd95=\ub9e4\ucd9c\uc561
- bar: \uce74\ud14c\uace0\ub9ac\ubcc4 \ube44\uad50 (\uad6d\uac00\ubcc4, \ud50c\ub7ab\ud3fc\ubcc4 \ub9e4\ucd9c \ub4f1)
- horizontal_bar: \ud56d\ubaa9\uc774 \ub9ce\uc744 \ub54c (7\uac1c \uc774\uc0c1) \ub610\ub294 \uc774\ub984\uc774 \uae34 \uce74\ud14c\uace0\ub9ac
- pie: \ube44\uc728/\uad6c\uc131 (\uc804\uccb4 \ub300\ube44 \ube44\uc911) - \ub3c4\ub11b \uc2a4\ud0c0\uc77c\ub85c \ub80c\ub354\ub428
- grouped_bar: \uc5ec\ub7ec \uc9c0\ud45c\ub97c \uce74\ud14c\uace0\ub9ac\ubcc4\ub85c \ube44\uad50
- stacked_bar: \ub204\uc801 \ube44\uad50

## \ubc18\ud658 JSON \ud615\uc2dd
{{
  "needs_chart": true/false,
  "chart_type": "bar|horizontal_bar|line|pie|grouped_bar|stacked_bar",
  "x_column": "\uacb0\uacfc \ucef4\ub7fc\uba85",
  "y_column": "\uacb0\uacfc \ucef4\ub7fc\uba85" \ub610\ub294 ["\ucef4\ub7fc1", "\ucef4\ub7fc2"],
  "title": "\ucc28\ud2b8 \uc81c\ubaa9 (\ud55c\uad6d\uc5b4)",
  "x_label": "X\ucd95 \ub77c\ubca8",
  "y_label": "Y\ucd95 \ub77c\ubca8"
}}

needs_chart\uac00 false\uc774\uba74 \ub2e4\ub978 \ud544\ub4dc\ub294 \ube44\uc6cc\ub450\uc138\uc694."""
