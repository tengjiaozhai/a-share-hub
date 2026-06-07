"""Tests for dashboard theme switch functionality."""
import pytest
from fastapi.testclient import TestClient


THEME_IDS = [
    "trading-terminal", "mission-control", "neutral-modern", "hud-signal",
    "mono-grid", "openai-editorial", "nvidia-power", "coinbase-institutional",
]


def test_theme_preference_round_trip(test_app):
    client = TestClient(test_app)
    # Save theme
    resp = client.put("/api/v1/dashboard/preferences", json={"theme_id": "mission-control"})
    assert resp.status_code == 200
    # Read back
    resp = client.get("/api/v1/dashboard/preferences")
    assert resp.status_code == 200
    assert resp.json()["theme_id"] == "mission-control"


def test_invalid_theme_id_is_rejected(test_app):
    client = TestClient(test_app)
    resp = client.put("/api/v1/dashboard/preferences", json={"theme_id": "not-a-theme"})
    assert resp.status_code == 400


def test_default_theme_is_trading_terminal(test_app):
    client = TestClient(test_app)
    resp = client.get("/api/v1/dashboard/preferences")
    assert resp.status_code == 200
    # Default should be trading-terminal if never set
    assert resp.json().get("theme_id") == "trading-terminal"


def test_all_theme_ids_are_accepted(test_app):
    client = TestClient(test_app)
    for tid in THEME_IDS:
        resp = client.put("/api/v1/dashboard/preferences", json={"theme_id": tid})
        assert resp.status_code == 200, f"theme_id={tid} rejected"
        resp = client.get("/api/v1/dashboard/preferences")
        assert resp.json()["theme_id"] == tid


def test_theme_survives_other_preference_save(test_app):
    client = TestClient(test_app)
    # Save theme
    client.put("/api/v1/dashboard/preferences", json={"theme_id": "nvidia-power"})
    # Save other prefs
    client.put("/api/v1/dashboard/preferences", json={"market": "us", "capital_base": 500000})
    # Theme should persist
    resp = client.get("/api/v1/dashboard/preferences")
    assert resp.json()["theme_id"] == "nvidia-power"
    assert resp.json()["market"] == "us"


def test_dashboard_html_includes_theme_bootstrap():
    from src.api.dashboard_page.render import render_dashboard_html
    html = render_dashboard_html(theme_id="trading-terminal")
    assert 'data-theme="trading-terminal"' in html
    assert "theme-switcher" in html
    assert "theme.js" in html or "INLINE_THEME_JS" not in html


def test_dashboard_html_with_different_theme():
    from src.api.dashboard_page.render import render_dashboard_html
    html = render_dashboard_html(theme_id="mission-control")
    assert 'data-theme="mission-control"' in html


def test_dashboard_html_includes_theme_css():
    from src.api.dashboard_page.render import render_dashboard_html
    html = render_dashboard_html()
    assert "theme-menu" in html
    assert "theme-swatch" in html
