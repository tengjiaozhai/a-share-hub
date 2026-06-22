from datetime import datetime, timedelta

from src.api.dashboard_page.render import render_dashboard_html

def test_dashboard_is_only_html_entrypoint(authenticated_client):
    assert authenticated_client.get("/dashboard").status_code == 200
    assert authenticated_client.get("/new").status_code == 404
    assert authenticated_client.get("/static/index.html").status_code == 404

def test_render_dashboard_html_contains_alpha_contract():
    html = render_dashboard_html()
    assert "view-alpha" in html
    assert "alpha-holdings-summary" in html
    assert "alpha-fill-history" in html
    assert "alpha-multi-leg-history" in html
    assert 'id="alpha-saved-holdings"' in html
    assert 'id="alpha-analysis-builder"' in html
    assert 'id="alpha-stock-cards"' in html
    assert 'id="alpha-add-stock-card"' in html
    assert "生成分析" in html
    assert "const ALPHA_REPORT_API = '/api/v1/alpha/portfolio/report';" in html
    assert "const ALPHA_HOLDINGS_API = '/api/v1/alpha/holdings';" in html
    assert "loadAlphaReport" in html


def test_render_dashboard_html_removes_legacy_alpha_inputs():
    html = render_dashboard_html()
    assert 'id="alpha-report-symbol"' not in html
    assert 'id="alpha-report-position-ratio"' not in html
    assert 'id="alpha-report-buy-time"' not in html
    assert "分析股票" not in html


def test_render_dashboard_html_contains_alpha_builder_javascript_contract():
    html = render_dashboard_html()
    required_markers = [
        "createAlphaStockCard",
        "createAlphaLotRow",
        "collectAlphaReportPositions",
        "renderAlphaSavedHoldings",
        "loadAlphaSavedHoldings",
        "saveAlphaHoldings",
        "updateAlphaHolding",
        "deleteAlphaHolding",
        "data-alpha-history-edit",
        "data-alpha-history-delete",
        "alpha-add-stock-card",
        "data-alpha-add-lot",
        "data-alpha-remove-stock",
        "data-alpha-remove-lot",
        "positions: positions",
        "analysisContext.lot_count",
        "analysisContext.total_cost",
        "analysisContext.weighted_avg_cost",
    ]
    for marker in required_markers:
        assert marker in html


def test_render_dashboard_html_removes_legacy_alpha_preferences_path():
    html = render_dashboard_html()
    forbidden_markers = [
        "analysis_positions",
        "saveAlphaAnalysisPositions",
        "loadAlphaAnalysisPositions",
    ]
    for marker in forbidden_markers:
        assert marker not in html

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
        'id="run-history-filters"',
        'id="run-center-list"',
        'id="case-stage-rail"',
        'id="case-pane-reconcile"',
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

def test_render_dashboard_html_uses_theme_control_wording_not_terminal_wording():
    html = render_dashboard_html()
    assert 'id="theme-switcher-label">界面主题</span>' in html
    assert 'aria-label="切换界面主题"' in html
    assert "当前主题：" in html
    assert 'id="theme-switcher-label">Trading Terminal</span>' not in html

def test_render_dashboard_html_explains_live_run_connection_states():
    html = render_dashboard_html()
    required_markers = [
        "已提交，等待策略引擎接收",
        "实时流已连接，等待策略事件",
        "连接中断，正在重连；运行仍在继续",
        "实时连接已断开，请在运行中心继续查看本轮状态",
        "本轮完成，运行中心已记录结果",
    ]
    for marker in required_markers:
        assert marker in html

def test_render_dashboard_html_contains_reconcile_renderer_hooks():
    html = render_dashboard_html()
    assert "renderReconcile(" in html
    assert "renderRunPnlSummary(" in html
    assert "duration_ms" in html

def test_render_dashboard_html_contains_incremental_history_and_window_switch_contract():
    html = render_dashboard_html()
    required_markers = [
        'id="run-center-footer"',
        'run-history-load-more',
        'loadMoreHistoryRuns',
        'setPerformanceWindow(',
        "selectedPerformanceWindow = window || '7d'",
        'timeline-summary',
    ]
    for marker in required_markers:
        assert marker in html

def test_dashboard_route_uses_rendered_split_html(authenticated_client):
    response = authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert response.text == render_dashboard_html()

def test_dashboard_preferences_and_workbench_stay_server_backed(authenticated_client, pg_store):
    pg_store.set_preference("dashboard", {
            "watchlist": ["600519.SH", "000858.SZ"],
            "capital_base": 1200000,
            "max_position_ratio": 0.25,
            "stop_loss_ratio": -0.05,
            "max_daily_loss_ratio": -0.03,
            "execution_mode": "full",
        },
    )

    decision_run_id = pg_store.insert_decision_run(symbol="600519.SH",
        prompt_hash="dashboard-seed",
        model_name="mock",
        raw_output='{"action":"BUY","confidence":80}',
        parsed_action="BUY",
        confidence=80,
        target_position_ratio=0.25,
        reason="seed decision",
        input_snapshot={"symbol": "600519.SH", "features": {"decision_mode": "mock"}, "market_context": {"mode": "shadow"}},
    )
    target_position_id = pg_store.insert_target_position(decision_run_id=decision_run_id,
        symbol="600519.SH",
        action="BUY",
        target_value=300000,
        target_position_ratio=0.25,
        expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
    )
    execution_order_id = pg_store.insert_execution_order(target_position_id=target_position_id,
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        limit_price=1000.0,
    )
    pg_store.insert_broker_order_event(
        execution_order_id=execution_order_id,
        event_id="evt-001",
        event_type="SUBMITTED",
        payload={"broker_order_id": "paper-001"},
    )

    html = authenticated_client.get("/dashboard").text
    prefs = authenticated_client.get("/api/v1/dashboard/preferences").json()
    workbench = authenticated_client.get("/api/v1/dashboard/workbench").json()

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
        'id="alpha-analysis-builder"',
        'id="alpha-stock-cards"',
        'id="alpha-add-stock-card"',
        "const ALPHA_REPORT_API = '/api/v1/alpha/portfolio/report';",
        'loadAlphaReport',
        'aLoadQuotes',
    ]
    for marker in required_markers:
        assert marker in html

    forbidden_markers = [
        'id="alpha-fill-form"',
        'id="alpha-fill-ticket"',
        'id="alpha-fill-executed-at"',
        'id="alpha-rebuild-opening-cash"',
        'id="alpha-rebuild-price-map"',
        'submitAlphaManualFill',
        'handleAlphaFillTicketChange',
    ]
    for marker in forbidden_markers:
        assert marker not in html

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

def test_render_dashboard_html_does_not_contain_legacy_run_api():
    """旧 /api/v1/dashboard/run endpoint 必须已删除（No Legacy By Default）"""
    import re

    html = render_dashboard_html()
    legacy_match = re.search(r"/api/v1/dashboard/run(?!s)", html)
    assert not legacy_match, (
        f"Legacy /api/v1/dashboard/run reference still in page (matches: {legacy_match.group(0) if legacy_match else None!r})"
    )

def test_render_dashboard_html_contains_resilient_sse_onerror():
    """SSE onerror 必须有重连容忍，不直接 close 流"""
    html = render_dashboard_html()
    assert ("重试中" in html) or ("reconnect" in html.lower()) or ("reconnectAttempts" in html), (
        "SSE onerror must be resilient (allow auto-reconnect)"
    )
    assert ("RECONNECT" in html) or ("reconnect" in html), (
        "Reconnect constants missing"
    )

def test_render_dashboard_html_sse_timeouts_match_backend_run_time():
    """SSE 心跳/硬性超时常量必须 ≥ 后端实测的完整 run 耗时（≥ 60s / ≥ 120s）。

    后端一次完整 run（含 LLM 决策 5 个 symbol）实测 ≈ 35s，留 2x 安全余量：
    - 心跳阈值：≥ 60s（避免误判"无事件"）
    - 硬性上限：≥ 120s（允许偶发慢 LLM 推理）
    """
    html = render_dashboard_html()
    import re
    hb_match = re.search(r"RUN_STREAM_HEARTBEAT_MS\s*=\s*([\d_]+)", html)
    ht_match = re.search(r"RUN_STREAM_HARD_TIMEOUT_MS\s*=\s*([\d_]+)", html)
    assert hb_match, "RUN_STREAM_HEARTBEAT_MS constant missing"
    assert ht_match, "RUN_STREAM_HARD_TIMEOUT_MS constant missing"
    heartbeat_ms = int(hb_match.group(1).replace("_", ""))
    hard_timeout_ms = int(ht_match.group(1).replace("_", ""))
    assert heartbeat_ms >= 60_000, (
        f"heartbeat {heartbeat_ms}ms too short; "
        "实测后端 run ≈ 35s，30s 心跳会误判超时"
    )
    assert hard_timeout_ms >= heartbeat_ms, (
        f"hard timeout {hard_timeout_ms}ms must be >= heartbeat {heartbeat_ms}ms"
    )
    assert hard_timeout_ms >= 120_000, (
        f"hard timeout {hard_timeout_ms}ms too short; 至少要给 LLM 推理 120s"
    )

def test_render_dashboard_html_contains_insufficient_data_warning_helper():
    html = render_dashboard_html()
    assert "insufficientDataWarningHtml" in html
    assert "数据不足" in html

def test_render_dashboard_html_contains_run_card_hint():
    html = render_dashboard_html()
    assert "run-card-hint" in html
    assert "点击查看案件详情" in html

def test_render_dashboard_html_contains_case_drawer_contract():
    """验证 drawer 容器和关闭控件已嵌入"""
    html = render_dashboard_html()
    assert 'id="case-drawer"' in html
    assert 'class="case-drawer"' in html
    assert 'id="drawer-backdrop"' in html
    assert 'class="drawer-close"' in html
    assert 'closeCaseDrawer' in html
    assert 'class="case-shell"' in html

def test_render_dashboard_html_drawer_not_open_by_default():
    """验证 drawer 默认状态是关闭的（无 open class，aria-hidden=true）"""
    html = render_dashboard_html()
    assert 'id="case-drawer"' in html
    assert 'id="drawer-backdrop"' in html
    assert 'class="case-drawer"' in html
    assert 'class="drawer-backdrop"' in html
    assert 'aria-hidden="true"' in html

def test_render_dashboard_html_contains_close_button():
    """验证 close 按钮已嵌入"""
    html = render_dashboard_html()
    assert 'id="drawer-close"' in html
    assert 'closeCaseDrawer()' in html
    assert 'aria-label="关闭案件视图"' in html

def test_render_dashboard_html_rail_bottom_removed():
    """验证 rail-bottom 已被 drawer 取代"""
    html = render_dashboard_html()
    assert 'class="rail-bottom"' not in html

def test_render_dashboard_html_contains_skeleton_function():
    """验证 skeleton 函数和样式已嵌入"""
    html = render_dashboard_html()
    assert 'showCaseDrawerSkeleton' in html
    assert 'case-skeleton' in html
    assert 'skeleton-shimmer' in html
