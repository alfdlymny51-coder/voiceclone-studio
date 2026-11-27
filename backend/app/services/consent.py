"""منطق الموافقة: نص إقرار قياسي + تحقق صوتي اختياري بعبارة عشوائية."""
from __future__ import annotations

import random

CONSENT_STATEMENT = (
    "أنا {speaker_name}، أقرّ بأنني المالك الشرعي لهذا الصوت أو أنني حاصل على "
    "إذن خطّي صريح من صاحبه، وأوافق على استخدام عيّناتي الصوتية لتدريب نموذج "
    "تحويل النص إلى كلام ضمن هذا المشروع فقط، وأتحمّل كامل المسؤولية القانونية "
    "عن أي استخدام يخالف ذلك."
)

# عبارات تحقق صوتية عشوائية (liveness) — يقرؤها صاحب الصوت أثناء التسجيل
_LIVENESS_PHRASES = [
    "أوافق على استنساخ صوتي لهذا المشروع فقط",
    "أنا صاحب هذا الصوت وأمنح موافقتي الكاملة",
    "أسجّل هذه العبارة بمحض إرادتي اليوم",
    "أؤكد موافقتي على تدريب نموذج صوتي باسمي",
]


def random_liveness_phrase() -> str:
    return random.choice(_LIVENESS_PHRASES)


def consent_text(speaker_name: str) -> str:
    return CONSENT_STATEMENT.format(speaker_name=speaker_name)
