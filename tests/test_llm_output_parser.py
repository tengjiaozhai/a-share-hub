from src.decision.decision_runner import parse_decision_output

def test_parse_empty_string():
    result = parse_decision_output("")
    assert result.action == "HOLD"

def test_parse_invalid_json():
    result = parse_decision_output("{invalid}")
    assert result.action == "HOLD"

def test_parse_missing_required_fields():
    result = parse_decision_output('{"symbol": "600519.SH"}')
    assert result.action == "HOLD"
