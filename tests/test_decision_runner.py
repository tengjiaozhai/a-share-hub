from src.decision.decision_runner import parse_decision_output, create_decision_run

def test_invalid_llm_output_downgrades_to_hold():
    result = parse_decision_output("not-json")
    assert result.action == "HOLD"
    assert result.confidence == 0

def test_valid_llm_output_parsed_correctly():
    valid_json = '{"symbol": "600519.SH", "action": "BUY", "confidence": 80, "target_position_ratio": 0.15, "reason": "Strong signal"}'
    result = parse_decision_output(valid_json)
    assert result.symbol == "600519.SH"
    assert result.action == "BUY"
    assert result.confidence == 80

def test_decision_run_captures_prompt_hash_and_snapshot():
    run = create_decision_run(
        symbol="600519.SH",
        prompt_hash="abc123",
        input_snapshot={"symbol": "600519.SH"},
    )
    assert run["symbol"] == "600519.SH"
    assert run["prompt_hash"] == "abc123"
