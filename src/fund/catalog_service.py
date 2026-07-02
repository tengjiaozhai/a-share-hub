"""基金目录服务"""
import ast
import math
import re
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd
import requests

from src.core.market_clock import is_continuous_session
from src.data.providers.akshare_catalog import infer_exchange
from src.us_stock.cache import TTLMemoryCache
from src.us_stock.yahoo_provider import _safe_float, _safe_int

# 缓存 TTL 配置（秒）
ETF_SPOT_CACHE_TTL_TRADING = 30  # 交易时段：30 秒
ETF_SPOT_CACHE_TTL_NON_TRADING = 300  # 非交易时段：5 分钟
FUND_NAV_CACHE_TTL = 3600  # 基金净值：1 小时
ETF_HISTORY_CACHE_TTL = 1800  # ETF 历史行情：30 分钟
FUNDCODE_SEARCH_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
FUNDCODE_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}
_FUNDCODE_SEARCH_PATTERN = re.compile(r"var\s+r\s*=\s*(\[[\s\S]*?\])\s*;")
_EXCHANGE_TRADED_FUND_KEYWORDS = ("ETF", "LOF", "REIT")
_FUND_CATALOG_COLUMNS = ["code", "name", "fund_type", "pinyin_abbr", "pinyin_full", "is_exchange_traded", "exchange", "symbol"]
_SH_EXCHANGE_TRADED_PREFIXES = ("50", "51", "52", "56", "58")
_SZ_EXCHANGE_TRADED_PREFIXES = ("15", "16", "18")


class FundNavUnavailableError(Exception):
    """场内基金当前数据源不支持真实净值"""

    def __init__(self, symbol: str, reason: str):
        self.code = "fund_nav_unsupported"
        self.symbol = symbol
        self.reason = reason
        super().__init__(f"{symbol}: {reason}")


class FundNotFoundError(Exception):
    """基金目录中找不到 symbol"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"Fund {symbol} not found")


def _has_exchange_traded_prefix(code: str) -> bool:
    return code.startswith(_SH_EXCHANGE_TRADED_PREFIXES) or code.startswith(_SZ_EXCHANGE_TRADED_PREFIXES)


def _is_exchange_traded_fund(code: str, name: str, fund_type: str) -> bool:
    normalized_name = (name or "").upper()
    raw_text = fund_type or ""
    text = raw_text.upper()

    if "联接" in raw_text and "ETF" in text:
        return False

    if _has_exchange_traded_prefix(code):
        return True

    if any(keyword in normalized_name for keyword in _EXCHANGE_TRADED_FUND_KEYWORDS):
        return True

    return any(keyword in text for keyword in _EXCHANGE_TRADED_FUND_KEYWORDS) or "封闭" in raw_text


def _infer_fund_exchange(code: str, name: str, fund_type: str) -> str:
    if not _is_exchange_traded_fund(code, name, fund_type):
        return "OTC"

    if code.startswith(_SH_EXCHANGE_TRADED_PREFIXES):
        return "SH"
    if code.startswith(_SZ_EXCHANGE_TRADED_PREFIXES):
        return "SZ"

    try:
        inferred = infer_exchange(code)
    except ValueError:
        return "OTC"

    return inferred if inferred in {"SH", "SZ", "BJ"} else "OTC"


def _build_market_metadata(code: str, name: str, fund_type: str) -> tuple[bool, str]:
    is_exchange_traded = _is_exchange_traded_fund(code, name, fund_type)
    exchange = _infer_fund_exchange(code, name, fund_type)
    return is_exchange_traded, exchange


def parse_fundcode_search_js(payload: str) -> pd.DataFrame:
    match = _FUNDCODE_SEARCH_PATTERN.search(payload)
    if match is None:
        raise ValueError("fundcode_search payload missing var r array")

    raw_records = ast.literal_eval(match.group(1))
    rows: list[dict] = []
    for raw_record in raw_records:
        if not isinstance(raw_record, (list, tuple)) or len(raw_record) < 5:
            continue

        code = str(raw_record[0]).strip().zfill(6)
        pinyin_abbr = str(raw_record[1] or "").strip()
        name = str(raw_record[2] or "").strip()
        fund_type = str(raw_record[3] or "").strip()
        pinyin_full = str(raw_record[4] or "").strip()
        is_exchange_traded, exchange = _build_market_metadata(code, name, fund_type)

        rows.append(
            {
                "code": code,
                "name": name,
                "fund_type": fund_type,
                "pinyin_abbr": pinyin_abbr,
                "pinyin_full": pinyin_full,
                "is_exchange_traded": is_exchange_traded,
                "exchange": exchange,
                "symbol": f"{code}.{exchange}",
            }
        )

    return pd.DataFrame(
        rows,
        columns=_FUND_CATALOG_COLUMNS,
    )


def _empty_fund_catalog() -> pd.DataFrame:
    return pd.DataFrame(columns=_FUND_CATALOG_COLUMNS)


def _paginate_records(items: list[dict], page: int, page_size: int) -> dict:
    total = len(items)
    total_pages = math.ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


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
            DataFrame with columns: symbol, code, name, fund_type, pinyin_abbr, pinyin_full, exchange
        """
        if not force_refresh and self._is_cache_valid():
            return self._cache.copy()

        try:
            response = requests.get(FUNDCODE_SEARCH_URL, headers=FUNDCODE_SEARCH_HEADERS, timeout=10)
            response.raise_for_status()
            df = parse_fundcode_search_js(response.text)
        except (requests.RequestException, SyntaxError, ValueError) as e:
            print(f"Error fetching fund catalog: {e}")
            if self._cache is not None:
                return self._cache.copy()
            return _empty_fund_catalog()

        self._cache = df
        self._cache_time = datetime.now()

        return df.copy()

    def _build_catalog_lookup(self) -> dict[str, dict]:
        df = self.get_fund_catalog()
        if df.empty:
            return {}
        return {
            str(record["code"]): record
            for record in df.to_dict("records")
        }
    
    def search_funds(
        self,
        query: str = '',
        fund_type: str = '',
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """搜索基金"""
        df = self.get_fund_catalog()

        if fund_type:
            df = df[df['fund_type'] == fund_type]

        if query:
            query_text = query.strip()
            df = df[
                df['code'].str.contains(query_text, case=False, na=False, regex=False)
                | df['name'].str.contains(query_text, case=False, na=False, regex=False)
                | df['fund_type'].str.contains(query_text, case=False, na=False, regex=False)
                | df['pinyin_abbr'].str.contains(query_text, case=False, na=False, regex=False)
                | df['pinyin_full'].str.contains(query_text, case=False, na=False, regex=False)
            ]

        return _paginate_records(df.to_dict('records'), page=page, page_size=page_size)
    
    def get_fund_by_symbol(self, symbol: str) -> Optional[dict]:
        """根据 symbol 获取基金信息"""
        df = self.get_fund_catalog()
        result = df[df['symbol'] == symbol]
        if result.empty:
            return None
        return result.iloc[0].to_dict()
    
    def _filter_etf_spot_items(self, items: list[dict], query: str) -> list[dict]:
        query_text = query.strip().lower()
        if not query_text:
            return items
        return [
            item for item in items
            if query_text in str(item.get('code', '')).lower()
            or query_text in str(item.get('name', '')).lower()
        ]

    def get_etf_spot(
        self,
        page: int = 1,
        page_size: int = 20,
        query: str = '',
        force_refresh: bool = False,
    ) -> dict:
        """获取 ETF 实时行情（带缓存）
        
        Args:
            page: 页码
            page_size: 每页数量
            query: 仅按代码/名称筛选
            force_refresh: 强制刷新缓存
        
        Returns:
            分页 ETF 实时行情对象
        """
        # 检查缓存
        if not force_refresh:
            cached = self._etf_spot_cache.get(self._etf_spot_cache_key)
            if cached is not None:
                self._stats['etf_spot_hits'] += 1
                return _paginate_records(self._filter_etf_spot_items(cached, query), page=page, page_size=page_size)
        
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

            catalog_lookup = self._build_catalog_lookup()
            if catalog_lookup:
                df['catalog_meta'] = df['code'].astype(str).map(catalog_lookup)
                df = df[df['catalog_meta'].notna()].copy()
                df = df[df['catalog_meta'].apply(lambda meta: bool(meta.get('is_exchange_traded', False)))].copy()
                df = df[
                    df['catalog_meta'].apply(
                        lambda meta: bool(meta.get('exchange')) and meta.get('symbol') == f"{meta.get('code')}.{meta.get('exchange')}"
                    )
                ].copy()
                df['exchange'] = df['catalog_meta'].apply(lambda meta: meta['exchange'])
                df['symbol'] = df['catalog_meta'].apply(lambda meta: meta['symbol'])
            else:
                df = df.iloc[0:0].copy()
            
            # 安全转换数值
            for col in ['price', 'change_pct', 'change', 'open', 'high', 'low', 'prev_close']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: _safe_float(x, None))
            
            for col in ['volume', 'amount']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: _safe_int(x, 0))
            
            # 过滤无效价格
            df = df[df['price'].notna() & (df['price'] > 0)]
            if 'catalog_meta' in df.columns:
                df = df.drop(columns=['catalog_meta'])
            
            # 转换为列表并缓存
            result = df.to_dict('records')
            self._etf_spot_cache.set(self._etf_spot_cache_key, result)
            
            filtered = self._filter_etf_spot_items(result, query)
            return _paginate_records(filtered, page=page, page_size=page_size)
            
        except Exception as e:
            print(f"Error fetching ETF spot: {e}")
            return _paginate_records([], page=page, page_size=page_size)

    def _resolve_fund_record(self, symbol: str) -> dict:
        df = self.get_fund_catalog()
        code = symbol.split('.')[0] if '.' in symbol else symbol

        if '.' in symbol:
            exact_symbol = df[df['symbol'] == symbol]
            if not exact_symbol.empty:
                return exact_symbol.iloc[0].to_dict()

        code_matches = df[df['code'] == code]
        if code_matches.empty:
            raise FundNotFoundError(symbol)

        if '.' in symbol:
            exchange = symbol.split('.', 1)[1].upper()
            exchange_matches = code_matches[code_matches['exchange'].str.upper() == exchange]
            if not exchange_matches.empty:
                return exchange_matches.iloc[0].to_dict()

        return code_matches.iloc[0].to_dict()

    def _fetch_otc_fund_nav_frame(self, code: str, fund_type: str) -> pd.DataFrame:
        if "货币" in (fund_type or ""):
            return ak.fund_money_fund_info_em(symbol=code)
        if "理财" in (fund_type or ""):
            return ak.fund_financial_fund_info_em(symbol=code)
        if "分级" in (fund_type or ""):
            return ak.fund_graded_fund_info_em(symbol=code)
        return ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势', period='成立来')

    def _normalize_fund_nav_frame(self, df: pd.DataFrame) -> list[dict]:
        column_mapping = {
            '净值日期': 'date',
            '单位净值': 'nav',
            '累计净值': 'acc_nav',
            '日增长率': 'change_pct',
            '申购状态': 'purchase_status',
            '赎回状态': 'redeem_status',
        }

        available_columns = [col for col in column_mapping.keys() if col in df.columns]
        if not available_columns:
            return []

        normalized = df[available_columns].rename(columns=column_mapping).copy()

        for col in ['nav', 'acc_nav', 'change_pct']:
            if col in normalized.columns:
                normalized[col] = normalized[col].apply(lambda x: _safe_float(x, None))

        if 'date' in normalized.columns:
            normalized['date'] = pd.to_datetime(normalized['date']).dt.strftime('%Y-%m-%d')

        return normalized.to_dict('records')
    
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
            fund = self._resolve_fund_record(symbol)
            code = str(fund['code'])
            is_exchange_traded = bool(fund.get('is_exchange_traded', False))
            
            # 设置默认日期范围
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

            if is_exchange_traded:
                raise FundNavUnavailableError(
                    symbol=symbol,
                    reason='true NAV unavailable for exchange-traded fund via current provider',
                )

            fund_type = str(fund.get('fund_type', ''))
            df = self._fetch_otc_fund_nav_frame(code=code, fund_type=fund_type)
            result = self._normalize_fund_nav_frame(df)
            if result and ('date' in result[0]):
                result = [
                    row for row in result
                    if start_date <= row['date'].replace('-', '') <= end_date
                ]
            
            # 缓存结果
            self._fund_nav_cache.set(cache_key, result)
            
            return result
        except (FundNavUnavailableError, FundNotFoundError):
            raise
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
