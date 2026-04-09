from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.data_fetcher import MasterStockLoader
from src.db import init_db
from src.repository import StockRepository

UTC = timezone.utc
MASTER_SYNC_KEY = "master_list_last_sync"
MASTER_SYNC_HOURS = 24


def bootstrap_master_data(force_refresh: bool = False) -> int:
    init_db()
    repo = StockRepository()

    needs_refresh = force_refresh
    last_sync = repo.get_meta(MASTER_SYNC_KEY)

    if not needs_refresh and not last_sync:
        needs_refresh = True
    elif not needs_refresh and last_sync:
        cutoff = datetime.now(UTC) - timedelta(hours=MASTER_SYNC_HOURS)
        needs_refresh = datetime.fromisoformat(last_sync) < cutoff

    loader = MasterStockLoader()
    total_stocks = 0

    # Load Nifty 500
    if needs_refresh:
        master_df = loader.load(index_type="nifty500", prefer_remote=True)
    else:
        master_df = loader.load(index_type="nifty500", prefer_remote=False)
    
    if not master_df.empty:
        repo.upsert_stocks_master(master_df, index_type="nifty500")
        total_stocks += len(master_df)

    # Load Nifty Microcap 250 (optional - may fail silently)
    try:
        if needs_refresh:
            microcap_df = loader.load(index_type="nifty_microcap250", prefer_remote=True)
        else:
            microcap_df = loader.load(index_type="nifty_microcap250", prefer_remote=False)
        
        if not microcap_df.empty:
            repo.upsert_stocks_master(microcap_df, index_type="nifty_microcap250")
            total_stocks += len(microcap_df)
    except Exception:
        # Nifty Microcap 250 is optional, continue if it fails
        pass

    if needs_refresh and total_stocks > 0:
        repo.set_meta(MASTER_SYNC_KEY, datetime.now(UTC).isoformat())

    if total_stocks == 0:
        current = repo.get_stocks()
        total_stocks = len(current)

    return total_stocks
