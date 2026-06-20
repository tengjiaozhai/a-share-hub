"""Alpha 组合报告服务（V1：基于规则的报告聚合）。

报告组成：
- 持仓快照（来自 AlphaPortfolioService）
- 每个持仓的 fill 汇总、浮盈浮亏、影子意见、回测指标、规则化建议

设计原则：
- 纯函数（_build_recommendation / _build_shadow_section / _build_position_section / _build_fill_summary）
  便于单元测试，不依赖 store / IO。
- 默认 provider 是私有方法，可通过构造函数注入以便测试时替换。
- 不引用 FastAPI / HTTPException（Clean Architecture：service 层不感知 HTTP）。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from src.data.providers.akshare_catalog import normalize_symbol as normalize_a_share_symbol

PositionDict = dict
FillDict = dict
ShadowDict = dict
BacktestDict = dict

ShadowOpinionProvider = Callable[[dict | None, str], ShadowDict]
BacktestProvider = Callable[[str, str, float], BacktestDict]

_VALID_WINDOWS = {"30d", "60d", "120d"}


def _normalize_window(window: str | None) -> str:
    if window in _VALID_WINDOWS:
        return window
    return "60d"


def normalize_report_symbol(symbol: str) -> str:
    raw_text = str(symbol or "").strip()
    if not raw_text:
        return ""
    text = raw_text.upper()
    if "." in text:
        return text
    if text.isdigit() and len(text) == 6:
        return normalize_a_share_symbol(text)
    if raw_text.endswith(("x", "X")):
        return raw_text
    return f"{text}.US"


def normalize_report_symbols(symbols: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols or []:
        normalized_symbol = normalize_report_symbol(symbol)
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        normalized.append(normalized_symbol)
    return normalized


def normalize_report_positions(positions: list[dict] | None) -> list[dict]:
    normalized_positions: list[dict] = []
    for position in positions or []:
        symbol = normalize_report_symbol(position.get("symbol"))
        if not symbol:
            continue

        normalized_lots: list[dict] = []
        for lot in position.get("lots") or []:
            buy_date = str(lot.get("buy_date") or "").strip()
            quantity = float(lot.get("quantity", 0.0) or 0.0)
            buy_price = float(lot.get("buy_price", 0.0) or 0.0)
            if not buy_date or quantity <= 0:
                continue
            normalized_lots.append(
                {
                    "buy_date": buy_date,
                    "buy_price": buy_price,
                    "quantity": quantity,
                }
            )

        normalized_positions.append({"symbol": symbol, "lots": normalized_lots})
    return normalized_positions


def _normalize_analysis_input(payload: dict, symbols: list[str]) -> dict:
    normalized_positions = normalize_report_positions(payload.get("positions"))
    return {
        "symbols": symbols,
        "positions": normalized_positions,
    }


def _build_analysis_context(position: dict | None) -> dict:
    if not position:
        return {}
    lots = position.get("lots") or []
    if not lots:
        return {}

    total_quantity = sum(float(lot.get("quantity", 0.0) or 0.0) for lot in lots)
    total_cost = sum(
        float(lot.get("quantity", 0.0) or 0.0) * float(lot.get("buy_price", 0.0) or 0.0)
        for lot in lots
    )
    buy_dates = [str(lot.get("buy_date")) for lot in lots if lot.get("buy_date")]
    weighted_avg_cost = 0.0 if total_quantity == 0 else round(total_cost / total_quantity, 6)
    return {
        "lot_count": len(lots),
        "total_quantity": round(total_quantity, 6),
        "total_cost": round(total_cost, 6),
        "weighted_avg_cost": weighted_avg_cost,
        "first_buy_date": min(buy_dates) if buy_dates else None,
        "last_buy_date": max(buy_dates) if buy_dates else None,
    }


def _build_fill_summary(fills_for_symbol: list[FillDict]) -> dict:
    """汇总单只标的的 fill 列表。"""
    buy_quantity = 0.0
    sell_quantity = 0.0
    for fill in fills_for_symbol:
        quantity = float(fill.get("executed_quantity", 0.0) or 0.0)
        side = str(fill.get("action", "")).upper()
        if side == "BUY":
            buy_quantity += quantity
        elif side == "SELL":
            sell_quantity += quantity
    return {
        "count": len(fills_for_symbol),
        "buy_quantity": round(buy_quantity, 6),
        "sell_quantity": round(sell_quantity, 6),
    }


def _build_position_section(position: PositionDict) -> dict:
    """把 store 返回的 position 字典补充上 unrealized_pnl / unrealized_pnl_pct。"""
    quantity = float(position.get("quantity", 0.0) or 0.0)
    avg_cost = float(position.get("avg_cost", 0.0) or 0.0)
    mark_price = float(position.get("mark_price", avg_cost) or avg_cost)
    unrealized_pnl = round((mark_price - avg_cost) * quantity, 6)
    unrealized_pnl_pct = (
        0.0 if avg_cost == 0 or quantity == 0 else round((mark_price - avg_cost) / avg_cost, 6)
    )
    return {
        "symbol": position["symbol"],
        "quantity": quantity,
        "avg_cost": avg_cost,
        "mark_price": mark_price,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_pct": unrealized_pnl_pct,
    }


def _build_shadow_section(latest_workbench: dict | None, symbol: str) -> dict:
    """从 latest_workbench 中提取标的的影子意见；无数据时返回 UNKNOWN。"""
    if not latest_workbench:
        return {"action": "UNKNOWN", "confidence": 0, "reason": "无最近模拟交易"}

    history = latest_workbench.get("history") or {}
    latest_run = latest_workbench.get("latest_run") or {}
    candidates: list[dict] = []
    for source in (history.get("decisions"), latest_run.get("decision_items"), latest_run.get("target_items")):
        if isinstance(source, list):
            candidates.extend(row for row in source if isinstance(row, dict))

    for row in candidates:
        row_symbol = str(row.get("symbol") or row.get("asset_symbol") or "").upper()
        if row_symbol and row_symbol == symbol.upper():
            action = str(row.get("action") or row.get("parsed_action") or row.get("signal") or "HOLD").upper()
            confidence = row.get("confidence")
            try:
                confidence_value = float(confidence) if confidence is not None else 0.5
            except (TypeError, ValueError):
                confidence_value = 0.5
            confidence_value = max(0.0, min(1.0, confidence_value))
            reason = str(row.get("reason") or row.get("thesis") or "来自最近模拟交易")
            return {"action": action, "confidence": confidence_value, "reason": reason}

    return {"action": "UNKNOWN", "confidence": 0, "reason": "无最近模拟交易"}


def _build_backtest_section(
    symbol: str,
    window: str,
    opening_cash: float,
    backtest_provider: BacktestProvider,
) -> dict:
    """调用 provider 拿回测指标，失败/无数据时返回 no_data，不抛异常。"""
    try:
        result = backtest_provider(symbol, _normalize_window(window), float(opening_cash))
    except Exception:
        return {
            "status": "no_data",
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "trade_count": 0,
            "score": "N/A",
        }
    if not isinstance(result, dict):
        return {
            "status": "no_data",
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "trade_count": 0,
            "score": "N/A",
        }
    status = result.get("status", "ok")
    return {
        "status": "ok" if status == "ok" else "no_data",
        "total_return": float(result.get("total_return", 0.0) or 0.0),
        "max_drawdown": float(result.get("max_drawdown", 0.0) or 0.0),
        "trade_count": int(result.get("trade_count", 0) or 0),
        "score": result.get("score", "N/A"),
    }


def _build_recommendation(position: PositionDict, shadow: dict, backtest: dict) -> dict:
    """7 条规则的报告建议（V1 规则化）。

    规则：
    1. 无持仓 -> WATCH
    2. 浮亏 <= -8% -> EXIT 或 REDUCE
    3. 浮亏 <= -3% 且 shadow=SELL -> REDUCE
    4. 浮盈 >= 10% 且回测最大回撤偏大 -> REDUCE
    5. 浮盈 > 0 且 shadow=HOLD/BUY 且回测为正 -> HOLD
    6. shadow=BUY 且回测为正且当前浮盈不高 -> ADD
    7. 其他 -> WATCH
    """
    shadow_action = str(shadow.get("action", "UNKNOWN")).upper() if shadow else "UNKNOWN"
    backtest_status = str(backtest.get("status", "no_data"))
    backtest_total_return = float(backtest.get("total_return", 0.0) or 0.0)
    backtest_max_dd = float(backtest.get("max_drawdown", 0.0) or 0.0)
    backtest_positive = backtest_status == "ok" and backtest_total_return > 0
    quantity = float(position.get("quantity", 0.0) or 0.0)
    if quantity <= 0:
        if shadow_action == "BUY" and backtest_positive:
            return {
                "action": "ADD",
                "confidence": 0.55,
                "reason": "当前无持仓，影子建议买入且回测为正，可作为建仓候选",
            }
        if shadow_action == "SELL":
            return {
                "action": "WATCH",
                "confidence": 0.5,
                "reason": "当前无持仓，影子侧偏空，暂列观察",
            }
        return {
            "action": "WATCH",
            "confidence": 0.4,
            "reason": "当前无持仓，可先结合影子与回测继续观察",
        }

    pnl_pct = float(position.get("unrealized_pnl_pct", 0.0) or 0.0)

    if pnl_pct <= -0.08:
        return {
            "action": "EXIT" if pnl_pct <= -0.15 else "REDUCE",
            "confidence": min(0.95, 0.7 + abs(pnl_pct)),
            "reason": f"浮亏 {pnl_pct:.2%} 触发止损阈值 -8%",
        }

    if pnl_pct <= -0.03 and shadow_action == "SELL":
        return {
            "action": "REDUCE",
            "confidence": 0.7,
            "reason": "浮亏且影子建议卖出，建议减仓",
        }

    if pnl_pct >= 0.10 and backtest_max_dd >= 0.20:
        return {
            "action": "REDUCE",
            "confidence": 0.65,
            "reason": "浮盈较大且回测最大回撤偏高，锁定部分收益",
        }

    if pnl_pct > 0 and shadow_action in {"HOLD", "BUY"} and backtest_positive:
        return {
            "action": "HOLD",
            "confidence": 0.7,
            "reason": "浮盈、影子正向、回测为正，继续持有",
        }

    if shadow_action == "BUY" and backtest_positive and pnl_pct < 0.05:
        return {
            "action": "ADD",
            "confidence": 0.6,
            "reason": "影子买入且回测为正，浮盈不偏高，可考虑加仓",
        }

    return {"action": "WATCH", "confidence": 0.5, "reason": "无明确触发条件，观望"}


class AlphaPortfolioReportService:
    def __init__(
        self,
        store,
        user_id: str | None = None,
        shadow_opinion_provider: ShadowOpinionProvider | None = None,
        backtest_provider: BacktestProvider | None = None,
    ) -> None:
        self._store = store
        self._user_id = user_id
        self._shadow = shadow_opinion_provider or self._default_shadow_provider
        self._backtest = backtest_provider or self._default_backtest_provider

    def generate_report(self, payload: dict) -> dict:
        """主入口：拼装 {generated_at, portfolio_snapshot, items[]}。"""
        normalized_positions = normalize_report_positions(payload.get("positions"))
        symbols = normalize_report_symbols(payload.get("symbols") or [])
        if normalized_positions and not symbols:
            symbols = [position["symbol"] for position in normalized_positions]
        analysis_input = _normalize_analysis_input(payload, symbols)
        requested_positions = {position["symbol"]: position for position in analysis_input["positions"]}
        include_shadow = bool(payload.get("include_shadow", True))
        include_backtest = bool(payload.get("include_backtest", True))
        backtest_window = _normalize_window(payload.get("backtest_window"))
        opening_cash = float(payload.get("opening_cash", 10_000.0) or 0.0)

        positions = self._store.list_alpha_positions()
        fills = self._store.list_all_alpha_manual_fills()
        snapshot = self._store.get_latest_alpha_portfolio_snapshot()
        ticket_lookup = self._build_ticket_lookup()

        latest_workbench = self._latest_workbench()
        if symbols:
            positions_by_symbol = {row["symbol"]: row for row in positions}
            positions = [
                positions_by_symbol.get(
                    symbol,
                    {
                        "symbol": symbol,
                        "quantity": 0.0,
                        "avg_cost": 0.0,
                        "mark_price": 0.0,
                    },
                )
                for symbol in symbols
            ]

        items: list[dict] = []
        for position in positions:
            position_section = _build_position_section(position)
            symbol = position_section["symbol"]
            fills_for_symbol = self._enrich_fills_for_symbol(fills, ticket_lookup, symbol)
            fill_summary = _build_fill_summary(fills_for_symbol)

            if include_shadow:
                shadow = self._shadow(latest_workbench, symbol)
            else:
                shadow = {"action": "UNKNOWN", "confidence": 0, "reason": "未启用影子意见"}

            if include_backtest:
                backtest = _build_backtest_section(
                    symbol=symbol,
                    window=backtest_window,
                    opening_cash=opening_cash,
                    backtest_provider=self._backtest,
                )
            else:
                backtest = {
                    "status": "no_data",
                    "total_return": 0.0,
                    "max_drawdown": 0.0,
                    "trade_count": 0,
                    "score": "N/A",
                }

            recommendation = _build_recommendation(position_section, shadow, backtest)

            items.append(
                {
                    **position_section,
                    "analysis_context": _build_analysis_context(requested_positions.get(symbol)),
                    "fill_summary": fill_summary,
                    "shadow": shadow,
                    "backtest": backtest,
                    "recommendation": recommendation,
                }
            )

        return {
            "generated_at": datetime.now(UTC).astimezone().isoformat(),
            "portfolio_snapshot": snapshot or {},
            "analysis_input": analysis_input,
            "backtest_window": backtest_window,
            "items": items,
        }

    def _build_ticket_lookup(self) -> dict[str, dict]:
        return {
            ticket["ticket_id"]: ticket
            for ticket in self._store.list_alpha_tickets()
        }

    @staticmethod
    def _enrich_fills_for_symbol(
        fills: list[dict],
        ticket_lookup: dict[str, dict],
        symbol: str,
    ) -> list[dict]:
        enriched: list[dict] = []
        for fill in fills:
            ticket = ticket_lookup.get(fill["ticket_id"]) or {}
            if ticket.get("asset_symbol") != symbol:
                continue
            enriched.append(
                {
                    **fill,
                    "asset_symbol": ticket.get("asset_symbol"),
                    "action": ticket.get("action"),
                }
            )
        return enriched

    def _latest_workbench(self) -> dict | None:
        """从最近一次 dashboard run summary 取出 latest_workbench，缺失返回 None。"""
        summaries = self._store.list_dashboard_run_summaries(limit=1)
        if not summaries:
            return None
        return summaries[0].get("latest_workbench") or None

    def _default_shadow_provider(self, latest_workbench: dict | None, symbol: str) -> dict:
        return _build_shadow_section(latest_workbench, symbol)

    def _default_backtest_provider(self, symbol: str, window: str, opening_cash: float) -> dict:
        """V1 默认 provider：尽量复用真实回测引擎，失败/无数据时返回 no_data。"""
        try:
            from datetime import datetime as _dt
            from datetime import timedelta as _td

            from src.backtest.engine import run_daily_backtest
            from src.backtest.metrics import calculate_metrics
        except Exception:
            return {"status": "no_data", "score": "N/A"}

        end_date = _dt.utcnow().date()
        try:
            window_days = int(window.rstrip("d"))
        except (AttributeError, ValueError):
            window_days = 60
        start_date = end_date - _td(days=window_days)

        try:
            if symbol.upper().endswith(".US"):
                from src.us_stock.yahoo_provider import YahooProvider

                provider = YahooProvider()
                klines = provider.get_kline(symbol, interval="1d", range_str=f"{max(window_days, 30)}d")
                bars = [
                    {
                        "date": k.timestamp.strftime("%Y-%m-%d")
                        if hasattr(k.timestamp, "strftime")
                        else str(k.timestamp)[:10],
                        "open": k.open,
                        "high": k.high,
                        "low": k.low,
                        "close": k.close,
                        "volume": k.volume,
                    }
                    for k in klines
                ]
            else:
                from src.data.providers.akshare_provider import AkshareProvider

                bars_df = AkshareProvider().get_history(symbol, start_date, end_date)
                if bars_df is None or getattr(bars_df, "empty", True):
                    return {"status": "no_data", "score": "N/A"}
                bars = bars_df.to_dict("records")
        except Exception:
            return {"status": "no_data", "score": "N/A"}

        if not bars or len(bars) < 30:
            return {"status": "no_data", "score": "N/A"}

        try:
            result = run_daily_backtest(
                symbol=symbol,
                bars=bars,
                initial_cash=float(opening_cash),
                signals=[],
                lot_size=100,
                lot_size_a=100,
                lot_size_us=1,
                market="CN_A" if not symbol.upper().endswith(".US") else "US",
                fee_bps=0.0,
                slippage_bps=0.0,
            )
            metrics = calculate_metrics(result["equity_curve"], result["trades"])
            return {
                "status": "ok",
                "total_return": float(metrics.get("total_return", 0.0)),
                "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                "trade_count": len(result["trades"]),
                "score": metrics.get("sharpe", "N/A"),
            }
        except Exception:
            return {"status": "no_data", "score": "N/A"}
