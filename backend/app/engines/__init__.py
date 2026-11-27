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

    يتطلب: pip install TTS  + GPU >= 8GB VRAM (أو CPU بطيء).
    """

    name = "xtts"

    def __init__(self) -> None:
        self._tts = None

    def _load(self):
        if self._tts is None:
            import torch  # noqa: F401
            from TTS.api import TTS
            self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        return self._tts

    def train(self, sample_bytes_list: list[bytes], workdir: Path) -> dict:
        # XTTS zero-shot: لا تدريب فعلي — نحفظ العينات المرجعية كـ speaker WAVs.
        # للـ fine-tuning الحقيقي راجع models/scripts/finetune_xtts.py
        workdir.mkdir(parents=True, exist_ok=True)
        refs = []
        for i, b in enumerate(sample_bytes_list):
            p = workdir / f"ref_{i}.wav"
            p.write_bytes(b)
            refs.append(str(p))
        return {"references": refs}

    def synthesize(self, text: str, model_dir: Path, speed: float = 1.0, quality: str = "high") -> bytes:
        import json
        refs = json.loads((model_dir / "refs.json").read_text(encoding="utf-8"))
        tts = self._load()
        out = BytesIO()
        wav = tts.tts(text=text, speaker_wav=refs, language="ar", speed=speed)
        import numpy as np
        import soundfile as sf  # type: ignore
        sf.write(out, np.array(wav), 24000, format="WAV")
        return out.getvalue()


def get_engine(name: str):
    if name == "xtts":
        return XTTSv2Engine()
    return MockEngine()
