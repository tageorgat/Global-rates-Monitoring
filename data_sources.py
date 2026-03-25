from __future__ import annotations

from io import StringIO
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests

from config import RAW_DIR, TRACKED_RATES, RateConfig
from utils import utc_now_ts

REQUEST_TIMEOUT = 25
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
BOE_CSV_URL = (
    "https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp"
    "?csv.x=yes&Datefrom=01/Jan/1990&Dateto=now&SeriesCodes={series}"
    "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N"
)
USER_AGENT = {"User-Agent": "Mozilla/5.0 StreamlitRatesMonitor/3.0"}

# Cleaner public Euribor source
BOF_EURIBOR_URL = (
    "https://www.suomenpankki.fi/en/statistics/interest-rates-and-exchange-rates/"
    "euribor-rates/"
)

BOF_EURIBOR_COLUMN_MAP = {
    "EURIBOR_1M": "1 month",
    "EURIBOR_3M": "3 month",
    "EURIBOR_6M": "6 month",
    "EURIBOR_12M": "12 month",
}


def load_metric_live(
    cfg: RateConfig,
    existing_metric_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, dict]:
    loaders = {
        "fred": _load_fred,
        "boe_csv": _load_boe,
        "euribor_html": _load_euribor,
    }

    last_success = None
    if (
        existing_metric_df is not None
        and not existing_metric_df.empty
        and "date" in existing_metric_df.columns
    ):
        last_success = pd.to_datetime(existing_metric_df["date"], errors="coerce").max()
        if pd.notna(last_success):
            last_success = last_success.date()
        else:
            last_success = None

    try:
        df = loaders[cfg.source_kind](cfg, last_success)

        if df.empty:
            status = _status_payload(
                cfg,
                "up_to_date",
                0,
                "No newer rows than stored history",
                last_success,
            )
            return df, status

        latest_date = pd.to_datetime(df["date"], errors="coerce").max()
        status = _status_payload(
            cfg,
            "success",
            len(df),
            "Loaded successfully",
            latest_date,
        )
        return df, status

    except Exception as exc:
        status = _status_payload(cfg, "error", 0, str(exc), None)
        return pd.DataFrame(), status


def _load_fred(cfg: RateConfig, last_success_date=None) -> pd.DataFrame:
    url = FRED_CSV_URL.format(series=cfg.source_series)
    res = requests.get(url, timeout=REQUEST_TIMEOUT, headers=USER_AGENT)
    res.raise_for_status()

    RAW_DIR.joinpath(f"{cfg.code}_fred.csv").write_text(res.text, encoding="utf-8")

    df = pd.read_csv(StringIO(res.text))
    if df.shape[1] < 2:
        raise ValueError("Unexpected FRED CSV format")

    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "value"]).copy()

    if last_success_date is not None:
        df = df[df["date"].dt.date > last_success_date].copy()

    return _decorate(df, cfg)


def _load_boe(cfg: RateConfig, last_success_date=None) -> pd.DataFrame:
    url = BOE_CSV_URL.format(series=cfg.source_series)
    res = requests.get(url, timeout=REQUEST_TIMEOUT, headers=USER_AGENT)
    res.raise_for_status()

    RAW_DIR.joinpath(f"{cfg.code}_boe.csv").write_text(res.text, encoding="utf-8")

    text = res.text
    lines = [line for line in text.splitlines() if line.strip()]

    start_idx = 0
    for i, line in enumerate(lines):
        if "DATE" in line.upper() and "," in line:
            start_idx = i
            break

    csv_text = "\n".join(lines[start_idx:])
    df = pd.read_csv(StringIO(csv_text))

    date_col = df.columns[0]
    value_col = df.columns[-1]

    df = df[[date_col, value_col]].copy()
    df.columns = ["date", "value"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "value"]).copy()

    if last_success_date is not None:
        df = df[df["date"].dt.date > last_success_date].copy()

    return _decorate(df, cfg)


def _load_euribor(cfg: RateConfig, last_success_date=None) -> pd.DataFrame:
    res = requests.get(BOF_EURIBOR_URL, timeout=REQUEST_TIMEOUT, headers=USER_AGENT)
    res.raise_for_status()

    html = res.text
    RAW_DIR.joinpath(f"{cfg.code}_euribor_bof.html").write_text(html, encoding="utf-8")

    tables = pd.read_html(StringIO(html))
    if not tables:
        raise ValueError("No tables found on Bank of Finland Euribor page")

    target_label = BOF_EURIBOR_COLUMN_MAP.get(cfg.code)
    if target_label is None:
        raise ValueError(f"Unsupported Euribor code: {cfg.code}")

    euribor_df = None

    for table in tables:
        cols = [str(c).strip() for c in table.columns]

        # Try to find the table that contains Date + Euribor tenors
        has_date = any("date" in c.lower() for c in cols)
        has_target = any(target_label.lower() in c.lower() for c in cols)

        if has_date and has_target:
            euribor_df = table.copy()
            euribor_df.columns = cols
            break

    if euribor_df is None:
        raise ValueError(f"Could not identify Euribor table for {cfg.code}")

    date_col = None
    for c in euribor_df.columns:
        if "date" in c.lower():
            date_col = c
            break
    if date_col is None:
        date_col = euribor_df.columns[0]

    value_col = None
    for c in euribor_df.columns:
        if target_label.lower() in str(c).lower():
            value_col = c
            break

    if value_col is None:
        raise ValueError(f"Could not find Euribor tenor column '{target_label}'")

    df = euribor_df[[date_col, value_col]].copy()
    df.columns = ["date", "value"]

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df["value"] = (
        df["value"]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.extract(r"([-+]?\d*\.?\d+)")[0]
    )
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    df = df.dropna(subset=["date", "value"]).copy()
    df = df[(df["date"] >= pd.Timestamp("1999-01-01")) & (df["value"].between(-5, 20))].copy()
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    if last_success_date is not None:
        df = df[df["date"].dt.date > last_success_date].copy()

    return _decorate(df, cfg)


def generate_sample_history() -> pd.DataFrame:
    """
    Fallback/bootstrap data only.
    Used when the app has no stored history yet.
    This should not drive live values after refresh succeeds.
    """
    dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=365 * 5, freq="B")
    rng = np.random.default_rng(42)

    base_values = {
        "ECB_DFR": 2.50,
        "ECB_MRO": 2.65,
        "FED_FUNDS": 4.35,
        "SOFR": 4.30,
        "BOE_BANK_RATE": 4.25,
        "EURIBOR_1M": 1.96,
        "EURIBOR_3M": 2.18,
        "EURIBOR_6M": 2.52,
        "EURIBOR_12M": 2.79,
        "DE_10Y": 2.45,
        "GR_10Y": 3.35,
        "US_10Y": 4.10,
        "EA_HICP": 2.10,
    }

    rows = []
    for cfg in TRACKED_RATES:
        noise = rng.normal(0, 0.02, len(dates)).cumsum() / 6
        trend = np.linspace(-0.35, 0.0, len(dates))
        values = np.maximum(-1, base_values.get(cfg.code, 2.0) + noise + trend)

        if cfg.code == "EA_HICP":
            dates_metric = pd.date_range(end=pd.Timestamp.today().normalize(), periods=60, freq="MS")
            noise_m = rng.normal(0, 0.05, len(dates_metric)).cumsum() / 4
            vals = np.maximum(-2, base_values.get(cfg.code, 2.0) + noise_m)
            frame = pd.DataFrame({"date": dates_metric, "value": vals})

        elif cfg.code in {"DE_10Y", "GR_10Y"}:
            dates_metric = pd.date_range(end=pd.Timestamp.today().normalize(), periods=60, freq="MS")
            noise_m = rng.normal(0, 0.03, len(dates_metric)).cumsum() / 4
            vals = np.maximum(-1, base_values.get(cfg.code, 2.0) + noise_m)
            frame = pd.DataFrame({"date": dates_metric, "value": vals})

        else:
            frame = pd.DataFrame({"date": dates, "value": values})

        rows.append(_decorate(frame, cfg))

    return pd.concat(rows, ignore_index=True)


def _decorate(df: pd.DataFrame, cfg: RateConfig) -> pd.DataFrame:
    out = df.copy()
    out["metric_code"] = cfg.code
    out["metric_name"] = cfg.name
    out["category"] = cfg.category
    out["region"] = cfg.region
    out["tenor"] = cfg.tenor
    out["source_name"] = cfg.source_name
    out["source_series"] = cfg.source_series
    out["frequency"] = cfg.frequency
    out["units"] = cfg.units
    out["loaded_at"] = utc_now_ts()

    return out[
        [
            "date",
            "metric_code",
            "metric_name",
            "category",
            "region",
            "tenor",
            "value",
            "source_name",
            "source_series",
            "frequency",
            "units",
            "loaded_at",
        ]
    ]


def _status_payload(
    cfg: RateConfig,
    status: str,
    rows_loaded: int,
    message: str,
    latest_date,
) -> dict:
    now_utc = utc_now_ts()

    return {
        "metric_code": cfg.code,
        "metric_name": cfg.name,
        "source_name": cfg.source_name,
        "status": status,
        "rows_loaded": rows_loaded,
        "message": message,
        "last_attempt_utc": now_utc,
        "last_success_utc": now_utc if status == "success" else None,
        "latest_data_date": (
            pd.to_datetime(latest_date).date().isoformat()
            if latest_date is not None and pd.notna(latest_date)
            else None
        ),
    }
