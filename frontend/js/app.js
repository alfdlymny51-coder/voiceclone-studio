/* VoiceClone Studio — منطق الواجهة الأمامية */
const $ = (s) => document.querySelector(s);

const apiBaseInput = $("#apiBase");
apiBaseInput.value = localStorage.getItem("vcs_api") || "";
apiBaseInput.addEventListener("change", () => {
  localStorage.setItem("vcs_api", apiBaseInput.value.trim());
  checkHealth(); loadProjects();
});

const api = (path, opts = {}) => {
  const base = apiBaseInput.value.trim().replace(/\/$/, "");
  return fetch(base + path, opts).then(async (r) => {
    if (!r.ok) {
      let msg = "خطأ " + r.status;
      try { msg = (await r.json()).detail || msg; } catch {}
      throw new Error(msg);
    }
    return r.status === 204 ? null : r.json();
  });
};

async function checkHealth() {
  try {
    const h = await api("/api/health");
    $("#health").textContent = "متصل · " + h.engine;
    $("#engineName").textContent = h.engine;
  } catch { $("#health").textContent = "غير متصل"; }
}

/* ---------- قائمة المشاريع ---------- */
const STATUS_AR = { awaiting_consent: "بانتظار الموافقة", collecting_samples: "جمع العيّنات", ready: "جاهز" };

async function loadProjects() {
  const { projects } = await api("/api/projects");
  $("#projectList").innerHTML = projects.map(p => `
    <div class="card" data-id="${p.id}">
      <h3>${esc(p.name)}</h3>
      <div class="meta">المتحدث: ${esc(p.speaker_name)} · ${p.samples} عيّنة</div>
      <span class="pill ${p.status}">${STATUS_AR[p.status] || p.status}</span>
    </div>`).join("") || `<p class="hint">لا مشاريع بعد — أنشئ مشروعك الأول.</p>`;
  document.querySelectorAll(".card").forEach(c =>
    c.addEventListener("click", () => openProject(c.dataset.id)));
}

$("#newProjectForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const p = await api("/api/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: $("#projName").value, speaker_name: $("#speakerName").value }),
    });
    $("#projName").value = $("#speakerName").value = "";
    openProject(p.id);
  } catch (err) { alert(err.message); }
});

/* ---------- تفاصيل المشروع ---------- */
let current = null;

async function openProject(pid) {
  const p = await api(`/api/projects/${pid}`);
  current = p;
  $("#projectsPanel").classList.add("hidden");
  $("#detailPanel").classList.remove("hidden");
  $("#detailTitle").textContent = `${p.name} — ${p.speaker_name}`;
  $("#statusLine").innerHTML = `<span class="pill ${p.status}">${STATUS_AR[p.status] || p.status}</span>`;

  const consented = p.consent && p.consent.verified;
  $("#consentDone").classList.toggle("hidden", !consented);
  $("#consentBtn").classList.toggle("hidden", !!consented);
  if (!consented) {
    const t = await api(`/api/projects/${pid}/consent/text`);
    $("#consentStatement").textContent = t.statement;
    $("#liveness").textContent = t.liveness_phrase;
  }
  $("#stepSamples").classList.toggle("disabled", !consented);
  $("#stepTrain").classList.toggle("disabled", !consented || p.samples.length === 0);
  $("#stepSynth").classList.toggle("disabled", p.status !== "ready");

  renderSamples(p.samples);
  renderOutputs(p.outputs);
}

$("#backBtn").addEventListener("click", () => {
  $("#detailPanel").classList.add("hidden");
  $("#projectsPanel").classList.remove("hidden");
  loadProjects();
});

/* الموافقة */
["c1", "c2", "c3"].forEach(id => $("#" + id).addEventListener("change", () => {
  $("#consentBtn").disabled = !($("#c1").checked && $("#c2").checked && $("#c3").checked);
}));
$("#consentBtn").addEventListener("click", async () => {
  try {
    await api(`/api/projects/${current.id}/consent`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agreed: $("#c2").checked,
        is_owner_or_authorized: $("#c1").checked,
        accepts_legal_liability: $("#c3").checked }),
    });
    openProject(current.id);
  } catch (err) { alert(err.message); }
});

/* العينات */
function renderSamples(samples) {
  $("#sampleList").innerHTML = samples.map(s => `
    <li>
      <audio controls src="${apiUrl()}/api/samples/${s.id}/audio"></audio>
      <span class="meta">#${s.id.slice(0, 6)}</span>
      <button class="btn ghost" data-del="${s.id}">حذف</button>
    </li>`).join("");
  document.querySelectorAll("[data-del]").forEach(b =>
    b.addEventListener("click", async () => {
      await api(`/api/samples/${b.dataset.del}`, { method: "DELETE" });
      openProject(current.id);
    }));
}

$("#uploadBtn").addEventListener("click", async () => {
  const f = $("#fileInput").files[0];
  if (!f) return alert("اختر ملفاً صوتياً أولاً");
  await uploadBlob(f, f.name);
});

async function uploadBlob(blob, name) {
  const fd = new FormData();
  fd.append("file", blob, name);
  try {
    await api(`/api/projects/${current.id}/samples`, { method: "POST", body: fd });
    openProject(current.id);
  } catch (err) { alert(err.message); }
}

/* تسجيل من الميكروفون */
let recorder = null;
$("#recordBtn").addEventListener("click", async () => {
  if (recorder && recorder.state === "recording") { recorder.stop(); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.ondataavailable = (e) => chunks.push(e.data);
    recorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      $("#recordBtn").classList.remove("rec");
      $("#recordBtn").textContent = "● تسجيل من الميكروفون";
      await uploadBlob(new Blob(chunks, { type: "audio/webm" }), "mic.webm");
    };
    recorder.start();
    $("#recordBtn").classList.add("rec");
    $("#recordBtn").textContent = "■ إيقاف التسجيل";
  } catch { alert("تعذّر الوصول للميكروفون"); }
});

/* التدريب */
$("#trainBtn").addEventListener("click", async () => {
  try {
    const job = await api(`/api/projects/${current.id}/train`, { method: "POST" });
    pollJob(job.id, $("#trainStatus"), () => openProject(current.id));
  } catch (err) { alert(err.message); }
});

/* التوليد */
$("#speed").addEventListener("input", () => $("#speedVal").textContent = (+$("#speed").value).toFixed(1) + "×");
$("#synthBtn").addEventListener("click", async () => {
  const text = $("#synthText").value.trim();
  if (!text) return alert("اكتب نصاً أولاً");
  try {
    const job = await api(`/api/projects/${current.id}/synthesize`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, speed: +$("#speed").value, quality: $("#quality").value }),
    });
    pollJob(job.id, $("#synthStatus"), () => openProject(current.id));
  } catch (err) { alert(err.message); }
});

function renderOutputs(outputs) {
  $("#outputList").innerHTML = outputs.map(o => `
    <div class="output-item">
      <span class="txt">${esc(o.text_preview || "")}</span>
      <audio controls src="${apiUrl()}/api/outputs/${o.id}/audio"></audio>
      <a class="btn" href="${apiUrl()}/api/outputs/${o.id}/audio" download>تنزيل</a>
    </div>`).join("");
}

async function pollJob(jid, el, done) {
  el.textContent = "⏳ جارٍ التنفيذ…";
  const t = setInterval(async () => {
    const j = await api(`/api/jobs/${jid}`);
    if (j.status === "done") { clearInterval(t); el.textContent = "✔ اكتمل"; done && done(); }
    else if (j.status === "failed") { clearInterval(t); el.textContent = "✖ فشل: " + (j.error || ""); }
  }, 800);
}

function apiUrl() { return apiBaseInput.value.trim().replace(/\/$/, ""); }
function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

checkHealth();
loadProjects();
