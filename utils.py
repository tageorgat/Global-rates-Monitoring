from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
import plotly.graph_objects as go


def fmt_pct(value: Optional[float], digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.{digits}f}%"


def fmt_bps(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value * 100:.0f} bps"


def fmt_num(value: Optional[float], digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{value:.{digits}f}"


def utc_now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_datetime(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    out = df.copy()
    if col in out.columns:
        out.loc[:, col] = pd.to_datetime(out[col], errors="coerce")
    return out


def filter_from_start_date(
    df: pd.DataFrame,
    start_date: str | date = "2019-01-01",
    date_col: str = "date",
) -> pd.DataFrame:
    out = df.copy()
    if out.empty or date_col not in out.columns:
        return out
    out.loc[:, date_col] = pd.to_datetime(out[date_col], errors="coerce")
    start_ts = pd.Timestamp(start_date)
    return out[out[date_col] >= start_ts].copy()


def monthly_axis_config(month_count: int | None = None) -> dict:
    # Reduce x-axis clutter depending on date span
    if month_count is None or month_count <= 18:
        dtick = "M1"
    elif month_count <= 36:
        dtick = "M2"
    elif month_count <= 72:
        dtick = "M3"
    else:
        dtick = "M6"

    return {
        "tickformat": "%b %Y",
        "dtick": dtick,
        "ticklabelmode": "period",
        "tickangle": -90,
        "showgrid": False,
    }


def apply_standard_timeseries_layout(
    fig: go.Figure,
    y_title: str = "Rate (%)",
    month_count: int | None = None,
) -> go.Figure:
    fig.update_layout(
        height=540,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=90, b=40),
        title=dict(y=0.97),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.06,
            xanchor="left",
            x=0,
            title=None,
        ),
        xaxis_title="Month",
        yaxis_title=y_title,
    )
    fig.update_xaxes(**monthly_axis_config(month_count=month_count))
    return fig
