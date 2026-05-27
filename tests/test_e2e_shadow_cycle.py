from pathlib import Path


def test_shadow_cycle_script_calls_real_cli_commands():
    script = Path("scripts/run_shadow_cycle.sh").read_text()
    assert "src.main decide" in script
    assert "src.main shadow-execute" in script
    assert "src.main reconcile" in script
    assert "src.main evaluate-shadow --window 1m" in script
