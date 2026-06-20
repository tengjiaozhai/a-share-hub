import logging

from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.orm import Session

from src.core.tenant import TenantContext
from src.storage.models import USStockWatchlistRow
from src.us_stock.models import USWatchlistItem

logger = logging.getLogger(__name__)


class WatchlistStore:
    """美股自选列表 CRUD，基于 SQLAlchemy engine。"""

    def __init__(self, engine, tenant: TenantContext):
        self._engine = engine
        self._tenant = tenant

    @property
    def _user_id(self) -> str:
        return self._tenant.user_id

    def list_items(self, page: int = 1, page_size: int = 20) -> tuple[list[USWatchlistItem], int]:
        offset = (page - 1) * page_size
        with Session(self._engine) as session:
            total = session.scalar(
                select(func.count()).select_from(USStockWatchlistRow).where(
                    USStockWatchlistRow.user_id == self._user_id
                )
            ) or 0
            rows = session.scalars(
                select(USStockWatchlistRow)
                .where(USStockWatchlistRow.user_id == self._user_id)
                .order_by(USStockWatchlistRow.sort_order, USStockWatchlistRow.id)
                .limit(page_size)
                .offset(offset)
            ).all()
        items = [
            USWatchlistItem(
                id=row.id,
                symbol=row.symbol,
                name=row.name,
                sort_order=row.sort_order,
                created_at=row.created_at,
            )
            for row in rows
        ]
        return items, total

    def add(self, symbol: str, name: str, sort_order: int = 0) -> USWatchlistItem:
        from sqlalchemy.exc import IntegrityError

        row = USStockWatchlistRow(
            user_id=self._user_id,
            symbol=symbol.upper(),
            name=name,
            sort_order=sort_order,
        )
        with Session(self._engine) as session:
            session.add(row)
            try:
                session.commit()
            except IntegrityError as e:
                session.rollback()
                raise ValueError(f"Symbol {symbol} already exists in watchlist") from e
            session.refresh(row)
        return USWatchlistItem(
            id=row.id,
            symbol=row.symbol,
            name=row.name,
            sort_order=row.sort_order,
            created_at=row.created_at,
        )

    def remove(self, symbol: str) -> bool:
        with Session(self._engine) as session:
            result = session.execute(
                sa_delete(USStockWatchlistRow).where(
                    USStockWatchlistRow.user_id == self._user_id,
                    USStockWatchlistRow.symbol == symbol.upper(),
                )
            )
            session.commit()
            return result.rowcount > 0

    def get_by_symbol(self, symbol: str) -> USWatchlistItem | None:
        with Session(self._engine) as session:
            row = session.scalar(
                select(USStockWatchlistRow).where(
                    USStockWatchlistRow.user_id == self._user_id,
                    USStockWatchlistRow.symbol == symbol.upper(),
                )
            )
        if not row:
            return None
        return USWatchlistItem(
            id=row.id,
            symbol=row.symbol,
            name=row.name,
            sort_order=row.sort_order,
            created_at=row.created_at,
        )
