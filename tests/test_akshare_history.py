from datetime import datetime
from unittest.mock import patch, MagicMock
import json

from src.data.providers.akshare_provider import _fetch_tencent_kline, AkshareProvider


_FAKE_RESPONSE = '''{
  "code": 0,
  "data": {
    "sh600519": {
      "qfqday": [
        ["2025-01-02", "1472.443", "1436.443", "1472.933", "1428.443", "50029.000"],
        ["2025-01-03", "1442.943", "1423.443", "1443.433", "1415.453", "32628.000"]
      ]
    }
  }
}'''

_FAKE_DATA = json.loads(_FAKE_RESPONSE)


def _make_mock_resp(data=None):
    mock_resp = MagicMock()
    mock_resp.json.return_value = data if data is not None else _FAKE_DATA
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_fetch_tencent_kline_parses_response():
    with patch("src.data.providers.akshare_provider.requests.get", return_value=_make_mock_resp()):
        df = _fetch_tencent_kline("sh600519", "2025-01-01", "2025-01-31")

    assert len(df) == 2
    assert list(df.columns) == ["date", "open", "close", "high", "low", "volume"]
    assert df.iloc[0]["date"] == "2025-01-02"
    assert df.iloc[0]["close"] == 1436.443
    assert df.iloc[1]["volume"] == 32628


def test_fetch_tencent_kline_returns_empty_on_no_data():
    with patch("src.data.providers.akshare_provider.requests.get", return_value=_make_mock_resp({"code": 0, "data": {"sh999999": {}}})):
        df = _fetch_tencent_kline("sh999999", "2025-01-01", "2025-01-31")

    assert df.empty


def test_fetch_tencent_kline_returns_empty_on_network_error():
    with patch("src.data.providers.akshare_provider.requests.get", side_effect=Exception("timeout")):
        df = _fetch_tencent_kline("sh600519", "2025-01-01", "2025-01-31")

    assert df.empty


def test_akshare_provider_get_history_returns_dataframe():
    provider = AkshareProvider()
    with patch("src.data.providers.akshare_provider.requests.get", return_value=_make_mock_resp()):
        df = provider.get_history("600519.SH", datetime(2025, 1, 1), datetime(2025, 1, 31))

    assert not df.empty
    assert "date" in df.columns
    assert "close" in df.columns


def test_akshare_provider_get_history_accepts_verified_fund_code_without_exchange_suffix():
    provider = AkshareProvider()
    with patch("src.data.providers.akshare_provider.requests.get", return_value=_make_mock_resp()) as mock_get:
        df = provider.get_history("512650", datetime(2025, 1, 1), datetime(2025, 1, 31))

    assert not df.empty
    called_url = mock_get.call_args.args[0]
    assert "fqkline/get" in called_url
    assert "sh512650" in called_url
