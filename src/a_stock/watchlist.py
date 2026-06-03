import logging
from typing import Any

from src.a_stock.models import AStockWatchlistItem

logger = logging.getLogger(__name__)


class AShareWatchlistStore:
    """A 股自选列表 CRUD。"""

    def __init__(self, conn: Any):
        self._conn = conn

    def list_items(self) -> list[AStockWatchlistItem]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM a_share_watchlist ORDER BY sort_order, id"
            )
            rows = cur.fetchall()
        return [
            AStockWatchlistItem(
                id=row["id"],
                symbol=row["symbol"],
                name=row["name"],
                sort_order=row["sort_order"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def add(self, symbol: str, name: str, sort_order: int = 0) -> AStockWatchlistItem:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO a_share_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
                    "RETURNING id, symbol, name, sort_order, created_at",
                    (symbol.upper(), name, sort_order),
                )
                row = cur.fetchone()
                self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise ValueError(f"Symbol {symbol} already exists in watchlist") from e
            raise

        return AStockWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )

    def remove(self, symbol: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM a_share_watchlist WHERE symbol = %s", (symbol.upper(),))
            deleted = cur.rowcount > 0
            self._conn.commit()
        return deleted

    def get_by_symbol(self, symbol: str) -> AStockWatchlistItem | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM a_share_watchlist WHERE symbol = %s",
                (symbol.upper(),),
            )
            row = cur.fetchone()
        if not row:
            return None
        return AStockWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )