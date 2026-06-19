from html import escape
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _read(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def render_login_html(next_url: str = "/dashboard", error: str = "") -> str:
    return _render("login.html", next_url, error)


def render_register_html(next_url: str = "/dashboard", error: str = "") -> str:
    return _render("register.html", next_url, error)


def _render(template: str, next_url: str, error: str) -> str:
    html = _read(template)
    return (
        html.replace("{{INLINE_STYLES}}", _read("styles/auth.css"))
        .replace("{{INLINE_AUTH_JS}}", _read("scripts/auth.js"))
        .replace("{{NEXT_VALUE}}", escape(next_url or "/dashboard", quote=True))
        .replace("{{ERROR_BLOCK}}", _error_block(error))
    )


def _error_block(error: str) -> str:
    if not error:
        return ""
    return f'<div class="auth-error">{escape(error)}</div>'
