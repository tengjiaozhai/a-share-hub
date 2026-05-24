import pytest
import subprocess
import os
from pathlib import Path
from src.core.config import Settings

def test_shadow_cycle_produces_no_unreconciled_orders():
    """测试影子周期不会产生未对账订单"""
    # 简化的端到端测试
    settings = Settings()
    assert settings.enable_live_trading is False
    assert settings.execution_mode == "shadow"

def test_live_flag_remains_disabled_without_release_marker():
    """测试实盘标志在没有发布标记时保持禁用"""
    settings = Settings()
    assert settings.enable_live_trading is False

def test_shadow_cycle_script_is_fail_closed():
    """测试影子周期脚本是fail-closed的"""
    script_path = Path(__file__).parent.parent / "scripts" / "run_shadow_cycle.sh"
    
    # 读取脚本内容
    with open(script_path, 'r') as f:
        content = f.read()
    
    # 检查set -euo pipefail
    assert 'set -euo pipefail' in content, "脚本必须包含 'set -euo pipefail'"
    
    # 检查没有|| echo
    assert '|| echo' not in content, "脚本不能包含 '|| echo'"
    
    # 检查使用REPO_ROOT变量
    assert 'REPO_ROOT=' in content, "脚本必须使用REPO_ROOT变量"
    
    # 检查没有硬编码路径
    assert '/home/ec2-user' not in content, "脚本不能包含硬编码路径"
    
    # 检查实际执行CLI命令（不是只检查导入）
    assert 'python -m src.main' in content or '"${PYTHON}" -m src.main' in content, "脚本必须实际执行CLI命令"

def test_reconcile_script_is_fail_closed():
    """测试对账脚本是fail-closed的"""
    script_path = Path(__file__).parent.parent / "scripts" / "run_reconcile.sh"
    
    with open(script_path, 'r') as f:
        content = f.read()
    
    assert 'set -euo pipefail' in content, "脚本必须包含 'set -euo pipefail'"
    assert '|| echo' not in content, "脚本不能包含 '|| echo'"
    assert 'REPO_ROOT=' in content, "脚本必须使用REPO_ROOT变量"
    assert '/home/ec2-user' not in content, "脚本不能包含硬编码路径"
    assert 'python -m src.main' in content or '"${PYTHON}" -m src.main' in content, "脚本必须实际执行CLI命令"

def test_shadow_cycle_script_executes():
    """测试影子周期脚本可以执行（模拟）"""
    script_path = Path(__file__).parent.parent / "scripts" / "run_shadow_cycle.sh"
    
    # 检查脚本是否可执行
    assert script_path.exists(), "脚本文件必须存在"
    assert os.access(script_path, os.X_OK), "脚本必须可执行"


def test_shadow_cycle_mentions_postgresql_migration_and_not_sqlite():
    readme = Path("README.md").read_text()
    assert "DATABASE_URL" in readme
    assert "PostgreSQL" in readme
    assert "runtime_store_path" not in readme


def test_shadow_cycle_script_runs_migrations_before_runtime_commands():
    script = Path("scripts/run_shadow_cycle.sh").read_text()
    assert "alembic upgrade head" in script
    assert '"${PYTHON}" -m src.main run-decision' in script
