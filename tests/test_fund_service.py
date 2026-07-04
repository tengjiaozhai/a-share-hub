"""基金服务测试"""
import threading
import time

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.fund.catalog_service import FundCatalogService


class TestFundCatalogService:
    """基金目录服务测试"""
    
    def setup_method(self):
        """测试前准备"""
        self._redis_patcher = patch("src.fund.catalog_service.should_use_redis_cache", return_value=False)
        self._redis_patcher.start()
        self.service = FundCatalogService(enable_etf_spot_warmer=False)

    def teardown_method(self):
        self._redis_patcher.stop()
    
    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_returns_paginated_shape(self, mock_catalog, mock_ak):
        """测试获取 ETF 实时行情返回分页对象"""
        mock_catalog.return_value = pd.DataFrame([
            {"code": "510300", "name": "沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "hs300", "pinyin_full": "hushen300etf", "is_exchange_traded": True, "exchange": "SH", "symbol": "510300.SH"},
            {"code": "159919", "name": "嘉实沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "js300", "pinyin_full": "jiashihushen300etf", "is_exchange_traded": True, "exchange": "SZ", "symbol": "159919.SZ"},
        ])
        # 模拟 akshare 返回数据
        mock_df = pd.DataFrame({
            '代码': ['510300', '159919'],
            '名称': ['沪深300ETF', '嘉实沪深300ETF'],
            '最新价': [4.123, 4.056],
            '涨跌幅': [1.23, -0.45],
            '涨跌额': [0.05, -0.02],
            '成交量': [1000000, 500000],
            '成交额': [4123000, 2028000],
            '开盘价': [4.10, 4.08],
            '最高价': [4.15, 4.10],
            '最低价': [4.08, 4.02],
            '昨收': [4.07, 4.08],
        })
        mock_ak.fund_etf_spot_em.return_value = mock_df
        
        result = self.service.get_etf_spot(page=1, page_size=1)
        
        assert result["total"] == 2
        assert result["page"] == 1
        assert result["page_size"] == 1
        assert result["total_pages"] == 2
        assert len(result["items"]) == 1
        assert result["items"][0]['code'] == '510300'
        assert result["items"][0]['name'] == '沪深300ETF'
        assert result["items"][0]['price'] == 4.123
        assert result["items"][0]['change_pct'] == 1.23
        mock_ak.fund_etf_spot_em.assert_called_once()

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_supports_code_name_filter_before_pagination(self, mock_catalog, mock_ak):
        """测试 ETF 实时行情仅按代码和名称过滤，并在分页前过滤"""
        mock_catalog.return_value = pd.DataFrame([
            {"code": "510300", "name": "沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "hs300", "pinyin_full": "hushen300etf", "is_exchange_traded": True, "exchange": "SH", "symbol": "510300.SH"},
            {"code": "159919", "name": "嘉实沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "js300", "pinyin_full": "jiashihushen300etf", "is_exchange_traded": True, "exchange": "SZ", "symbol": "159919.SZ"},
            {"code": "512650", "name": "华泰柏瑞沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "ht300", "pinyin_full": "huataibairui300etf", "is_exchange_traded": True, "exchange": "SH", "symbol": "512650.SH"},
        ])
        mock_df = pd.DataFrame({
            '代码': ['510300', '159919', '512650'],
            '名称': ['沪深300ETF', '嘉实沪深300ETF', '华泰柏瑞沪深300ETF'],
            '最新价': [4.123, 4.056, 4.222],
            '涨跌幅': [1.23, -0.45, 0.66],
            '涨跌额': [0.05, -0.02, 0.03],
            '成交量': [1000000, 500000, 800000],
            '成交额': [4123000, 2028000, 3377600],
        })
        mock_ak.fund_etf_spot_em.return_value = mock_df

        result = self.service.get_etf_spot(query='沪深300', page=2, page_size=1)

        assert result["total"] == 3
        assert result["page"] == 2
        assert result["page_size"] == 1
        assert result["total_pages"] == 3
        assert [item["code"] for item in result["items"]] == ["159919"]

        name_only = self.service.get_etf_spot(query='嘉实', page=1, page_size=10)
        assert [item["code"] for item in name_only["items"]] == ["159919"]

        no_pinyin_match = self.service.get_etf_spot(query='htbrhs300', page=1, page_size=10)
        assert no_pinyin_match == {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 10,
            "total_pages": 0,
        }

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_with_cache(self, mock_catalog, mock_ak):
        """测试 ETF 实时行情缓存复用原始列表，再做过滤分页"""
        mock_catalog.return_value = pd.DataFrame([
            {"code": "510300", "name": "沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "hs300", "pinyin_full": "hushen300etf", "is_exchange_traded": True, "exchange": "SH", "symbol": "510300.SH"},
        ])
        mock_df = pd.DataFrame({
            '代码': ['510300'],
            '名称': ['沪深300ETF'],
            '最新价': [4.123],
            '涨跌幅': [1.23],
            '涨跌额': [0.05],
            '成交量': [1000000],
            '成交额': [4123000],
        })
        mock_ak.fund_etf_spot_em.return_value = mock_df
        
        # 第一次调用
        result1 = self.service.get_etf_spot(page=1, page_size=1)
        assert mock_ak.fund_etf_spot_em.call_count == 1
        
        # 第二次调用应该使用缓存
        result2 = self.service.get_etf_spot(query='510300', page=1, page_size=1)
        assert mock_ak.fund_etf_spot_em.call_count == 1  # 没有再次调用
        
        # 强制刷新
        result3 = self.service.get_etf_spot(page=1, page_size=1, force_refresh=True)
        assert mock_ak.fund_etf_spot_em.call_count == 2
        
        # 验证缓存统计
        stats = self.service.get_cache_stats()
        assert stats['etf_spot']['hits'] == 1
        assert stats['etf_spot']['misses'] == 2
    
    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_error(self, mock_catalog, mock_ak):
        """测试获取 ETF 实时行情失败"""
        mock_catalog.return_value = pd.DataFrame(columns=["code", "name", "fund_type", "pinyin_abbr", "pinyin_full", "is_exchange_traded", "exchange", "symbol"])
        mock_ak.fund_etf_spot_em.side_effect = Exception("Network error")
        
        result = self.service.get_etf_spot()
        
        assert result == {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
        }

    @patch("src.fund.catalog_service.RedisCache")
    @patch("src.fund.catalog_service.should_use_redis_cache", return_value=True)
    def test_get_etf_spot_uses_redis_cache_before_remote_fetch(self, _mock_use_redis, mock_redis_cache):
        """测试内存冷缓存时优先读取 Redis，共享多进程缓存"""
        mock_redis_cache.return_value.get_json.return_value = {
            "items": [
                {"code": "510300", "name": "沪深300ETF", "price": 4.123, "change_pct": 1.23},
            ]
        }
        service = FundCatalogService(enable_etf_spot_warmer=False)

        with patch("src.fund.catalog_service.ak") as mock_ak:
            result = service.get_etf_spot(page=1, page_size=20)

        assert result["total"] == 1
        assert result["items"][0]["code"] == "510300"
        mock_redis_cache.return_value.get_json.assert_called_once()
        mock_ak.fund_etf_spot_em.assert_not_called()

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_waits_for_inflight_refresh_instead_of_duplicate_fetch(self, mock_catalog, mock_ak):
        """测试冷启动并发请求只触发一次远端 ETF 行情拉取"""
        service = FundCatalogService(enable_etf_spot_warmer=False)
        mock_catalog.return_value = pd.DataFrame([
            {"code": "510300", "name": "沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "hs300", "pinyin_full": "hushen300etf", "is_exchange_traded": True, "exchange": "SH", "symbol": "510300.SH"},
        ])
        mock_df = pd.DataFrame({
            '代码': ['510300'],
            '名称': ['沪深300ETF'],
            '最新价': [4.123],
            '涨跌幅': [1.23],
            '涨跌额': [0.05],
            '成交量': [1000000],
            '成交额': [4123000],
        })
        refresh_started = threading.Event()

        def slow_fetch():
            refresh_started.set()
            time.sleep(0.1)
            return mock_df

        mock_ak.fund_etf_spot_em.side_effect = slow_fetch

        worker = threading.Thread(target=service._refresh_etf_spot)
        worker.start()
        assert refresh_started.wait(timeout=1)

        result = service.get_etf_spot(page=1, page_size=20)
        worker.join(timeout=1)

        assert result["total"] == 1
        assert result["items"][0]["code"] == "510300"
        assert mock_ak.fund_etf_spot_em.call_count == 1

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_prewarm_etf_spot_cache_populates_cache_and_starts_warmer(self, mock_catalog, mock_ak):
        """测试启动预热会填充缓存并启动后台维持线程"""
        service = FundCatalogService(enable_etf_spot_warmer=True)
        mock_catalog.return_value = pd.DataFrame([
            {"code": "510300", "name": "沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "hs300", "pinyin_full": "hushen300etf", "is_exchange_traded": True, "exchange": "SH", "symbol": "510300.SH"},
        ])
        mock_df = pd.DataFrame({
            '代码': ['510300'],
            '名称': ['沪深300ETF'],
            '最新价': [4.123],
            '涨跌幅': [1.23],
            '涨跌额': [0.05],
            '成交量': [1000000],
            '成交额': [4123000],
        })
        mock_ak.fund_etf_spot_em.return_value = mock_df

        assert service.prewarm_etf_spot_cache(force_refresh=True) is True

        cached = service._get_etf_spot_cached_items()
        assert cached is not None
        assert len(cached) == 1
        assert cached[0]["code"] == "510300"
        assert service._etf_spot_warm_thread is not None
        service.stop_etf_spot_warmer()

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_fund_nav_routes_otc_open_fund_to_open_fund_api(self, mock_catalog, mock_ak):
        """测试 OTC 开放式基金走开放式基金净值接口"""
        mock_catalog.return_value = pd.DataFrame([
            {
                "code": "000041",
                "name": "华夏全球股票(QDII)",
                "fund_type": "股票型",
                "pinyin_abbr": "hxqqgp",
                "pinyin_full": "huaxiaquanqiugupiao",
                "is_exchange_traded": False,
                "exchange": "OTC",
                "symbol": "000041.OTC",
            }
        ])

        # 模拟 akshare 返回数据
        mock_df = pd.DataFrame({
            '净值日期': ['2024-01-01', '2024-01-02'],
            '单位净值': [1.2345, 1.2400],
            '累计净值': [1.5678, 1.5733],
            '日增长率': [0.45, 0.44],
        })
        mock_ak.fund_open_fund_info_em.return_value = mock_df
        
        result = self.service.get_fund_nav(symbol='000041', start_date='20240101', end_date='20240102')
        
        assert len(result) == 2
        assert result[0]['date'] == '2024-01-01'
        assert result[0]['nav'] == 1.2345
        assert result[0]['acc_nav'] == 1.5678
        mock_ak.fund_open_fund_info_em.assert_called_once_with(
            symbol='000041', indicator='单位净值走势', period='成立来'
        )
        mock_ak.fund_etf_fund_info_em.assert_not_called()

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_fund_nav_with_cache(self, mock_catalog, mock_ak):
        """测试基金净值缓存"""
        mock_catalog.return_value = pd.DataFrame([
            {
                "code": "000041",
                "name": "华夏全球股票(QDII)",
                "fund_type": "股票型",
                "pinyin_abbr": "hxqqgp",
                "pinyin_full": "huaxiaquanqiugupiao",
                "is_exchange_traded": False,
                "exchange": "OTC",
                "symbol": "000041.OTC",
            }
        ])
        mock_df = pd.DataFrame({
            '净值日期': ['2024-01-01'],
            '单位净值': [1.0],
            '累计净值': [1.0],
            '日增长率': [0.0],
        })
        mock_ak.fund_open_fund_info_em.return_value = mock_df
        
        # 第一次调用
        result1 = self.service.get_fund_nav(symbol='000041.OTC')
        assert mock_ak.fund_open_fund_info_em.call_count == 1
        
        # 第二次调用应该使用缓存
        result2 = self.service.get_fund_nav(symbol='000041.OTC')
        assert mock_ak.fund_open_fund_info_em.call_count == 1
        
        # 不同参数应该重新调用
        result3 = self.service.get_fund_nav(symbol='000041.OTC', start_date='20240101')
        assert mock_ak.fund_open_fund_info_em.call_count == 2
        
        # 验证缓存统计
        stats = self.service.get_cache_stats()
        assert stats['fund_nav']['hits'] == 1
        assert stats['fund_nav']['misses'] == 2
    
    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_fund_nav_rejects_exchange_traded_etf_without_true_nav(self, mock_catalog, mock_ak):
        """测试交易所基金无真实净值时返回受控领域错误"""
        from src.fund.catalog_service import FundNavUnavailableError

        mock_catalog.return_value = pd.DataFrame([
            {
                "code": "511280",
                "name": "某场内ETF",
                "fund_type": "ETF",
                "pinyin_abbr": "etf",
                "pinyin_full": "etf",
                "is_exchange_traded": True,
                "exchange": "SH",
                "symbol": "511280.SH",
            }
        ])

        with pytest.raises(FundNavUnavailableError) as exc_info:
            self.service.get_fund_nav(symbol='511280.SH')

        assert exc_info.value.code == "fund_nav_unsupported"
        assert "511280.SH" in str(exc_info.value)
        mock_ak.fund_open_fund_info_em.assert_not_called()
        mock_ak.fund_etf_fund_info_em.assert_not_called()
    
    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_fund_nav_error(self, mock_catalog, mock_ak):
        """测试获取基金历史净值失败"""
        mock_catalog.return_value = pd.DataFrame([
            {
                "code": "000041",
                "name": "华夏全球股票(QDII)",
                "fund_type": "股票型",
                "pinyin_abbr": "hxqqgp",
                "pinyin_full": "huaxiaquanqiugupiao",
                "is_exchange_traded": False,
                "exchange": "OTC",
                "symbol": "000041.OTC",
            }
        ])
        mock_ak.fund_open_fund_info_em.side_effect = Exception("API error")
        
        result = self.service.get_fund_nav(symbol='000041')
        
        assert result == []

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_fund_nav_uses_explicit_market_metadata_not_fund_type_heuristic(self, mock_catalog, mock_ak):
        """测试 NAV 路由使用显式市场属性，而不是 fund_type 子串猜测"""
        mock_catalog.return_value = pd.DataFrame([
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
        ])
        mock_ak.fund_open_fund_info_em.return_value = pd.DataFrame({
            '净值日期': ['2024-01-01'],
            '单位净值': [1.1111],
            '累计净值': [1.1111],
            '日增长率': [0.0],
        })

        result = self.service.get_fund_nav(symbol='013456.OTC', start_date='20240101', end_date='20240131')

        assert result[0]['nav'] == 1.1111
        mock_ak.fund_open_fund_info_em.assert_called_once_with(
            symbol='013456', indicator='单位净值走势', period='成立来'
        )

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_uses_catalog_exchange_traded_metadata_for_scope(self, mock_catalog, mock_ak):
        """测试 ETF 实时行情使用 catalog 显式元数据限制场内范围"""
        mock_catalog.return_value = pd.DataFrame([
            {
                "code": "510300",
                "name": "沪深300ETF",
                "fund_type": "ETF",
                "pinyin_abbr": "hs300",
                "pinyin_full": "hushen300etf",
                "is_exchange_traded": True,
                "exchange": "SH",
                "symbol": "510300.SH",
            },
            {
                "code": "013456",
                "name": "某ETF联接A",
                "fund_type": "ETF联接",
                "pinyin_abbr": "etflj",
                "pinyin_full": "etflianjie",
                "is_exchange_traded": False,
                "exchange": "OTC",
                "symbol": "013456.OTC",
            },
        ])
        mock_ak.fund_etf_spot_em.return_value = pd.DataFrame({
            '代码': ['510300', '013456'],
            '名称': ['沪深300ETF', '某ETF联接A'],
            '最新价': [4.123, 1.234],
            '涨跌幅': [1.23, 0.1],
            '涨跌额': [0.05, 0.01],
            '成交量': [1000000, 200000],
            '成交额': [4123000, 246800],
            '开盘价': [4.10, 1.22],
            '最高价': [4.15, 1.25],
            '最低价': [4.08, 1.20],
            '昨收': [4.07, 1.22],
        })

        result = self.service.get_etf_spot(page=1, page_size=10)

        assert [item['code'] for item in result['items']] == ['510300']

    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_drops_rows_without_catalog_metadata(self, mock_catalog, mock_ak):
        """测试 ETF 实时行情无法通过 catalog 解析元数据时 fail closed"""
        mock_catalog.return_value = pd.DataFrame([
            {
                "code": "510300",
                "name": "沪深300ETF",
                "fund_type": "ETF",
                "pinyin_abbr": "hs300",
                "pinyin_full": "hushen300etf",
                "is_exchange_traded": True,
                "exchange": "SH",
                "symbol": "510300.SH",
            },
        ])
        mock_ak.fund_etf_spot_em.return_value = pd.DataFrame({
            '代码': ['510300', '159919'],
            '名称': ['沪深300ETF', '未收录ETF'],
            '最新价': [4.123, 2.345],
            '涨跌幅': [1.23, 0.5],
            '涨跌额': [0.05, 0.01],
            '成交量': [1000000, 300000],
            '成交额': [4123000, 703500],
            '开盘价': [4.10, 2.33],
            '最高价': [4.15, 2.36],
            '最低价': [4.08, 2.30],
            '昨收': [4.07, 2.34],
        })

        result = self.service.get_etf_spot(page=1, page_size=10)

        assert [item['code'] for item in result['items']] == ['510300']
        assert result['items'][0]['exchange'] == 'SH'
        assert result['items'][0]['symbol'] == '510300.SH'
    
    @patch('src.fund.catalog_service.ak')
    def test_get_etf_history(self, mock_ak):
        """测试获取 ETF 历史行情"""
        # 模拟 akshare 返回数据
        mock_df = pd.DataFrame({
            '日期': ['2024-01-01', '2024-01-02'],
            '开盘': [4.10, 4.12],
            '收盘': [4.12, 4.15],
            '最高': [4.15, 4.18],
            '最低': [4.08, 4.10],
            '成交量': [1000000, 1200000],
            '成交额': [4120000, 4980000],
            '涨跌幅': [0.49, 0.73],
            '涨跌额': [0.02, 0.03],
        })
        mock_ak.fund_etf_hist_em.return_value = mock_df
        
        result = self.service.get_etf_history(symbol='159707', period='daily', 
                                               start_date='20240101', end_date='20240102')
        
        assert len(result) == 2
        assert result[0]['date'] == '2024-01-01'
        assert result[0]['open'] == 4.10
        assert result[0]['close'] == 4.12
        assert result[0]['volume'] == 1000000
        mock_ak.fund_etf_hist_em.assert_called_once_with(
            symbol='159707', period='daily', start_date='20240101', end_date='20240102'
        )
    
    @patch('src.fund.catalog_service.ak')
    def test_get_etf_history_with_cache(self, mock_ak):
        """测试 ETF 历史行情缓存"""
        mock_df = pd.DataFrame({
            '日期': ['2024-01-01'],
            '开盘': [4.10],
            '收盘': [4.12],
            '最高': [4.15],
            '最低': [4.08],
            '成交量': [1000000],
        })
        mock_ak.fund_etf_hist_em.return_value = mock_df
        
        # 第一次调用
        result1 = self.service.get_etf_history(symbol='159707', period='daily')
        assert mock_ak.fund_etf_hist_em.call_count == 1
        
        # 第二次调用应该使用缓存
        result2 = self.service.get_etf_history(symbol='159707', period='daily')
        assert mock_ak.fund_etf_hist_em.call_count == 1
        
        # 不同周期应该重新调用
        result3 = self.service.get_etf_history(symbol='159707', period='weekly')
        assert mock_ak.fund_etf_hist_em.call_count == 2
        
        # 验证缓存统计
        stats = self.service.get_cache_stats()
        assert stats['etf_history']['hits'] == 1
        assert stats['etf_history']['misses'] == 2
    
    @patch('src.fund.catalog_service.ak')
    def test_get_etf_history_error(self, mock_ak):
        """测试获取 ETF 历史行情失败"""
        mock_ak.fund_etf_hist_em.side_effect = Exception("API error")
        
        result = self.service.get_etf_history(symbol='159707')
        
        assert result == []
    
    @patch('src.fund.catalog_service.ak')
    @patch.object(FundCatalogService, 'get_fund_catalog')
    def test_get_etf_spot_nan_handling(self, mock_catalog, mock_ak):
        """测试 ETF 实时行情 NaN 处理"""
        mock_catalog.return_value = pd.DataFrame([
            {"code": "510300", "name": "沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "hs300", "pinyin_full": "hushen300etf", "is_exchange_traded": True, "exchange": "SH", "symbol": "510300.SH"},
            {"code": "159919", "name": "嘉实沪深300ETF", "fund_type": "ETF", "pinyin_abbr": "js300", "pinyin_full": "jiashihushen300etf", "is_exchange_traded": True, "exchange": "SZ", "symbol": "159919.SZ"},
        ])
        # 模拟包含 NaN 的数据
        mock_df = pd.DataFrame({
            '代码': ['510300', '159919'],
            '名称': ['沪深300ETF', '嘉实沪深300ETF'],
            '最新价': [4.123, float('nan')],  # 第二个是 NaN
            '涨跌幅': [1.23, float('nan')],
            '涨跌额': [0.05, float('nan')],
            '成交量': [1000000, 500000],
            '成交额': [4123000, 2028000],
            '开盘价': [4.10, float('nan')],
            '最高价': [4.15, float('nan')],
            '最低价': [4.08, float('nan')],
            '昨收': [4.07, float('nan')],
        })
        mock_ak.fund_etf_spot_em.return_value = mock_df
        
        result = self.service.get_etf_spot(page=1, page_size=2)
        
        # 应该只返回有效价格的 ETF
        assert len(result["items"]) == 1
        assert result["items"][0]['code'] == '510300'
    
    def test_clear_cache(self):
        """测试清除缓存"""
        # 清除所有缓存
        self.service.clear_cache('all')
        
        stats = self.service.get_cache_stats()
        assert stats['etf_spot']['hits'] == 0
        assert stats['etf_spot']['misses'] == 0
    
    def test_get_cache_stats(self):
        """测试获取缓存统计"""
        stats = self.service.get_cache_stats()
        
        assert 'etf_spot' in stats
        assert 'fund_nav' in stats
        assert 'etf_history' in stats
        
        assert 'hits' in stats['etf_spot']
        assert 'misses' in stats['etf_spot']
        assert 'hit_rate' in stats['etf_spot']
        assert 'ttl' in stats['etf_spot']


class TestFundRoutes:
    """基金 API 路由测试"""
    
    def test_get_etf_spot_endpoint(self, authenticated_client):
        """测试 ETF 实时行情接口"""
        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.get_etf_spot.return_value = {
                "items": [{'code': '510300', 'name': '沪深300ETF', 'price': 4.123}],
                "total": 1,
                "page": 2,
                "page_size": 5,
                "total_pages": 1,
            }
            
            response = authenticated_client.get('/api/v1/fund/etf/spot?page=2&page_size=5&query=5103')
            
            assert response.status_code == 200
            data = response.json()
            assert data["items"][0]['code'] == '510300'
            assert data["page"] == 2
            assert data["page_size"] == 5
            mock_service.return_value.get_etf_spot.assert_called_once_with(page=2, page_size=5, query='5103', force_refresh=False)
    
    def test_get_etf_spot_with_force_refresh(self, authenticated_client):
        """测试 ETF 实时行情接口强制刷新"""
        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.get_etf_spot.return_value = {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
                "total_pages": 0,
            }
            
            response = authenticated_client.get('/api/v1/fund/etf/spot?force_refresh=true')
            
            assert response.status_code == 200
            mock_service.return_value.get_etf_spot.assert_called_once_with(page=1, page_size=20, query='', force_refresh=True)

    def test_get_fund_nav_endpoint(self, authenticated_client):
        """测试基金净值查询接口"""
        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.get_fund_nav.return_value = [
                {'date': '2024-01-01', 'nav': 1.2345, 'acc_nav': 1.5678}
            ]
            
            response = authenticated_client.get('/api/v1/fund/nav/511280?start_date=20240101&end_date=20240102')
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]['nav'] == 1.2345

    def test_get_fund_nav_endpoint_returns_422_for_unsupported_exchange_traded_nav(self, authenticated_client):
        """测试场内基金无真实净值时接口返回 422 领域错误"""
        from src.fund.catalog_service import FundNavUnavailableError

        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.get_fund_nav.side_effect = FundNavUnavailableError(
                symbol='511280.SH',
                reason='true NAV unavailable for exchange-traded fund via current provider',
            )

            response = authenticated_client.get('/api/v1/fund/nav/511280.SH')

        assert response.status_code == 422
        assert response.json() == {
            'detail': {
                'code': 'fund_nav_unsupported',
                'symbol': '511280.SH',
                'reason': 'true NAV unavailable for exchange-traded fund via current provider',
            }
        }
    
    def test_get_etf_history_endpoint(self, authenticated_client):
        """测试 ETF 历史行情接口"""
        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.get_etf_history.return_value = [
                {'date': '2024-01-01', 'open': 4.10, 'close': 4.12}
            ]
            
            response = authenticated_client.get('/api/v1/fund/etf/history/159707?period=daily')
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]['close'] == 4.12
    
    def test_get_cache_stats_endpoint(self, authenticated_client):
        """测试缓存统计接口"""
        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.get_cache_stats.return_value = {
                'etf_spot': {'hits': 10, 'misses': 2, 'hit_rate': 0.83, 'ttl': 30},
                'fund_nav': {'hits': 5, 'misses': 3, 'hit_rate': 0.625, 'ttl': 3600},
                'etf_history': {'hits': 8, 'misses': 4, 'hit_rate': 0.667, 'ttl': 1800},
            }
            
            response = authenticated_client.get('/api/v1/fund/cache/stats')
            
            assert response.status_code == 200
            data = response.json()
            assert data['etf_spot']['hits'] == 10
            assert data['etf_spot']['hit_rate'] == 0.83
    
    def test_clear_cache_endpoint(self, authenticated_client):
        """测试清除缓存接口"""
        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.clear_cache.return_value = None
            
            response = authenticated_client.post('/api/v1/fund/cache/clear?cache_type=all')
            
            assert response.status_code == 200
            data = response.json()
            assert 'message' in data
            mock_service.return_value.clear_cache.assert_called_once_with(cache_type='all')
