from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.api.dashboard_page.render import render_dashboard_html
from src.main import build_app
from src.storage.dependencies import get_runtime_store
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def build_dashboard_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    app = build_app()
    app.dependency_overrides[get_runtime_store] = lambda: store
    return TestClient(app), store


def test_dashboard_is_only_html_entrypoint():
    client, _ = build_dashboard_client()

    assert client.get("/dashboard").status_code == 200
    assert client.get("/new").status_code == 404
    assert client.get("/static/index.html").status_code == 404


def test_render_dashboard_html_contains_alpha_contract():
    html = render_dashboard_html()
    assert "view-alpha" in html
    assert "alpha-execution-capability" in html
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in html
    assert "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';" in html
    assert "runAlphaScan" in html
    assert "proposeTopAlphaTicket" in html


def test_render_dashboard_html_contains_market_contract():
    html = render_dashboard_html()
    assert "view-market" in html
    assert "A 股工作台" in html
    assert "aLoadQuotes" in html


def test_render_dashboard_html_contains_strategy_workbench_contract():
    html = render_dashboard_html()

    for marker in [
        'id="scan-btn"',
        'id="run-btn"',
        'id="bt-btn"',
        'id="last-run"',
        'id="risk-pnl"',
    ]:
        assert marker in html


def test_render_dashboard_html_contains_streaming_run_markers():
    html = render_dashboard_html()
    required_markers = [
        'id="run-trace-id"',
        'id="stream-status"',
        'id="run-pnl-net"',
        'id="run-pnl-fee"',
        'id="run-pnl-unrealized"',
        'id="tab-reconcile"',
        'id="tb-reconcile"',
    ]
    for marker in required_markers:
        assert marker in html


def test_render_dashboard_html_contains_streaming_run_javascript_contract():
    html = render_dashboard_html()
    assert "const RUNS_API = '/api/v1/dashboard/runs';" in html
    assert "const RUN_EVENTS_API = (runContextId) =>" in html
    assert "new EventSource" in html
    assert "connectRunStream" in html


def test_render_dashboard_html_contains_reconcile_renderer_hooks():
    html = render_dashboard_html()
    assert "renderReconcile(" in html
    assert "renderRunPnlSummary(" in html
    assert "duration_ms" in html


def test_dashboard_route_uses_rendered_split_html():
    client = TestClient(build_app())
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert response.text == render_dashboard_html()


def test_dashboard_preferences_and_workbench_stay_server_backed():
    client, store = build_dashboard_client()

    store.set_preference(
        "dashboard",
        {
            "watchlist": ["600519.SH", "000858.SZ"],
            "capital_base": 1200000,
            "max_position_ratio": 0.25,
            "stop_loss_ratio": -0.05,
            "max_daily_loss_ratio": -0.03,
            "execution_mode": "full",
        },
    )

    decision_run_id = store.insert_decision_run(
        symbol="600519.SH",
        prompt_hash="dashboard-seed",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.25,
        reason="seed decision",
        input_snapshot={"symbol": "600519.SH", "features": {"decision_mode": "mock"}, "market_context": {"mode": "shadow"}},
    )
    target_position_id = store.insert_target_position(
        decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=300000,
        target_position_ratio=0.25,
        expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
    )
    execution_order_id = store.insert_execution_order(
        target_position_id=target_position_id,
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=1000.0,
    )
    store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-001",
        event_type="SUBMITTED",
        payload={"broker_order_id": "paper-001"},
    )

    html = client.get("/dashboard").text
    prefs = client.get("/api/v1/dashboard/preferences").json()
    workbench = client.get("/api/v1/dashboard/workbench").json()

    assert "const WORKBENCH_API = '/api/v1/dashboard/workbench';" in html
    assert "const PREFS_API = '/api/v1/dashboard/preferences';" in html
    assert prefs["watchlist"] == ["600519.SH", "000858.SZ"]
    assert workbench["history"]["decisions"][0]["decision_run_id"] == decision_run_id
    assert workbench["history"]["targets"][0]["target_position_id"] == target_position_id
    assert workbench["history"]["orders"][0]["execution_order_id"] == execution_order_id


def test_render_dashboard_html_contains_market_and_alpha_controls():
    html = render_dashboard_html()
    required_markers = [
        'id="a-quotes-table"',
        'id="a-search-input"',
        'id="scan-btn"',
        'id="alpha-assets"',
        'id="alpha-ticket-form"',
        'id="alpha-execution-capability"',
        "const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';",
        "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';",
        "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';",
        'runAlphaScan',
        'proposeTopAlphaTicket',
        'aLoadQuotes',
    ]
    for marker in required_markers:
        assert marker in html


def test_dashboard_split_has_no_legacy_frontend_paths():
    from pathlib import Path

    assert not Path("src/api/dashboard.html").exists()
    assert not Path("src/api/static").exists()

    main_py = Path("src/main.py").read_text(encoding="utf-8")
    routes_py = Path("src/api/routes_dashboard.py").read_text(encoding="utf-8")

    assert "StaticFiles" not in main_py
    assert '/new' not in routes_py
    assert 'dashboard.html' not in routes_py


def test_render_dashboard_html_contains_stage_body_html_guards():
    import re

    html = render_dashboard_html()
    assert "function stageBodyHtml" in html

    match = re.search(r"function stageBodyHtml\(.*?\n}", html, re.DOTALL)
    assert match, "stageBodyHtml not found"
    fn_src = match.group(0)

    assert ("if (!step" in fn_src) or ("if (!step ||" in fn_src), (
        "stageBodyHtml must guard against null/undefined step"
    )

    for line in fn_src.split("\n"):
        if ".map(" in line and "toList(" not in line:
            raise AssertionError(
                f"stageBodyHtml line has .map without toList: {line.strip()}"
            )


def test_render_dashboard_html_contains_sse_timeout_handler():
    html = render_dashboard_html()

    assert ("setTimeout" in html) or ("超时" in html), (
        "SSE timeout handler missing in dashboard_run.js"
    )
    assert ("运行超时" in html) or ("force close" in html) or ("forceClose" in html), (
        "SSE timeout UI message missing (运行超时 / force close / forceClose)"
    )


def test_render_dashboard_html_contains_inline_favicon_link():
    html = render_dashboard_html()
    assert 'rel="icon"' in html, "favicon link missing"
