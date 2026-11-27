"""ما قبل معالجة العينات الصوتية للتدريب.

الاستخدام:
    python models/scripts/preprocess.py --input data/<speaker>/raw --output data/<speaker>/wavs

الخطوات: إعادة ترميز إلى 22.05kHz أحادي → إزالة الصمت (silero-vad) → تطبيع ‑23 LUFS → تقسيم 5-15 ث.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

TARGET_SR = 22050
TARGET_LUFS = -23


def normalize(src: Path, dst: Path) -> None:
    """ffmpeg: mono 22.05kHz + loudnorm إلى -23 LUFS."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-ac", "1", "-ar", str(TARGET_SR),
        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-2:LRA=11",
        str(dst),
    ], check=True, capture_output=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    files = sorted(p for p in args.input.rglob("*") if p.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a", ".webm", ".ogg"})
    for i, f in enumerate(files, 1):
        out = args.output / f"{i:04d}.wav"
        print(f"[{i}/{len(files)}] {f.name} -> {out.name}")
        normalize(f, out)
    print("تم. الخطوة التالية: إزالة الصمت والتقسيم — راجع docs/ARCHITECTURE.md")


if __name__ == "__main__":
    main()
