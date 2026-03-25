from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (
    APP_SUBTITLE,
    APP_TITLE,
    MIN_HISTORY_START,
    TRACKED_RATES,
)
from metrics import build_spreads, latest_points
from services import (
    bootstrap_if_empty,
    get_master_data_cached,
    get_status_cached,
    refresh_all_sources,
)
from utils import filter_from_start_date, fmt_pct

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

if "bootstrapped" not in st.session_state:
    bootstrap_if_empty()
    st.session_state.bootstrapped = True


def load_all():
    data_local = get_master_data_cached()
    status_local = get_status_cached()

    # Global floor: keep history from 2000 onward only
    data_local = filter_from_start_date(
        data_local,
        start_date=MIN_HISTORY_START,
        date_col="date",
    )

    spreads_local = build_spreads(data_local)
    latest_local = latest_points(data_local)
    return data_local, status_local, spreads_local, latest_local


data, status, spreads, latest = load_all()

with st.sidebar:
    st.subheader("Controls")

    if st.button("Refresh live data", use_container_width=True, type="primary"):
        with st.spinner("Refreshing sources and updating stored history..."):
            refresh_all_sources()

            # Clear cached readers so fresh data is reloaded immediately
            get_master_data_cached.clear()
            get_status_cached.clear()

            data, status, spreads, latest = load_all()

        st.success("Refresh completed.")
        st.rerun()

    st.write(f"Tracked series: **{len(TRACKED_RATES)}**")
    st.write(f"Loaded rows: **{len(data):,}**")
    st.write(f"History window: **from {MIN_HISTORY_START} onward**")

    if not status.empty and "status" in status.columns:
        success_like = status["status"].isin(["success", "up_to_date", "cache_fallback"])
        success_count = int(success_like.sum())
        st.write(f"Source health: **{success_count}/{len(status)}**")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Series", len(TRACKED_RATES))
c2.metric("History rows", f"{len(data):,}")
c3.metric("Spread series", spreads["spread_code"].nunique() if not spreads.empty else 0)
c4.metric("Latest points", latest["metric_code"].nunique() if not latest.empty else 0)

st.markdown("### Latest market snapshot")
if latest.empty:
    st.info("No data loaded yet.")
else:
    latest_view = latest[
        ["metric_name", "region", "category", "date", "value", "delta"]
    ].copy()

    latest_view["date"] = pd.to_datetime(latest_view["date"], errors="coerce").dt.date
    latest_view["value"] = latest_view["value"].map(fmt_pct)
    latest_view["delta"] = latest_view["delta"].map(
        lambda x: f"{x:.2f} pp" if pd.notna(x) else "—"
    )

    st.dataframe(latest_view, use_container_width=True, hide_index=True)

st.markdown("### Included rates")
if data.empty:
    st.info("No rate metadata available yet.")
else:
    rate_cols = [
        "metric_code",
        "metric_name",
        "category",
        "region",
        "tenor",
        "source_name",
        "source_series",
    ]
    rate_cols = [c for c in rate_cols if c in data.columns]

    rate_df = data[rate_cols].drop_duplicates().sort_values(
        by=[c for c in ["category", "region", "metric_name"] if c in rate_cols]
    )

    st.dataframe(rate_df, use_container_width=True, hide_index=True)

st.markdown("### Source status")
if status.empty:
    st.info("No source status available yet.")
else:
    status_cols = [
        "metric_name",
        "source_name",
        "status",
        "rows_loaded",
        "latest_data_date",
        "last_success_utc",
        "last_attempt_utc",
        "message",
    ]
    status_cols = [c for c in status_cols if c in status.columns]

    status_view = status[status_cols].copy()
    st.dataframe(status_view, use_container_width=True, hide_index=True)

st.markdown("### Suggested next pages")
st.write("Use the left sidebar pages for trends, comparisons, spreads, and source admin.")