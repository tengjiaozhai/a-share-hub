"""基金目录服务测试"""
from unittest.mock import MagicMock, patch

import pandas as pd
import requests

from src.fund.catalog_service import FundCatalogService, parse_fundcode_search_js


FUNDCODE_SEARCH_JS = """
var r = [
["512650","htbrhs300","华泰柏瑞沪深300ETF","ETF","huataibairuihushen300etf"],
["159707","gfzz500","广发中证500ETF","ETF","guangfazhongzheng500etf"],
["000001","hxczhh","华夏成长混合","混合型","huaxiachengzhanghunhe"],
["830001","bjfund","北交所样例基金","ETF","beijiaosuoyanglijijin"]
];
"""


def _mock_catalog_response(text: str = FUNDCODE_SEARCH_JS) -> MagicMock:
    response = MagicMock()
    response.text = text
    response.raise_for_status.return_value = None
    return response


def test_parse_fundcode_search_js_normalizes_records():
    """测试 Eastmoney JS 解析与标准化"""
    df = parse_fundcode_search_js(FUNDCODE_SEARCH_JS)

    assert list(df.columns) == [
        "code",
        "name",
        "fund_type",
        "pinyin_abbr",
        "pinyin_full",
        "is_exchange_traded",
        "exchange",
        "symbol",
    ]
    assert df.to_dict("records") == [
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
        {
            "code": "830001",
            "name": "北交所样例基金",
            "fund_type": "ETF",
            "pinyin_abbr": "bjfund",
            "pinyin_full": "beijiaosuoyanglijijin",
            "is_exchange_traded": True,
            "exchange": "BJ",
            "symbol": "830001.BJ",
        },
    ]


def test_parse_fundcode_search_js_keeps_etf_link_fund_otc():
    """测试 ETF联接 产品不会被误判为场内基金"""
    payload = """
var r = [
["013456","etflj","某ETF联接A","ETF联接","etflianjie"]
];
"""

    df = parse_fundcode_search_js(payload)

    assert df.to_dict("records") == [
        {
            "code": "013456",
            "name": "某ETF联接A",
            "fund_type": "ETF联接",
            "pinyin_abbr": "etflj",
            "pinyin_full": "etflianjie",
            "is_exchange_traded": False,
            "exchange": "OTC",
            "symbol": "013456.OTC",
        }
    ]


def test_parse_fundcode_search_js_trusts_infer_exchange_sh_sz_bj_results():
    """测试交易所 fallback 信任 infer_exchange 返回的 SH/SZ/BJ"""
    payload = """
var r = [
["600001","sample","样例ETF","ETF","sampleetf"]
];
"""

    with patch("src.fund.catalog_service.infer_exchange", return_value="SH"):
        df = parse_fundcode_search_js(payload)

    assert df.to_dict("records") == [
        {
            "code": "600001",
            "name": "样例ETF",
            "fund_type": "ETF",
            "pinyin_abbr": "sample",
            "pinyin_full": "sampleetf",
            "is_exchange_traded": True,
            "exchange": "SH",
            "symbol": "600001.SH",
        }
    ]


def test_fund_catalog_service_caching():
    """测试基金目录服务缓存基于 Eastmoney 源生效"""
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()) as mock_get:
        service = FundCatalogService(cache_ttl_seconds=3600)

        df1 = service.get_fund_catalog()
        df2 = service.get_fund_catalog()
        df3 = service.get_fund_catalog(force_refresh=True)

    assert len(df1) == 4
    assert len(df2) == 4
    assert len(df3) == 4
    assert mock_get.call_count == 2


def test_fund_catalog_service_failure_does_not_cache_empty_result():
    """测试上游失败不会把空目录缓存成长期状态"""
    service = FundCatalogService(cache_ttl_seconds=3600)

    with patch(
        "src.fund.catalog_service.requests.get",
        side_effect=[
            requests.RequestException("boom"),
            _mock_catalog_response(),
        ],
    ):
        first = service.get_fund_catalog()
        second = service.get_fund_catalog()

    assert first.empty
    assert len(second) == 4


def test_fund_catalog_service_search_supports_filters_and_pagination():
    """测试基金搜索支持多字段匹配、筛选与分页"""
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        service = FundCatalogService()

        page = service.search_funds(query="etf", fund_type="ETF", page=2, page_size=1)

        assert page["total"] == 3
        assert page["page"] == 2
        assert page["page_size"] == 1
        assert page["total_pages"] == 3
        assert [item["code"] for item in page["items"]] == ["159707"]

        pinyin_match = service.search_funds(query="huaxiachengzhang", page=1, page_size=10)
        assert pinyin_match["total"] == 1
        assert pinyin_match["items"][0]["symbol"] == "000001.OTC"


def test_fund_catalog_service_search_treats_query_as_literal_text():
    """测试查询元字符按字面量匹配，不触发正则错误"""
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        service = FundCatalogService()

        result = service.search_funds(query="(", page=1, page_size=20)

    assert result == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }


def test_fund_catalog_service_search_empty_result_pagination():
    """测试空结果分页语义"""
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        service = FundCatalogService()

        result = service.search_funds(query="missing", page=1, page_size=10)

    assert result == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "total_pages": 0,
    }


def test_fund_catalog_service_search_out_of_range_page_returns_empty_items():
    """测试超出范围页码返回空 items，但保留总量信息"""
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        service = FundCatalogService()

        result = service.search_funds(query="ETF", page=5, page_size=2)

    assert result == {
        "items": [],
        "total": 3,
        "page": 5,
        "page_size": 2,
        "total_pages": 2,
    }


def test_fund_catalog_service_returns_empty_catalog_on_malformed_payload():
    """测试 Eastmoney 返回异常 JS 时服务返回受控空目录"""
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response("var broken = [];")):
        service = FundCatalogService()

        result = service.search_funds(page=1, page_size=20)

    assert result == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }
    assert list(service.get_fund_catalog().columns) == [
        "code",
        "name",
        "fund_type",
        "pinyin_abbr",
        "pinyin_full",
        "is_exchange_traded",
        "exchange",
        "symbol",
    ]


def test_fund_catalog_service_returns_empty_catalog_on_request_failure():
    """测试 Eastmoney 请求失败时服务返回受控空目录且不缓存空结果"""
    with patch(
        "src.fund.catalog_service.requests.get",
        side_effect=requests.RequestException("network failure"),
    ):
        service = FundCatalogService()

        result = service.search_funds(page=1, page_size=20)

    assert result == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }
    assert service._cache is None
    assert service._cache_time is None


def test_fund_catalog_service_get_by_symbol():
    """测试根据 symbol 获取基金信息"""
    with patch("src.fund.catalog_service.requests.get", return_value=_mock_catalog_response()):
        service = FundCatalogService()

        fund = service.get_fund_by_symbol("512650.SH")
        assert fund is not None
        assert fund["code"] == "512650"
        assert fund["name"] == "华泰柏瑞沪深300ETF"

        missing = service.get_fund_by_symbol("999999.SH")
        assert missing is None
