from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def render_dashboard_html(theme_id: str = "trading-terminal") -> str:
    html = _read("shell.html")
    replacements = {
        "{{INLINE_STYLES}}": _read("styles/dashboard.css"),
        "{{STATUS_BAR}}": _read("partials/status_bar.html"),
        "{{VIEW_DASHBOARD}}": _read("partials/view_dashboard.html"),
        "{{VIEW_MARKET}}": _read("partials/view_market.html"),
        "{{VIEW_ALPHA}}": _read("partials/view_alpha.html"),
        "{{INLINE_UTILS_JS}}": _read("scripts/utils.js"),
        "{{INLINE_THEME_JS}}": _read("scripts/theme.js"),
        "{{INLINE_DASHBOARD_JS}}": _read("scripts/dashboard.js"),
        "{{INLINE_MARKET_JS}}": _read("scripts/market.js"),
        "{{INLINE_ALPHA_JS}}": _read("scripts/alpha.js"),
        "{{VIEW_US_STOCK}}": _read("partials/view_us_stock.html"),
        "{{INLINE_US_STOCK_JS}}": _read("scripts/us_stock.js"),
        "{{INLINE_BOOTSTRAP_JS}}": _read("scripts/bootstrap.js"),
    }
    for marker, content in replacements.items():
        html = html.replace(marker, content)
    html = html.replace("{{THEME_ID}}", theme_id)
    return html
