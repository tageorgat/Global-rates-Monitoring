from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from config import APP_TITLE, TRACKED_RATES
from data_sources import latest_snapshot, load_rates_history
from metrics import add_change_columns
from utils import format_snapshot_table


st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")

st.title(APP_TITLE)
st.caption("A Streamlit starter app for monitoring 12 global rates and their history.")

with st.sidebar:
    st.header("App Controls")
    use_sample_data = st.toggle("Use sample data", value=True)
    last_n_days = st.slider("Default lookback (days)", min_value=90, max_value=3650, value=365)
    st.markdown("---")
    st.write("**Tracked rates**")
    for rate in TRACKED_RATES:
        st.caption(f"• {rate.metric_name}")

history = load_rates_history(use_sample_data=use_sample_data)
history = history.loc[history["date"] >= (history["date"].max() - timedelta(days=last_n_days))].copy()

snapshot = latest_snapshot(history)
snapshot = add_change_columns(snapshot, history)

col1, col2, col3 = st.columns(3)
col1.metric("Tracked rates", len(TRACKED_RATES))
col2.metric("History start", history["date"].min().strftime("%Y-%m-%d"))
col3.metric("Last observation", history["date"].max().strftime("%Y-%m-%d"))

st.subheader("Latest Snapshot")
st.dataframe(
    format_snapshot_table(
        snapshot[
            [
                "metric_name",
                "category",
                "region",
                "tenor",
                "value",
                "delta_1d",
                "delta_30d",
                "source_name",
            ]
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

st.subheader("How this V1 is organized")
st.markdown(
    """
- **Market Snapshot** page: latest values and category view
- **Historical Trends** page: single or multiple time-series charts
- **Compare Series** page: compare up to 3 selected metrics
- **Spreads Monitor** page: prebuilt sovereign and policy spreads
- **Data Admin** page: source metadata and data quality checks
    """
)

st.info(
    "V1 runs immediately with generated sample history. Replace the loader stubs in `data_sources.py` with live connectors when you are ready."
)
