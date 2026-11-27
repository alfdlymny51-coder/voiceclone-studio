"""اختبارات سير العمل الكامل: موافقة → عينة → تدريب → توليد → تدقيق."""
import io
import os
import tempfile

os.environ["VCS_DATA_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _make_project():
    r = client.post("/api/projects", json={"name": "اختبار", "speaker_name": "أحمد"})
    assert r.status_code == 201
    return r.json()["id"]


def _consent(pid):
    r = client.post(f"/api/projects/{pid}/consent", json={
        "agreed": True, "is_owner_or_authorized": True, "accepts_legal_liability": True})
    assert r.status_code == 200


def _fake_wav(n=2048):
    return b"RIFF" + n.to_bytes(4, "little") + b"WAVEfmt " + bytes(n)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_full_flow():
    pid = _make_project()

    # الرفع قبل الموافقة مرفوض
    r = client.post(f"/api/projects/{pid}/samples",
                    files={"file": ("a.wav", io.BytesIO(_fake_wav()), "audio/wav")})
    assert r.status_code == 403

    _consent(pid)

    r = client.post(f"/api/projects/{pid}/samples",
                    files={"file": ("a.wav", io.BytesIO(_fake_wav()), "audio/wav")})
    assert r.status_code == 201

    r = client.post(f"/api/projects/{pid}/train")
    assert r.status_code == 202
    jid = r.json()["id"]
    import time
    for _ in range(50):
        job = client.get(f"/api/jobs/{jid}").json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "done", job.get("error")

    r = client.post(f"/api/projects/{pid}/synthesize",
                    json={"text": "مرحباً بالعالم", "speed": 1.0, "quality": "high"})
    assert r.status_code == 202
    jid = r.json()["id"]
    for _ in range(50):
        job = client.get(f"/api/jobs/{jid}").json()
        if job["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "done", job.get("error")
    import json
    oid = json.loads(job["result"])["output_id"]
    r = client.get(f"/api/outputs/{oid}/audio")
    assert r.status_code == 200 and r.content[:4] == b"RIFF"

    # سلسلة التدقيق سليمة
    assert client.get("/api/audit/verify").json()["chain_valid"] is True


def test_consent_required():
    pid = _make_project()
    r = client.post(f"/api/projects/{pid}/train")
    assert r.status_code == 403
