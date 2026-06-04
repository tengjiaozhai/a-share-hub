from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


def score_quote(quote: dict[str, Any]) -> dict[str, Any]:
    """对单只股票的实时行情计算简化因子评分。

    因子权重: 涨跌幅(35%) + 振幅(25%) + 量比(20%) + 换手率(20%)
    """
    change_pct = _safe_float(quote.get("change_pct"))
    amplitude = _safe_float(quote.get("amplitude"))
    turnover = _safe_float(quote.get("turnover"))
    volume_ratio = _safe_float(quote.get("volume_ratio"))
    name = str(quote.get("name", ""))

    # 归一化到 [0, 1]
    f_change = max(0.0, min(1.0, (change_pct + 5) / 15))
    f_amplitude = max(0.0, min(1.0, amplitude / 15))
    f_turnover = max(0.0, min(1.0, turnover / 20))
    f_volume_ratio = max(0.0, min(1.0, volume_ratio / 5))

    score = (
        0.35 * f_change
        + 0.25 * f_amplitude
        + 0.20 * f_volume_ratio
        + 0.20 * f_turnover
    )

    if score >= 0.55 and change_pct > 0:
        action = "BUY"
    elif score <= 0.20 or change_pct < -3:
        action = "SELL"
    else:
        action = "HOLD"

    reasons = []
    if change_pct > 2:
        reasons.append(f"涨幅{change_pct:.1f}%，趋势向好")
    elif change_pct < -2:
        reasons.append(f"跌幅{change_pct:.1f}%，注意风险")
    if volume_ratio > 2:
        reasons.append(f"量比{volume_ratio:.1f}，资金活跃")
    if turnover > 5:
        reasons.append(f"换手{turnover:.1f}%，交投活跃")
    if amplitude > 8:
        reasons.append(f"振幅{amplitude:.1f}%，波动较大")
    if not reasons:
        reasons.append("指标平稳")

    return {
        "symbol": quote.get("symbol", ""),
        "name": name,
        "score": round(score, 4),
        "action": action,
        "reason": "、".join(reasons),
        "factors": {
            "change_pct": round(change_pct, 2),
            "amplitude": round(amplitude, 2),
            "turnover": round(turnover, 2),
            "volume_ratio": round(volume_ratio, 2),
        },
    }


def scan_market(
    stock_list: list[dict[str, str]],
    fetch_quotes_fn,
    top_n: int = 10,
) -> dict[str, Any]:
    """全市场扫描入口。

    stock_list: [{"symbol": "600519.SH", "name": "贵州茅台"}, ...]
    fetch_quotes_fn: callable(symbols: list[str]) -> DataFrame
    top_n: 每组返回前 N 只

    返回: {"buy": [...], "sell": [...], "hold": [...], "total_scanned": N}
    """
    symbols = [s["symbol"] for s in stock_list if s.get("symbol")]
    quotes_df = fetch_quotes_fn(symbols)

    if quotes_df.empty:
        return {"buy": [], "sell": [], "hold": [], "total_scanned": 0}

    results = []
    for _, row in quotes_df.iterrows():
        result = score_quote(row.to_dict())
        results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "buy": [r for r in results if r["action"] == "BUY"][:top_n],
        "sell": [r for r in results if r["action"] == "SELL"][:top_n],
        "hold": [r for r in results if r["action"] == "HOLD"][:top_n],
        "total_scanned": len(results),
    }


def confirm_buy_candidates(
    candidates: list[dict],
    kline_fetcher,
    config,
    top_n: int = 10,
    as_of: datetime | None = None,
) -> list[dict]:
    """对扫描器的 BUY 候选用历史 K 线做二次确认。

    candidates: 扫描器输出的 BUY 列表
    kline_fetcher: callable(symbol, start_date, end_date) -> DataFrame
    config: StrategyConfig
    top_n: 最终返回数量
    as_of: 确认基准日期，默认当前时间

    返回: 确认后的列表，每项增加 confirmed/final_score/final_action 字段
    """
    from src.indicators.technical_indicators import compute_features_from_bars
    from src.strategy.signal_engine import build_signal

    current = as_of or datetime.now()
    start = (current - timedelta(days=config.confirm_lookback_days)).date().isoformat()
    end = current.date().isoformat()

    confirmed = []
    for cand in candidates:
        symbol = cand["symbol"]
        enriched = dict(cand)
        try:
            df = kline_fetcher(symbol, start, end)
            if df.empty or len(df) < config.min_confirm_bars:
                enriched["confirmed"] = False
                enriched["final_score"] = 0.0
                enriched["final_action"] = "HOLD"
                enriched["confirm_reason"] = "历史数据不足"
                confirmed.append(enriched)
                continue
            features = compute_features_from_bars(df.to_dict("records"))
            signal = build_signal(symbol, features, config)
            rsi = signal.get("rsi_14", features.get("rsi_14", 50.0))
            enriched["confirmed"] = signal["action"] == "BUY" or (
                signal["technical_score"] >= config.buy_score_threshold - 0.015
                and features.get("volume_ratio_20", 0) > 2.0
                and rsi >= 45
            )
            enriched["final_score"] = signal["technical_score"]
            enriched["final_action"] = signal["action"]
            enriched["features"] = signal.get("features", features)
            enriched["contributions"] = signal.get("contributions", {})
            enriched["thresholds"] = signal.get("thresholds", {})
            enriched["confirm_reason"] = (
                f"趋势评分{signal['technical_score']:.4f}，"
                f"RSI={rsi:.2f}，信号{signal['action']}"
            )
        except Exception as exc:
            enriched["confirmed"] = False
            enriched["final_score"] = 0.0
            enriched["final_action"] = "HOLD"
            enriched["confirm_reason"] = f"确认失败: {exc}"
        confirmed.append(enriched)

    confirmed.sort(
        key=lambda row: (row["confirmed"], row.get("final_score", 0.0), row["score"]),
        reverse=True,
    )
    return confirmed[:top_n]


def score_us_quote(quote: dict[str, Any]) -> dict[str, Any]:
    change_pct = _safe_float(quote.get("change_pct"))
    volume = _safe_float(quote.get("volume"))
    name = str(quote.get("name", ""))

    f_change = max(0.0, min(1.0, change_pct / 5))
    f_volume = max(0.0, min(1.0, volume / 50_000_000))
    score = 0.50 * f_change + 0.50 * f_volume

    if score >= 0.45 and change_pct >= 2.0:
        action = "BUY"
    elif score <= 0.25 or change_pct < -3:
        action = "SELL"
    else:
        action = "HOLD"

    reasons = []
    if change_pct > 2:
        reasons.append(f"涨幅{change_pct:.1f}%，趋势向好")
    elif change_pct < -2:
        reasons.append(f"跌幅{change_pct:.1f}%，注意风险")
    if volume > 50_000_000:
        reasons.append(f"成交量{volume/10000:.0f}万，交投活跃")
    if not reasons:
        reasons.append("指标平稳")

    return {
        "symbol": quote.get("symbol", ""),
        "name": name,
        "score": round(score, 4),
        "action": action,
        "reason": "、".join(reasons),
        "factors": {
            "change_pct": round(change_pct, 2),
            "volume": round(volume, 0),
        },
    }


def scan_us_market(
    stock_list: list[dict[str, str]],
    fetch_quotes_fn,
    top_n: int = 10,
) -> dict[str, Any]:
    """美股全市场扫描入口。

    stock_list: [{"symbol": "AAPL", "name": "苹果"}, ...]
    fetch_quotes_fn: callable(symbols: list[str]) -> list[USQuote]
    top_n: 每组返回前 N 只

    返回: {"buy": [...], "sell": [...], "hold": [...], "total_scanned": N}
    """
    symbols = [s["symbol"] for s in stock_list if s.get("symbol")]
    quotes = fetch_quotes_fn(symbols)

    if not quotes:
        return {"buy": [], "sell": [], "hold": [], "total_scanned": 0}

    results = []
    for quote in quotes:
        quote_dict = quote.model_dump() if hasattr(quote, "model_dump") else quote
        result = score_us_quote(quote_dict)
        results.append(result)

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "buy": [r for r in results if r["action"] == "BUY"][:top_n],
        "sell": [r for r in results if r["action"] == "SELL"][:top_n],
        "hold": [r for r in results if r["action"] == "HOLD"][:top_n],
        "total_scanned": len(results),
    }


def confirm_us_buy_candidates(
    candidates: list[dict],
    kline_fetcher,
    top_n: int = 10,
) -> list[dict]:
    """对扫描器的美股 BUY 候选用历史 K 线做二次确认。

    candidates: 扫描器输出的 BUY 列表
    kline_fetcher: callable(symbol, interval, range_str) -> list[USKline]
    top_n: 最终返回数量

    返回: 确认后的列表，每项增加 confirmed/final_score/final_action 字段
    """
    from src.indicators.technical_indicators import compute_features_from_bars
    from src.strategy.signal_engine import build_signal
    from src.strategy.strategy_config import StrategyConfig
    from src.core.config import Settings

    settings = Settings()
    config = StrategyConfig.from_settings(settings)

    confirmed = []
    for cand in candidates:
        symbol = cand["symbol"]
        try:
            klines = kline_fetcher(symbol, "1d", "1y")
            if not klines or len(klines) < config.min_confirm_bars:
                cand["confirmed"] = False
                cand["final_score"] = 0.0
                cand["final_action"] = "HOLD"
                cand["confirm_reason"] = "历史数据不足"
                confirmed.append(cand)
                continue
            bars = [
                {"close": k.close, "volume": k.volume, "date": k.timestamp.isoformat()}
                for k in klines
            ]
            features = compute_features_from_bars(bars)
            signal = build_signal(symbol, features, config)
            cand["confirmed"] = signal["action"] == "BUY"
            cand["final_score"] = signal["technical_score"]
            cand["final_action"] = signal["action"]
            if not cand["confirmed"]:
                cand["confirm_reason"] = f"趋势评分{signal['technical_score']:.4f}，信号{signal['action']}"
            else:
                cand["confirm_reason"] = f"趋势评分{signal['technical_score']:.4f}，确认BUY"
        except Exception as e:
            cand["confirmed"] = False
            cand["final_score"] = 0.0
            cand["final_action"] = "HOLD"
            cand["confirm_reason"] = f"确认失败: {e}"
        confirmed.append(cand)

    # 排序：已确认的在前，按扫描器评分降序
    confirmed.sort(key=lambda x: (x["confirmed"], x["score"]), reverse=True)
    return confirmed[:top_n]


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
