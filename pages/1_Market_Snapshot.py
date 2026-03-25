from __future__ import annotations

import streamlit as st

from services import get_master_data_cached
from metrics import latest_points
from utils import fmt_pct

st.title("Market Snapshot")

data = get_master_data_cached()
latest = latest_points(data)

if latest.empty:
    st.info("No data available.")
else:
    for category, sub in latest.sort_values(["category", "metric_name"]).groupby("category"):
        st.subheader(category)
        cols = st.columns(3)
        for i, (_, row) in enumerate(sub.iterrows()):
            delta = row.get("delta")
            cols[i % 3].metric(
                row["metric_name"],
                fmt_pct(row["value"]),
                None if delta != delta else f"{delta:.2f} pp",
                help=f"Last available date: {row['date'].date()} | Source: {row['source_name']}"
            )
