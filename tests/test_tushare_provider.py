from unittest.mock import MagicMock, patch
from src.data.providers.tushare_provider import TushareProvider

def test_not_available_without_token():
    p = TushareProvider(token="")
    assert p.is_available() is False

@patch("src.data.providers.tushare_provider.logger")
def test_available_with_token(mock_logger):
    mock_ts = MagicMock()
    mock_ts.pro_api.return_value = MagicMock()
    with patch.dict("sys.modules", {"tushare": mock_ts}):
        p = TushareProvider(token="test_token")
        assert p.is_available() is True

def test_to_ts_code():
    from src.data.providers.tushare_provider import _to_ts_code
    assert _to_ts_code("600519.SH") == "600519.SH"
    assert _to_ts_code("000001.sz") == "000001.SZ"
