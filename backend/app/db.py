"""قاعدة البيانات (SQLite) — مشاريع، عينات، موافقات، مهام."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    speaker_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'awaiting_consent',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    statement TEXT NOT NULL,
    consent_audio_ref TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    storage_ref TEXT NOT NULL,
    duration_sec REAL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    kind TEXT NOT NULL,               -- train | synth
    status TEXT NOT NULL DEFAULT 'queued',  -- queued|running|done|failed
    params TEXT NOT NULL DEFAULT '{}',
    result TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outputs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    project_id TEXT NOT NULL,
    storage_ref TEXT NOT NULL,
    text_preview TEXT,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return uuid.uuid4().hex


class DB:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def _q(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def _one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        rows = self._q(sql, params)
        return rows[0] if rows else None

    def _x(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    # ---- projects ----
    def create_project(self, name: str, speaker_name: str) -> dict[str, Any]:
        pid = _uid()
        self._x(
            "INSERT INTO projects(id,name,speaker_name,created_at) VALUES(?,?,?,?)",
            (pid, name, speaker_name, _now()),
        )
        return self.get_project(pid)  # type: ignore[return-value]

    def get_project(self, pid: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM projects WHERE id=?", (pid,))

    def list_projects(self) -> list[dict[str, Any]]:
        return self._q("SELECT * FROM projects ORDER BY created_at DESC")

    def set_project_status(self, pid: str, status: str) -> None:
        self._x("UPDATE projects SET status=? WHERE id=?", (status, pid))

    # ---- consent ----
    def create_consent(self, project_id: str, statement: str, audio_ref: str | None) -> dict[str, Any]:
        cid = _uid()
        self._x(
            "INSERT INTO consents(id,project_id,statement,consent_audio_ref,created_at) VALUES(?,?,?,?,?)",
            (cid, project_id, statement, audio_ref, _now()),
        )
        return self.get_consent(project_id)  # type: ignore[return-value]

    def get_consent(self, project_id: str) -> dict[str, Any] | None:
        return self._one(
            "SELECT * FROM consents WHERE project_id=? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        )

    def verify_consent(self, consent_id: str) -> None:
        self._x("UPDATE consents SET verified=1 WHERE id=?", (consent_id,))

    def has_valid_consent(self, project_id: str) -> bool:
        row = self.get_consent(project_id)
        return bool(row and row["verified"])

    # ---- samples ----
    def add_sample(self, project_id: str, storage_ref: str, duration_sec: float | None) -> dict[str, Any]:
        sid = _uid()
        self._x(
            "INSERT INTO samples(id,project_id,storage_ref,duration_sec,created_at) VALUES(?,?,?,?,?)",
            (sid, project_id, storage_ref, duration_sec, _now()),
        )
        return self._one("SELECT * FROM samples WHERE id=?", (sid,))  # type: ignore[return-value]

    def list_samples(self, project_id: str) -> list[dict[str, Any]]:
        return self._q("SELECT * FROM samples WHERE project_id=? ORDER BY created_at", (project_id,))

    def count_samples(self, project_id: str) -> int:
        row = self._one("SELECT COUNT(*) c FROM samples WHERE project_id=?", (project_id,))
        return int(row["c"]) if row else 0

    def delete_sample(self, sample_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM samples WHERE id=?", (sample_id,))
        if row:
            self._x("DELETE FROM samples WHERE id=?", (sample_id,))
        return row

    # ---- jobs ----
    def create_job(self, project_id: str, kind: str, params: dict[str, Any]) -> dict[str, Any]:
        jid = _uid()
        now = _now()
        self._x(
            "INSERT INTO jobs(id,project_id,kind,params,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (jid, project_id, kind, json.dumps(params, ensure_ascii=False), now, now),
        )
        return self.get_job(jid)  # type: ignore[return-value]

    def get_job(self, jid: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM jobs WHERE id=?", (jid,))

    def update_job(self, jid: str, status: str, result: str | None = None, error: str | None = None) -> None:
        self._x(
            "UPDATE jobs SET status=?, result=?, error=?, updated_at=? WHERE id=?",
            (status, result, error, _now(), jid),
        )

    def list_jobs(self, project_id: str) -> list[dict[str, Any]]:
        return self._q("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC", (project_id,))

    # ---- outputs ----
    def add_output(self, job_id: str, project_id: str, storage_ref: str, text_preview: str) -> dict[str, Any]:
        oid = _uid()
        self._x(
            "INSERT INTO outputs(id,job_id,project_id,storage_ref,text_preview,created_at) VALUES(?,?,?,?,?,?)",
            (oid, job_id, project_id, storage_ref, text_preview[:80], _now()),
        )
        return self._one("SELECT * FROM outputs WHERE id=?", (oid,))  # type: ignore[return-value]

    def list_outputs(self, project_id: str) -> list[dict[str, Any]]:
        return self._q("SELECT * FROM outputs WHERE project_id=? ORDER BY created_at DESC", (project_id,))

    def get_output(self, oid: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM outputs WHERE id=?", (oid,))
