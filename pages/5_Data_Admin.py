from __future__ import annotations

import streamlit as st

from services import get_master_data_cached, get_status_cached, refresh_all_sources

st.title("Data Admin")

if st.button("Run refresh now", type="primary"):
    with st.spinner("Refreshing live data..."):
        refresh_all_sources()
        get_master_data_cached.clear()
        get_status_cached.clear()
    st.success("Refresh completed.")
    st.rerun()

data = get_master_data_cached()
status = get_status_cached()

st.subheader("Source status")
if status.empty:
    st.info("No status rows yet.")
else:
    preferred_cols = [
        "metric_code",
        "metric_name",
        "source_name",
        "status",
        "rows_loaded",
        "latest_data_date",
        "last_success_utc",
        "last_attempt_utc",
        "message",
    ]
    show_cols = [c for c in preferred_cols if c in status.columns]
    st.dataframe(status[show_cols].sort_values(["status", "metric_code"]), use_container_width=True, hide_index=True)

st.subheader("Stored history summary")
if data.empty:
    st.info("No stored data yet.")
else:
    summary = data.groupby(["metric_code", "metric_name", "source_name"], as_index=False).agg(
        rows=("value", "size"),
        start_date=("date", "min"),
        end_date=("date", "max"),
    )
    st.dataframe(summary.sort_values("metric_code"), use_container_width=True, hide_index=True)

st.subheader("Notes")
st.write("Healthy states: success = new rows fetched, up_to_date = source responded but nothing newer than stored history, cache_fallback = live fetch failed but stored history is preserved.")
