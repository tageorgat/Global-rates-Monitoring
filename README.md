# Global Rates Monitor V3

A Streamlit monitoring app for 13 tracked macro/market series with:
- stored historical data
- safer refresh logic
- source status visibility
- spread analytics
- sample-data bootstrap for first run

## Tracked series
1. ECB Deposit Facility Rate
2. ECB Main Refinancing Operations Rate
3. Federal Funds Effective Rate
4. SOFR
5. Bank of England Bank Rate
6. Euribor 1M
7. Euribor 3M
8. Euribor 6M
9. Euribor 12M
10. Germany 10Y government bond yield
11. Greece 10Y government bond yield
12. US 10Y Treasury yield
13. Euro Area HICP YoY

## V3 vs V2
V3 adds:
- local historical store in `data/cache/`
- cached loads with `st.cache_data`
- preserve last good history if a live source fails
- visible source status table
- refresh button that only appends/replaces new dates

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Important notes
- On first run, the app bootstraps with sample historical data so it opens immediately.
- When you press **Refresh live data**, it tries to load each source and merge new rows into the stored history.
- If parquet writing is unavailable, the app falls back to CSV storage.
- Live connectors depend on external websites and may need small parser updates over time.

## Main folders
- `app.py` home page
- `pages/` Streamlit multipage views
- `data_sources.py` live loaders + sample generator
- `storage.py` local persistence
- `services.py` refresh orchestration + caching
- `data/cache/` stored history and source status

## Source approach in this starter
- FRED CSV for several policy and market rates
- BoE CSV export for Bank Rate
- Public Euribor history page parsing for 1M / 3M / 6M / 12M

For production hardening, the next improvement is to add source-specific validation rules and optional scheduled refresh jobs.
