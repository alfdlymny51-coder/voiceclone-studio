"""طبقة تجريد محركات TTS/الاستنساخ الصوتي.

- MockEngine: يعمل فوراً بدون GPU — يولّد نغمة مركّبة لاختبار سير العمل كاملاً.
- XTTSv2Engine: محرك الإنتاج (Coqui TTS XTTS v2، استنساخ zero-shot متعدد اللغات
  يدعم العربية)، يتطلب GPU بذاكرة >= 8GB. يُحمَّل كسولاً عند أول استخدام.

للتدريب الكامل (fine-tuning) راجع docs/TRAINING.md وملفات models/scripts/.
"""
from __future__ import annotations

import math
import struct
import wave
from io import BytesIO
from pathlib import Path


def _sine_wav_bytes(freq: float, seconds: float, rate: int = 22050) -> bytes:
    n = int(rate * seconds)
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            # غلاف بسيط + توافقية ثانية لمحاكاة "نبرة" مميزة لكل متحدث
            env = min(1.0, i / (rate * 0.05), (n - i) / (rate * 0.1))
            v = env * (0.6 * math.sin(2 * math.pi * freq * i / rate)
                       + 0.25 * math.sin(2 * math.pi * freq * 2 * i / rate))
            frames += struct.pack("<h", int(v * 32767 * 0.7))
        w.writeframes(bytes(frames))
    return buf.getvalue()


class MockEngine:
    """محرك تطوير: 'بصمة' المتحدث = دالة ثابتة من العينات، والتوليد نغمة مشتقة منها."""

    name = "mock"

    def extract_speaker_embedding(self, sample_bytes_list: list[bytes]) -> dict:
        import hashlib
        h = hashlib.sha256(b"".join(sample_bytes_list)).digest()
        base_freq = 120 + h[0]  # 120-375 Hz بصمة صوتية وهمية
        return {"base_freq": float(base_freq), "fingerprint": h.hex()[:16]}

    def train(self, sample_bytes_list: list[bytes], workdir: Path) -> dict:
        emb = self.extract_speaker_embedding(sample_bytes_list)
        workdir.mkdir(parents=True, exist_ok=True)
        import json
        (workdir / "speaker_model.json").write_text(json.dumps(emb), encoding="utf-8")
        return emb

    def synthesize(self, text: str, model_dir: Path, speed: float = 1.0, quality: str = "high") -> bytes:
        import json
        emb = json.loads((model_dir / "speaker_model.json").read_text(encoding="utf-8"))
        seconds = max(0.6, min(12.0, len(text) * 0.07 / max(0.5, speed)))
        return _sine_wav_bytes(emb["base_freq"], seconds)


class XTTSv2Engine:
    """محرك الإنتاج — Coqui XTTS v2 (zero-shot voice cloning, 17 لغة منها العربية).

    يتطلب: pip install coqui-tts  + GPU >= 8GB VRAM (أو CPU بطيء: دقائق لكل جملة).
    الاستنساخ zero-shot: نبرة الصوت تُؤخذ مباشرة من العينات المرجعية المرفوعة.
    """

    name = "xtts"

    def __init__(self) -> None:
        self._tts = None

    def _load(self):
        if self._tts is None:
            import os
            os.environ.setdefault("COQUI_TOS_AGREED", "1")  # قبول ترخيص CPML غير تفاعلياً
            from TTS.api import TTS
            self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=False)
        return self._tts

    def train(self, sample_bytes_list: list[bytes], workdir: Path) -> dict:
        # XTTS zero-shot: لا تدريب فعلي — نحفظ العينات المرجعية كـ speaker WAVs.
        # للـ fine-tuning الحقيقي راجع models/scripts/finetune_xtts.py
        import json
        workdir.mkdir(parents=True, exist_ok=True)
        refs = []
        for i, b in enumerate(sample_bytes_list):
            p = workdir / f"ref_{i}.wav"
            p.write_bytes(b)
            refs.append(str(p))
        (workdir / "refs.json").write_text(json.dumps(refs), encoding="utf-8")
        return {"references": refs, "engine": self.name}

    def synthesize(self, text: str, model_dir: Path, speed: float = 1.0, quality: str = "high") -> bytes:
        import json
        refs = json.loads((model_dir / "refs.json").read_text(encoding="utf-8"))
        tts = self._load()
        out = BytesIO()
        wav = tts.tts(text=text, speaker_wav=refs[:3], language="ar", speed=speed)
        import numpy as np
        import soundfile as sf  # type: ignore
        sf.write(out, np.array(wav), 24000, format="WAV")
        return out.getvalue()


class PiperEngine:
    """محرك كلام عربي حقيقي خفيف (Piper TTS) — يعمل على CPU بدون GPU.

    ملاحظة أمانة: هذا المحرك ينطق النص بصوت عربي عام (ar_JO-kareem)،
    وليس بصوت صاحب العينات. الاستنساخ الحقيقي للنبرة يتطلب XTTSv2Engine على GPU.
    """

    name = "piper"
    _BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/ar/ar_JO/kareem/medium/"
    _MODEL = "ar_JO-kareem-medium.onnx"

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._dir = (cache_dir or Path("./data/models")) / "piper"
        self._voice = None

    def _load(self):
        if self._voice is None:
            import urllib.request
            from piper import PiperVoice
            self._dir.mkdir(parents=True, exist_ok=True)
            model = self._dir / self._MODEL
            cfg = self._dir / (self._MODEL + ".json")
            for p in (model, cfg):
                if not p.exists():
                    urllib.request.urlretrieve(self._BASE + p.name, p)
            self._voice = PiperVoice.load(str(model), config_path=str(cfg))
        return self._voice

    def train(self, sample_bytes_list: list[bytes], workdir: Path) -> dict:
        workdir.mkdir(parents=True, exist_ok=True)
        import json
        info = {"engine": self.name, "note": "صوت عربي عام — النبرة غير مستنسخة",
                "samples_received": len(sample_bytes_list)}
        (workdir / "speaker_model.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        return info

    def synthesize(self, text: str, model_dir: Path, speed: float = 1.0, quality: str = "high") -> bytes:
        voice = self._load()
        buf = BytesIO()
        kwargs = {}
        try:
            from piper import SynthesisConfig
            kwargs["syn_config"] = SynthesisConfig(length_scale=1.0 / max(0.5, min(2.0, speed)))
        except Exception:  # noqa: BLE001 — إصدار piper قد لا يدعم SynthesisConfig
            pass
        with wave.open(buf, "wb") as w:
            if hasattr(voice, "synthesize_wav"):
                voice.synthesize_wav(text, w, **kwargs)
            else:
                voice.synthesize(text, w)
        return buf.getvalue()


def get_engine(name: str, cache_dir: Path | None = None):
    if name == "xtts":
        return XTTSv2Engine()
    if name == "piper":
        return PiperEngine(cache_dir)
    return MockEngine()
