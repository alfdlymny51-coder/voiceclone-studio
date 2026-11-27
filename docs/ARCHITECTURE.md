# معمارية التعلم الآلي — VoiceClone Studio

## نظرة عامة

يدعم المشروع مسارين:

| المسار | الوصف | متى تستخدمه |
|---|---|---|
| **Zero-shot cloning** | XTTS v2 (Coqui) — استنساخ فوري من ٦–٣٠ ثانية صوت مرجعي دون تدريب | الإنتاج السريع، دعم ١٧ لغة منها العربية |
| **Fine-tuning كامل** | تدريب مخصّص على بيانات المتحدث | أعلى جودة ومطابقة نبرة، بيانات ≥ 30 دقيقة |

## المعماريات المدروسة

### 1. SV2TTS (Real-Time Voice Cloning)
ثلاث مراحل متسلسلة:
1. **Speaker Encoder** (GE2E / Resemblyzer): يحوّل العيّنة إلى متجه embedding بُعده 256.
2. **Synthesizer** (Tacotron 2 معدّل): نص + embedding → مخطط Mel.
3. **Vocoder** (WaveRNN أو HiFi-GAN): Mel → موجة صوتية 22.05kHz.

- متطلبات: RTX 3060 (12GB) أو أعلى، ~50GB مساحة للبيانات الوسيطة.
- البيانات: 30–120 دقيقة صوت نظيف 22.05kHz أحادي، مع نصوص مطابقة (transcripts).

### 2. Glow-TTS / VITS + HiFi-GAN
- **Glow-TTS**: تدفق توليدي (normalizing flows) سريع التقارب، محاذاة نص-صوت داخلية (MAS).
- **VITS**: نهائي-إلى-نهائي (end-to-end) — جودة أعلى وزمن تدريب أطول.
- **HiFi-GAN**: vocoder قياسي لتحويل Mel إلى موجة عالية الدقة.
- متطلبات: GPU بذاكرة 16GB+ (V100/A100 مفضّل)، بيانات 1–5 ساعات للصوت الواحد.

### 3. XTTS v2 (المُعتمد كمحرك إنتاج افتراضي)
- استنساخ zero-shot متعدد اللغات، جودة ممتازة للعربية، يعمل على RTX 3080 (10GB).
- fine-tuning اختياري عبر `models/scripts/finetune_xtts.py`.

## خط سير التدريب (Pipeline)

```
عينات خام → preprocessing → speaker embedding → [zero-shot | fine-tune] → تقييم → نموذج نهائي
```

1. **ما قبل المعالجة** (`models/scripts/preprocess.py`):
   - إعادة الترميز إلى WAV 22.05kHz أحادي (`ffmpeg`)
   - إزالة الصمت (silero-vad VAD)
   - تطبيع الشدة إلى ‑23 LUFS
   - تقسيم إلى مقاطع 5–15 ثانية
   - تنقية النصوص (تطبيع الأرقام والتشكيل للعربية)
2. **استخراج بصمة المتحدث**: Resemblyzer أو الـ encoder الداخلي في XTTS.
3. **Fine-tuning**: معدل تعلم 5e-6، batch 4 مع gradient accumulation، 20–60 خطوة/دقيقة بيانات على A100.
4. **تقييم الجودة**:
   - موضوعي: MOS بشري (1–5)، خصوصاً naturalness + similarity
   - آلي: SECS (Speaker Encoder Cosine Similarity) ≥ 0.75، WER عبر ASR (whisper-large-v3)
5. **التصدير**: `models/configs/export.md` + حفظ checkpoint مع بطاقة نموذج (model card) تتضمن الموافقة.

## تنسيق البيانات

```
data/<speaker_id>/
  wavs/0001.wav ...           # 22.05kHz mono 16-bit
  metadata.csv                # filename|raw_text|normalized_text
  consent.json                # مرجع الموافقة الموثّقة (إلزامي)
```

## متطلبات GPU

| المهمة | الحد الأدنى | الموصى به |
|---|---|---|
| Inference (XTTS) | 8GB VRAM (RTX 3070) | 12GB+ |
| Fine-tune XTTS | 16GB | 24GB (RTX 4090/A5000) |
| تدريب VITS من الصفر | 24GB | A100 40GB |

## واجهات API

- REST: `/api/projects`, `/api/samples`, `/api/train`, `/api/synthesize` (موثّقة تلقائياً في `/docs`)
- التنفيذ الحالي بطلب/استطلاع (polling) لحالة المهمة. مسار ترقية: WebSocket `/ws/jobs/{id}` لبث التقدم لحظياً.
