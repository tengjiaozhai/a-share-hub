from sqlalchemy import create_engine

from src.api.routes_broker_events import receive_broker_event
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_receive_broker_event(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    result = receive_broker_event(
        {"event_id": "E1", "event_type": "FILLED", "order_id": "O1"}, store=store
    )
    assert result["received"] is True
    assert result["event_type"] == "FILLED"
