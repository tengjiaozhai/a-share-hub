from src.alpha.ledger import AlphaPortfolioState, apply_manual_fill, mark_to_market


class AlphaPortfolioService:
    def __init__(self, store) -> None:
        self._store = store

    def rebuild_from_manual_fills(
        self,
        opening_cash: float,
        price_map: dict[str, float],
        ticket_lookup: dict[str, dict],
    ) -> dict:
        state = AlphaPortfolioState(cash_balance=opening_cash, realized_pnl=0.0, positions={})
        for fill in self._store.list_all_alpha_manual_fills():
            ticket = ticket_lookup[fill["ticket_id"]]
            state = apply_manual_fill(
                state,
                symbol=ticket["asset_symbol"],
                side=ticket["action"],
                quantity=fill["executed_quantity"],
                price=fill["executed_price"],
            )

        summary = mark_to_market(state, price_map)
        positions = [
            {
                "symbol": position.symbol,
                "quantity": position.quantity,
                "avg_cost": position.avg_cost,
                "mark_price": price_map.get(position.symbol, position.avg_cost),
            }
            for position in state.positions.values()
            if position.quantity > 0
        ]
        self._store.replace_alpha_positions(positions)
        self._store.insert_alpha_portfolio_snapshot(**summary)
        summary["positions"] = positions
        return summary
