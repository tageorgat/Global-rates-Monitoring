from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

APP_TITLE = "Global Rates Tracker"
APP_SUBTITLE = "Historical monitoring with local cache, safer refreshes, and spread analytics"
DEFAULT_LOOKBACK_DAYS = 365 * 5
DATE_FMT = "%Y-%m-%d"
PCT_FMT = "{:.2f}%"
BPS_FMT = "{:.0f} bps"

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
STATUS_PATH = CACHE_DIR / "source_status.csv"
MASTER_DATA_PATH = CACHE_DIR / "rates_history.parquet"
MASTER_DATA_CSV_PATH = CACHE_DIR / "rates_history.csv"

RAW_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MIN_HISTORY_START = "2019-01-01"
DEFAULT_HISTORY_START = "2019-01-01"



@dataclass(frozen=True)
class RateConfig:
    code: str
    name: str
    category: str
    region: str
    tenor: Optional[str]
    source_name: str
    source_kind: str
    source_series: str
    units: str = "Percent"
    frequency: str = "Daily"
    enabled: bool = True


TRACKED_RATES: list[RateConfig] = [
    RateConfig("ECB_DFR", "ECB Deposit Facility Rate", "Policy Rate", "Eurozone", None, "FRED", "fred", "ECBDFR"),
    RateConfig("ECB_MRO", "ECB Main Refinancing Operations Rate", "Policy Rate", "Eurozone", None, "FRED", "fred", "ECBMRRFR"),
    RateConfig("FED_FUNDS", "Federal Funds Effective Rate", "Policy Rate", "United States", None, "FRED", "fred", "DFF"),
    RateConfig("SOFR", "SOFR", "Money Market", "United States", "ON", "FRED", "fred", "SOFR"),
    RateConfig("BOE_BANK_RATE", "Bank of England Bank Rate", "Policy Rate", "United Kingdom", None, "BOE", "boe_csv", "IUDBEDR"),
    RateConfig("EURIBOR_1M", "Euribor 1M", "Money Market", "Eurozone", "1M", "EMMI", "euribor_html", "1-month-euribor-rate"),
    RateConfig("EURIBOR_3M", "Euribor 3M", "Money Market", "Eurozone", "3M", "EMMI", "euribor_html", "3-month-euribor-rate"),
    RateConfig("EURIBOR_6M", "Euribor 6M", "Money Market", "Eurozone", "6M", "EMMI", "euribor_html", "6-month-euribor-rate"),
    RateConfig("EURIBOR_12M", "Euribor 12M", "Money Market", "Eurozone", "12M", "EMMI", "euribor_html", "12-month-euribor-rate"),
    RateConfig("DE_10Y", "Germany 10Y Government Bond Yield", "Sovereign Yield", "Germany", "10Y", "FRED", "fred", "IRLTLT01DEM156N"),
    RateConfig("GR_10Y", "Greece 10Y Government Bond Yield", "Sovereign Yield", "Greece", "10Y", "FRED", "fred", "IRLTLT01GRM156N"),
    RateConfig("US_10Y", "US 10Y Treasury Yield", "Sovereign Yield", "United States", "10Y", "FRED", "fred", "DGS10"),
    RateConfig("EA_HICP", "Euro Area HICP YoY", "Inflation", "Eurozone", None, "FRED", "fred", "CP0000EZ19M086NEST"),
]

SPREAD_DEFINITIONS = {
    "GR_MINUS_DE_10Y": ("GR_10Y", "DE_10Y", "Greece 10Y - Germany 10Y"),
    "EURIBOR_3M_MINUS_ECB_DFR": ("EURIBOR_3M", "ECB_DFR", "Euribor 3M - ECB DFR"),
    "EURIBOR_12M_MINUS_ECB_MRO": ("EURIBOR_12M", "ECB_MRO", "Euribor 12M - ECB MRO"),
    "US_10Y_MINUS_FED_FUNDS": ("US_10Y", "FED_FUNDS", "US 10Y - Fed Funds"),
}

DEFAULT_COMPARE_CODES = ["ECB_DFR", "EURIBOR_3M", "DE_10Y"]
