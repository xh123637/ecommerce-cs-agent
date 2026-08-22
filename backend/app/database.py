"""SQLite connection and schema initialization."""

import sqlite3
from contextlib import contextmanager

from .config import DATA_DIR, DB_PATH


@contextmanager
def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'customer',
                display_name  TEXT NOT NULL DEFAULT '',
                wechat_openid TEXT UNIQUE,
                created_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id            TEXT PRIMARY KEY,
                category      TEXT NOT NULL,
                title         TEXT NOT NULL,
                description   TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT '待处理',
                priority      TEXT NOT NULL DEFAULT '中',
                resolution    TEXT NOT NULL DEFAULT '',
                customer_id   INTEGER NOT NULL,
                created_by    INTEGER,
                assigned_to   INTEGER,
                source        TEXT NOT NULL DEFAULT 'web',
                language      TEXT NOT NULL DEFAULT 'zh',
                contact       TEXT NOT NULL DEFAULT '',
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                resolved_at   TEXT,
                FOREIGN KEY (customer_id) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id),
                FOREIGN KEY (assigned_to) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS knowledge_base (
                id          TEXT PRIMARY KEY,
                category    TEXT NOT NULL,
                title       TEXT NOT NULL,
                content     TEXT NOT NULL,
                tags        TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id   TEXT NOT NULL,
                step        TEXT NOT NULL,
                input       TEXT NOT NULL DEFAULT '',
                output      TEXT NOT NULL DEFAULT '',
                latency_ms  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id   TEXT NOT NULL,
                rating      INTEGER NOT NULL,
                comment     TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                ticket_id   TEXT,
                title       TEXT NOT NULL,
                content     TEXT NOT NULL DEFAULT '',
                is_read     INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );

            CREATE TABLE IF NOT EXISTS rlhf_feedback (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id    TEXT NOT NULL,
                ai_reply     TEXT NOT NULL DEFAULT '',
                human_reply  TEXT NOT NULL DEFAULT '',
                label        TEXT NOT NULL DEFAULT '',
                rating       INTEGER NOT NULL DEFAULT 0,
                comment      TEXT NOT NULL DEFAULT '',
                created_at   TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id    TEXT NOT NULL,
                filename     TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT '',
                size         INTEGER NOT NULL DEFAULT 0,
                path         TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                title       TEXT NOT NULL DEFAULT '',
                memory      TEXT NOT NULL DEFAULT '[]',
                ticket_id   INTEGER,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS conversation_messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role            TEXT NOT NULL,
                content         TEXT NOT NULL DEFAULT '',
                tools           TEXT NOT NULL DEFAULT '[]',
                compactions     INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );
            """
        )
        _ensure_column(conn, "tickets", "source", "source TEXT NOT NULL DEFAULT 'web'")
        _ensure_column(conn, "tickets", "created_by", "created_by INTEGER")
        _ensure_column(conn, "tickets", "language", "language TEXT NOT NULL DEFAULT 'zh'")
        _ensure_column(conn, "tickets", "contact", "contact TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "tickets", "shipper_code", "shipper_code TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "tickets", "tracking_no", "tracking_no TEXT NOT NULL DEFAULT ''")
        _ensure_column(conn, "users", "wechat_openid", "wechat_openid TEXT")
        _ensure_column(conn, "conversations", "ticket_id", "ticket_id INTEGER")
