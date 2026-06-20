import json
from unittest.mock import MagicMock

from src.api.routes_broker_events import receive_broker_event
from src.core.tenant import TenantContext
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_receive_broker_event(tmp_path):
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))

    class FakeRequest:
        async def body(self):
            return json.dumps({"event_id": "E1", "event_type": "FILLED", "order_id": "O1"}).encode()

    import asyncio
    result = asyncio.run(receive_broker_event(request=FakeRequest(), store=store))
    assert result["received"] is True
    assert result["event_type"] == "FILLED"
