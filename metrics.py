from __future__ import annotations

import pandas as pd

from config import SPREAD_DEFINITIONS


def latest_points(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    work = df.sort_values(["metric_code", "date"]).copy()
    work["prev_value"] = work.groupby("metric_code")["value"].shift(1)
    latest = work.groupby("metric_code", as_index=False).tail(1).copy()
    latest.loc[:, "delta"] = latest["value"] - latest["prev_value"]
    return latest


def build_spreads(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "spread_code", "spread_name", "left_code", "right_code", "value"])

    pivot = df.pivot_table(index="date", columns="metric_code", values="value", aggfunc="last").sort_index()
    rows = []
    for spread_code, (left, right, spread_name) in SPREAD_DEFINITIONS.items():
        if left not in pivot.columns or right not in pivot.columns:
            continue
        series = pivot[left] - pivot[right]
        tmp = series.reset_index()
        tmp.columns = ["date", "value"]
        tmp["spread_code"] = spread_code
        tmp["spread_name"] = spread_name
        tmp["left_code"] = left
        tmp["right_code"] = right
        rows.append(tmp)
    if not rows:
        return pd.DataFrame(columns=["date", "spread_code", "spread_name", "left_code", "right_code", "value"])
    return pd.concat(rows, ignore_index=True)
