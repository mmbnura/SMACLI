from __future__ import annotations

from src.data_fetcher import MasterStockLoader
from src.db import init_db
from src.repository import StockRepository


def bootstrap_master_data() -> int:
    init_db()
    repo = StockRepository()
    current = repo.get_stocks()
    if not current.empty:
        return len(current)

    loader = MasterStockLoader()
    master_df = loader.load()
    repo.upsert_stocks_master(master_df)
    return len(master_df)
