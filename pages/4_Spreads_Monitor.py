from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DEFAULT_HISTORY_START, MIN_HISTORY_START
from metrics import build_spreads
from services import get_master_data_cached
from utils import filter_from_start_date, monthly_axis_config

st.title("Spreads Monitor")
st.caption("Monitor calculated spreads between tracked rates over time.")

data = get_master_data_cached()

if data.empty:
    st.info("No data available.")
    st.stop()

data = data.copy()
data["date"] = pd.to_datetime(data["date"], errors="coerce")
data = data.dropna(subset=["date", "value"])

# Global floor from 2000 onward
data = filter_from_start_date(data, start_date=MIN_HISTORY_START, date_col="date")

spreads = build_spreads(data)

if spreads.empty:
    st.info("No spreads available.")
    st.stop()

spreads = spreads.copy()
spreads["date"] = pd.to_datetime(spreads["date"], errors="coerce")
spreads = spreads.dropna(subset=["date", "value"])

spread_meta = (
    spreads[["spread_code", "spread_name"]]
    .drop_duplicates()
    .sort_values("spread_name")
)

available_spreads = spread_meta["spread_code"].tolist()
spread_name_map = dict(zip(spread_meta["spread_code"], spread_meta["spread_name"]))

default_spread = available_spreads[0] if available_spreads else None

c1, c2 = st.columns([2, 1])

with c1:
    selected_spread = st.selectbox(
        "Select spread",
        options=available_spreads,
        index=0 if default_spread else None,
        format_func=lambda x: spread_name_map.get(x, x),
    )

with c2:
    max_allowed = spreads["date"].max().date()
    start_date = st.date_input(
        "Start date",
        value=pd.Timestamp(DEFAULT_HISTORY_START).date(),
        min_value=pd.Timestamp(MIN_HISTORY_START).date(),
        max_value=max_allowed,
    )

if not selected_spread:
    st.warning("No spread selected.")
    st.stop()

chart_df = spreads[spreads["spread_code"] == selected_spread].copy()
chart_df = filter_from_start_date(chart_df, start_date=start_date, date_col="date")

if chart_df.empty:
    st.warning("No spread data available for the selected date range.")
    st.stop()

# Monthly detail for readability
monthly_df = (
    chart_df.set_index("date")["value"]
    .resample("MS")
    .last()
    .reset_index()
    .dropna(subset=["value"])
)

monthly_df["spread_name"] = spread_name_map[selected_spread]

fig = px.line(
    monthly_df,
    x="date",
    y="value",
    title=spread_name_map[selected_spread],
)

fig.update_layout(
    xaxis_title="Month",
    yaxis_title="Spread (pp)",
    hovermode="x unified",
)

fig.update_xaxes(**monthly_axis_config())

st.plotly_chart(fig, use_container_width=True)

st.markdown("### Data preview")
preview = monthly_df.copy()
preview["date"] = preview["date"].dt.date
st.dataframe(preview, use_container_width=True, hide_index=True)