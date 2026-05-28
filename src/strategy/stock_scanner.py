from __future__ import annotations

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


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
