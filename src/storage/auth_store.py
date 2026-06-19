import uuid
from datetime import datetime

from sqlalchemy import func, or_, select

from src.storage.auth_models import AppUserRow


class AuthStore:
    def __init__(self, engine) -> None:
        self.engine = engine

    def count_users(self) -> int:
        with self.engine.begin() as conn:
            return int(conn.execute(select(func.count()).select_from(AppUserRow.__table__)).scalar() or 0)

    def create_user(self, username: str, email: str, password_hash: str, role: str) -> dict:
        user_id = f"usr-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        with self.engine.begin() as conn:
            conn.execute(
                AppUserRow.__table__.insert().values(
                    user_id=user_id,
                    username=username,
                    email=email,
                    password_hash=password_hash,
                    role=role,
                    disabled=False,
                    created_at=now,
                    last_login_at=now,
                )
            )
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(AppUserRow.__table__).where(AppUserRow.user_id == user_id)
            ).mappings().first()
        return dict(row) if row else None

    def get_user_by_account(self, account: str) -> dict | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(AppUserRow.__table__).where(
                    or_(AppUserRow.username == account, AppUserRow.email == account)
                )
            ).mappings().first()
        return dict(row) if row else None

    def mark_login(self, user_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                AppUserRow.__table__.update()
                .where(AppUserRow.user_id == user_id)
                .values(last_login_at=datetime.utcnow())
            )
