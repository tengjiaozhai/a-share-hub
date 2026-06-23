"""Symbol normalization helpers shared across the alpha pipeline."""

from __future__ import annotations

from src.data.providers.akshare_catalog import normalize_symbol as normalize_a_share_symbol


def normalize_report_symbol(symbol: str) -> str:
    raw_text = str(symbol or "").strip()
    if not raw_text:
        return ""
    text = raw_text.upper()
    if "." in text:
        return text
    if text.isdigit() and len(text) == 6:
        return normalize_a_share_symbol(text)
    if raw_text.endswith(("x", "X")):
        return raw_text
    return f"{text}.US"


def normalize_report_symbols(symbols: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols or []:
        normalized_symbol = normalize_report_symbol(symbol)
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        normalized.append(normalized_symbol)
    return normalized
