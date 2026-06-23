from src.alpha.symbols import normalize_report_symbol, normalize_report_symbols


def test_normalize_report_symbol_a_share():
    assert normalize_report_symbol("600519") == "600519.SH"


def test_normalize_report_symbol_us():
    assert normalize_report_symbol("AAPL") == "AAPL.US"


def test_normalize_report_symbol_already_suffixed():
    assert normalize_report_symbol("AAPL.US") == "AAPL.US"


def test_normalize_report_symbol_blank_returns_empty():
    assert normalize_report_symbol("") == ""
    assert normalize_report_symbol(None) == ""


def test_normalize_report_symbols_dedupes_and_skips_empty():
    result = normalize_report_symbols(["aapl", "AAPL.US", "600519", ""])
    assert result == ["AAPL.US", "600519.SH"]
