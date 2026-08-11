"""SQLite: аудит решений, идемпотентность, очередь ревью, результаты задач.
В PoC это одно хранилище; в проде — журнал аудита, кеш идемпотентности и
рабочая очередь живут отдельно (см. дизайн-документ)."""
import json
import sqlite3
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    request_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    decision TEXT NOT NULL,
    confidence REAL,
    threshold REAL,
    reason TEXT,
    model_version TEXT,
    payload_masked TEXT
);
CREATE INDEX IF NOT EXISTS audit_request ON audit(request_id);
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS review (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    request_id TEXT NOT NULL,
    payload_masked TEXT,
    reason TEXT,
    status TEXT NOT NULL,
    verdict TEXT,
    reviewer TEXT,
    comment TEXT
);
CREATE TABLE IF NOT EXISTS task (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    request_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT
);
"""


class Store:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def log_decision(self, *, request_id: str, actor: str, decision: str,
                     confidence: float | None, threshold: float | None, reason: str,
                     model_version: str, payload_masked: str) -> None:
        self.conn.execute(
            "INSERT INTO audit(ts, request_id, actor, decision, confidence, threshold,"
            " reason, model_version, payload_masked) VALUES(?,?,?,?,?,?,?,?,?)",
            (time.time(), request_id, actor, decision, confidence, threshold,
             reason, model_version, payload_masked),
        )
        self.conn.commit()

    def decisions(self, request_id: str) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM audit WHERE request_id=? ORDER BY id", (request_id,))
        return [dict(r) for r in cur.fetchall()]

    def get_idempotent(self, key: str) -> dict | None:
        row = self.conn.execute("SELECT response FROM idempotency WHERE key=?", (key,)).fetchone()
        return json.loads(row["response"]) if row else None

    def put_idempotent(self, key: str, response: dict) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO idempotency(key, response, ts) VALUES(?,?,?)",
            (key, json.dumps(response, ensure_ascii=False), time.time()),
        )
        self.conn.commit()

    def enqueue_review(self, request_id: str, payload_masked: str, reason: str) -> str:
        review_id = uuid.uuid4().hex[:12]
        self.conn.execute(
            "INSERT INTO review(id, ts, request_id, payload_masked, reason, status)"
            " VALUES(?,?,?,?,?,'pending')",
            (review_id, time.time(), request_id, payload_masked, reason),
        )
        self.conn.commit()
        return review_id

    def pending_reviews(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM review WHERE status='pending' ORDER BY ts")
        return [dict(r) for r in cur.fetchall()]

    def resolve_review(self, review_id: str, verdict: str, reviewer: str, comment: str = "") -> dict | None:
        row = self.conn.execute("SELECT * FROM review WHERE id=?", (review_id,)).fetchone()
        if row is None or row["status"] != "pending":
            return None
        self.conn.execute(
            "UPDATE review SET status='resolved', verdict=?, reviewer=?, comment=? WHERE id=?",
            (verdict, reviewer, comment, review_id),
        )
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM review WHERE id=?", (review_id,)).fetchone())

    def put_task(self, task_id: str, request_id: str, status: str, result: dict | None = None) -> None:
        self.conn.execute(
            "INSERT INTO task(id, ts, request_id, status, result) VALUES(?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET status=excluded.status, result=excluded.result",
            (task_id, time.time(), request_id, status,
             json.dumps(result, ensure_ascii=False) if result is not None else None),
        )
        self.conn.commit()

    def get_task(self, task_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM task WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["result"] = json.loads(data["result"]) if data["result"] else None
        return data
