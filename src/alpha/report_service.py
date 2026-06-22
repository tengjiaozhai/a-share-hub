"""Alpha 组合报告服务（DeepSeek pipeline）。

报告组成：
- 持仓快照（来自 AlphaPortfolioService）
- 每个持仓的 snapshot → research → trader → risk → persist

设计原则：
- 纯函数（_build_position_section / _build_fill_summary / _build_backtest_section）
  便于单元测试，不依赖 store / IO。
- 默认 provider 是私有方法，可通过构造函数注入以便测试时替换。
- 不引用 FastAPI / HTTPException（Clean Architecture：service 层不感知 HTTP）。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from src.alpha.analysis_agents import AnalysisAgentError
from src.alpha.analysis_risk import evaluate_risk
from src.data.providers.akshare_catalog import normalize_symbol as normalize_a_share_symbol

PositionDict = dict
FillDict = dict
BacktestDict = dict

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


def _build_positions_from_holdings_entries(entries: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        symbol = normalize_report_symbol(entry.get("symbol"))
        if not symbol:
            continue
        grouped.setdefault(symbol, []).append(
            {
                "buy_date": str(entry.get("buy_date") or "").strip(),
                "buy_price": float(entry.get("buy_price", 0.0) or 0.0),
                "quantity": float(entry.get("quantity", 0.0) or 0.0),
            }
        )
    return [{"symbol": symbol, "lots": lots} for symbol, lots in grouped.items()]


def _yahoo_symbol(symbol: str) -> str:
    return symbol[:-3] if symbol.upper().endswith(".US") else symbol


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


def _normalize_analysis_input(symbols: list[str], normalized_positions: list[dict]) -> dict:
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


class AlphaPortfolioReportService:
    def __init__(
        self,
        store,
        *,
        snapshot_builder,
        research_manager,
        trader,
        model_name: str,
        max_position_ratio: float = 0.2,
        backtest_provider: BacktestProvider | None = None,
    ) -> None:
        self._store = store
        self._snapshot_builder = snapshot_builder
        self._research_manager = research_manager
        self._trader = trader
        self._model_name = model_name
        self._max_position_ratio = max_position_ratio
        self._backtest = backtest_provider or self._default_backtest_provider

    def generate_report(self, payload: dict) -> dict:
        normalized_positions = normalize_report_positions(payload.get("positions"))
        if not normalized_positions:
            normalized_positions = _build_positions_from_holdings_entries(self._store.list_alpha_holdings_entries())
        symbols = normalize_report_symbols(payload.get("symbols") or [])
        if normalized_positions and not symbols:
            symbols = [position["symbol"] for position in normalized_positions]
        analysis_input = _normalize_analysis_input(symbols, normalized_positions)
        requested_positions = {position["symbol"]: position for position in analysis_input["positions"]}
        backtest_window = _normalize_window(payload.get("backtest_window"))
        opening_cash = float(payload.get("opening_cash", 10_000.0) or 0.0)

        positions = self._store.list_alpha_positions()
        fills = self._store.list_all_alpha_manual_fills()
        ticket_lookup = self._build_ticket_lookup()

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

        holdings_by_symbol: dict[str, list[dict]] = {}
        for position in normalized_positions:
            holdings_by_symbol[position["symbol"]] = position.get("lots", [])

        market_totals: dict[str, float] = {}
        for position in positions:
            symbol = position["symbol"]
            market = "us" if symbol.upper().endswith(".US") else "a"
            mv = float(position.get("quantity", 0.0) or 0.0) * float(position.get("mark_price", 0.0) or 0.0)
            market_totals[market] = market_totals.get(market, 0.0) + mv

        items: list[dict] = []
        for position in positions:
            position_section = _build_position_section(position)
            symbol = position_section["symbol"]
            market = "us" if symbol.upper().endswith(".US") else "a"
            lots = holdings_by_symbol.get(symbol, [])
            fills_for_symbol = self._enrich_fills_for_symbol(fills, ticket_lookup, symbol)
            fill_summary = _build_fill_summary(fills_for_symbol)

            backtest = _build_backtest_section(
                symbol=symbol,
                window=backtest_window,
                opening_cash=opening_cash,
                backtest_provider=self._backtest,
            )

            snapshot = None
            research = None
            trader_result = None
            risk = None
            status = "completed"
            error = None
            try:
                snapshot = self._snapshot_builder.build(
                    symbol=symbol,
                    lots=lots,
                    portfolio_market_value=market_totals.get(market, 0.0),
                )
                research = self._research_manager.analyze(snapshot)
                trader_result = self._trader.propose(snapshot, research)
                risk = evaluate_risk(
                    snapshot,
                    research,
                    trader_result,
                    max_position_ratio=self._max_position_ratio,
                )
            except Exception as exc:
                status = "failed"
                error = str(exc)

            run_id = self._store.insert_alpha_analysis_run(
                symbol=symbol,
                status=status,
                snapshot=snapshot.model_dump() if snapshot else None,
                research=research.model_dump() if research else None,
                trader=trader_result.model_dump() if trader_result else None,
                risk=risk.model_dump() if risk else None,
                model_name=self._model_name,
                error=error,
            )

            items.append(
                {
                    "run_id": run_id,
                    "status": status,
                    "symbol": symbol,
                    "snapshot": snapshot.model_dump() if snapshot else None,
                    "research": research.model_dump() if research else None,
                    "trader": trader_result.model_dump() if trader_result else None,
                    "risk": risk.model_dump() if risk else None,
                    "model_name": self._model_name,
                    "error": error,
                    "analysis_context": _build_analysis_context(requested_positions.get(symbol)),
                    "fill_summary": fill_summary,
                    "backtest": backtest,
                }
            )

        return {
            "generated_at": datetime.now(UTC).astimezone().isoformat(),
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

    def _default_backtest_provider(self, symbol: str, window: str, opening_cash: float) -> dict:
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
                klines = provider.get_kline(_yahoo_symbol(symbol), interval="1d", range_str=f"{max(window_days, 30)}d")
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
