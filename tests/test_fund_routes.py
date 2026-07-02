"""基金 API 路由测试"""

from unittest.mock import MagicMock, patch

import requests

from src.api import routes_fund

FUNDCODE_SEARCH_JS = """
var r = [
["512650","htbrhs300","华泰柏瑞沪深300ETF","ETF","huataibairuihushen300etf"],
["159707","gfzz500","广发中证500ETF","ETF","guangfazhongzheng500etf"],
["000001","hxczhh","华夏成长混合","混合型","huaxiachengzhanghunhe"]
];
"""


def _mock_catalog_response() -> MagicMock:
    response = MagicMock()
    response.text = FUNDCODE_SEARCH_JS
    response.raise_for_status.return_value = None
    return response


def test_fund_catalog_endpoint_returns_paginated_shape(authenticated_client):
    """测试基金目录接口返回分页对象"""
    routes_fund._fund_catalog_service = None
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        response = authenticated_client.get("/api/v1/fund/catalog")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "items": [
            {
                "code": "512650",
                "name": "华泰柏瑞沪深300ETF",
                "fund_type": "ETF",
                "pinyin_abbr": "htbrhs300",
                "pinyin_full": "huataibairuihushen300etf",
                "is_exchange_traded": True,
                "exchange": "SH",
                "symbol": "512650.SH",
            },
            {
                "code": "159707",
                "name": "广发中证500ETF",
                "fund_type": "ETF",
                "pinyin_abbr": "gfzz500",
                "pinyin_full": "guangfazhongzheng500etf",
                "is_exchange_traded": True,
                "exchange": "SZ",
                "symbol": "159707.SZ",
            },
            {
                "code": "000001",
                "name": "华夏成长混合",
                "fund_type": "混合型",
                "pinyin_abbr": "hxczhh",
                "pinyin_full": "huaxiachengzhanghunhe",
                "is_exchange_traded": False,
                "exchange": "OTC",
                "symbol": "000001.OTC",
            },
        ],
        "total": 3,
        "page": 1,
        "page_size": 20,
        "total_pages": 1,
    }


def test_fund_catalog_endpoint_supports_query_filters_and_pagination(authenticated_client):
    """测试基金目录接口支持筛选与分页参数"""
    routes_fund._fund_catalog_service = None
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        response = authenticated_client.get(
            "/api/v1/fund/catalog",
            params={"query": "guangfa", "fund_type": "ETF", "page": 1, "page_size": 1},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total_pages"] == 1
    assert [item["symbol"] for item in data["items"]] == ["159707.SZ"]


def test_fund_catalog_endpoint_enforces_page_size_max(authenticated_client):
    """测试基金目录接口限制 page_size 最大值"""
    response = authenticated_client.get("/api/v1/fund/catalog?page_size=101")

    assert response.status_code == 422


def test_fund_watchlist_endpoints(authenticated_client):
    with patch("src.api.routes_fund._get_watchlist_store") as mock_store:
        item = MagicMock()
        item.model_dump.return_value = {"id": 1, "symbol": "020972.OTC", "name": "华夏基金", "sort_order": 0}
        mock_store.return_value.add.return_value = item
        create = authenticated_client.post(
            "/api/v1/fund/watchlist",
            json={"symbol": "020972.OTC", "name": "华夏基金"},
        )
    assert create.status_code == 200
    assert create.json()["symbol"] == "020972.OTC"

    with patch("src.api.routes_fund._get_watchlist_store") as mock_store:
        item = MagicMock()
        item.model_dump.return_value = {"id": 1, "symbol": "020972.OTC", "name": "华夏基金", "sort_order": 0}
        mock_store.return_value.list_items.return_value = ([item], 1)
        listing = authenticated_client.get("/api/v1/fund/watchlist")
    assert listing.status_code == 200
    data = listing.json()
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "020972.OTC"

    with patch("src.api.routes_fund._get_watchlist_store") as mock_store:
        mock_store.return_value.add.side_effect = ValueError("Symbol 020972.OTC already exists in watchlist")
        duplicate = authenticated_client.post(
            "/api/v1/fund/watchlist",
            json={"symbol": "020972.OTC", "name": "华夏基金"},
        )
    assert duplicate.status_code == 409

    with patch("src.api.routes_fund._get_watchlist_store") as mock_store:
        mock_store.return_value.remove.return_value = True
        delete = authenticated_client.delete("/api/v1/fund/watchlist/020972.OTC")
    assert delete.status_code == 200
    assert delete.json() == {"removed": True, "symbol": "020972.OTC"}


def test_fund_catalog_endpoint_returns_empty_page_on_upstream_failure(authenticated_client):
    """测试上游目录源失败时接口仍返回受控分页对象"""
    routes_fund._fund_catalog_service = None
    with patch(
        "src.fund.catalog_service.requests.get",
        side_effect=requests.RequestException("network failure"),
    ):
        response = authenticated_client.get("/api/v1/fund/catalog", params={"query": "ETF", "page": 3, "page_size": 5})

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 3,
        "page_size": 5,
        "total_pages": 0,
    }


def test_fund_catalog_get_by_symbol(authenticated_client):
    """测试根据 symbol 获取基金信息"""
    routes_fund._fund_catalog_service = None
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        response = authenticated_client.get("/api/v1/fund/catalog/512650.SH")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "512650"
        assert data["name"] == "华泰柏瑞沪深300ETF"

        missing = authenticated_client.get("/api/v1/fund/catalog/999999.SH")
        assert missing.status_code == 404


def test_etf_spot_endpoint_returns_paginated_shape(authenticated_client):
    """测试 ETF 实时行情接口返回分页对象并透传分页参数"""
    with patch("src.api.routes_fund._get_fund_catalog_service") as mock_service:
        mock_service.return_value.get_etf_spot.return_value = {
            "items": [{"code": "510300", "name": "沪深300ETF", "price": 4.123}],
            "total": 1,
            "page": 2,
            "page_size": 5,
            "total_pages": 1,
        }

        response = authenticated_client.get(
            "/api/v1/fund/etf/spot",
            params={"page": 2, "page_size": 5, "query": "5103"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"code": "510300", "name": "沪深300ETF", "price": 4.123}],
        "total": 1,
        "page": 2,
        "page_size": 5,
        "total_pages": 1,
    }
    mock_service.return_value.get_etf_spot.assert_called_once_with(
        page=2,
        page_size=5,
        query="5103",
        force_refresh=False,
    )


def test_fund_nav_endpoint_returns_422_domain_error_for_unsupported_exchange_traded_nav(authenticated_client):
    """测试场内基金缺少真实净值时返回 422 领域错误"""
    from src.fund.catalog_service import FundNavUnavailableError

    with patch("src.api.routes_fund._get_fund_catalog_service") as mock_service:
        mock_service.return_value.get_fund_nav.side_effect = FundNavUnavailableError(
            symbol="511280.SH",
            reason="true NAV unavailable for exchange-traded fund via current provider",
        )

        response = authenticated_client.get("/api/v1/fund/nav/511280.SH")

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "fund_nav_unsupported",
            "symbol": "511280.SH",
            "reason": "true NAV unavailable for exchange-traded fund via current provider",
        }
    }


def test_fund_nav_endpoint_returns_404_for_missing_symbol(authenticated_client):
    """测试基金净值接口将 FundNotFoundError 映射为 HTTP 404"""
    from src.fund.catalog_service import FundNotFoundError

    with patch("src.api.routes_fund._get_fund_catalog_service") as mock_service:
        mock_service.return_value.get_fund_nav.side_effect = FundNotFoundError("999999.OTC")

        response = authenticated_client.get("/api/v1/fund/nav/999999.OTC")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Fund 999999.OTC not found",
    }
