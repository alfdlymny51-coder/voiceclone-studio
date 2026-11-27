"""اختبار محرك Piper (يتخطى تلقائياً إن لم يُثبَّت piper-tts)."""
import io
import wave

import pytest

piper = pytest.importorskip("piper")

from pathlib import Path  # noqa: E402

from app.engines import PiperEngine  # noqa: E402


def test_piper_real_arabic_speech(tmp_path: Path):
    eng = PiperEngine(cache_dir=tmp_path)
    info = eng.train([b"fake"], tmp_path / "model")
    assert info["engine"] == "piper"
    wav = eng.synthesize("مرحباً بالعالم", tmp_path / "model", speed=1.0)
    assert wav[:4] == b"RIFF"
    r = wave.open(io.BytesIO(wav))
    assert r.getframerate() == 22050
    assert r.getnframes() / r.getframerate() > 0.5  # كلام حقيقي وليس صمتاً
