from src.core.tenant import TenantContext
from src.storage.runtime_store import RuntimeStore


def test_analysis_runs_round_trip_and_are_user_isolated(pg_engine):
    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    bob = RuntimeStore(pg_engine, TenantContext("bob"))
    run_id = alice.insert_alpha_analysis_run(
        symbol="600703.SH",
        status="completed",
        snapshot={"close": 16.0},
        research={"rating": "OVERWEIGHT"},
        trader={"action": "BUY"},
        risk={"action": "ADD"},
        model_name="deepseek-v4-pro",
        error=None,
    )

    assert alice.get_alpha_analysis_run(run_id)["risk"] == {"action": "ADD"}
    assert bob.get_alpha_analysis_run(run_id) is None
    assert bob.list_alpha_analysis_runs(symbol="600703.SH") == []
