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
