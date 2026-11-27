# VoiceClone Studio 🎙️

تطبيق ويب لاستنساخ الصوت (Text-to-Speech voice cloning) بموافقة موثّقة وامتثال أخلاقي مدمج.

> ⚖️ **تنبيه**: لا يتيح النظام أي تدريب أو توليد قبل توثيق موافقة صاحب الصوت. راجع [docs/PRIVACY.md](docs/PRIVACY.md).

## المزايا

- 📝 **موافقة إلزامية** بإقرار ثلاثي + عبارة تحقق صوتية (liveness)
- 🔐 **تخزين مشفّر** (Fernet/AES) لجميع العيّنات والمخرجات
- 🧾 **سجل تدقيق** hash-chain غير قابل للتعديل مع تحقق آلي
- 🚨 **كشف إساءة**: حدود معدل + إنذارات تلقائية
- 🧠 **محركان**: `mock` للتطوير الفوري، و`xtts` (Coqui XTTS v2) للاستنساخ الحقيقي بالعربية
- 🐳 **Docker + Compose** (CPU وGPU)، **GitHub Actions**: اختبارات، نشر GHCR، GitHub Pages، ونشر ذاتي على GPU runner

## التشغيل السريع

### محلياً (بدون GPU)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
# افتح http://localhost:8000
```

### بالحاوية
```bash
cd deploy
VCS_STORAGE_KEY=$(python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())") \
  docker compose up --build
# الواجهة + API معاً على http://localhost:8000
```

### محرك XTTS الحقيقي (يتطلب GPU ≥ 8GB وNVIDIA Container Toolkit)
```bash
cd deploy
docker compose --profile gpu up --build gpu-worker
```

## هيكل المستودع

```
├── frontend/            # واجهة عربية RTL ثابتة (تُنشر على GitHub Pages)
├── backend/             # FastAPI: مشاريع، موافقات، عينات، تدريب، توليد، تدقيق
│   ├── app/engines/     # MockEngine + XTTSv2Engine
│   └── tests/           # اختبارات سير العمل الكامل
├── models/              # إعدادات النماذج + سكربتات preprocessing و fine-tuning
├── deploy/              # Dockerfiles (CPU/GPU) + docker-compose
├── docs/                # المعمارية + سياسة الخصوصية
└── .github/workflows/   # CI + GHCR + Pages + نشر self-hosted
```

## سير الاستخدام

1. أنشئ مشروعاً وحدّد اسم المتحدث
2. وثّق الموافقة (٣ إقرارات إلزامية)
3. ارفع ٣–١٠ عيّنات نظيفة أو سجّل من الميكروفون
4. درّب النموذج ثم ولّد الكلام مع التحكم بالسرعة والجودة
5. شغّل أو نزّل المخرجات — كل شيء مسجّل في سجل التدقيق

## النشر على GitHub

بعد رفع المستودع:
- **Pages**: فعّل Settings → Pages → GitHub Actions — يُنشر `frontend/` تلقائياً
- **GHCR**: كل push على `main` يبني الصورة وينشرها إلى `ghcr.io/<user>/voiceclone-studio`
- **GPU ذاتي**: سجّل runner ثم شغّل workflow «Deploy backend» يدوياً

## الترخيص

MIT — الاستخدام القانوني والأخلاقي مسؤولية المشغّل والمستخدم.
