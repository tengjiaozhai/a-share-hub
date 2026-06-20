from sqlalchemy import create_engine

from src.storage.auth_models import AppUserRow
from src.storage.auth_store import AuthStore
from src.storage.models import Base


def test_set_role_requires_existing_user_and_allowed_role(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/auth.db", future=True)
    Base.metadata.create_all(engine)
    store = AuthStore(engine)
    user = store.create_user("alice", "alice@example.com", "hash", "user")

    assert store.set_role(user["user_id"], "admin") is True
    assert store.get_user(user["user_id"])["role"] == "admin"
    assert store.set_role("missing", "admin") is False
