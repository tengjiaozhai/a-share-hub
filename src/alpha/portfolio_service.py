from src.alpha.ledger import AlphaPortfolioState, apply_manual_fill, mark_to_market


class AlphaPortfolioService:
    def __init__(self, store, user_id: str) -> None:
        self._store = store
        self._user_id = user_id

    def load_portfolio(self) -> dict:
        ticket_lookup = self._build_ticket_lookup()
        fills = [
            self._enrich_fill(fill, ticket_lookup[fill["ticket_id"]])
            for fill in reversed(self._store.list_all_alpha_manual_fills(self._user_id))
        ]
        return {
            "snapshot": self._store.get_latest_alpha_portfolio_snapshot(self._user_id),
            "positions": self._store.list_alpha_positions(self._user_id),
            "fills": fills,
        }

    def rebuild_from_manual_fills(
        self,
        opening_cash: float,
        price_map: dict[str, float],
        ticket_lookup: dict[str, dict] | None = None,
    ) -> dict:
        resolved_ticket_lookup = ticket_lookup or self._build_ticket_lookup()
        state = AlphaPortfolioState(cash_balance=opening_cash, realized_pnl=0.0, positions={})
        for fill in self._store.list_all_alpha_manual_fills(self._user_id):
            ticket = resolved_ticket_lookup[fill["ticket_id"]]
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
        self._store.replace_alpha_positions(self._user_id, positions)
        self._store.insert_alpha_portfolio_snapshot(self._user_id, **summary)
        summary["positions"] = positions
        return summary

    def rebuild_portfolio(self, opening_cash: float, price_map: dict[str, float]) -> dict:
        self.rebuild_from_manual_fills(opening_cash=opening_cash, price_map=price_map)
        return self.load_portfolio()

    def _build_ticket_lookup(self) -> dict[str, dict]:
        return {
            ticket["ticket_id"]: ticket
            for ticket in self._store.list_alpha_tickets(self._user_id)
        }

    def _enrich_fill(self, fill: dict, ticket: dict) -> dict:
        return {
            **fill,
            "asset_symbol": ticket["asset_symbol"],
            "underlying_symbol": ticket["underlying_symbol"],
            "action": ticket["action"],
            "ticket_status": ticket["status"],
        }
