from sqlalchemy import Column, DateTime, Integer, Numeric, String, func

from .base import Base


class CryptoMarketBar(Base):
    __tablename__ = "crypto_market_bar"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    trade_time = Column(DateTime, nullable=False, index=True)
    open = Column(Numeric(20, 8))
    high = Column(Numeric(20, 8))
    low = Column(Numeric(20, 8))
    close = Column(Numeric(20, 8))
    volume = Column(Numeric(20, 8))
    quote_volume = Column(Numeric(20, 8))
    trades_count = Column(Integer)
    created_at = Column(DateTime, default=func.now())
