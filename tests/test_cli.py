import argparse
import pytest
from src.main import build_cli_parser


class TestBuildCliParser:
    def test_parser_returns_ArgumentParser(self):
        parser = build_cli_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_default_command_is_serve(self):
        parser = build_cli_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestSyncMarket:
    def test_requires_symbols(self):
        parser = build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["sync-market"])

    def test_parses_symbols(self):
        parser = build_cli_parser()
        args = parser.parse_args(["sync-market", "--symbols", "600519.SH", "000001.SZ"])
        assert args.command == "sync-market"
        assert args.symbols == ["600519.SH", "000001.SZ"]

    def test_default_interval_and_limit(self):
        parser = build_cli_parser()
        args = parser.parse_args(["sync-market", "--symbols", "600519.SH"])
        assert args.interval == "daily"
        assert args.limit == 100

    def test_custom_interval_and_limit(self):
        parser = build_cli_parser()
        args = parser.parse_args(["sync-market", "--symbols", "600519.SH", "--interval", "weekly", "--limit", "50"])
        assert args.interval == "weekly"
        assert args.limit == 50


class TestBuildFeatures:
    def test_requires_symbols(self):
        parser = build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["build-features"])

    def test_parses_symbols_and_top_n(self):
        parser = build_cli_parser()
        args = parser.parse_args(["build-features", "--symbols", "600519.SH", "--top-n", "5"])
        assert args.command == "build-features"
        assert args.symbols == ["600519.SH"]
        assert args.top_n == 5

    def test_default_top_n(self):
        parser = build_cli_parser()
        args = parser.parse_args(["build-features", "--symbols", "600519.SH"])
        assert args.top_n == 10


class TestRunDecision:
    def test_requires_symbols(self):
        parser = build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["run-decision"])

    def test_mock_llm_flag(self):
        parser = build_cli_parser()
        args = parser.parse_args(["run-decision", "--symbols", "600519.SH", "--mock-llm"])
        assert args.command == "run-decision"
        assert args.mock_llm is True

    def test_no_mock_llm_by_default(self):
        parser = build_cli_parser()
        args = parser.parse_args(["run-decision", "--symbols", "600519.SH"])
        assert args.mock_llm is False


class TestPlanExecution:
    def test_requires_symbols_and_nav(self):
        parser = build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["plan-execution", "--symbols", "600519.SH"])

    def test_parses_symbols_and_nav(self):
        parser = build_cli_parser()
        args = parser.parse_args(["plan-execution", "--symbols", "600519.SH", "--nav", "1000000"])
        assert args.command == "plan-execution"
        assert args.symbols == ["600519.SH"]
        assert args.nav == 1000000.0


class TestShadowExecute:
    def test_requires_symbols(self):
        parser = build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["shadow-execute"])

    def test_mock_broker_flag(self):
        parser = build_cli_parser()
        args = parser.parse_args(["shadow-execute", "--symbols", "600519.SH", "--mock-broker"])
        assert args.command == "shadow-execute"
        assert args.mock_broker is True

    def test_no_mock_broker_by_default(self):
        parser = build_cli_parser()
        args = parser.parse_args(["shadow-execute", "--symbols", "600519.SH"])
        assert args.mock_broker is False


class TestReconcile:
    def test_requires_symbols(self):
        parser = build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["reconcile"])

    def test_parses_symbols(self):
        parser = build_cli_parser()
        args = parser.parse_args(["reconcile", "--symbols", "600519.SH", "000001.SZ"])
        assert args.command == "reconcile"
        assert args.symbols == ["600519.SH", "000001.SZ"]


class TestServe:
    def test_serve_command(self):
        parser = build_cli_parser()
        args = parser.parse_args(["serve"])
        assert args.command == "serve"
