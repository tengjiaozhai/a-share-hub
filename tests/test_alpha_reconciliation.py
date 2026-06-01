from src.alpha.reconciliation import reconcile_alpha_positions


def test_reconcile_alpha_positions_detects_quantity_and_cash_drift():
    result = reconcile_alpha_positions(
        internal_positions={"AAPLx": 1.2, "SPYx": 2.0},
        external_positions={"AAPLx": 1.0, "SPYx": 2.0},
        internal_cash=8_500.0,
        external_cash=8_420.0,
    )

    assert result["status"] == "MISMATCH"
    assert "AAPLx" in result["discrepancies"]["positions"]
    assert result["discrepancies"]["cash"]["difference"] == 80.0


def test_reconcile_alpha_positions_handles_float_precision():
    result = reconcile_alpha_positions(
        internal_positions={"AAPLx": 1.000000001},
        external_positions={"AAPLx": 1.0},
        internal_cash=1000.0,
        external_cash=1000.0,
    )

    assert result["status"] == "MATCHED"
    assert "AAPLx" not in result["discrepancies"]["positions"]
