from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "nse500_advisor.db"
MASTER_CSV_PATH = DATA_DIR / "nifty500_master.csv"
MASTER_MICROCAP250_CSV_PATH = DATA_DIR / "nifty_microcap250_master.csv"

# Optional sources for auto-bootstrap of index lists when local CSV is missing.
NIFTY500_CSV_URL = (
    "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
)

# Nifty Microcap 250 list
NIFTY_MICROCAP250_CSV_URLS = [
    "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv",
]

HISTORY_PERIOD = "1y"
HISTORY_INTERVAL = "1d"

# Refresh thresholds (hours)
PRICE_REFRESH_HOURS = 8
FUNDAMENTAL_REFRESH_HOURS = 24
