"""Tiny SQLite store that remembers which group chats the bot is in.

This is NOT game statistics (which we intentionally don't persist). It only
lets the admin pick a target chat from a list, surviving bot restarts.
"""
import sqlite3
from contextlib import closing


def init_db(path: str) -> None:
    with closing(sqlite3.connect(path)) as c:
        c.execute("CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, title TEXT)")
        c.commit()


def upsert_chat(path: str, chat_id: int, title: str) -> None:
    with closing(sqlite3.connect(path)) as c:
        c.execute(
            "INSERT INTO chats(chat_id, title) VALUES(?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title",
            (chat_id, title),
        )
        c.commit()


def remove_chat(path: str, chat_id: int) -> None:
    with closing(sqlite3.connect(path)) as c:
        c.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
        c.commit()


def list_chats(path: str) -> list[tuple[int, str]]:
    with closing(sqlite3.connect(path)) as c:
        rows = c.execute("SELECT chat_id, title FROM chats ORDER BY title").fetchall()
    return [(int(r[0]), r[1] or str(r[0])) for r in rows]


def get_title(path: str, chat_id: int) -> str | None:
    with closing(sqlite3.connect(path)) as c:
        row = c.execute("SELECT title FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
    return row[0] if row else None
