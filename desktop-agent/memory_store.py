"""
AURA Desktop Agent — Local Persistent Memory & Companion Progression Store (SQLite)
Zero external database setup required for standalone desktop companion mode.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import AGENT_DIR, settings

DB_PATH = AGENT_DIR / "data" / "aura_memory.db"

BOND_TIERS = [
    (0, "New Acquaintance"),
    (50, "Lab Regular"),
    (150, "Study & Gaming Partner"),
    (350, "Trusted Confidant"),
    (700, "Inner Circle"),
    (1200, "Best Companion"),
]


def _bond_tier_for_xp(xp: int) -> Dict[str, Any]:
    level = 1
    title = BOND_TIERS[0][1]
    next_xp = BOND_TIERS[1][0]
    current_floor = 0
    for idx, (threshold, name) in enumerate(BOND_TIERS):
        if xp >= threshold:
            level = idx + 1
            title = name
            current_floor = threshold
            next_xp = BOND_TIERS[idx + 1][0] if idx + 1 < len(BOND_TIERS) else threshold
    return {
        "level": level,
        "title": title,
        "xp": xp,
        "floor_xp": current_floor,
        "next_xp": next_xp,
    }


class MemoryStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS profile (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        emotion TEXT DEFAULT 'neutral',
                        source TEXT DEFAULT 'voice',
                        created_at REAL NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL DEFAULT 'fact',
                        content TEXT NOT NULL,
                        importance INTEGER NOT NULL DEFAULT 5,
                        created_at REAL NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        text TEXT NOT NULL,
                        trigger_at REAL NOT NULL,
                        fired INTEGER NOT NULL DEFAULT 0,
                        created_at REAL NOT NULL
                    );
                    """
                )
                now = str(time.time())
                defaults = {
                    "user_name": settings.user_name,
                    "bond_xp": "10",
                    "mood": "playful",
                    "total_headpats": "0",
                    "total_pokes": "0",
                    "total_chats": "0",
                    "first_met_at": now,
                    "last_seen_at": now,
                }
                for k, v in defaults.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO profile (key, value) VALUES (?, ?)",
                        (k, v),
                    )
                conn.commit()
            finally:
                conn.close()

    def get_profile(self) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute("SELECT key, value FROM profile").fetchall()
                raw = {r["key"]: r["value"] for r in rows}
            finally:
                conn.close()

        xp = int(raw.get("bond_xp", "0"))
        return {
            "user_name": raw.get("user_name", settings.user_name),
            "mood": raw.get("mood", "playful"),
            "total_headpats": int(raw.get("total_headpats", "0")),
            "total_pokes": int(raw.get("total_pokes", "0")),
            "total_chats": int(raw.get("total_chats", "0")),
            "first_met_at": float(raw.get("first_met_at", time.time())),
            "last_seen_at": float(raw.get("last_seen_at", time.time())),
            "bond": _bond_tier_for_xp(xp),
        }

    def set_profile_value(self, key: str, value: Any) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO profile (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(value)),
                )
                conn.commit()
            finally:
                conn.close()

    def add_bond_xp(self, delta: int, stat_key: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT value FROM profile WHERE key = 'bond_xp'").fetchone()
                cur_xp = int(row["value"]) if row else 0
                new_xp = max(0, cur_xp + delta)
                conn.execute(
                    "INSERT INTO profile (key, value) VALUES ('bond_xp', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (str(new_xp),),
                )
                conn.execute(
                    "INSERT INTO profile (key, value) VALUES ('last_seen_at', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (str(time.time()),),
                )
                if stat_key:
                    srow = conn.execute(
                        "SELECT value FROM profile WHERE key = ?", (stat_key,)
                    ).fetchone()
                    cur_stat = int(srow["value"]) if srow else 0
                    conn.execute(
                        "INSERT INTO profile (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (stat_key, str(cur_stat + 1)),
                    )
                conn.commit()
            finally:
                conn.close()
        return self.get_profile()

    def add_message(
        self, role: str, content: str, emotion: str = "neutral", source: str = "voice"
    ) -> int:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO messages (role, content, emotion, source, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (role, content, emotion, source, time.time()),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def get_recent_messages(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, role, content, emotion, source, created_at "
                    "FROM messages ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [dict(r) for r in reversed(rows)]
            finally:
                conn.close()

    def add_memory(self, content: str, category: str = "fact", importance: int = 5) -> int:
        cleaned = content.strip()
        if not cleaned:
            return -1
        with self._lock:
            conn = self._connect()
            try:
                existing = conn.execute(
                    "SELECT id FROM memories WHERE LOWER(content) = LOWER(?)",
                    (cleaned,),
                ).fetchone()
                if existing:
                    return int(existing["id"])
                cur = conn.execute(
                    "INSERT INTO memories (category, content, importance, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (category, cleaned, importance, time.time()),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def delete_memory(self, memory_id: int) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                conn.commit()
            finally:
                conn.close()

    def list_memories(self, limit: int = 40) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, category, content, importance, created_at "
                    "FROM memories ORDER BY importance DESC, created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def format_memory_prompt(self, limit: int = 16) -> str:
        mems = self.list_memories(limit=limit)
        if not mems:
            return "No saved long-term memories yet — pay attention to learn about the user."
        return "\n".join(f"- [{m['category']}] {m['content']}" for m in mems)

    def add_reminder(self, text: str, delay_seconds: float) -> Dict[str, Any]:
        now = time.time()
        trigger_at = now + max(5.0, delay_seconds)
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "INSERT INTO reminders (text, trigger_at, fired, created_at) "
                    "VALUES (?, ?, 0, ?)",
                    (text.strip(), trigger_at, now),
                )
                conn.commit()
                rid = int(cur.lastrowid)
            finally:
                conn.close()
        return {
            "id": rid,
            "text": text.strip(),
            "trigger_at": trigger_at,
            "trigger_iso": datetime.fromtimestamp(trigger_at).strftime("%H:%M:%S"),
            "fired": False,
        }

    def list_pending_reminders(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, text, trigger_at, fired, created_at "
                    "FROM reminders WHERE fired = 0 ORDER BY trigger_at ASC"
                ).fetchall()
                return [
                    {
                        "id": r["id"],
                        "text": r["text"],
                        "trigger_at": r["trigger_at"],
                        "trigger_iso": datetime.fromtimestamp(r["trigger_at"]).strftime("%H:%M:%S"),
                        "fired": bool(r["fired"]),
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def pop_due_reminders(self) -> List[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, text, trigger_at FROM reminders "
                    "WHERE fired = 0 AND trigger_at <= ?",
                    (now,),
                ).fetchall()
                if not rows:
                    return []
                ids = [r["id"] for r in rows]
                conn.executemany(
                    "UPDATE reminders SET fired = 1 WHERE id = ?",
                    [(i,) for i in ids],
                )
                conn.commit()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def delete_reminder(self, reminder_id: int) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
                conn.commit()
            finally:
                conn.close()


memory_store = MemoryStore()
