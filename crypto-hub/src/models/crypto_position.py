from sqlalchemy import Column, DateTime, Integer, Numeric, String, func

from .base import Base


class CryptoPosition(Base):
    __tablename__ = "crypto_position"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, unique=True, index=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_cost = Column(Numeric(20, 8))
    market_value = Column(Numeric(20, 8))
    unrealized_pnl = Column(Numeric(20, 8))
    realized_pnl = Column(Numeric(20, 8))
    updated_at = Column(DateTime, onupdate=func.now())
