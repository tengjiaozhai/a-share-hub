"""重置 system 用户的密码为已知值（仅用于测试）。

修复方式：直接 UPDATE app_users.password_hash
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.auth_security import hash_password  # noqa: E402

import psycopg  # noqa: E402

from src.core.config import Settings  # noqa: E402

settings = Settings()
dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
conn = psycopg.connect(dsn, autocommit=True)
cur = conn.cursor()

new_password = "test-system-2026"
new_hash = hash_password(new_password)
cur.execute(
    "UPDATE app_users SET password_hash = %s WHERE user_id = 'system' RETURNING username",
    (new_hash,),
)
print(f"Reset password for system user ({cur.fetchone()[0]}): {new_password}")
conn.close()
