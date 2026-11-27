"""نقطة تشغيل موحّدة للنشر السحابي: تقرأ PORT من البيئة وتشغّل الخادم.

الاستخدام:  python run.py        (يستمع على $PORT أو 8000 افتراضياً)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

import uvicorn  # noqa: E402

# بيئة الاستضافة السحابية: المحرك الافتراضي piper (كلام عربي حقيقي على CPU).
# للتجاوز: VCS_TTS_ENGINE=mock|xtts python run.py
os.environ.setdefault("VCS_TTS_ENGINE", "piper")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")))
