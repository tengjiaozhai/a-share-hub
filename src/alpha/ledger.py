from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlphaPositionState:
    symbol: str
    quantity: float
    avg_cost: float


@dataclass(frozen=True)
class AlphaPortfolioState:
    cash_balance: float
    realized_pnl: float
    positions: dict[str, AlphaPositionState] = field(default_factory=dict)


def apply_manual_fill(
    state: AlphaPortfolioState,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
) -> AlphaPortfolioState:
    positions = dict(state.positions)
    current = positions.get(symbol, AlphaPositionState(symbol=symbol, quantity=0.0, avg_cost=0.0))
    cash_balance = state.cash_balance
    realized_pnl = state.realized_pnl

    if side == "BUY":
        total_cost = current.quantity * current.avg_cost + quantity * price
        new_quantity = current.quantity + quantity
        positions[symbol] = AlphaPositionState(
            symbol=symbol,
            quantity=new_quantity,
            avg_cost=(total_cost / new_quantity) if new_quantity else 0.0,
        )
        cash_balance -= quantity * price
    else:
        realized_pnl += (price - current.avg_cost) * quantity
        new_quantity = max(current.quantity - quantity, 0.0)
        positions[symbol] = AlphaPositionState(symbol=symbol, quantity=new_quantity, avg_cost=current.avg_cost)
        cash_balance += quantity * price

    return AlphaPortfolioState(
        cash_balance=cash_balance,
        realized_pnl=realized_pnl,
        positions=positions,
    )


def mark_to_market(state: AlphaPortfolioState, prices: dict[str, float]) -> dict[str, float]:
    unrealized = 0.0
    market_value = 0.0
    for symbol, position in state.positions.items():
        mark_price = prices.get(symbol, position.avg_cost)
        market_value += position.quantity * mark_price
        unrealized += (mark_price - position.avg_cost) * position.quantity
    return {
        "cash_balance": state.cash_balance,
        "realized_pnl": state.realized_pnl,
        "unrealized_pnl": unrealized,
        "nav": state.cash_balance + market_value,
    }
