def test_post_analysis_runs_returns_202(authenticated_client, monkeypatch):
    from src.api import routes_alpha

    class FakeService:
        def start(self, request):
            return {
                "run_id": "alpha-ar-test",
                "symbol": request.symbol,
                "market": "us",
                "status": "accepted",
                "stream_url": "/api/v1/alpha/analysis-runs/alpha-ar-test/events",
                "created_at": "2026-06-22T15:10:00+08:00",
            }

        async def execute(self, run_id: str) -> None:
            return None

    monkeypatch.setattr(routes_alpha, "_build_run_service", lambda store, user_id, holdings_store: FakeService())

    response = authenticated_client.post(
        "/api/v1/alpha/analysis-runs",
        json={"symbol": "MU.US", "backtest_window": "60d", "include_backtest": True},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["symbol"] == "MU.US"
    assert body["stream_url"].endswith("/alpha-ar-test/events")


def test_old_portfolio_report_returns_404(authenticated_client):
    response = authenticated_client.post(
        "/api/v1/alpha/portfolio/report", json={"symbols": ["MU.US"]}
    )
    assert response.status_code == 404


def test_get_run_detail_returns_full_payload(authenticated_client, monkeypatch):
    from src.api import routes_alpha

    class FakeRunStore:
        def get_run_detail(self, run_id):
            return {
                "run_id": run_id,
                "symbol": "MU.US",
                "market": "us",
                "status": "completed",
                "current_stage": "completed",
                "model_name": "deepseek-v4-pro",
                "created_at": "2026-06-22T15:10:00+08:00",
                "started_at": "2026-06-22T15:10:00+08:00",
                "finished_at": "2026-06-22T15:11:00+08:00",
                "snapshot": {"close": 110.0},
                "research": {"rating": "OVERWEIGHT"},
                "trader": {"action": "BUY"},
                "risk": {"action": "ADD"},
                "backtest": {"status": "ok"},
                "error": None,
                "error_stage": None,
                "events": [],
            }

    monkeypatch.setattr(routes_alpha, "_build_run_store", lambda store, user_id: FakeRunStore())
    response = authenticated_client.get("/api/v1/alpha/analysis-runs/alpha-ar-test")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "MU.US"
    assert body["snapshot"]["close"] == 110.0


def test_get_run_detail_404_when_missing(authenticated_client, monkeypatch):
    from src.api import routes_alpha

    class FakeRunStore:
        def get_run_detail(self, run_id):
            return None

    monkeypatch.setattr(routes_alpha, "_build_run_store", lambda store, user_id: FakeRunStore())
    response = authenticated_client.get("/api/v1/alpha/analysis-runs/missing")
    assert response.status_code == 404


def test_list_runs_returns_summary_only_with_cursor(authenticated_client, monkeypatch):
    from src.api import routes_alpha

    class FakeRunStore:
        def list_runs(self, *, market=None, status_filter=None, limit=20, cursor_run_id=None):
            return {
                "items": [
                    {
                        "run_id": "alpha-ar-1",
                        "symbol": "MU.US",
                        "market": "us",
                        "status": "completed",
                        "current_stage": "completed",
                        "risk_action": "ADD",
                        "research_rating": "OVERWEIGHT",
                        "research_confidence": 0.7,
                        "close_date": "2026-06-22",
                        "created_at": "2026-06-22T15:10:00+08:00",
                        "finished_at": "2026-06-22T15:11:00+08:00",
                    }
                ],
                "next_cursor": "alpha-ar-1",
            }

    monkeypatch.setattr(routes_alpha, "_build_run_store", lambda store, user_id: FakeRunStore())
    response = authenticated_client.get("/api/v1/alpha/analysis-runs?market=us&limit=20")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["next_cursor"] == "alpha-ar-1"
    first = body["items"][0]
    assert "snapshot" not in first
    assert "research" not in first
    assert "trader" not in first
    assert "risk" not in first
    assert "backtest" not in first


def test_events_stream_returns_text_event_stream(authenticated_client, monkeypatch):
    from src.api import routes_alpha

    class FakeRunStore:
        def get_run(self, run_id):
            return {"run_id": run_id, "symbol": "MU.US", "status": "completed"}
        def list_events(self, run_id, after_seq=0):
            return [
                {"seq": 1, "stage": "accepted", "status": "done", "payload": {}, "event_type": "accepted"},
                {"seq": 2, "stage": "snapshot", "status": "done", "payload": {}, "event_type": "stage"},
            ]

    monkeypatch.setattr(routes_alpha, "_build_run_store", lambda store, user_id: FakeRunStore())
    response = authenticated_client.get("/api/v1/alpha/analysis-runs/alpha-ar-test/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
