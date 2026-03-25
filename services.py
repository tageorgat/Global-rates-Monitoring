from __future__ import annotations

from typing import Tuple

import pandas as pd
import streamlit as st

from config import TRACKED_RATES
from data_sources import generate_sample_history, load_metric_live
from storage import append_or_replace, load_master_data, load_status, save_master_data, save_status


@st.cache_data(ttl=900, show_spinner=False)
def get_master_data_cached() -> pd.DataFrame:
    return load_master_data()


@st.cache_data(ttl=900, show_spinner=False)
def get_status_cached() -> pd.DataFrame:
    return load_status()



def clear_caches() -> None:
    get_master_data_cached.clear()
    get_status_cached.clear()



def bootstrap_if_empty() -> Tuple[pd.DataFrame, pd.DataFrame]:
    data = load_master_data()
    status = load_status()
    if data.empty:
        sample = generate_sample_history()
        save_master_data(sample)
        clear_caches()
        data = load_master_data()
    return data, status



def refresh_all_sources(use_existing_as_fallback: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    existing = load_master_data()
    status_existing = load_status()
    new_frames = []
    status_rows = []

    for cfg in TRACKED_RATES:
        existing_metric = existing[existing["metric_code"] == cfg.code].copy() if not existing.empty else pd.DataFrame()
        df_new, status = load_metric_live(cfg, existing_metric)

        if not status_existing.empty:
            prev = status_existing[status_existing["metric_code"] == cfg.code]
        else:
            prev = pd.DataFrame()

        prev_last_success = prev.iloc[-1].get("last_success_utc") if not prev.empty else None
        prev_latest_data = prev.iloc[-1].get("latest_data_date") if not prev.empty else None

        if status["status"] == "success":
            new_frames.append(df_new)
        elif status["status"] == "up_to_date":
            status["last_success_utc"] = prev_last_success or status["last_attempt_utc"]
            status["latest_data_date"] = prev_latest_data or status["latest_data_date"]
        elif status["status"] == "error" and use_existing_as_fallback and not existing_metric.empty:
            status["status"] = "cache_fallback"
            status["message"] = f"{status['message']} | kept stored history"
            status["rows_loaded"] = int(len(existing_metric))
            status["last_success_utc"] = prev_last_success
            status["latest_data_date"] = existing_metric["date"].max().date().isoformat()
        else:
            status["last_success_utc"] = prev_last_success
            status["latest_data_date"] = prev_latest_data

        status_rows.append(status)

    combined_new = pd.concat([f for f in new_frames if not f.empty], ignore_index=True) if any(not f.empty for f in new_frames) else pd.DataFrame()
    merged = append_or_replace(existing, combined_new)
    new_status = pd.DataFrame(status_rows)
    save_master_data(merged)
    save_status(new_status)
    clear_caches()
    return merged, new_status
