"""基金服务测试"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.fund.catalog_service import FundCatalogService


class TestFundCatalogService:
    """基金目录服务测试"""
    
    def setup_method(self):
        """测试前准备"""
        self.service = FundCatalogService()
    
    @patch('src.fund.catalog_service.ak')
    def test_get_etf_spot(self, mock_ak):
        """测试获取 ETF 实时行情"""
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
        
        result = self.service.get_etf_spot(limit=2)
        
        assert len(result) == 2
        assert result[0]['code'] == '510300'
        assert result[0]['name'] == '沪深300ETF'
        assert result[0]['price'] == 4.123
        assert result[0]['change_pct'] == 1.23
        mock_ak.fund_etf_spot_em.assert_called_once()
    
    @patch('src.fund.catalog_service.ak')
    def test_get_etf_spot_with_cache(self, mock_ak):
        """测试 ETF 实时行情缓存"""
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
        result1 = self.service.get_etf_spot(limit=1)
        assert mock_ak.fund_etf_spot_em.call_count == 1
        
        # 第二次调用应该使用缓存
        result2 = self.service.get_etf_spot(limit=1)
        assert mock_ak.fund_etf_spot_em.call_count == 1  # 没有再次调用
        
        # 强制刷新
        result3 = self.service.get_etf_spot(limit=1, force_refresh=True)
        assert mock_ak.fund_etf_spot_em.call_count == 2
        
        # 验证缓存统计
        stats = self.service.get_cache_stats()
        assert stats['etf_spot']['hits'] == 1
        assert stats['etf_spot']['misses'] == 2
    
    @patch('src.fund.catalog_service.ak')
    def test_get_etf_spot_error(self, mock_ak):
        """测试获取 ETF 实时行情失败"""
        mock_ak.fund_etf_spot_em.side_effect = Exception("Network error")
        
        result = self.service.get_etf_spot()
        
        assert result == []
    
    @patch('src.fund.catalog_service.ak')
    def test_get_fund_nav(self, mock_ak):
        """测试获取基金历史净值"""
        # 模拟 akshare 返回数据
        mock_df = pd.DataFrame({
            '净值日期': ['2024-01-01', '2024-01-02'],
            '单位净值': [1.2345, 1.2400],
            '累计净值': [1.5678, 1.5733],
            '日增长率': [0.45, 0.44],
            '申购状态': ['开放申购', '开放申购'],
            '赎回状态': ['开放赎回', '开放赎回'],
        })
        mock_ak.fund_etf_fund_info_em.return_value = mock_df
        
        result = self.service.get_fund_nav(symbol='511280', start_date='20240101', end_date='20240102')
        
        assert len(result) == 2
        assert result[0]['date'] == '2024-01-01'
        assert result[0]['nav'] == 1.2345
        assert result[0]['acc_nav'] == 1.5678
        mock_ak.fund_etf_fund_info_em.assert_called_once_with(
            fund='511280', start_date='20240101', end_date='20240102'
        )
    
    @patch('src.fund.catalog_service.ak')
    def test_get_fund_nav_with_cache(self, mock_ak):
        """测试基金净值缓存"""
        mock_df = pd.DataFrame({
            '净值日期': ['2024-01-01'],
            '单位净值': [1.0],
            '累计净值': [1.0],
            '日增长率': [0.0],
        })
        mock_ak.fund_etf_fund_info_em.return_value = mock_df
        
        # 第一次调用
        result1 = self.service.get_fund_nav(symbol='511280')
        assert mock_ak.fund_etf_fund_info_em.call_count == 1
        
        # 第二次调用应该使用缓存
        result2 = self.service.get_fund_nav(symbol='511280')
        assert mock_ak.fund_etf_fund_info_em.call_count == 1
        
        # 不同参数应该重新调用
        result3 = self.service.get_fund_nav(symbol='511280', start_date='20240101')
        assert mock_ak.fund_etf_fund_info_em.call_count == 2
        
        # 验证缓存统计
        stats = self.service.get_cache_stats()
        assert stats['fund_nav']['hits'] == 1
        assert stats['fund_nav']['misses'] == 2
    
    @patch('src.fund.catalog_service.ak')
    def test_get_fund_nav_with_symbol_suffix(self, mock_ak):
        """测试获取基金历史净值（带交易所后缀）"""
        mock_df = pd.DataFrame({
            '净值日期': ['2024-01-01'],
            '单位净值': [1.0],
            '累计净值': [1.0],
            '日增长率': [0.0],
        })
        mock_ak.fund_etf_fund_info_em.return_value = mock_df
        
        result = self.service.get_fund_nav(symbol='511280.SH')
        
        # 应该提取纯代码 511280
        mock_ak.fund_etf_fund_info_em.assert_called_once()
        call_args = mock_ak.fund_etf_fund_info_em.call_args
        assert call_args[1]['fund'] == '511280'
    
    @patch('src.fund.catalog_service.ak')
    def test_get_fund_nav_error(self, mock_ak):
        """测试获取基金历史净值失败"""
        mock_ak.fund_etf_fund_info_em.side_effect = Exception("API error")
        
        result = self.service.get_fund_nav(symbol='511280')
        
        assert result == []
    
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
    def test_get_etf_spot_nan_handling(self, mock_ak):
        """测试 ETF 实时行情 NaN 处理"""
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
        
        result = self.service.get_etf_spot(limit=2)
        
        # 应该只返回有效价格的 ETF
        assert len(result) == 1
        assert result[0]['code'] == '510300'
    
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
            mock_service.return_value.get_etf_spot.return_value = [
                {'code': '510300', 'name': '沪深300ETF', 'price': 4.123}
            ]
            
            response = authenticated_client.get('/api/v1/fund/etf/spot?limit=10')
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]['code'] == '510300'
            mock_service.return_value.get_etf_spot.assert_called_once_with(limit=10, force_refresh=False)
    
    def test_get_etf_spot_with_force_refresh(self, authenticated_client):
        """测试 ETF 实时行情接口强制刷新"""
        with patch('src.api.routes_fund._get_fund_catalog_service') as mock_service:
            mock_service.return_value.get_etf_spot.return_value = []
            
            response = authenticated_client.get('/api/v1/fund/etf/spot?force_refresh=true')
            
            assert response.status_code == 200
            mock_service.return_value.get_etf_spot.assert_called_once_with(limit=50, force_refresh=True)
    
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
