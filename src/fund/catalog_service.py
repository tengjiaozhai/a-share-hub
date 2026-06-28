"""基金目录服务"""
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd

from src.core.market_clock import is_continuous_session
from src.data.providers.akshare_catalog import normalize_symbol
from src.us_stock.cache import TTLMemoryCache
from src.us_stock.yahoo_provider import _safe_float, _safe_int

# 缓存 TTL 配置（秒）
ETF_SPOT_CACHE_TTL_TRADING = 30  # 交易时段：30 秒
ETF_SPOT_CACHE_TTL_NON_TRADING = 300  # 非交易时段：5 分钟
FUND_NAV_CACHE_TTL = 3600  # 基金净值：1 小时
ETF_HISTORY_CACHE_TTL = 1800  # ETF 历史行情：30 分钟


class FundCatalogService:
    """基金目录服务，提供基金代码查询、净值查询和 ETF 行情"""
    
    def __init__(self, cache_ttl_seconds: int = 86400):
        self._cache_ttl = cache_ttl_seconds
        self._cache: Optional[pd.DataFrame] = None
        self._cache_time: Optional[datetime] = None
        
        # ETF 行情缓存
        self._etf_spot_cache = TTLMemoryCache(ttl_seconds=ETF_SPOT_CACHE_TTL_TRADING)
        self._etf_spot_cache_key = "etf_spot:all"
        
        # 基金净值缓存（按 symbol 缓存）
        self._fund_nav_cache = TTLMemoryCache(ttl_seconds=FUND_NAV_CACHE_TTL)
        
        # ETF 历史行情缓存（按 symbol+period 缓存）
        self._etf_history_cache = TTLMemoryCache(ttl_seconds=ETF_HISTORY_CACHE_TTL)
        
        # 缓存统计
        self._stats = {
            'etf_spot_hits': 0,
            'etf_spot_misses': 0,
            'fund_nav_hits': 0,
            'fund_nav_misses': 0,
            'etf_history_hits': 0,
            'etf_history_misses': 0,
        }
    
    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._cache is None or self._cache_time is None:
            return False
        return datetime.now() - self._cache_time < timedelta(seconds=self._cache_ttl)
    
    def _get_etf_spot_ttl(self) -> int:
        """根据当前时间获取 ETF 行情缓存 TTL"""
        if is_continuous_session(datetime.now()):
            return ETF_SPOT_CACHE_TTL_TRADING
        return ETF_SPOT_CACHE_TTL_NON_TRADING
    
    def get_fund_catalog(self, force_refresh: bool = False) -> pd.DataFrame:
        """获取基金目录
        
        Returns:
            DataFrame with columns: symbol, code, name, fund_type, exchange
        """
        if not force_refresh and self._is_cache_valid():
            return self._cache.copy()
        
        # 调用 akshare 获取基金目录
        df = ak.fund_name_em()
        
        # 标准化列名
        df = df.rename(columns={
            '基金代码': 'code',
            '基金简称': 'name',
            '基金类型': 'fund_type'
        })
        
        # 只保留需要的列
        df = df[['code', 'name', 'fund_type']].copy()
        
        # 添加交易所信息
        df['exchange'] = df['code'].apply(self._infer_exchange)
        
        # 生成标准 symbol
        df['symbol'] = df['code'] + '.' + df['exchange']
        
        # 更新缓存
        self._cache = df
        self._cache_time = datetime.now()
        
        return df.copy()
    
    def _infer_exchange(self, code: str) -> str:
        """推断基金交易所"""
        try:
            return normalize_symbol(code).split('.')[1]
        except ValueError:
            return 'UNKNOWN'
    
    def search_funds(self, query: str = '', fund_type: str = '', limit: int = 50) -> list[dict]:
        """搜索基金"""
        df = self.get_fund_catalog()
        
        if query:
            df = df[df['name'].str.contains(query, case=False, na=False) | 
                    df['code'].str.contains(query, na=False)]
        
        if fund_type:
            df = df[df['fund_type'] == fund_type]
        
        return df.head(limit).to_dict('records')
    
    def get_fund_by_symbol(self, symbol: str) -> Optional[dict]:
        """根据 symbol 获取基金信息"""
        df = self.get_fund_catalog()
        result = df[df['symbol'] == symbol]
        if result.empty:
            return None
        return result.iloc[0].to_dict()
    
    def get_etf_spot(self, limit: int = 50, force_refresh: bool = False) -> list[dict]:
        """获取 ETF 实时行情（带缓存）
        
        Args:
            limit: 返回数量限制
            force_refresh: 强制刷新缓存
        
        Returns:
            List of ETF spot quotes with price, volume, etc.
        """
        # 检查缓存
        if not force_refresh:
            cached = self._etf_spot_cache.get(self._etf_spot_cache_key)
            if cached is not None:
                self._stats['etf_spot_hits'] += 1
                return cached[:limit]
        
        self._stats['etf_spot_misses'] += 1
        
        try:
            # 动态调整缓存 TTL
            current_ttl = self._get_etf_spot_ttl()
            if self._etf_spot_cache._ttl != current_ttl:
                self._etf_spot_cache = TTLMemoryCache(ttl_seconds=current_ttl)
            
            df = ak.fund_etf_spot_em()
            
            # 标准化列名
            column_mapping = {
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change',
                '成交量': 'volume',
                '成交额': 'amount',
                '开盘价': 'open',
                '最高价': 'high',
                '最低价': 'low',
                '昨收': 'prev_close',
            }
            
            # 只保留存在的列
            available_columns = [col for col in column_mapping.keys() if col in df.columns]
            df = df[available_columns].rename(columns=column_mapping)
            
            # 添加交易所信息
            df['exchange'] = df['code'].apply(self._infer_exchange)
            df['symbol'] = df['code'] + '.' + df['exchange']
            
            # 安全转换数值
            for col in ['price', 'change_pct', 'change', 'open', 'high', 'low', 'prev_close']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: _safe_float(x, None))
            
            for col in ['volume', 'amount']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: _safe_int(x, 0))
            
            # 过滤无效价格
            df = df[df['price'].notna() & (df['price'] > 0)]
            
            # 转换为列表并缓存
            result = df.to_dict('records')
            self._etf_spot_cache.set(self._etf_spot_cache_key, result)
            
            return result[:limit]
            
        except Exception as e:
            print(f"Error fetching ETF spot: {e}")
            return []
    
    def get_fund_nav(self, symbol: str, start_date: str = '', end_date: str = '', 
                    force_refresh: bool = False) -> list[dict]:
        """获取基金历史净值（带缓存）
        
        Args:
            symbol: 基金代码（如 511280 或 511280.SH）
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            force_refresh: 强制刷新缓存
        
        Returns:
            List of NAV records with date, nav, acc_nav, etc.
        """
        # 生成缓存键
        cache_key = f"nav:{symbol}:{start_date}:{end_date}"
        
        # 检查缓存
        if not force_refresh:
            cached = self._fund_nav_cache.get(cache_key)
            if cached is not None:
                self._stats['fund_nav_hits'] += 1
                return cached
        
        self._stats['fund_nav_misses'] += 1
        
        try:
            # 提取纯代码
            code = symbol.split('.')[0] if '.' in symbol else symbol
            
            # 设置默认日期范围
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            
            df = ak.fund_etf_fund_info_em(fund=code, start_date=start_date, end_date=end_date)
            
            # 标准化列名
            column_mapping = {
                '净值日期': 'date',
                '单位净值': 'nav',
                '累计净值': 'acc_nav',
                '日增长率': 'change_pct',
                '申购状态': 'purchase_status',
                '赎回状态': 'redeem_status',
            }
            
            # 只保留存在的列
            available_columns = [col for col in column_mapping.keys() if col in df.columns]
            df = df[available_columns].rename(columns=column_mapping)
            
            # 安全转换数值
            for col in ['nav', 'acc_nav', 'change_pct']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: _safe_float(x, None))
            
            # 转换日期格式
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            result = df.to_dict('records')
            
            # 缓存结果
            self._fund_nav_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            print(f"Error fetching fund NAV for {symbol}: {e}")
            return []
    
    def get_etf_history(self, symbol: str, period: str = 'daily', 
                       start_date: str = '', end_date: str = '',
                       force_refresh: bool = False) -> list[dict]:
        """获取 ETF 历史行情（带缓存）
        
        Args:
            symbol: ETF 代码（如 159707 或 159707.SZ）
            period: 周期 ('daily', 'weekly', 'monthly')
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            force_refresh: 强制刷新缓存
        
        Returns:
            List of OHLCV records
        """
        # 生成缓存键
        cache_key = f"history:{symbol}:{period}:{start_date}:{end_date}"
        
        # 检查缓存
        if not force_refresh:
            cached = self._etf_history_cache.get(cache_key)
            if cached is not None:
                self._stats['etf_history_hits'] += 1
                return cached
        
        self._stats['etf_history_misses'] += 1
        
        try:
            # 提取纯代码
            code = symbol.split('.')[0] if '.' in symbol else symbol
            
            # 设置默认日期范围
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            
            df = ak.fund_etf_hist_em(symbol=code, period=period, 
                                     start_date=start_date, end_date=end_date)
            
            # 标准化列名
            column_mapping = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change',
                '换手率': 'turnover',
            }
            
            # 只保留存在的列
            available_columns = [col for col in column_mapping.keys() if col in df.columns]
            df = df[available_columns].rename(columns=column_mapping)
            
            # 安全转换数值
            for col in ['open', 'close', 'high', 'low', 'amount', 'amplitude', 'change_pct', 'change', 'turnover']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: _safe_float(x, None))
            
            for col in ['volume']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: _safe_int(x, 0))
            
            # 转换日期格式
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            result = df.to_dict('records')
            
            # 缓存结果
            self._etf_history_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            print(f"Error fetching ETF history for {symbol}: {e}")
            return []
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            'etf_spot': {
                'hits': self._stats['etf_spot_hits'],
                'misses': self._stats['etf_spot_misses'],
                'hit_rate': self._stats['etf_spot_hits'] / max(1, self._stats['etf_spot_hits'] + self._stats['etf_spot_misses']),
                'ttl': self._get_etf_spot_ttl(),
            },
            'fund_nav': {
                'hits': self._stats['fund_nav_hits'],
                'misses': self._stats['fund_nav_misses'],
                'hit_rate': self._stats['fund_nav_hits'] / max(1, self._stats['fund_nav_hits'] + self._stats['fund_nav_misses']),
                'ttl': FUND_NAV_CACHE_TTL,
            },
            'etf_history': {
                'hits': self._stats['etf_history_hits'],
                'misses': self._stats['etf_history_misses'],
                'hit_rate': self._stats['etf_history_hits'] / max(1, self._stats['etf_history_hits'] + self._stats['etf_history_misses']),
                'ttl': ETF_HISTORY_CACHE_TTL,
            },
        }
    
    def clear_cache(self, cache_type: str = 'all') -> None:
        """清除缓存
        
        Args:
            cache_type: 缓存类型 ('etf_spot', 'fund_nav', 'etf_history', 'all')
        """
        if cache_type in ('etf_spot', 'all'):
            self._etf_spot_cache.clear()
        if cache_type in ('fund_nav', 'all'):
            self._fund_nav_cache.clear()
        if cache_type in ('etf_history', 'all'):
            self._etf_history_cache.clear()
        if cache_type in ('catalog', 'all'):
            self._cache = None
            self._cache_time = None
