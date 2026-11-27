"""المسارات (routers) — API كامل للمشاريع والموافقة والعينات والتوليد."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..deps import App, get_app
from ..services.consent import consent_text, random_liveness_phrase

router = APIRouter(prefix="/api")


def _actor(request: Request) -> str:
    return request.headers.get("x-user", request.client.host if request.client else "anon")


def _guard(request: Request, app: App) -> str:
    actor = _actor(request)
    if not app.abuse.check_rate(actor):
        raise HTTPException(429, "تم تجاوز حدّ الطلبات — أبطئ قليلاً")
    return actor


# ---------- النماذج ----------
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    speaker_name: str = Field(min_length=1, max_length=120)


class ConsentIn(BaseModel):
    agreed: bool
    is_owner_or_authorized: bool
    accepts_legal_liability: bool


class SynthIn(BaseModel):
    text: str = Field(min_length=1)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    quality: str = Field(default="high", pattern="^(draft|standard|high)$")


# ---------- مشاريع ----------
@router.get("/projects")
def list_projects(request: Request, app: App = Depends(get_app)):
    _guard(request, app)
    projects = app.db.list_projects()
    for p in projects:
        p["samples"] = app.db.count_samples(p["id"])
        p["consent_verified"] = app.db.has_valid_consent(p["id"])
    return {"projects": projects}


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, request: Request, app: App = Depends(get_app)):
    actor = _guard(request, app)
    p = app.db.create_project(body.name, body.speaker_name)
    app.audit.record("project_created", actor, {"project": p["id"], "speaker": body.speaker_name})
    return p


@router.get("/projects/{pid}")
def get_project(pid: str, request: Request, app: App = Depends(get_app)):
    _guard(request, app)
    p = app.db.get_project(pid)
    if not p:
        raise HTTPException(404, "المشروع غير موجود")
    p["samples"] = app.db.list_samples(pid)
    p["jobs"] = app.db.list_jobs(pid)
    p["outputs"] = app.db.list_outputs(pid)
    p["consent"] = app.db.get_consent(pid)
    return p


# ---------- الموافقة ----------
@router.get("/projects/{pid}/consent/text")
def get_consent_text(pid: str, request: Request, app: App = Depends(get_app)):
    _guard(request, app)
    p = app.db.get_project(pid)
    if not p:
        raise HTTPException(404, "المشروع غير موجود")
    return {"statement": consent_text(p["speaker_name"]),
            "liveness_phrase": random_liveness_phrase()}


@router.post("/projects/{pid}/consent")
def submit_consent(pid: str, body: ConsentIn, request: Request, app: App = Depends(get_app)):
    actor = _guard(request, app)
    p = app.db.get_project(pid)
    if not p:
        raise HTTPException(404, "المشروع غير موجود")
    if not (body.agreed and body.is_owner_or_authorized and body.accepts_legal_liability):
        app.abuse._flag(actor, "consent_rejected", {"project": pid})
        raise HTTPException(403, "لا يمكن المتابعة دون إقرار كامل بالموافقة والمسؤولية")
    c = app.db.create_consent(pid, consent_text(p["speaker_name"]), audio_ref=None)
    app.db.verify_consent(c["id"])
    app.db.set_project_status(pid, "collecting_samples")
    app.audit.record("consent_verified", actor, {"project": pid, "speaker": p["speaker_name"]})
    return {"verified": True}


# ---------- العينات ----------
@router.post("/projects/{pid}/samples", status_code=201)
async def upload_sample(pid: str, file: UploadFile, request: Request, app: App = Depends(get_app)):
    actor = _guard(request, app)
    p = app.db.get_project(pid)
    if not p:
        raise HTTPException(404, "المشروع غير موجود")
    if not app.db.has_valid_consent(pid):
        raise HTTPException(403, "يجب توثيق موافقة صاحب الصوت أولاً")
    if app.db.count_samples(pid) >= app.settings.max_samples_per_project:
        raise HTTPException(400, "بلغت الحد الأقصى للعينات")
    data = await file.read()
    if len(data) > app.settings.max_sample_seconds * 64000:  # تقدير تقريبي
        raise HTTPException(400, "حجم العينة يتجاوز الحد المسموح")
    ref = app.storage.save(data, ".wav")
    s = app.db.add_sample(pid, ref, duration_sec=None)
    app.audit.record("sample_uploaded", actor, {"project": pid, "bytes": len(data)})
    return s


@router.get("/samples/{sid}/audio")
def get_sample_audio(sid: str, request: Request, app: App = Depends(get_app)):
    _guard(request, app)
    rows = app.db._q("SELECT * FROM samples WHERE id=?", (sid,))
    if not rows:
        raise HTTPException(404, "العينة غير موجودة")
    data = app.storage.load(rows[0]["storage_ref"])
    return Response(content=data, media_type="audio/wav")


@router.delete("/samples/{sid}", status_code=204)
def delete_sample(sid: str, request: Request, app: App = Depends(get_app)):
    actor = _guard(request, app)
    row = app.db.delete_sample(sid)
    if not row:
        raise HTTPException(404, "العينة غير موجودة")
    app.storage.delete(row["storage_ref"])
    app.audit.record("sample_deleted", actor, {"sample": sid})
    return Response(status_code=204)


# ---------- التدريب والتوليد ----------
@router.post("/projects/{pid}/train", status_code=202)
def train(pid: str, request: Request, app: App = Depends(get_app)):
    actor = _guard(request, app)
    if not app.db.has_valid_consent(pid):
        raise HTTPException(403, "موافقة صاحب الصوت غير موثّقة")
    if app.db.count_samples(pid) < 1:
        raise HTTPException(400, "ارفع عيّنة واحدة على الأقل قبل التدريب")
    job = app.db.create_job(pid, "train", {})
    app.audit.record("train_requested", actor, {"project": pid})
    app.runner.submit(job["id"])
    return job


@router.post("/projects/{pid}/synthesize", status_code=202)
def synthesize(pid: str, body: SynthIn, request: Request, app: App = Depends(get_app)):
    actor = _guard(request, app)
    if not app.db.has_valid_consent(pid):
        raise HTTPException(403, "موافقة صاحب الصوت غير موثّقة")
    if len(body.text) > app.settings.max_synth_chars:
        raise HTTPException(400, f"النص يتجاوز {app.settings.max_synth_chars} حرفاً")
    job = app.db.create_job(pid, "synth", body.model_dump())
    app.audit.record("synth_requested", actor, {"project": pid, "chars": len(body.text)})
    app.runner.submit(job["id"])
    return job


@router.get("/jobs/{jid}")
def job_status(jid: str, request: Request, app: App = Depends(get_app)):
    _guard(request, app)
    job = app.db.get_job(jid)
    if not job:
        raise HTTPException(404, "المهمة غير موجودة")
    return job


# ---------- المخرجات ----------
@router.get("/outputs/{oid}/audio")
def output_audio(oid: str, request: Request, app: App = Depends(get_app)):
    _guard(request, app)
    out = app.db.get_output(oid)
    if not out:
        raise HTTPException(404, "المخرج غير موجود")
    data = app.storage.load(out["storage_ref"])
    return Response(content=data, media_type="audio/wav",
                    headers={"Content-Disposition": f'attachment; filename="vcs_{oid[:8]}.wav"'})


# ---------- تدقيق ----------
@router.get("/audit/verify")
def audit_verify(request: Request, app: App = Depends(get_app)):
    _guard(request, app)
    return {"chain_valid": app.audit.verify()}
