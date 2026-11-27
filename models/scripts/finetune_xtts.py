"""Fine-tuning لنموذج XTTS v2 على صوت متحدث محدد (يتطلب GPU >= 16GB).

الاستخدام:
    python models/scripts/finetune_xtts.py --data data/<speaker> --out models/checkpoints/<speaker>

البيانات المطلوبة داخل --data:
    wavs/*.wav + metadata.csv (filename|raw_text|normalized_text) + consent.json

ملاحظة: يجب التحقق من وجود consent.json صالح قبل أي تدريب — لا تتجاوز هذا الشرط.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def check_consent(data_dir: Path) -> None:
    consent = data_dir / "consent.json"
    if not consent.exists():
        sys.exit("❌ لا يوجد consent.json — التدريب دون موافقة موثّقة ممنوع.")
    payload = json.loads(consent.read_text(encoding="utf-8"))
    if not payload.get("verified"):
        sys.exit("❌ الموافقة غير موثّقة (verified=false).")
    print(f"✔ موافقة موثّقة للمتحدث: {payload.get('speaker', '؟')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--lr", type=float, default=5e-6)
    args = ap.parse_args()

    check_consent(args.data)

    # يتطلب: pip install TTS trainer
    # المرجع الكامل لإعدادات XTTS fine-tune:
    # https://github.com/coqui-ai/TTS — recipes/ljspeech/xtts_v2
    from trainer import Trainer, TrainerArgs  # type: ignore
    from TTS.config.shared_configs import BaseDatasetConfig  # type: ignore

    dataset = BaseDatasetConfig(
        formatter="coqui",
        meta_file_train="metadata.csv",
        path=str(args.data),
        language="ar",
    )
    trainer_args = TrainerArgs(
        restore_path=None,
        lr=args.lr,
    )
    print(f"بدء التدريب: data={args.data} out={args.out} epochs={args.epochs} lr={args.lr}")
    print("ملاحظة: أكمل إعداد GPTTrainer وفق recipe الرسمي — هذا القالب يفرض فحص الموافقة أولاً.")
    _ = (Trainer, trainer_args, dataset)  # placeholder wiring


if __name__ == "__main__":
    main()
