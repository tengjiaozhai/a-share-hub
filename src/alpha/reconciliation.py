EPSILON = 1e-8


def reconcile_alpha_positions(
    internal_positions: dict[str, float],
    external_positions: dict[str, float],
    internal_cash: float,
    external_cash: float,
) -> dict:
    position_diff = {}
    for symbol in sorted(set(internal_positions) | set(external_positions)):
        internal_qty = internal_positions.get(symbol, 0.0)
        external_qty = external_positions.get(symbol, 0.0)
        if abs(internal_qty - external_qty) > EPSILON:
            position_diff[symbol] = {
                "internal": internal_qty,
                "external": external_qty,
                "difference": internal_qty - external_qty,
            }

    cash_diff = {
        "internal": internal_cash,
        "external": external_cash,
        "difference": round(internal_cash - external_cash, 2),
    }
    has_cash_drift = abs(cash_diff["difference"]) > EPSILON
    status = "MATCHED" if not position_diff and not has_cash_drift else "MISMATCH"
    return {"status": status, "discrepancies": {"positions": position_diff, "cash": cash_diff}}
