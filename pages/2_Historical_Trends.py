from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import DEFAULT_LOOKBACK_DAYS
from services import get_master_data_cached

st.title("Historical Trends")

data = get_master_data_cached()
if data.empty:
    st.info("No data available.")
    st.stop()

metric_names = sorted(data["metric_name"].unique())
selected = st.multiselect("Choose series", metric_names, default=metric_names[:4])
start_date = st.date_input("Start date", value=(pd.Timestamp.today() - pd.Timedelta(days=DEFAULT_LOOKBACK_DAYS)).date())
filtered = data[data["metric_name"].isin(selected) & (data["date"].dt.date >= start_date)].copy()

fig = px.line(filtered, x="date", y="value", color="metric_name", title="Tracked rates over time")
fig.update_layout(legend_title_text="Series")
st.plotly_chart(fig, use_container_width=True)

st.dataframe(filtered.sort_values(["metric_name", "date"], ascending=[True, False]), use_container_width=True, hide_index=True)
