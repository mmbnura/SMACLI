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

    if needs_refresh:
        master_df = loader.load(prefer_remote=True)
        repo.upsert_stocks_master(master_df)
        repo.set_meta(MASTER_SYNC_KEY, datetime.now(UTC).isoformat())
        return len(master_df)

    current = repo.get_stocks()
    if current.empty:
        master_df = loader.load(prefer_remote=False)
        repo.upsert_stocks_master(master_df)
        return len(master_df)

    return len(current)
