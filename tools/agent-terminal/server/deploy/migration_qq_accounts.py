"""迁移脚本：创建 qq_accounts 表用于管理 QQ 账号池。"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "agent.db"


def run():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS qq_accounts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname        TEXT NOT NULL DEFAULT '',
            uin             TEXT NOT NULL DEFAULT '',
            midas_openid    TEXT NOT NULL DEFAULT '',
            midas_openkey   TEXT NOT NULL DEFAULT '',
            p_uin           TEXT NOT NULL DEFAULT '',
            p_skey          TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'ACTIVE'
                            CHECK(status IN ('ACTIVE','EXPIRED','ERROR')),
            last_verified_at TEXT,
            error_message   TEXT DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- 唯一索引：确保不重复添加同一个 QQ 号
        CREATE UNIQUE INDEX IF NOT EXISTS idx_qq_accounts_uin ON qq_accounts(uin);
    """)

    conn.commit()
    conn.close()
    print(f"✓ qq_accounts 表已就绪（{DB_PATH}）")


if __name__ == "__main__":
    run()
