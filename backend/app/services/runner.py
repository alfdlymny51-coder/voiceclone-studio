"""منفّذ المهام الخلفية (train / synth) بخيط بسيط — قابل للاستبدال بـ Celery/Redis."""
from __future__ import annotations

import json
import threading
from pathlib import Path

from ..audit import AuditLog
from ..db import DB
from ..engines import get_engine
from ..storage import EncryptedStorage


class JobRunner:
    def __init__(self, db: DB, storage: EncryptedStorage, audit: AuditLog,
                 engine_name: str, data_dir: Path) -> None:
        self._db = db
        self._storage = storage
        self._audit = audit
        self._engine = get_engine(engine_name)
        self._models_dir = data_dir / "models"
        self._models_dir.mkdir(parents=True, exist_ok=True)

    def submit(self, job_id: str) -> None:
        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()

    def _run(self, job_id: str) -> None:
        job = self._db.get_job(job_id)
        if not job:
            return
        self._db.update_job(job_id, "running")
        try:
            if job["kind"] == "train":
                self._run_train(job)
            elif job["kind"] == "synth":
                self._run_synth(job)
            else:
                raise ValueError(f"unknown job kind {job['kind']}")
        except Exception as exc:  # noqa: BLE001
            self._db.update_job(job_id, "failed", error=str(exc))
            self._audit.record("job_failed", job["project_id"], {"job": job_id, "error": str(exc)})

    def _run_train(self, job: dict) -> None:
        pid = job["project_id"]
        samples = self._db.list_samples(pid)
        if not samples:
            raise RuntimeError("لا توجد عيّنات صوتية للتدريب")
        blobs = [self._storage.load(s["storage_ref"]) for s in samples]
        model_dir = self._models_dir / pid
        emb = self._engine.train(blobs, model_dir)
        self._db.update_job(job["id"], "done", result=json.dumps(emb, ensure_ascii=False))
        self._db.set_project_status(pid, "ready")
        self._audit.record("model_trained", pid, {"samples": len(samples), "engine": self._engine.name})

    def _run_synth(self, job: dict) -> None:
        pid = job["project_id"]
        params = json.loads(job["params"])
        model_dir = self._models_dir / pid
        if not (model_dir / "speaker_model.json").exists() and not (model_dir / "refs.json").exists():
            # للمحرك mock نتدرّب تلقائياً إن لم يوجد نموذج
            samples = self._db.list_samples(pid)
            blobs = [self._storage.load(s["storage_ref"]) for s in samples]
            self._engine.train(blobs, model_dir)
        wav = self._engine.synthesize(
            text=params["text"],
            model_dir=model_dir,
            speed=float(params.get("speed", 1.0)),
            quality=str(params.get("quality", "high")),
        )
        ref = self._storage.save(wav, ".wav")
        out = self._db.add_output(job["id"], pid, ref, params["text"])
        self._db.update_job(job["id"], "done", result=json.dumps({"output_id": out["id"]}))
        self._audit.record("audio_synthesized", pid, {"job": job["id"], "chars": len(params["text"])})
