"""基金 API 路由测试"""
import pytest
from unittest.mock import patch
import pandas as pd


def test_fund_catalog_endpoint(authenticated_client):
    """测试基金目录 API 端点"""
    mock_df = pd.DataFrame({
        '基金代码': ['512650', '159707'],
        '基金简称': ['华泰柏瑞沪深300ETF', '广发中证500ETF'],
        '基金类型': ['ETF', 'ETF']
    })
    
    with patch('src.fund.catalog_service.ak.fund_name_em', return_value=mock_df):
        response = authenticated_client.get('/api/v1/fund/catalog')
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]['code'] == '512650'
        assert data[0]['symbol'] == '512650.SH'


def test_fund_catalog_search(authenticated_client):
    """测试基金目录搜索"""
    mock_df = pd.DataFrame({
        '基金代码': ['512650', '159707', '166009'],
        '基金简称': ['华泰柏瑞沪深300ETF', '广发中证500ETF', '中欧医疗健康混合A'],
        '基金类型': ['ETF', 'ETF', '混合型']
    })
    
    with patch('src.fund.catalog_service.ak.fund_name_em', return_value=mock_df):
        # 按名称搜索
        response = authenticated_client.get('/api/v1/fund/catalog?query=沪深300')
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['code'] == '512650'
        
        # 按类型筛选
        response = authenticated_client.get('/api/v1/fund/catalog?fund_type=ETF')
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


def test_fund_catalog_get_by_symbol(authenticated_client):
    """测试根据 symbol 获取基金信息"""
    mock_df = pd.DataFrame({
        '基金代码': ['512650', '159707'],
        '基金简称': ['华泰柏瑞沪深300ETF', '广发中证500ETF'],
        '基金类型': ['ETF', 'ETF']
    })
    
    with patch('src.fund.catalog_service.ak.fund_name_em', return_value=mock_df):
        # 获取存在的基金
        response = authenticated_client.get('/api/v1/fund/catalog/512650.SH')
        assert response.status_code == 200
        data = response.json()
        assert data['code'] == '512650'
        assert data['name'] == '华泰柏瑞沪深300ETF'
        
        # 获取不存在的基金
        response = authenticated_client.get('/api/v1/fund/catalog/999999.SH')
        assert response.status_code == 404
