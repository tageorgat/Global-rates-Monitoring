from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd


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
    start_date: str | date = "2000-01-01",
    date_col: str = "date",
) -> pd.DataFrame:
    out = df.copy()
    if out.empty or date_col not in out.columns:
        return out
    out.loc[:, date_col] = pd.to_datetime(out[date_col], errors="coerce")
    start_ts = pd.Timestamp(start_date)
    return out[out[date_col] >= start_ts].copy()


def monthly_axis_config() -> dict:
    return {
        "tickformat": "%b %Y",
        "dtick": "M1",
        "ticklabelmode": "period",
    }