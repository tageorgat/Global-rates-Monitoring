from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DEFAULT_HISTORY_START, MIN_HISTORY_START
from services import get_master_data_cached
from utils import apply_standard_timeseries_layout, filter_from_start_date

st.title("Historical Trends")
st.caption("Explore tracked rates over time.")

data = get_master_data_cached()

if data.empty:
    st.info("No data available.")
    st.stop()

data = data.copy()
data["date"] = pd.to_datetime(data["date"], errors="coerce")
data = data.dropna(subset=["date", "value"]).copy()
data = filter_from_start_date(data, start_date=MIN_HISTORY_START, date_col="date")

series_meta = (
    data[["metric_code", "metric_name", "category", "region"]]
    .drop_duplicates()
    .sort_values(["category", "region", "metric_name"])
)

available_names = series_meta["metric_name"].tolist()
default_names = available_names[:4] if len(available_names) >= 4 else available_names

controls_col1, controls_col2 = st.columns([2, 1])

with controls_col1:
    selected_names = st.multiselect(
        "Choose series",
        options=available_names,
        default=default_names,
    )

with controls_col2:
    max_allowed = data["date"].max().date()
    start_date = st.date_input(
        "Start date",
        value=pd.Timestamp(DEFAULT_HISTORY_START).date(),
        min_value=pd.Timestamp(MIN_HISTORY_START).date(),
        max_value=max_allowed,
    )

if not selected_names:
    st.warning("Select at least one series.")
    st.stop()

chart_df = data[data["metric_name"].isin(selected_names)].copy()
chart_df = filter_from_start_date(chart_df, start_date=start_date, date_col="date")

if chart_df.empty:
    st.warning("No data available for the selected date range.")
    st.stop()

monthly_df = (
    chart_df.set_index("date")
    .groupby("metric_name")["value"]
    .resample("MS")
    .last()
    .reset_index()
    .dropna(subset=["value"])
)

fig = px.line(
    monthly_df,
    x="date",
    y="value",
    color="metric_name",
    title="Tracked rates over time",
)

month_count = monthly_df["date"].nunique()
fig = apply_standard_timeseries_layout(fig, y_title="Rate (%)", month_count=month_count)

st.plotly_chart(fig, use_container_width=True)

st.markdown("### Data preview")
preview = monthly_df.copy()
preview["date"] = preview["date"].dt.date
st.dataframe(preview, use_container_width=True, hide_index=True)
