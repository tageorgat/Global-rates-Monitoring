from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import CACHE_DIR, MASTER_DATA_CSV_PATH, MASTER_DATA_PATH, STATUS_PATH


STATUS_COLUMNS = [
    "metric_code",
    "metric_name",
    "source_name",
    "status",
    "rows_loaded",
    "message",
    "last_attempt_utc",
    "last_success_utc",
    "latest_data_date",
]


def _empty_master_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "date",
            "metric_code",
            "metric_name",
            "category",
            "region",
            "tenor",
            "value",
            "source_name",
            "source_series",
            "frequency",
            "units",
            "loaded_at",
        ]
    )


def _empty_status_df() -> pd.DataFrame:
    return pd.DataFrame(columns=STATUS_COLUMNS)


def load_master_data() -> pd.DataFrame:
    if MASTER_DATA_PATH.exists():
        try:
            df = pd.read_parquet(MASTER_DATA_PATH)
        except Exception:
            df = _empty_master_df()
    elif MASTER_DATA_CSV_PATH.exists():
        try:
            df = pd.read_csv(MASTER_DATA_CSV_PATH, parse_dates=["date"])
        except Exception:
            df = _empty_master_df()
    else:
        df = _empty_master_df()

    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).reset_index(drop=True)
    return df


def save_master_data(df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if not out.empty and "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
    try:
        out.to_parquet(MASTER_DATA_PATH, index=False)
    except Exception:
        out.to_csv(MASTER_DATA_CSV_PATH, index=False)


def load_status() -> pd.DataFrame:
    if not STATUS_PATH.exists():
        return _empty_status_df()
    try:
        df = pd.read_csv(STATUS_PATH)
    except Exception:
        return _empty_status_df()
    for col in STATUS_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[STATUS_COLUMNS]


def save_status(df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for col in STATUS_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out[STATUS_COLUMNS].to_csv(STATUS_PATH, index=False)


def append_or_replace(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        combined = incoming.copy()
    elif incoming is None or incoming.empty:
        combined = existing.copy()
    else:
        combined = pd.concat([existing, incoming], ignore_index=True)

    if combined.empty:
        return _empty_master_df()

    if "date" in combined.columns:
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
        combined = combined.dropna(subset=["date"])

    combined = combined.sort_values(["metric_code", "date", "loaded_at"])
    combined = combined.drop_duplicates(subset=["metric_code", "date"], keep="last")
    return combined.reset_index(drop=True)
