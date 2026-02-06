"""Chart generation module using Plotly.

Generates interactive HTML charts with hover tooltips.
Charts are served via FastAPI static endpoint.
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = structlog.get_logger(__name__)

# --- Looker Studio Dark Theme Constants ---
DARK_BG = "#1e1e1e"
PLOT_BG = "#1e1e1e"
GRID_COLOR = "#333333"
TEXT_COLOR = "#cccccc"
TITLE_COLOR = "#ffffff"
LABEL_COLOR = "#999999"

# Line chart colors
LINE_COLORS = ["#4285F4", "#EA4335", "#34A853", "#FBBC04", "#FF6D01", "#46BDC6",
               "#7BAAF7", "#F07B72", "#57BB8A", "#FFD54F"]

# Bar/Pie chart colors
BAR_COLORS = [
    "#EA4335", "#4285F4", "#FBBC04", "#34A853", "#FF6D01",
    "#46BDC6", "#7BAAF7", "#F07B72", "#57BB8A", "#FFD54F",
]

CHARTS_DIR = Path(__file__).resolve().parent.parent / "static" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def _format_number(val: float) -> str:
    """Format large numbers with Korean units."""
    if abs(val) >= 1e8:
        return f"{val / 1e8:,.1f}억"
    elif abs(val) >= 1e4:
        return f"{val / 1e4:,.0f}만"
    else:
        return f"{val:,.0f}"


def _pivot_grouped_data(
    data: List[Dict], x_col: str, y_col: str, group_col: str
) -> tuple:
    """Pivot long-format grouped data into wide format for multi-series charts.

    Input:  [{continent: "CIS", month: "01", sales: 100}, {continent: "US", month: "01", sales: 200}, ...]
    Output: [{month: "01", CIS: 100, US: 200}, ...], ["CIS", "US"]

    Returns:
        (pivoted_data, y_columns_list) or ([], []) on failure.
    """
    from collections import OrderedDict

    try:
        # Collect unique x values (preserving order) and group names
        x_order = list(OrderedDict.fromkeys(str(row.get(x_col, "")) for row in data))
        groups = list(OrderedDict.fromkeys(str(row.get(group_col, "")) for row in data))

        # Build pivot dict: {x_val: {group: y_val}}
        pivot = {x: {} for x in x_order}
        for row in data:
            x = str(row.get(x_col, ""))
            g = str(row.get(group_col, ""))
            v = float(row.get(y_col, 0) or 0)
            pivot[x][g] = v

        # Convert to wide-format rows
        wide_data = []
        for x in x_order:
            row = {x_col: x}
            for g in groups:
                row[g] = pivot[x].get(g, 0)
            wide_data.append(row)

        logger.info("pivot_grouped_data", x_count=len(x_order), groups=len(groups), group_names=groups[:5])
        return wide_data, groups
    except Exception as e:
        logger.error("pivot_failed", error=str(e))
        return [], []


def _get_dark_layout(title: str, x_label: str, y_label: str, chart_type: str) -> dict:
    """Create Plotly layout with dark theme."""
    layout = dict(
        title=dict(
            text=title,
            font=dict(size=16, color=TITLE_COLOR, family="Malgun Gothic, sans-serif"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor=DARK_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR, family="Malgun Gothic, sans-serif"),
        xaxis=dict(
            title=dict(text=x_label, font=dict(size=12, color=LABEL_COLOR)),
            tickfont=dict(size=10, color=LABEL_COLOR),
            gridcolor=GRID_COLOR,
            linecolor=GRID_COLOR,
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            title=dict(text=y_label, font=dict(size=12, color=LABEL_COLOR)),
            tickfont=dict(size=10, color=LABEL_COLOR),
            gridcolor=GRID_COLOR,
            linecolor=GRID_COLOR,
            showgrid=True,
            zeroline=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(30,30,30,0.8)",
            bordercolor=GRID_COLOR,
            borderwidth=1,
            font=dict(size=10, color=TEXT_COLOR),
        ),
        margin=dict(l=60, r=30, t=80, b=60),
        hovermode="x unified" if chart_type == "line" else "closest",
    )
    return layout


def generate_chart(
    chart_config: Dict[str, Any],
    data: List[Dict[str, Any]],
) -> Optional[str]:
    """Generate an interactive chart and save as HTML file.

    Returns:
        Filename of saved HTML, or None if generation fails.
    """
    try:
        chart_type = chart_config.get("chart_type", "bar")
        x_col = chart_config.get("x_column", "")
        y_col = chart_config.get("y_column", "")
        title = chart_config.get("title", "")
        x_label = chart_config.get("x_label", "")
        y_label = chart_config.get("y_label", "")

        group_col = chart_config.get("group_column")

        if not data or not x_col or not y_col:
            return None

        # Pivot long-format grouped data into wide format for multi-series charts
        if group_col and isinstance(y_col, str):
            data, y_col = _pivot_grouped_data(data, x_col, y_col, group_col)
            if not data:
                return None

        # Readability guard: skip chart if too many categories
        max_items = {"bar": 15, "horizontal_bar": 20, "pie": 10, "line": 36}
        limit = max_items.get(chart_type, 20)
        check_count = len(data)
        if check_count > limit:
            logger.info("chart_skipped_too_many_items", chart_type=chart_type, items=check_count, limit=limit)
            return None

        x_values = [str(row.get(x_col, "")) for row in data]

        if isinstance(y_col, list):
            y_series = {}
            for col in y_col:
                y_series[col] = [float(row.get(col, 0) or 0) for row in data]
        else:
            y_values = [float(row.get(y_col, 0) or 0) for row in data]

        fig = go.Figure()

        # --- Line Chart ---
        if chart_type == "line":
            if isinstance(y_col, list):
                for i, col in enumerate(y_col):
                    color = LINE_COLORS[i % len(LINE_COLORS)]
                    hover_template = f"<b>{col}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>"
                    fig.add_trace(go.Scatter(
                        x=x_values,
                        y=y_series[col],
                        mode="lines+markers",
                        name=col,
                        line=dict(color=color, width=2),
                        marker=dict(size=6, color=color),
                        hovertemplate=hover_template,
                    ))
            else:
                hover_template = f"<b>{y_col}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>"
                fig.add_trace(go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines+markers",
                    name=y_col,
                    line=dict(color=LINE_COLORS[0], width=2.5),
                    marker=dict(size=7, color=LINE_COLORS[0]),
                    hovertemplate=hover_template,
                ))

        # --- Bar Chart ---
        elif chart_type == "bar":
            hover_texts = [f"{x}: {_format_number(y)}" for x, y in zip(x_values, y_values)]
            fig.add_trace(go.Bar(
                x=x_values,
                y=y_values,
                marker_color=BAR_COLORS[:len(x_values)],
                text=[_format_number(v) for v in y_values],
                textposition="outside",
                textfont=dict(size=10, color=TEXT_COLOR),
                hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>",
            ))

        # --- Horizontal Bar Chart ---
        elif chart_type == "horizontal_bar":
            fig.add_trace(go.Bar(
                x=y_values,
                y=x_values,
                orientation="h",
                marker_color=BAR_COLORS[:len(x_values)],
                text=[_format_number(v) for v in y_values],
                textposition="outside",
                textfont=dict(size=10, color=TEXT_COLOR),
                hovertemplate="%{y}<br>%{x:,.0f}<extra></extra>",
            ))

        # --- Pie/Donut Chart ---
        elif chart_type == "pie":
            filtered = [(x, y) for x, y in zip(x_values, y_values) if y > 0]
            if not filtered:
                return None
            pie_labels, pie_values = zip(*filtered)
            fig.add_trace(go.Pie(
                labels=pie_labels,
                values=pie_values,
                hole=0.4,
                marker=dict(colors=BAR_COLORS[:len(pie_values)], line=dict(color=DARK_BG, width=2)),
                textinfo="label+percent",
                textfont=dict(size=10, color=TITLE_COLOR),
                hovertemplate="%{label}<br>%{value:,.0f} (%{percent})<extra></extra>",
            ))

        # --- Stacked Bar ---
        elif chart_type == "stacked_bar" and isinstance(y_col, list):
            for i, col in enumerate(y_col):
                fig.add_trace(go.Bar(
                    x=x_values,
                    y=y_series[col],
                    name=col,
                    marker_color=BAR_COLORS[i % len(BAR_COLORS)],
                    hovertemplate=f"<b>{col}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>",
                ))
            fig.update_layout(barmode="stack")

        # --- Grouped Bar ---
        elif chart_type == "grouped_bar" and isinstance(y_col, list):
            for i, col in enumerate(y_col):
                fig.add_trace(go.Bar(
                    x=x_values,
                    y=y_series[col],
                    name=col,
                    marker_color=BAR_COLORS[i % len(BAR_COLORS)],
                    hovertemplate=f"<b>{col}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>",
                ))
            fig.update_layout(barmode="group")

        # Apply dark theme layout
        layout = _get_dark_layout(title, x_label, y_label, chart_type)

        # Adjust layout for specific chart types
        if chart_type == "pie":
            layout.pop("xaxis", None)
            layout.pop("yaxis", None)
            layout["legend"]["orientation"] = "v"
            layout["legend"]["y"] = 0.5
            layout["legend"]["yanchor"] = "middle"
            layout["legend"]["x"] = 1.05
            layout["legend"]["xanchor"] = "left"
        elif chart_type == "horizontal_bar":
            layout["xaxis"]["title"]["text"] = y_label
            layout["yaxis"]["title"]["text"] = x_label
            layout["yaxis"]["autorange"] = "reversed"
            layout["margin"]["l"] = 120

        fig.update_layout(**layout)

        # Save as PNG image (for Open WebUI compatibility)
        filename = f"{uuid.uuid4().hex}.png"
        filepath = CHARTS_DIR / filename

        try:
            fig.write_image(
                str(filepath),
                format="png",
                width=1200,
                height=600,
                scale=2,
            )
            logger.info("chart_generated", chart_type=chart_type, data_points=len(data), file=filename)
            return filename
        except Exception as img_error:
            logger.warning("chart_png_failed", error=str(img_error))
            # Fallback to HTML if PNG fails
            html_filename = f"{uuid.uuid4().hex}.html"
            html_filepath = CHARTS_DIR / html_filename
            fig.write_html(
                str(html_filepath),
                include_plotlyjs="cdn",
                full_html=True,
                config={
                    "displayModeBar": True,
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                    "displaylogo": False,
                    "responsive": True,
                },
            )
            logger.info("chart_generated_html_fallback", file=html_filename)
            return html_filename

    except Exception as e:
        logger.error("chart_generation_failed", error=str(e))
        return None


def get_chart_config_prompt(query: str, sql: str, results_preview: str, row_count: int) -> str:
    """Build a prompt for the LLM to decide chart configuration."""
    return f"""사용자의 질문과 SQL 결과를 분석해서 시각화가 적절한지 판단하고, 차트 설정을 JSON으로 반환하세요.

## 사용자 질문
{query}

## SQL
{sql}

## 결과 ({row_count}행)
{results_preview}

## 판단 기준
- 사용자가 "시각화", "차트", "그래프", "보여줘", "비교", "추이", "트렌드" 등을 요청하면 차트를 생성
- 비교 데이터(국가별, 월별, 플랫폼별 등)는 차트가 효과적
- 단일 숫자 결과(총 매출 1개)는 차트 불필요
- 결과가 2행 이상이고 숫자 컬럼이 있으면 차트 권장

## ⚠️ 가독성 판단 — 아래 경우 needs_chart: false
- bar 차트: 카테고리가 15개 초과 → 읽기 어려움
- horizontal_bar: 항목이 20개 초과
- pie/donut: 항목이 10개 초과
- line: x축 고유값 36개 초과 (3년치 월별 이상). 단, group_column이 있으면 x축 고유값 기준으로 판단 (예: 10대륙 x 12개월 = 120행이지만 x축은 12개로 OK)
- 라벨이 매우 길어서(30자+) 겹칠 경우
- 사람이 한눈에 파악하기 어려운 복잡한 데이터는 차트를 생성하지 마세요

## 차트 타입 선택 (중요!)
- **line**: 월별/일별 매출 추이, 시계열 데이터. "추이", "트렌드", "변화" 요청 시 반드시 line. 대륙별/국가별 등 그룹이 있으면 group_column을 지정하세요 (각 그룹이 별도 라인으로 표시됨)
- bar: 카테고리별 비교 (국가별, 플랫폼별 매출 등)
- horizontal_bar: 항목이 많을 때 (7개 이상) 또는 이름이 긴 카테고리
- pie: 비율/구성 (전체 대비 비중) - 도넛 스타일로 렌더됨
- grouped_bar: 여러 지표를 카테고리별로 비교
- stacked_bar: 누적 비교

## 반환 JSON 형식
{{
  "needs_chart": true/false,
  "chart_type": "bar|horizontal_bar|line|pie|grouped_bar|stacked_bar",
  "x_column": "결과 컬럼명",
  "y_column": "결과 컬럼명" 또는 ["컬럼1", "컬럼2"],
  "group_column": "그룹 컬럼명 (대륙별/국가별 등 long format일 때, 없으면 null)",
  "title": "차트 제목 (한국어)",
  "x_label": "X축 라벨",
  "y_label": "Y축 라벨"
}}

needs_chart가 false이면 다른 필드는 비워두세요."""
