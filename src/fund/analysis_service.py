"""基金分析服务
提供基金对比、基金评级、基金筛选等分析功能
"""
from datetime import datetime, timedelta
from typing import Optional
import akshare as ak
import pandas as pd
import numpy as np

from src.us_stock.cache import TTLMemoryCache
from src.us_stock.yahoo_provider import _safe_float, _safe_int


# 缓存 TTL 配置（秒）
FUND_PERFORMANCE_CACHE_TTL = 1800  # 基金业绩：30分钟
FUND_COMPARISON_CACHE_TTL = 900  # 基金对比：15分钟
FUND_SCREENING_CACHE_TTL = 3600  # 基金筛选：1小时


class FundAnalysisService:
    """基金分析服务，提供基金对比、评级、筛选等分析功能"""
    
    def __init__(self):
        # 业绩缓存
        self._performance_cache = TTLMemoryCache(ttl_seconds=FUND_PERFORMANCE_CACHE_TTL)
        # 对比缓存
        self._comparison_cache = TTLMemoryCache(ttl_seconds=FUND_COMPARISON_CACHE_TTL)
        # 筛选缓存
        self._screening_cache = TTLMemoryCache(ttl_seconds=FUND_SCREENING_CACHE_TTL)
    
    def get_fund_performance(self, symbol: str, force_refresh: bool = False) -> dict:
        """获取基金业绩分析
        
        Args:
            symbol: 基金代码（如 511280 或 511280.SH）
            force_refresh: 强制刷新缓存
        
        Returns:
            基金业绩分析数据
        """
        cache_key = f"performance:{symbol}"
        
        # 检查缓存
        if not force_refresh:
            cached = self._performance_cache.get(cache_key)
            if cached is not None:
                return cached
        
        try:
            # 提取纯代码
            code = symbol.split('.')[0] if '.' in symbol else symbol
            
            # 获取基金净值数据
            end_date = datetime.now().strftime('%Y%m%d')
            start_date_1y = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            start_date_3y = (datetime.now() - timedelta(days=1095)).strftime('%Y%m%d')
            
            # 获取1年净值数据
            df_1y = ak.fund_etf_fund_info_em(fund=code, start_date=start_date_1y, end_date=end_date)
            
            if df_1y.empty:
                return {"error": f"无法获取基金 {symbol} 的数据"}
            
            # 标准化列名
            df_1y = df_1y.rename(columns={
                '净值日期': 'date',
                '单位净值': 'nav',
                '累计净值': 'acc_nav',
                '日增长率': 'daily_return',
            })
            
            # 转换数据类型
            df_1y['nav'] = pd.to_numeric(df_1y['nav'], errors='coerce')
            df_1y['daily_return'] = pd.to_numeric(df_1y['daily_return'], errors='coerce')
            df_1y['date'] = pd.to_datetime(df_1y['date'])
            
            # 计算业绩指标
            latest_nav = df_1y['nav'].iloc[-1]
            earliest_nav = df_1y['nav'].iloc[0]
            
            # 收益率计算
            total_return_1y = (latest_nav / earliest_nav - 1) * 100 if earliest_nav > 0 else 0
            
            # 计算近1月、近3月、近6月收益
            now = datetime.now()
            nav_1m = df_1y[df_1y['date'] >= now - timedelta(days=30)]['nav'].iloc[0] if len(df_1y[df_1y['date'] >= now - timedelta(days=30)]) > 0 else earliest_nav
            nav_3m = df_1y[df_1y['date'] >= now - timedelta(days=90)]['nav'].iloc[0] if len(df_1y[df_1y['date'] >= now - timedelta(days=90)]) > 0 else earliest_nav
            nav_6m = df_1y[df_1y['date'] >= now - timedelta(days=180)]['nav'].iloc[0] if len(df_1y[df_1y['date'] >= now - timedelta(days=180)]) > 0 else earliest_nav
            
            return_1m = (latest_nav / nav_1m - 1) * 100 if nav_1m > 0 else 0
            return_3m = (latest_nav / nav_3m - 1) * 100 if nav_3m > 0 else 0
            return_6m = (latest_nav / nav_6m - 1) * 100 if nav_6m > 0 else 0
            
            # 计算年化收益率
            days = (df_1y['date'].iloc[-1] - df_1y['date'].iloc[0]).days
            annualized_return = ((1 + total_return_1y / 100) ** (365 / days) - 1) * 100 if days > 0 else 0
            
            # 计算最大回撤
            nav_series = df_1y['nav'].values
            peak = np.maximum.accumulate(nav_series)
            drawdown = (nav_series - peak) / peak
            max_drawdown = drawdown.min() * 100
            
            # 计算波动率（年化）
            daily_returns = df_1y['daily_return'].dropna() / 100
            volatility = daily_returns.std() * np.sqrt(252) * 100
            
            # 计算夏普比率（假设无风险利率为2%）
            risk_free_rate = 0.02
            excess_return = annualized_return / 100 - risk_free_rate
            sharpe_ratio = excess_return / (volatility / 100) if volatility > 0 else 0
            
            result = {
                "symbol": symbol,
                "latest_nav": float(latest_nav),
                "latest_date": df_1y['date'].iloc[-1].strftime('%Y-%m-%d'),
                "returns": {
                    "1m": round(return_1m, 2),
                    "3m": round(return_3m, 2),
                    "6m": round(return_6m, 2),
                    "1y": round(total_return_1y, 2),
                    "annualized": round(annualized_return, 2),
                },
                "risk_metrics": {
                    "max_drawdown": round(max_drawdown, 2),
                    "volatility": round(volatility, 2),
                    "sharpe_ratio": round(sharpe_ratio, 2),
                },
                "nav_history": [
                    {"date": row['date'].strftime('%Y-%m-%d'), "nav": float(row['nav'])}
                    for _, row in df_1y.tail(30).iterrows()
                ],
            }
            
            # 缓存结果
            self._performance_cache.set(cache_key, result)
            return result
            
        except Exception as e:
            return {"error": f"获取基金 {symbol} 业绩数据失败: {str(e)}"}
    
    def compare_funds(self, symbols: list[str], force_refresh: bool = False) -> dict:
        """对比多个基金
        
        Args:
            symbols: 基金代码列表
            force_refresh: 强制刷新缓存
        
        Returns:
            基金对比数据
        """
        cache_key = f"comparison:{','.join(sorted(symbols))}"
        
        # 检查缓存
        if not force_refresh:
            cached = self._comparison_cache.get(cache_key)
            if cached is not None:
                return cached
        
        try:
            results = []
            for symbol in symbols:
                perf = self.get_fund_performance(symbol, force_refresh=force_refresh)
                if "error" not in perf:
                    results.append(perf)
            
            if not results:
                return {"error": "无法获取任何基金的对比数据"}
            
            # 找出各项指标最优的基金
            best_return_1y = max(results, key=lambda x: x['returns']['1y'])
            best_sharpe = max(results, key=lambda x: x['risk_metrics']['sharpe_ratio'])
            lowest_drawdown = max(results, key=lambda x: x['risk_metrics']['max_drawdown'])  # 回撤是负数，越大越好
            
            comparison = {
                "funds": results,
                "summary": {
                    "best_return_1y": {
                        "symbol": best_return_1y['symbol'],
                        "value": best_return_1y['returns']['1y'],
                    },
                    "best_sharpe": {
                        "symbol": best_sharpe['symbol'],
                        "value": best_sharpe['risk_metrics']['sharpe_ratio'],
                    },
                    "lowest_drawdown": {
                        "symbol": lowest_drawdown['symbol'],
                        "value": lowest_drawdown['risk_metrics']['max_drawdown'],
                    },
                },
            }
            
            # 缓存结果
            self._comparison_cache.set(cache_key, comparison)
            return comparison
            
        except Exception as e:
            return {"error": f"基金对比失败: {str(e)}"}
    
    def screen_funds(self, 
                     fund_type: str = "",
                     min_return_1y: float = None,
                     max_drawdown: float = None,
                     min_sharpe: float = None,
                     limit: int = 20,
                     force_refresh: bool = False) -> list[dict]:
        """筛选基金
        
        Args:
            fund_type: 基金类型（如 ETF、股票型、混合型等）
            min_return_1y: 最低1年收益率
            max_drawdown: 最大回撤限制（负数）
            min_sharpe: 最低夏普比率
            limit: 返回数量限制
            force_refresh: 强制刷新缓存
        
        Returns:
            符合条件的基金列表
        """
        cache_key = f"screening:{fund_type}:{min_return_1y}:{max_drawdown}:{min_sharpe}:{limit}"
        
        # 检查缓存
        if not force_refresh:
            cached = self._screening_cache.get(cache_key)
            if cached is not None:
                return cached
        
        try:
            # 获取基金目录
            from src.fund.catalog_service import FundCatalogService
            catalog_service = FundCatalogService()
            catalog = catalog_service.get_fund_catalog(force_refresh=force_refresh)
            
            # 按类型筛选
            if fund_type:
                catalog = catalog[catalog['fund_type'].str.contains(fund_type, na=False)]
            
            # 限制数量以避免过多API调用
            catalog = catalog.head(50)
            
            # 获取每只基金的业绩数据
            screened_funds = []
            for _, row in catalog.iterrows():
                symbol = row['symbol']
                perf = self.get_fund_performance(symbol, force_refresh=False)
                
                if "error" in perf:
                    continue
                
                # 应用筛选条件
                if min_return_1y is not None and perf['returns']['1y'] < min_return_1y:
                    continue
                if max_drawdown is not None and perf['risk_metrics']['max_drawdown'] < max_drawdown:
                    continue
                if min_sharpe is not None and perf['risk_metrics']['sharpe_ratio'] < min_sharpe:
                    continue
                
                screened_funds.append({
                    "symbol": symbol,
                    "name": row['name'],
                    "fund_type": row['fund_type'],
                    "exchange": row['exchange'],
                    "returns": perf['returns'],
                    "risk_metrics": perf['risk_metrics'],
                    "latest_nav": perf['latest_nav'],
                })
            
            # 按1年收益率排序
            screened_funds.sort(key=lambda x: x['returns']['1y'], reverse=True)
            
            # 限制返回数量
            result = screened_funds[:limit]
            
            # 缓存结果
            self._screening_cache.set(cache_key, result)
            return result
            
        except Exception as e:
            return [{"error": f"基金筛选失败: {str(e)}"}]
    
    def get_fund_rating(self, symbol: str) -> dict:
        """获取基金评级
        
        Args:
            symbol: 基金代码
        
        Returns:
            基金评级数据
        """
        try:
            # 获取基金业绩数据
            perf = self.get_fund_performance(symbol)
            
            if "error" in perf:
                return perf
            
            # 根据业绩指标计算评级
            returns_1y = perf['returns']['1y']
            sharpe = perf['risk_metrics']['sharpe_ratio']
            max_dd = perf['risk_metrics']['max_drawdown']
            
            # 评级逻辑（简化版）
            score = 0
            
            # 收益率评分（40%）
            if returns_1y > 30:
                score += 40
            elif returns_1y > 20:
                score += 30
            elif returns_1y > 10:
                score += 20
            elif returns_1y > 0:
                score += 10
            
            # 夏普比率评分（30%）
            if sharpe > 2:
                score += 30
            elif sharpe > 1:
                score += 20
            elif sharpe > 0.5:
                score += 10
            
            # 回撤评分（30%）
            if max_dd > -10:
                score += 30
            elif max_dd > -20:
                score += 20
            elif max_dd > -30:
                score += 10
            
            # 评级映射
            if score >= 80:
                rating = "AAA"
                rating_label = "优秀"
            elif score >= 60:
                rating = "AA"
                rating_label = "良好"
            elif score >= 40:
                rating = "A"
                rating_label = "中等"
            elif score >= 20:
                rating = "B"
                rating_label = "一般"
            else:
                rating = "C"
                rating_label = "较差"
            
            return {
                "symbol": symbol,
                "rating": rating,
                "rating_label": rating_label,
                "score": score,
                "breakdown": {
                    "return_score": min(40, max(0, int(returns_1y / 30 * 40))),
                    "sharpe_score": min(30, max(0, int(sharpe / 2 * 30))),
                    "drawdown_score": min(30, max(0, int((100 + max_dd) / 100 * 30))),
                },
                "performance": perf,
            }
            
        except Exception as e:
            return {"error": f"获取基金 {symbol} 评级失败: {str(e)}"}
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "performance_cache": {
                "size": len(self._performance_cache._store),
            },
            "comparison_cache": {
                "size": len(self._comparison_cache._store),
            },
            "screening_cache": {
                "size": len(self._screening_cache._store),
            },
        }
