import subprocess
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_requirements_file():
    assert os.path.exists(os.path.join(PROJECT_DIR, "requirements.txt"))


def test_main_module():
    result = subprocess.run(
        ["python", "-c", "from src.main import app; print('OK')"],
        capture_output=True,
        text=True,
        cwd=PROJECT_DIR,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_scripts_exist():
    scripts_dir = os.path.join(PROJECT_DIR, "scripts")
    assert os.path.exists(os.path.join(scripts_dir, "deploy.sh"))
    assert os.path.exists(os.path.join(scripts_dir, "start.sh"))
    assert os.path.exists(os.path.join(scripts_dir, "stop.sh"))


def test_scripts_executable():
    scripts_dir = os.path.join(PROJECT_DIR, "scripts")
    for name in ["deploy.sh", "start.sh", "stop.sh"]:
        path = os.path.join(scripts_dir, name)
        assert os.access(path, os.X_OK), f"{name} should be executable"
