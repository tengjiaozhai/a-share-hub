from src.alpha.analysis_run_store import AnalysisRunStore
from src.core.tenant import TenantContext


def test_runs_and_events_persist_with_monotonic_seq(pg_engine):
    store = AnalysisRunStore(pg_engine, TenantContext("alice"))

    run_id = store.create_run(symbol="MU.US", model_name="deepseek-v4-pro")
    assert run_id.startswith("alpha-ar-")

    event_ids: list[int] = []
    for stage in ["accepted", "snapshot", "research"]:
        event_ids.append(
            store.append_event(run_id=run_id, stage=stage, status="done", payload={"stage": stage})
        )

    assert event_ids == sorted(event_ids)
    events = store.list_events(run_id)
    assert [e["stage"] for e in events] == ["accepted", "snapshot", "research"]
    assert all(e["user_id"] == "alice" for e in events)


def test_alpha_event_replay_uses_stage_as_sse_event_name():
    import asyncio
    import json

    from src.api.routes_alpha import _event_iter

    class FakeRunStore:
        def list_events(self, run_id, after_seq=0):
            return [
                {"seq": 1, "stage": "accepted", "status": "done", "payload": {}, "event_type": "accepted"},
                {"seq": 2, "stage": "snapshot", "status": "done", "payload": {}, "event_type": "stage"},
                {"seq": 3, "stage": "completed", "status": "done", "payload": {}, "event_type": "stage"},
            ]

    async def collect_events():
        return [
            event async for event in _event_iter(
                "alpha-ar-test",
                asyncio.Queue(),
                FakeRunStore(),
                last_seq=0,
                symbol="MU.US",
            )
        ]

    events = asyncio.run(collect_events())

    assert [event["event"] for event in events] == ["accepted", "snapshot", "completed"]
    assert json.loads(events[1]["data"])["symbol"] == "MU.US"
