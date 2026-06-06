import argparse

import pytest
from sqlalchemy import create_engine, func, select

from src.main import build_cli_parser, run_decide_command, run_halt_command
from src.storage.models import Base, KillSwitchEventRow
from src.storage.runtime_store import RuntimeStore


@pytest.fixture
def runtime_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    return RuntimeStore(engine)


class TestBuildCliParser:
    def test_parser_returns_argument_parser(self):
        parser = build_cli_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_current_commands_exist(self):
        parser = build_cli_parser()
        choices = parser._subparsers._group_actions[0].choices
        assert "decide" in choices
        assert "shadow-execute" in choices
        assert "live-execute" in choices
        assert "reconcile" in choices
        assert "halt" in choices
        assert "serve" in choices
        assert "run-decision" not in choices
        assert "plan-execution" not in choices

    def test_decide_requires_symbols(self):
        parser = build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["decide"])

    def test_halt_parses_resume_flag(self):
        parser = build_cli_parser()
        args = parser.parse_args(["halt", "--reason", "manual gate", "--resume"])
        assert args.command == "halt"
        assert args.reason == "manual gate"
        assert args.resume is True


def test_run_decide_command_persists_decision_and_target_position(runtime_store):
    summary = run_decide_command(symbols=["600519.SH"], mock_llm=True, store=runtime_store)

    assert summary["status"] == "ok"
    assert len(summary["decision_run_ids"]) == 1
    assert len(summary["target_position_ids"]) == 1

    decision_runs = runtime_store.list_decision_runs()
    assert len(decision_runs) == 1
    assert decision_runs[0]["symbol"] == "600519.SH"

    record = runtime_store.get_decision_run(summary["decision_run_ids"][0])
    assert record["parsed_action"] == "BUY"
    assert record["snapshot"]["features"]["mock_llm"] is True

    targets = runtime_store.list_active_target_positions()
    assert len(targets) == 1
    assert targets[0]["decision_run_id"] == summary["decision_run_ids"][0]
    assert targets[0]["target_value"] == 200000


def test_run_decide_command_is_blocked_when_kill_switch_active(runtime_store):
    runtime_store.set_kill_switch(True)

    summary = run_decide_command(symbols=["600519.SH"], mock_llm=True, store=runtime_store)

    assert summary["status"] == "blocked"
    assert summary["reason"] == "kill switch enabled"
    assert runtime_store.list_decision_runs() == []
    assert runtime_store.list_active_target_positions() == []


def test_run_halt_command_records_kill_switch_event(runtime_store):
    summary = run_halt_command(reason="manual gate", resume=False, store=runtime_store)

    assert summary["status"] == "ok"
    assert summary["active"] is True
    assert runtime_store.get_kill_switch() is True

    with runtime_store.engine.begin() as conn:
        event_count = conn.execute(select(func.count()).select_from(KillSwitchEventRow)).scalar_one()
    assert event_count == 1


def test_run_halt_command_can_resume(runtime_store):
    runtime_store.set_kill_switch(True)

    summary = run_halt_command(reason="resume gate", resume=True, store=runtime_store)

    assert summary["status"] == "ok"
    assert summary["active"] is False
    assert runtime_store.get_kill_switch() is False


def test_run_decide_command_uses_mock_settings_without_constructor_kwargs(runtime_store, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "fake-key")

    summary = run_decide_command(symbols=["600519.SH"], mock_llm=True, store=runtime_store)

    assert summary["status"] == "ok"
    assert len(summary["decision_run_ids"]) == 1
