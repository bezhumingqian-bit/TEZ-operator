"""初始化用户表 + 创建默认 admin 账号。

使用方式：
  python scripts/init_users.py          # 使用 .env 配置的数据库
  python scripts/init_users.py --sqlite  # 强制使用本地 SQLite（开发用）

默认 admin 账号：
  用户名: admin
  密码: admin123（请首次登录后修改）
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
from sqlalchemy import create_engine, text
from app.config import get_settings


def _hash_password(password: str) -> str:
    """密码哈希（SHA256 + salt）。

    必须与 app/routers/auth.py 的 _hash_password 保持一致：
    优先读 .env 的 TEZ_PASSWORD_SALT，未设置时才回退到默认盐。
    否则初始化写入的哈希与登录验证用的盐不一致，会导致密码永远验证失败。
    """
    salt = get_settings().password_salt or "tez_salt_2026"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def main():
    settings = get_settings()

    # --sqlite 标志：强制使用本地 SQLite
    if "--sqlite" in sys.argv:
        db_url = "sqlite:///./data/tez_operator.db"
        Path("./data").mkdir(exist_ok=True)
        print(f"[sqlite mode] 使用: {db_url}")
    else:
        db_url = settings.database_url
        print(f"使用数据库: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    engine = create_engine(db_url, pool_pre_ping=True)

    # 创建 users 表（兼容 MySQL 和 SQLite）
    with engine.begin() as conn:
        # MySQL 语法
        if "mysql" in db_url:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    display_name VARCHAR(100) NOT NULL DEFAULT '',
                    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login_at DATETIME
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
        else:
            # SQLite
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    display_name VARCHAR(100) NOT NULL DEFAULT '',
                    role VARCHAR(20) NOT NULL DEFAULT 'viewer',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    last_login_at DATETIME
                )
            """))
        print("users 表已创建")

    # 创建默认 admin
    with engine.begin() as conn:
        result = conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": "admin"})
        if result.fetchone():
            print("admin 用户已存在，跳过")
        else:
            from datetime import datetime
            conn.execute(
                text("""
                    INSERT INTO users (username, password_hash, display_name, role, is_active, created_at)
                    VALUES (:username, :password_hash, :display_name, :role, 1, :created_at)
                """),
                {
                    "username": "admin",
                    "password_hash": _hash_password("admin123"),
                    "display_name": "管理员",
                    "role": "admin",
                    "created_at": datetime.now(),
                },
            )
            print("创建默认 admin 用户（密码: admin123）")

    engine.dispose()
    print("\n完成！可以启动服务并登录了。")


if __name__ == "__main__":
    main()
