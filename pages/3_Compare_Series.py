from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DEFAULT_COMPARE_CODES, DEFAULT_HISTORY_START, MIN_HISTORY_START
from services import get_master_data_cached
from utils import filter_from_start_date, monthly_axis_config

st.title("Compare Series")
st.caption("Compare up to 3 tracked rates over time.")

data = get_master_data_cached()

if data.empty:
    st.info("No data available.")
    st.stop()

data = data.copy()
data["date"] = pd.to_datetime(data["date"], errors="coerce")
data = data.dropna(subset=["date", "value"])

# Global floor from 2000 onward
data = filter_from_start_date(data, start_date=MIN_HISTORY_START, date_col="date")

series_meta = (
    data[["metric_code", "metric_name", "category", "region"]]
    .drop_duplicates()
    .sort_values(["category", "region", "metric_name"])
)

code_to_name = dict(zip(series_meta["metric_code"], series_meta["metric_name"]))
available_codes = series_meta["metric_code"].tolist()

default_codes = [c for c in DEFAULT_COMPARE_CODES if c in available_codes]
if not default_codes:
    default_codes = available_codes[:3]

c1, c2 = st.columns([2, 1])

with c1:
    selected_codes = st.multiselect(
        "Select up to 3 series",
        options=available_codes,
        default=default_codes,
        format_func=lambda x: code_to_name.get(x, x),
        max_selections=3,
    )

with c2:
    max_allowed = data["date"].max().date()
    start_date = st.date_input(
        "Start date",
        value=pd.Timestamp(DEFAULT_HISTORY_START).date(),
        min_value=pd.Timestamp(MIN_HISTORY_START).date(),
        max_value=max_allowed,
    )

if not selected_codes:
    st.warning("Select at least one series.")
    st.stop()

chart_df = data[data["metric_code"].isin(selected_codes)].copy()
chart_df = filter_from_start_date(chart_df, start_date=start_date, date_col="date")

if chart_df.empty:
    st.warning("No data available for the selected date range.")
    st.stop()

# Monthly detail: keep month-end / month-start level for cleaner charting
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
    markers=False,
)

fig.update_layout(
    xaxis_title="Month",
    yaxis_title="Rate (%)",
    legend_title="Series",
    hovermode="x unified",
)

fig.update_xaxes(**monthly_axis_config())

st.plotly_chart(fig, use_container_width=True)

st.markdown("### Data preview")
preview = monthly_df.copy()
preview["date"] = preview["date"].dt.date
st.dataframe(preview, use_container_width=True, hide_index=True)