from pathlib import Path

from src.core.config import Settings


def test_settings_reads_database_url_and_redis_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db-host:5432/hub")
    monkeypatch.setenv("REDIS_URL", "redis://redis-host:6379/0")
    monkeypatch.setenv("REDIS_ENABLED", "false")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://user:pass@db-host:5432/hub"
    assert settings.redis_url == "redis://redis-host:6379/0"
    assert settings.redis_enabled is False


def test_settings_uses_explicit_ssh_keys_not_ambiguous_password(monkeypatch):
    monkeypatch.setenv("AWS_HOST", "10.0.0.1")
    monkeypatch.setenv("AWS_SSH_USER", "ec2-user")
    monkeypatch.setenv("AWS_SSH_KEY_PATH", "/tmp/key.pem")
    settings = Settings()
    assert settings.aws_host == "10.0.0.1"
    assert settings.aws_ssh_user == "ec2-user"
    assert settings.aws_ssh_key_path == Path("/tmp/key.pem")