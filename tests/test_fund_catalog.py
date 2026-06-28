"""基金目录服务测试"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.fund.catalog_service import FundCatalogService


def test_fund_catalog_service_returns_dataframe():
    """测试基金目录服务返回正确的 DataFrame"""
    mock_df = pd.DataFrame({
        '基金代码': ['512650', '159707', '166009'],
        '基金简称': ['华泰柏瑞沪深300ETF', '广发中证500ETF', '中欧医疗健康混合A'],
        '基金类型': ['ETF', 'ETF', '混合型']
    })
    
    with patch('src.fund.catalog_service.ak.fund_name_em', return_value=mock_df):
        service = FundCatalogService()
        df = service.get_fund_catalog()
        
        assert len(df) == 3
        assert 'symbol' in df.columns
        assert 'code' in df.columns
        assert 'name' in df.columns
        assert 'fund_type' in df.columns
        assert 'exchange' in df.columns
        
        # 验证 symbol 格式
        assert df.iloc[0]['symbol'] == '512650.SH'
        assert df.iloc[1]['symbol'] == '159707.SZ'
        assert df.iloc[2]['symbol'] == '166009.SZ'


def test_fund_catalog_service_caching():
    """测试基金目录服务的缓存机制"""
    mock_df = pd.DataFrame({
        '基金代码': ['512650'],
        '基金简称': ['华泰柏瑞沪深300ETF'],
        '基金类型': ['ETF']
    })
    
    with patch('src.fund.catalog_service.ak.fund_name_em', return_value=mock_df) as mock_func:
        service = FundCatalogService(cache_ttl_seconds=3600)
        
        # 第一次调用
        df1 = service.get_fund_catalog()
        assert mock_func.call_count == 1
        
        # 第二次调用应该使用缓存
        df2 = service.get_fund_catalog()
        assert mock_func.call_count == 1  # 不应该再次调用
        
        # 强制刷新
        df3 = service.get_fund_catalog(force_refresh=True)
        assert mock_func.call_count == 2


def test_fund_catalog_service_search():
    """测试基金搜索功能"""
    mock_df = pd.DataFrame({
        '基金代码': ['512650', '159707', '166009'],
        '基金简称': ['华泰柏瑞沪深300ETF', '广发中证500ETF', '中欧医疗健康混合A'],
        '基金类型': ['ETF', 'ETF', '混合型']
    })
    
    with patch('src.fund.catalog_service.ak.fund_name_em', return_value=mock_df):
        service = FundCatalogService()
        
        # 按名称搜索
        results = service.search_funds(query='沪深300')
        assert len(results) == 1
        assert results[0]['code'] == '512650'
        
        # 按代码搜索
        results = service.search_funds(query='159707')
        assert len(results) == 1
        assert results[0]['code'] == '159707'
        
        # 按类型筛选
        results = service.search_funds(fund_type='ETF')
        assert len(results) == 2
        
        # 限制返回数量
        results = service.search_funds(limit=1)
        assert len(results) == 1


def test_fund_catalog_service_get_by_symbol():
    """测试根据 symbol 获取基金信息"""
    mock_df = pd.DataFrame({
        '基金代码': ['512650', '159707'],
        '基金简称': ['华泰柏瑞沪深300ETF', '广发中证500ETF'],
        '基金类型': ['ETF', 'ETF']
    })
    
    with patch('src.fund.catalog_service.ak.fund_name_em', return_value=mock_df):
        service = FundCatalogService()
        
        # 获取存在的基金
        fund = service.get_fund_by_symbol('512650.SH')
        assert fund is not None
        assert fund['code'] == '512650'
        assert fund['name'] == '华泰柏瑞沪深300ETF'
        
        # 获取不存在的基金
        fund = service.get_fund_by_symbol('999999.SH')
        assert fund is None
