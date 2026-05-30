from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.base import Base
from src.models.crypto_market_bar import CryptoMarketBar
from src.models.crypto_order import CryptoOrder
from src.models.crypto_position import CryptoPosition


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()

def test_create_market_bar(db_session):
    """测试创建市场数据"""
    bar = CryptoMarketBar(
        symbol="BTCUSDT",
        trade_time=datetime(2024, 1, 1, 0, 0, 0),
        open=42000.0,
        high=42500.0,
        low=41800.0,
        close=42200.0,
        volume=1000.0,
        quote_volume=42200000.0,
        trades_count=5000
    )
    db_session.add(bar)
    db_session.commit()

    result = db_session.query(CryptoMarketBar).first()
    assert result.symbol == "BTCUSDT"
    assert result.close == 42200.0

def test_create_position(db_session):
    """测试创建持仓"""
    position = CryptoPosition(
        symbol="BTCUSDT",
        quantity=0.5,
        avg_cost=42000.0,
        market_value=21100.0,
        unrealized_pnl=100.0,
        realized_pnl=0.0
    )
    db_session.add(position)
    db_session.commit()

    result = db_session.query(CryptoPosition).first()
    assert result.symbol == "BTCUSDT"
    assert result.quantity == 0.5

def test_create_order(db_session):
    """测试创建订单"""
    order = CryptoOrder(
        order_id="12345678",
        symbol="BTCUSDT",
        side="BUY",
        type="LIMIT",
        quantity=0.1,
        price=42000.0,
        status="NEW"
    )
    db_session.add(order)
    db_session.commit()

    result = db_session.query(CryptoOrder).first()
    assert result.order_id == "12345678"
    assert result.side == "BUY"
