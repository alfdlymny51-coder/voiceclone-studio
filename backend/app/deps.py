"""حاوية الاعتماديات المشتركة."""
from __future__ import annotations

from dataclasses import dataclass

from .audit import AuditLog
from .config import get_settings
from .db import DB
from .services.abuse import AbuseGuard
from .storage import EncryptedStorage


@dataclass
class App:
    db: DB
    storage: EncryptedStorage
    audit: AuditLog
    abuse: AbuseGuard
    settings: object
    runner: object = None  # يُحقن في main بعد الإنشاء


_app: App | None = None


def build_app() -> App:
    global _app
    if _app is None:
        s = get_settings()
        db = DB(s.db_path)
        storage = EncryptedStorage(s.storage_dir, s.storage_key)
        audit = AuditLog(s.audit_path)
        abuse = AbuseGuard(audit, s.rate_limit_per_minute, s.abuse_alert_threshold)
        _app = App(db=db, storage=storage, audit=audit, abuse=abuse, settings=s)
    return _app


def get_app() -> App:
    return build_app()
