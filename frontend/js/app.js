const API_BASE = "http://localhost:8000";
let translations = {};
let currentLang = "en";

const el = (id) => document.getElementById(id);

const languageVoiceMap = {
  en: "en-US",
  hi: "hi-IN",
  te: "te-IN",
};

async function loadLanguage(lang) {
  const res = await fetch(`./i18n/${lang}.json`);
  translations = await res.json();
  currentLang = lang;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    if (translations[key]) node.textContent = translations[key];
  });

  speak(translations.speak_enter_location || "Enter your location");
}

function speak(text) {
  if (!window.speechSynthesis || !text) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = languageVoiceMap[currentLang] || "en-US";
  speechSynthesis.cancel();
  speechSynthesis.speak(utterance);
}

function showResult(payload) {
  el("resultBox").textContent = JSON.stringify(payload, null, 2);
  speak(translations.speak_result || "Top crop recommendations are ready");
}

async function uploadImage() {
  const file = el("soilImage").files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });
  const data = await res.json();

  const fields = ["N", "P", "K", "ph"];
  fields.forEach((key) => {
    if (data.extracted_values?.[key] !== null && data.extracted_values?.[key] !== undefined) {
      el(key).value = data.extracted_values[key];
    }
  });

  if (data.confidence_level === "high") {
    el("ocrStatus").textContent = `✅ OCR confidence high (${data.confidence})`;
  } else if (data.confidence_level === "medium") {
    el("ocrStatus").textContent = `⚠️ OCR confidence medium (${data.confidence}). Please verify values.`;
  } else {
    el("ocrStatus").textContent = "❌ Unable to extract confidently. Enter values manually.";
  }
}

async function predictAuto() {
  const payload = {
    N: Number(el("N").value),
    P: Number(el("P").value),
    K: Number(el("K").value),
    ph: Number(el("ph").value),
    duration_days: Number(el("duration").value),
    city: el("city").value || null,
    latitude: el("latitude").value ? Number(el("latitude").value) : null,
    longitude: el("longitude").value ? Number(el("longitude").value) : null,
    top_k: 3,
  };

  const res = await fetch(`${API_BASE}/predict-auto`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  showResult(data);
}

function useGps() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition((pos) => {
    el("latitude").value = pos.coords.latitude;
    el("longitude").value = pos.coords.longitude;
    el("city").value = "";
  });
}

el("languageSelect").addEventListener("change", (e) => loadLanguage(e.target.value));
el("uploadBtn").addEventListener("click", uploadImage);
el("predictAutoBtn").addEventListener("click", predictAuto);
el("gpsBtn").addEventListener("click", useGps);

loadLanguage("en");
speak("Welcome to AI crop advisor");
