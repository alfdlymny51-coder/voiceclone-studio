"""كشف الاستخدام المسيء: حدود معدل، عدّادات رفض، إنذارات تُكتب في سجل التدقيق."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from ..audit import AuditLog


class AbuseGuard:
    def __init__(self, audit: AuditLog, per_minute: int = 20, alert_threshold: int = 5) -> None:
        self._audit = audit
        self._per_minute = per_minute
        self._alert_threshold = alert_threshold
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._violations: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def check_rate(self, actor: str) -> bool:
        now = time.time()
        with self._lock:
            dq = self._hits[actor]
            while dq and now - dq[0] > 60:
                dq.popleft()
            if len(dq) >= self._per_minute:
                self._flag(actor, "rate_limit_exceeded", {"per_minute": self._per_minute})
                return False
            dq.append(now)
            return True

    def _flag(self, actor: str, kind: str, detail: dict) -> None:
        self._violations[actor] += 1
        self._audit.record("abuse_flag", actor, {"kind": kind, **detail,
                                                 "count": self._violations[actor]})
        if self._violations[actor] >= self._alert_threshold:
            # إنذار استخدام مسيء — في الإنتاج يُربط ببريد/Webhook
            self._audit.record("abuse_alert", actor,
                               {"total_violations": self._violations[actor],
                                "action": "review_required"})
