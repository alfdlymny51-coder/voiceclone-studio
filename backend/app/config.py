"""إعدادات التطبيق عبر متغيرات البيئة (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VCS_", env_file=".env", extra="ignore")

    # بيئة التشغيل: dev | prod
    env: str = "dev"

    # مفتاح تشفير التخزين (Fernet). في الإنتاج يجب تمريره عبر سرّ (secret).
    # توليد: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    storage_key: str = ""

    # المسارات
    data_dir: Path = Path("./data")

    # المحرك: mock | xtts
    tts_engine: str = "mock"

    # حدود الاستخدام المسيء
    rate_limit_per_minute: int = 20
    max_samples_per_project: int = 50
    max_sample_seconds: int = 300
    max_synth_chars: int = 2000
    abuse_alert_threshold: int = 5  # محاولات مرفوضة قبل الإنذار

    # CORS — أصل الواجهة على GitHub Pages أو غيره
    cors_origins: str = ("http://localhost:8000,http://127.0.0.1:8000,"
                         "https://alfdlymny51-coder.github.io")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "voiceclone.db"

    @property
    def storage_dir(self) -> Path:
        return self.data_dir / "storage"

    @property
    def audit_path(self) -> Path:
        return self.data_dir / "audit.log"


@lru_cache
def get_settings() -> Settings:
    return Settings()
