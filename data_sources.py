from __future__ import annotations

from io import StringIO
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import RAW_DIR, TRACKED_RATES, RateConfig
from utils import utc_now_ts

REQUEST_TIMEOUT = 60
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
BOE_CSV_URL = (
    "https://www.bankofengland.co.uk/boeapps/database/FromShowColumns.asp"
    "?csv.x=yes&Datefrom=01/Jan/1990&Dateto=now&SeriesCodes={series}"
    "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N"
)
USER_AGENT = {"User-Agent": "Mozilla/5.0 StreamlitRatesMonitor/3.0"}

# Keep compatibility with your CURRENT config.py slugs
EURIBOR_CURRENT_URLS = {
    "1-month-euribor-rate": "https://www.euribor-rates.eu/en/current-euribor-rates/1/euribor-rate-1-month/",
    "3-month-euribor-rate": "https://www.euribor-rates.eu/en/current-euribor-rates/2/euribor-rate-3-months/",
    "6-month-euribor-rate": "https://www.euribor-rates.eu/en/current-euribor-rates/3/euribor-rate-6-months/",
    "12-month-euribor-rate": "https://www.euribor-rates.eu/en/current-euribor-rates/4/euribor-rate-12-months/",
    # Also support cleaner identifiers if you later update config.py
    "EURIBOR_1M": "https://www.euribor-rates.eu/en/current-euribor-rates/1/euribor-rate-1-month/",
    "EURIBOR_3M": "https://www.euribor-rates.eu/en/current-euribor-rates/2/euribor-rate-3-months/",
    "EURIBOR_6M": "https://www.euribor-rates.eu/en/current-euribor-rates/3/euribor-rate-6-months/",
    "EURIBOR_12M": "https://www.euribor-rates.eu/en/current-euribor-rates/4/euribor-rate-12-months/",
}

# Match by aliases first; fallback to positional index if the page has a multi-tenor table:
# date | 1 week | 1 month | 3 months | 6 months | 12 months
EURIBOR_ALIASES = {
    "1-month-euribor-rate": ["1 month", "1-month", "1m"],
    "3-month-euribor-rate": ["3 months", "3 month", "3-month", "3m"],
    "6-month-euribor-rate": ["6 months", "6 month", "6-month", "6m"],
    "12-month-euribor-rate": ["12 months", "12 month", "12-month", "12m"],
    "EURIBOR_1M": ["1 month", "1-month", "1m"],
    "EURIBOR_3M": ["3 months", "3 month", "3-month", "3m"],
    "EURIBOR_6M": ["6 months", "6 month", "6-month", "6m"],
    "EURIBOR_12M": ["12 months", "12 month", "12-month", "12m"],
}

EURIBOR_POSITIONAL_INDEX = {
    "1-month-euribor-rate": 2,
    "3-month-euribor-rate": 3,
    "6-month-euribor-rate": 4,
    "12-month-euribor-rate": 5,
    "EURIBOR_1M": 2,
    "EURIBOR_3M": 3,
    "EURIBOR_6M": 4,
    "EURIBOR_12M": 5,
}


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(USER_AGENT)
    return session


SESSION = _build_session()


def _read_html_tables(html: str) -> list[pd.DataFrame]:
    """
    Try multiple parser flavors. This makes the error message much clearer
    when parser dependencies are missing.
    """
    last_err = None

    for kwargs in ({}, {"flavor": "lxml"}, {"flavor": "bs4"}):
        try:
            return pd.read_html(StringIO(html), **kwargs)
        except Exception as e:
            last_err = e

    raise ValueError(
        "HTML table parsing failed. Install parser dependencies with: "
        "pip install lxml beautifulsoup4 html5lib"
    ) from last_err


def _norm(text: str) -> str:
    return str(text).strip().lower().replace("\n", " ").replace("  ", " ")


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
    res = SESSION.get(url, timeout=REQUEST_TIMEOUT)
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
    res = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    res.raise_for_status()

    RAW_DIR.joinpath(f"{cfg.code}_boe.csv").write_text(res.text, encoding="utf-8")

    text = res.text
    lines = [line for line in text.splitlines() if line.strip()]

    start_idx = None
    for i, line in enumerate(lines):
        if "DATE" in line.upper() and "," in line:
            start_idx = i
            break

    if start_idx is None:
        raise ValueError("Could not locate BOE CSV header row")

    csv_text = "\n".join(lines[start_idx:])

    df = pd.read_csv(
        StringIO(csv_text),
        engine="python",
        on_bad_lines="skip",
    )

    if df.shape[1] < 2:
        raise ValueError("Unexpected BOE CSV format after parsing")

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
    url = EURIBOR_CURRENT_URLS.get(cfg.source_series)
    if not url:
        raise ValueError(f"Unsupported Euribor series: {cfg.source_series}")

    res = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    res.raise_for_status()

    html = res.text
    RAW_DIR.joinpath(f"{cfg.code}_euribor_current.html").write_text(html, encoding="utf-8")

    tables = _read_html_tables(html)
    aliases = [_norm(x) for x in EURIBOR_ALIASES.get(cfg.source_series, [])]
    fallback_idx = EURIBOR_POSITIONAL_INDEX.get(cfg.source_series)

    frames = []

    for table in tables:
        if table.empty or table.shape[1] < 2:
            continue

        working = table.copy()
        working.columns = [str(c).strip() for c in working.columns]

        # Try to locate date column
        date_col = None
        for c in working.columns:
            if "date" in _norm(c):
                date_col = c
                break
        if date_col is None:
            date_col = working.columns[0]

        # Try to locate the correct tenor column by header text
        value_col = None
        for c in working.columns:
            nc = _norm(c)
            if any(alias in nc for alias in aliases):
                value_col = c
                break

        # Fallback: many Euribor tables are [date, 1w, 1m, 3m, 6m, 12m]
        if value_col is None and fallback_idx is not None and working.shape[1] > fallback_idx:
            value_col = working.columns[fallback_idx]

        # Final fallback: if there are only 2 columns, use the 2nd one
        if value_col is None and working.shape[1] == 2:
            value_col = working.columns[1]

        if value_col is None:
            continue

        tmp = working[[date_col, value_col]].copy()
        tmp.columns = ["date", "value"]

        tmp["date"] = pd.to_datetime(tmp["date"], errors="coerce", dayfirst=True)
        tmp["value"] = (
            tmp["value"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.extract(r"([-+]?\d*\.?\d+)")[0]
        )
        tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")

        tmp = tmp.dropna(subset=["date", "value"]).copy()
        tmp = tmp[
            (tmp["date"] >= pd.Timestamp("1999-01-01"))
            & (tmp["value"].between(-5, 20))
        ].copy()

        if not tmp.empty:
            frames.append(tmp)

    if not frames:
        raise ValueError(f"Could not parse Euribor page for {cfg.code}")

    df = (
        pd.concat(frames, ignore_index=True)
        .sort_values("date")
        .drop_duplicates(subset=["date"], keep="last")
        .reset_index(drop=True)
    )

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
        "EURIBOR_6M": 2.59,
        "EURIBOR_12M": 2.93,
        "DE_10Y": 2.45,
        "GR_10Y": 3.35,
        "US_10Y": 4.10,
        "EA_HICP": 2.10,
    }

    rows = []
    for cfg in TRACKED_RATES:
        noise = rng.normal(0, 0.02, len(dates)).cumsum() / 6
        trend = np.linspace(-0.35, 0.0, len(dates))
        base = base_values.get(cfg.code, 2.0)
        values = np.maximum(-1, base + noise + trend)

        if cfg.code == "EA_HICP":
            dates_metric = pd.date_range(
                end=pd.Timestamp.today().normalize(),
                periods=60,
                freq="MS",
            )
            noise_m = rng.normal(0, 0.05, len(dates_metric)).cumsum() / 4
            vals = np.maximum(-2, base + noise_m)
            frame = pd.DataFrame({"date": dates_metric, "value": vals})

        elif cfg.code in {"DE_10Y", "GR_10Y"}:
            dates_metric = pd.date_range(
                end=pd.Timestamp.today().normalize(),
                periods=60,
                freq="MS",
            )
            noise_m = rng.normal(0, 0.03, len(dates_metric)).cumsum() / 4
            vals = np.maximum(-1, base + noise_m)
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
