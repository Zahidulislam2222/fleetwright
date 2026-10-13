"""SQLite is the action authority. A process death during ACTING never makes a retry safe."""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fw_agent.contracts import fingerprint
from fw_agent.privacy import private_file, restrict_existing_file


class Conflict(ValueError):
    """An action no longer has the exact, unused human approval required."""


class Store:
    def __init__(self, path: Path) -> None:
        private_file(path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, state TEXT NOT NULL, proposal TEXT NOT NULL,
                hash TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL,
                lab_token TEXT NOT NULL, error TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                at REAL NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts (
                task_id TEXT PRIMARY KEY, hash TEXT NOT NULL, title TEXT NOT NULL,
                body TEXT NOT NULL, at REAL NOT NULL
            );
        """)
        for suffix in ("-wal", "-shm"):
            restrict_existing_file(path.with_name(path.name + suffix))
        with self.lock:
            for row in self.db.execute("SELECT id FROM tasks WHERE state='ACTING'").fetchall():
                self.transition(row["id"], "UNKNOWN", "application restarted during action; reconcile only")
            for row in self.db.execute("SELECT id FROM tasks WHERE state='PREPARING'").fetchall():
                self.transition(row["id"], "FAILED", "application restarted before proposal; start a new task")

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def _event(self, task_id: str, state: str, detail: str) -> None:
        self.db.execute(
            "INSERT INTO events(task_id,at,state,detail) VALUES(?,?,?,?)", (task_id, time.time(), state, detail)
        )

    def create(self, proposal: dict[str, Any]) -> str:
        task_id = uuid.uuid4().hex
        with self.lock:
            self.db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,NULL)",
                (task_id, "PREPARING", json.dumps(proposal), "", 0, time.time(), secrets.token_urlsafe()),
            )
            self._event(task_id, "PREPARING", "reading allowed source and drafting locally")
        return task_id

    def get(self, task_id: str) -> dict[str, Any]:
        with self.lock:
            row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            result = dict(row)
            result.pop("lab_token")
            result["proposal"] = json.loads(result["proposal"])
            result["events"] = [
                dict(e)
                for e in self.db.execute(
                    "SELECT seq,at,state,detail FROM events WHERE task_id=? ORDER BY seq", (task_id,)
                )
            ]
            return result

    def list(self, limit: int) -> list[dict[str, Any]]:
        with self.lock:
            ids = [row["id"] for row in self.db.execute("SELECT id FROM tasks ORDER BY created DESC LIMIT ?", (limit,))]
            return [self.get(task_id) for task_id in ids]

    def ready(self, task_id: str, proposal: dict[str, Any], ttl: int) -> None:
        with self.lock:
            cur = self.db.execute(
                "UPDATE tasks SET state='AWAITING_APPROVAL',proposal=?,hash=?,expires=? "
                "WHERE id=? AND state='PREPARING'",
                (json.dumps(proposal), fingerprint(proposal), time.time() + ttl, task_id),
            )
            if cur.rowcount != 1:
                raise Conflict("task was cancelled while drafting")
            self._event(
                task_id, "AWAITING_APPROVAL", "exact destination, template, input and draft are bound for review"
            )

    def claim(self, task_id: str, approval_hash: str) -> dict[str, Any]:
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                task = self.get(task_id)
                if (
                    task["state"] != "AWAITING_APPROVAL"
                    or task["expires"] <= time.time()
                    or not secrets.compare_digest(task["hash"], approval_hash)
                    or not secrets.compare_digest(fingerprint(task["proposal"]), approval_hash)
                ):
                    raise Conflict("approval changed, expired or already consumed")
                self.db.execute("UPDATE tasks SET state='ACTING' WHERE id=?", (task_id,))
                self._event(task_id, "ACTING", "single-use exact approval consumed before browser action")
                self.db.execute("COMMIT")
                return task
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def transition(self, task_id: str, state: str, detail: str) -> None:
        with self.lock:
            current = self.get(task_id)["state"]
            allowed = {
                "PREPARING": {"FAILED", "CANCELLED"},
                "AWAITING_APPROVAL": {"FAILED", "CANCELLED"},
                "ACTING": {"CONFIRMED", "UNKNOWN"},
                "UNKNOWN": {"CONFIRMED"},
            }
            if state not in allowed.get(current, set()):
                raise Conflict(f"invalid transition from {current}")
            self.db.execute("UPDATE tasks SET state=?,error=? WHERE id=?", (state, detail, task_id))
            self._event(task_id, state, detail)

    def lab_token(self, task_id: str) -> str:
        with self.lock:
            row = self.db.execute("SELECT lab_token FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            return str(row["lab_token"])

    def receipt(self, task_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute("SELECT * FROM receipts WHERE task_id=?", (task_id,)).fetchone()
            return dict(row) if row else None

    def accept_lab(self, task_id: str, approval_hash: str, token: str, title: str, body: str) -> dict[str, Any]:
        """Owned destination accepts the exact authorized action, idempotently, with a receipt."""
        with self.lock:
            task = self.get(task_id)
            draft = task["proposal"].get("draft")
            if (
                task["state"] not in {"ACTING", "UNKNOWN"}
                or draft != {"title": title, "body": body}
                or not secrets.compare_digest(task["hash"], approval_hash)
                or not secrets.compare_digest(self.lab_token(task_id), token)
            ):
                raise Conflict("owned destination refused an unapproved or changed action")
            self.db.execute(
                "INSERT OR IGNORE INTO receipts VALUES(?,?,?,?,?)", (task_id, approval_hash, title, body, time.time())
            )
            result = self.receipt(task_id)
            assert result is not None
            return result
