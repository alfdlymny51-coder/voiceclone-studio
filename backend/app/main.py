"""نقطة تشغيل التطبيق."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .deps import build_app
from .routers.api import router as api_router
from .services.runner import JobRunner

settings = get_settings()
app_state = build_app()
app_state.runner = JobRunner(app_state.db, app_state.storage, app_state.audit,
                             settings.tts_engine, settings.data_dir)

app = FastAPI(title="VoiceClone Studio", version="0.1.0",
              description="استنساخ صوتي بموافقة موثّقة وامتثال أخلاقي")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "engine": settings.tts_engine, "env": settings.env}


# تقديم الواجهة الأمامية مباشرة (وضع الحاوية الموحّدة)
_frontend = Path(__file__).resolve().parents[2] / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")
