"""تخزين مشفّر للعينات الصوتية باستخدام Fernet (AES-128-CBC + HMAC).

الملفات لا تُحفظ أبداً بنص صريح على القرص. المفتاح يأتي من VCS_STORAGE_KEY.
"""
from __future__ import annotations

import base64
import hashlib
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class EncryptedStorage:
    def __init__(self, storage_dir: Path, key: str) -> None:
        if not key:
            # وضع التطوير فقط: مفتاح مشتق من ثابت — يجب ضبط VCS_STORAGE_KEY في الإنتاج
            key = base64.urlsafe_b64encode(hashlib.sha256(b"vcs-dev-only-insecure").digest()).decode()
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, suffix: str = ".bin") -> str:
        name = f"{uuid.uuid4().hex}{suffix}.enc"
        (self._dir / name).write_bytes(self._fernet.encrypt(data))
        return name

    def load(self, name: str) -> bytes:
        # منع path traversal
        safe = Path(name).name
        if safe != name:
            raise ValueError("invalid storage name")
        try:
            return self._fernet.decrypt((self._dir / safe).read_bytes())
        except InvalidToken as exc:
            raise ValueError("cannot decrypt object (wrong key?)") from exc

    def delete(self, name: str) -> None:
        safe = Path(name).name
        target = self._dir / safe
        if target.exists():
            target.unlink()
