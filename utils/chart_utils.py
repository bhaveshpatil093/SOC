"""
utils/chart_utils.py

Reusable Plotly chart builders for the ISRO SOC Analytics platform.

All charts share a consistent dark theme, colour palette, and typography.
Each function returns a go.Figure — the caller renders it with st.plotly_chart().

Usage:
    from utils import ChartUtils
    import streamlit as st

    fig = ChartUtils.event_volume_chart(df, title="Events over Time")
    st.plotly_chart(fig, use_container_width=True)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from config import get_logger

logger = get_logger(__name__)

# ─── Shared Design Tokens ─────────────────────────────────────────────────────

DARK_BG = "#0D1117"
PANEL_BG = "#161B22"
BORDER_COLOUR = "#30363D"
TEXT_COLOUR = "#E6EDF3"
SUBTEXT_COLOUR = "#8B949E"
ACCENT_PRIMARY = "#58A6FF"
ACCENT_SUCCESS = "#3FB950"
ACCENT_WARNING = "#D29922"
ACCENT_DANGER = "#F85149"
ACCENT_INFO = "#79C0FF"

# Sequential colour scales
SEQ_BLUE = px.colors.sequential.Blues
SEQ_RED = px.colors.sequential.Reds

# Categorical palette for multi-series charts
CAT_PALETTE = [
    "#58A6FF",  # Blue
    "#3FB950",  # Green
    "#F78166",  # Coral
    "#D29922",  # Yellow
    "#BC8CFF",  # Purple
    "#79C0FF",  # Light blue
    "#56D364",  # Light green
    "#FF7B72",  # Red-orange
]

# ─── Base layout ──────────────────────────────────────────────────────────────

def _base_layout(title: str = "", height: int = 400) -> Dict[str, Any]:
    """Return a shared dark-theme Plotly layout dict."""
    return dict(
        title=dict(
            text=title,
            font=dict(family="Inter, sans-serif", size=16, color=TEXT_COLOUR),
            x=0,
            xanchor="left",
        ),
        height=height,
        paper_bgcolor=PANEL_BG,
        plot_bgcolor=PANEL_BG,
        font=dict(family="Inter, sans-serif", color=TEXT_COLOUR, size=12),
        xaxis=dict(
            showgrid=True,
            gridcolor=BORDER_COLOUR,
            zeroline=False,
            tickfont=dict(color=SUBTEXT_COLOUR),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=BORDER_COLOUR,
            zeroline=False,
            tickfont=dict(color=SUBTEXT_COLOUR),
        ),
        legend=dict(
            bgcolor=PANEL_BG,
            bordercolor=BORDER_COLOUR,
            borderwidth=1,
            font=dict(color=TEXT_COLOUR),
        ),
        margin=dict(l=50, r=20, t=50, b=40),
        hovermode="x unified",
    )


# ─── Chart Builders ───────────────────────────────────────────────────────────

class ChartUtils:
    """Reusable Plotly chart builders with consistent dark theme."""

    @staticmethod
    def event_volume_chart(
        df: pd.DataFrame,
        time_col: str = "timestamp",
        count_col: str = "count",
        title: str = "Event Volume Over Time",
        colour: str = ACCENT_PRIMARY,
        height: int = 350,
        fill: bool = True,
    ) -> go.Figure:
        """
        Line chart of event counts over time.

        Args:
            df:        DataFrame with time and count columns.
            time_col:  Timestamp column name.
            count_col: Count column name.
            title:     Chart title.
            colour:    Line colour hex.
            height:    Chart height in pixels.
            fill:      Whether to fill under the line.
        """
        fig = go.Figure()
        if df.empty:
            return ChartUtils._empty_figure(title, height)

        fig.add_trace(
            go.Scatter(
                x=df[time_col],
                y=df[count_col],
                mode="lines",
                fill="tozeroy" if fill else None,
                line=dict(color=colour, width=2),
                fillcolor=f"rgba(88, 166, 255, 0.1)",
                name="Events",
                hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>Events: %{y:,}<extra></extra>",
            )
        )
        layout = _base_layout(title, height)
        layout["yaxis"]["tickformat"] = ",.0f"
        fig.update_layout(**layout)
        return fig

    @staticmethod
    def horizontal_bar_chart(
        df: pd.DataFrame,
        key_col: str = "value",
        count_col: str = "count",
        title: str = "Top Values",
        colour: str = ACCENT_PRIMARY,
        height: int = 400,
        max_rows: int = 20,
    ) -> go.Figure:
        """
        Horizontal bar chart for top-N terms aggregations.

        Args:
            df:       DataFrame with key and count columns.
            key_col:  Category column name.
            count_col: Count column name.
            max_rows: Maximum bars to display.
        """
        if df.empty:
            return ChartUtils._empty_figure(title, height)

        display_df = df.head(max_rows).copy()
        display_df = display_df.sort_values(count_col, ascending=True)

        fig = go.Figure(
            go.Bar(
                x=display_df[count_col],
                y=display_df[key_col].astype(str),
                orientation="h",
                marker=dict(
                    color=display_df[count_col],
                    colorscale=[[0, "#1F3B5E"], [1, colour]],
                    line=dict(color=BORDER_COLOUR, width=0.5),
                ),
                hovertemplate="%{y}: <b>%{x:,}</b><extra></extra>",
            )
        )
        layout = _base_layout(title, height)
        layout["xaxis"]["tickformat"] = ",.0f"
        layout["hovermode"] = "y unified"
        fig.update_layout(**layout)
        return fig

    @staticmethod
    def severity_donut(
        df: pd.DataFrame,
        key_col: str = "value",
        count_col: str = "count",
        title: str = "Severity Distribution",
        height: int = 350,
    ) -> go.Figure:
        """
        Donut chart for severity/category distributions.
        """
        if df.empty:
            return ChartUtils._empty_figure(title, height)

        colours = [_severity_colour(k) for k in df[key_col].astype(str)]

        fig = go.Figure(
            go.Pie(
                labels=df[key_col].astype(str),
                values=df[count_col],
                hole=0.55,
                marker=dict(colors=colours, line=dict(color=PANEL_BG, width=2)),
                textinfo="label+percent",
                textfont=dict(color=TEXT_COLOUR, size=11),
                hovertemplate="%{label}: <b>%{value:,}</b> (%{percent})<extra></extra>",
            )
        )
        layout = _base_layout(title, height)
        layout.pop("xaxis", None)
        layout.pop("yaxis", None)
        layout["showlegend"] = True
        fig.update_layout(**layout)
        return fig

    @staticmethod
    def multi_series_line_chart(
        dfs: Dict[str, pd.DataFrame],
        time_col: str = "timestamp",
        count_col: str = "count",
        title: str = "Multi-Series Trend",
        height: int = 400,
    ) -> go.Figure:
        """
        Overlay multiple time series on one chart.

        Args:
            dfs: Dict mapping series label → DataFrame.
        """
        fig = go.Figure()
        for idx, (label, df) in enumerate(dfs.items()):
            if df.empty:
                continue
            colour = CAT_PALETTE[idx % len(CAT_PALETTE)]
            fig.add_trace(
                go.Scatter(
                    x=df[time_col],
                    y=df[count_col],
                    mode="lines",
                    name=label,
                    line=dict(color=colour, width=2),
                    hovertemplate=f"<b>{label}</b><br>%{{x|%H:%M}}: %{{y:,}}<extra></extra>",
                )
            )
        layout = _base_layout(title, height)
        fig.update_layout(**layout)
        return fig

    @staticmethod
    def heatmap(
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        z_col: str,
        title: str = "Activity Heatmap",
        height: int = 400,
    ) -> go.Figure:
        """
        Heatmap chart — useful for hour-of-day × day-of-week activity maps.
        """
        if df.empty:
            return ChartUtils._empty_figure(title, height)

        pivot = df.pivot_table(index=y_col, columns=x_col, values=z_col, fill_value=0)
        fig = go.Figure(
            go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale="Blues",
                hovertemplate=f"{x_col}: %{{x}}<br>{y_col}: %{{y}}<br>Count: %{{z:,}}<extra></extra>",
            )
        )
        layout = _base_layout(title, height)
        layout.pop("hovermode", None)
        fig.update_layout(**layout)
        return fig

    @staticmethod
    def kpi_metric(
        label: str,
        value: str,
        delta: Optional[str] = None,
        colour: str = ACCENT_PRIMARY,
    ) -> None:
        """
        Render a KPI metric card using st.metric (Streamlit-aware helper).

        Must be called inside a Streamlit context.
        """
        import streamlit as st
        st.metric(label=label, value=value, delta=delta)

    @staticmethod
    def scatter_anomaly(
        df: pd.DataFrame,
        x_col: str,
        y_col: str,
        label_col: str,
        anomaly_col: str = "is_anomaly",
        title: str = "Anomaly Detection",
        height: int = 450,
    ) -> go.Figure:
        """
        Scatter plot with anomalies highlighted in red.

        Args:
            df:          DataFrame with point data.
            x_col:       X-axis column.
            y_col:       Y-axis column.
            label_col:   Column for hover labels.
            anomaly_col: Boolean column — True = anomaly.
        """
        if df.empty:
            return ChartUtils._empty_figure(title, height)

        normal = df[~df[anomaly_col].astype(bool)]
        anomalies = df[df[anomaly_col].astype(bool)]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=normal[x_col],
                y=normal[y_col],
                mode="markers",
                name="Normal",
                marker=dict(color=ACCENT_INFO, size=5, opacity=0.6),
                hovertext=normal[label_col].astype(str),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=anomalies[x_col],
                y=anomalies[y_col],
                mode="markers",
                name="Anomaly",
                marker=dict(color=ACCENT_DANGER, size=10, symbol="x", opacity=0.9),
                hovertext=anomalies[label_col].astype(str),
            )
        )
        fig.update_layout(**_base_layout(title, height))
        return fig

    @staticmethod
    def _empty_figure(title: str, height: int) -> go.Figure:
        """Return a placeholder figure when data is unavailable."""
        fig = go.Figure()
        fig.add_annotation(
            text="No data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color=SUBTEXT_COLOUR),
        )
        fig.update_layout(**_base_layout(title, height))
        return fig


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _severity_colour(severity: str) -> str:
    """Map severity string to chart colour."""
    mapping = {
        "critical": ACCENT_DANGER,
        "high": "#FF8C00",
        "medium": ACCENT_WARNING,
        "low": ACCENT_SUCCESS,
        "info": ACCENT_INFO,
        "informational": ACCENT_INFO,
        "unknown": BORDER_COLOUR,
    }
    return mapping.get(severity.lower(), CAT_PALETTE[0])
