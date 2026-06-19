import logging
from typing import Any

from src.us_stock.models import USWatchlistItem

logger = logging.getLogger(__name__)


class WatchlistStore:
    """美股自选列表 CRUD，基于 psycopg 连接。"""

    def __init__(self, conn: Any, user_id: str):
        self._conn = conn
        self._user_id = user_id

    def list_items(self, page: int = 1, page_size: int = 20) -> tuple[list[USWatchlistItem], int]:
        offset = (page - 1) * page_size
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM us_watchlist WHERE user_id = %s", (self._user_id,))
            total = cur.fetchone()["count"]
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM us_watchlist "
                "WHERE user_id = %s ORDER BY sort_order, id LIMIT %s OFFSET %s",
                (self._user_id, page_size, offset),
            )
            rows = cur.fetchall()
        items = [
            USWatchlistItem(
                id=row["id"],
                symbol=row["symbol"],
                name=row["name"],
                sort_order=row["sort_order"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
        return items, total

    def add(self, symbol: str, name: str, sort_order: int = 0) -> USWatchlistItem:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO us_watchlist (user_id, symbol, name, sort_order) "
                    "VALUES (%s, %s, %s, %s) "
                    "RETURNING id, symbol, name, sort_order, created_at",
                    (self._user_id, symbol.upper(), name, sort_order),
                )
                row = cur.fetchone()
                self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise ValueError(f"Symbol {symbol} already exists in watchlist") from e
            raise

        return USWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )

    def remove(self, symbol: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM us_watchlist WHERE user_id = %s AND symbol = %s",
                (self._user_id, symbol.upper()),
            )
            deleted = cur.rowcount > 0
            self._conn.commit()
        return deleted

    def get_by_symbol(self, symbol: str) -> USWatchlistItem | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM us_watchlist "
                "WHERE user_id = %s AND symbol = %s",
                (self._user_id, symbol.upper()),
            )
            row = cur.fetchone()
        if not row:
            return None
        return USWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )
