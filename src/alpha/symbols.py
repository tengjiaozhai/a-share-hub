"""Symbol normalization helpers shared across the alpha pipeline."""

from __future__ import annotations

from src.data.providers.akshare_catalog import normalize_symbol as normalize_a_share_symbol

_SH_FUND_PREFIXES = ("50", "51", "52", "56", "58")
_SZ_FUND_PREFIXES = ("15", "16", "18")
_FUND_SUFFIXES = (".OTC",)


def classify_report_market(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return "a"
    if text.endswith(".US"):
        return "us"
    if text.endswith(_FUND_SUFFIXES):
        return "fund"
    code = text.split(".", 1)[0]
    if code.isdigit() and len(code) == 6 and code.startswith(_SH_FUND_PREFIXES + _SZ_FUND_PREFIXES):
        return "fund"
    return "a"


def normalize_report_symbol(symbol: str) -> str:
    raw_text = str(symbol or "").strip()
    if not raw_text:
        return ""
    text = raw_text.upper()
    if "." in text:
        return text
    if text.isdigit() and len(text) == 6:
        if text.startswith(_SH_FUND_PREFIXES):
            return f"{text}.SH"
        if text.startswith(_SZ_FUND_PREFIXES):
            return f"{text}.SZ"
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
