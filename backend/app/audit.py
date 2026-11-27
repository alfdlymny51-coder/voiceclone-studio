"""سجل تدقيق غير قابل للتعديل: كل سطر JSON مرتبط بسابقه عبر SHA-256 (hash chain)."""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    """Appends tamper-evident records; verification walks the chain."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._read_last_hash()

    def _read_last_hash(self) -> str:
        if not self._path.exists():
            return "0" * 64
        last = ""
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        if not last:
            return "0" * 64
        try:
            return json.loads(last)["hash"]
        except (json.JSONDecodeError, KeyError):
            return "0" * 64

    @staticmethod
    def _digest(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def record(self, event: str, actor: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "actor": actor,
            "detail": detail or {},
            "prev": self._last_hash,
        }
        entry["hash"] = self._digest(json.dumps(entry, sort_keys=True, ensure_ascii=False))
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._last_hash = entry["hash"]
        return entry

    def verify(self) -> bool:
        """يعيد فحص السلسلة كاملة؛ أي تعديل يكسرها."""
        prev = "0" * 64
        if not self._path.exists():
            return True
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                stored = entry.pop("hash")
                if entry["prev"] != prev:
                    return False
                if self._digest(json.dumps(entry, sort_keys=True, ensure_ascii=False)) != stored:
                    return False
                prev = stored
        return True
