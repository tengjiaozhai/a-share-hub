from pathlib import Path


def test_dashboard_stream_smoke_script_uses_new_run_endpoints():
    script = Path("scripts/run_dashboard_stream_smoke.sh").read_text(encoding="utf-8")
    assert "POST /api/v1/dashboard/runs" not in script
    assert 'curl -s -X POST "$BASE_URL/api/v1/dashboard/runs"' in script
    assert 'curl -sN "$BASE_URL/api/v1/dashboard/runs/${RUN_CONTEXT_ID}/events"' in script
    assert "python3 - <<'PY'" in script
    assert "run.completed" in script
