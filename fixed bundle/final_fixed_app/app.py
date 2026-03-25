from __future__ import annotations

import streamlit as st

from config import APP_SUBTITLE, APP_TITLE, TRACKED_RATES
from metrics import build_spreads, latest_points
from services import (
    bootstrap_if_empty,
    get_master_data_cached,
    get_status_cached,
    refresh_all_sources,
)
from utils import fmt_pct

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
    spreads_local = build_spreads(data_local)
    latest_local = latest_points(data_local)
    return data_local, status_local, spreads_local, latest_local


data, status, spreads, latest = load_all()

with st.sidebar:
    st.subheader("Controls")

    if st.button("Refresh live data", use_container_width=True, type="primary"):
        with st.spinner("Refreshing sources and updating stored history..."):
            refresh_all_sources()
            get_master_data_cached.clear()
            get_status_cached.clear()
            data, status, spreads, latest = load_all()
        st.success("Refresh completed.")
        st.rerun()

    st.write(f"Tracked series: **{len(TRACKED_RATES)}**")
    st.write(f"Loaded rows: **{len(data):,}**")

    if not status.empty and "status" in status.columns:
        success_like = status["status"].isin(["success", "up_to_date"]).sum()
        st.write(f"Healthy sources: **{int(success_like)}/{len(status)}**")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Series", len(TRACKED_RATES))
c2.metric("History rows", f"{len(data):,}")
c3.metric("Spread series", spreads["spread_code"].nunique() if not spreads.empty else 0)
c4.metric("Latest points", latest["metric_code"].nunique() if not latest.empty else 0)

st.markdown("### Latest market snapshot")
if latest.empty:
    st.info("No data loaded yet.")
else:
    latest_view = latest[["metric_name", "region", "category", "date", "value", "delta"]].copy()
    latest_view["date"] = latest_view["date"].dt.date
    latest_view["value"] = latest_view["value"].map(fmt_pct)
    latest_view["delta"] = latest_view["delta"].map(lambda x: f"{x:.2f} pp" if x == x else "—")
    st.dataframe(latest_view, use_container_width=True, hide_index=True)

st.markdown("### Included rates")
rate_df = data[["metric_code", "metric_name", "category", "region", "tenor", "source_name", "source_series"]].drop_duplicates()
st.dataframe(rate_df, use_container_width=True, hide_index=True)

st.markdown("### Suggested next pages")
st.write("Use the left sidebar pages for trends, comparisons, spreads, and source admin.")
