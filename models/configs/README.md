# إعدادات النموذج الافتراضية

## XTTS v2 (محرك الإنتاج)
```yaml
model: tts_models/multilingual/multi-dataset/xtts_v2
sample_rate: 24000
languages: [ar, en, fr, es, de, ...]   # 17 لغة
inference:
  temperature: 0.65
  top_p: 0.85
  speed_range: [0.5, 2.0]
reference_audio:
  min_seconds: 6
  recommended_seconds: 30
  max_files: 10
```

## SV2TTS (بديل)
```yaml
speaker_encoder: resemblyzer          # embedding dim: 256
synthesizer: tacotron2_modified
vocoder: hifigan_v1
sample_rate: 22050
```

## عتبات الجودة قبل اعتماد النموذج
- SECS (تشابه بصمة المتحدث) ≥ 0.75
- WER (whisper-large-v3 على المخرجات) ≤ 10%
- MOS بشري ≥ 4.0/5
