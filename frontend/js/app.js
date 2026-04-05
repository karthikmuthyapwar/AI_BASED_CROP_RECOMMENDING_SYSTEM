const API_BASE = "http://localhost:8000";
let translations = {};
let currentLang = localStorage.getItem("lang") || "en";

const el = (id) => document.getElementById(id);

const languageVoiceMap = {
  en: "en-US",
  hi: "hi-IN",
  te: "te-IN",
};

const appState = {
  token: localStorage.getItem("token") || "",
  user: JSON.parse(localStorage.getItem("user") || "null"),
};

function setButtonLoading(buttonId, loadingText, isLoading) {
  const button = el(buttonId);
  if (!button) return;
  if (!button.dataset.defaultText) button.dataset.defaultText = button.textContent;
  button.disabled = isLoading;
  button.textContent = isLoading ? loadingText : button.dataset.defaultText;
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (appState.token) headers.Authorization = `Bearer ${appState.token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

async function loadLanguage(lang) {
  const res = await fetch(`./i18n/${lang}.json`);
  translations = await res.json();
  currentLang = lang;
  localStorage.setItem("lang", lang);

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.dataset.i18n;
    if (!translations[key]) return;

    if (node.tagName === "LABEL" && node.querySelector("input, select, textarea")) {
      const existingTextNode = Array.from(node.childNodes).find(
        (child) => child.nodeType === Node.TEXT_NODE
      );
      if (existingTextNode) {
        existingTextNode.textContent = `${translations[key]} `;
      } else {
        node.insertBefore(document.createTextNode(`${translations[key]} `), node.firstChild);
      }
      return;
    }

    node.textContent = translations[key];
  });
}

function speak(text) {
  if (!window.speechSynthesis || !text) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = languageVoiceMap[currentLang] || "en-US";
  speechSynthesis.cancel();
  speechSynthesis.speak(utterance);
}

function highlightAndSpeak(elementId, text) {
  const node = el(elementId);
  if (node) {
    node.classList.add("highlight");
    setTimeout(() => node.classList.remove("highlight"), 1800);
  }
  speak(text);
}

function persistForm() {
  const ids = ["N", "P", "K", "ph", "city", "duration", "latitude", "longitude"];
  const values = {};
  ids.forEach((id) => {
    if (el(id)) values[id] = el(id).value;
  });
  localStorage.setItem("form", JSON.stringify(values));
}

function clearPredictionForm() {
  ["N", "P", "K", "ph", "city", "duration", "latitude", "longitude"].forEach((id) => {
    if (el(id)) el(id).value = "";
  });
  localStorage.removeItem("form");
  localStorage.removeItem("last_result");
  el("resultBox").textContent = "";
  el("ocrStatus").textContent = "";
  el("locationStatus").textContent = "";
  renderClimateDetails({});
  refreshPredictButtonState();
}

function isLocationFilled() {
  const city = (el("city")?.value || "").trim();
  const lat = el("latitude")?.value;
  const lon = el("longitude")?.value;
  return Boolean(city) || (lat !== "" && lon !== "");
}

function isPredictFormValid() {
  const requiredIds = ["N", "P", "K", "ph", "duration"];
  return requiredIds.every((id) => {
    const value = el(id)?.value;
    return value !== undefined && value !== null && String(value).trim() !== "";
  }) && isLocationFilled();
}

function refreshPredictButtonState() {
  const predictBtn = el("predictAutoBtn");
  if (!predictBtn) return;
  predictBtn.disabled = !isPredictFormValid();
}

function restoreForm() {
  const saved = JSON.parse(localStorage.getItem("form") || "{}");
  Object.entries(saved).forEach(([key, value]) => {
    if (el(key)) el(key).value = value;
  });
  refreshPredictButtonState();
}

function showDashboard() {
  el("authSection").classList.add("hidden");
  el("dashboardSection").classList.remove("hidden");
  el("sidebar").classList.remove("hidden");
  el("historySection").classList.add("hidden");

  speak(translations.speak_logged_in || "You have logged in");
  highlightAndSpeak("soilImage", translations.speak_upload);
  highlightAndSpeak("duration", translations.speak_duration);
  highlightAndSpeak("city", translations.speak_location);
}

function showAuth() {
  el("authSection").classList.remove("hidden");
  el("dashboardSection").classList.add("hidden");
  el("sidebar").classList.add("hidden");
  el("historySection").classList.add("hidden");
}

function setSession(authData) {
  appState.token = authData.access_token;
  appState.user = authData.user;
  localStorage.setItem("token", appState.token);
  localStorage.setItem("user", JSON.stringify(appState.user));
}

async function login() {
  try {
    const data = await api("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: el("loginUsername").value,
        password: el("loginPassword").value,
      }),
    });
    setSession(data);
    if (data.user.default_language) {
      await loadLanguage(data.user.default_language);
      el("languageSelect").value = data.user.default_language;
    }
    if (!data.user.default_language) {
      el("languageSetup").classList.remove("hidden");
    } else {
      el("languageSetup").classList.add("hidden");
    }
    clearPredictionForm();
    showDashboard();
    await loadHistory();
  } catch (err) {
    el("authStatus").textContent = err.message;
  }
}

async function sendVerificationCode() {
  try {
    const data = await api("/auth/register-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: el("signupUsername").value,
        email: el("signupEmail").value,
        password: el("signupPassword").value,
      }),
    });
    if (data.verification_code) {
      el("verifyCode").value = data.verification_code;
      el("authStatus").textContent = `${data.message} Code auto-filled in Verification Code field.`;
    } else {
      el("authStatus").textContent = data.message;
    }
  } catch (err) {
    el("authStatus").textContent = err.message;
  }
}

async function verifyAccount() {
  try {
    const data = await api("/auth/verify-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: el("signupEmail").value, code: el("verifyCode").value }),
    });
    el("authStatus").textContent = `Account created for ${data.username}. Please login.`;
  } catch (err) {
    el("authStatus").textContent = err.message;
  }
}

async function saveDefaultLanguage() {
  try {
    await api("/auth/set-language", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: el("languageSelect").value }),
    });
    el("languageSetup").classList.add("hidden");
  } catch (err) {
    el("authStatus").textContent = err.message;
  }
}

function showResult(payload) {
  el("resultBox").textContent = JSON.stringify(payload, null, 2);
  localStorage.setItem("last_result", JSON.stringify(payload));
  renderClimateDetails(payload.weather_used);
  speak(translations.speak_result || "Top crop recommendations are ready");
}

function renderClimateDetails(weatherUsed = {}) {
  const avgTemperature = weatherUsed.avg_temperature;
  const avgHumidity = weatherUsed.avg_humidity;
  const totalRainfall = weatherUsed.total_rainfall;
  const note = weatherUsed.note || "";

  el("avgTemperature").value =
    avgTemperature !== undefined && avgTemperature !== null ? Number(avgTemperature).toFixed(2) : "N/A";
  el("avgHumidity").value =
    avgHumidity !== undefined && avgHumidity !== null ? Number(avgHumidity).toFixed(2) : "N/A";
  el("totalRainfall").value =
    totalRainfall !== undefined && totalRainfall !== null ? Number(totalRainfall).toFixed(2) : "N/A";
  el("weatherNote").value = note || "N/A";
}

async function uploadImage() {
  setButtonLoading("uploadBtn", "Extracting values from image...", true);
  el("ocrStatus").textContent = "Extracting values from image...";
  try {
    const file = el("soilImage").files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);

    const data = await api("/upload", {
      method: "POST",
      body: formData,
      headers: {},
    });

    ["N", "P", "K", "ph"].forEach((key) => {
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
      highlightAndSpeak("N", translations.speak_ocr_fail);
    }
    persistForm();
  } catch (err) {
    el("ocrStatus").textContent = err.message;
  } finally {
    setButtonLoading("uploadBtn", "Extracting values from image...", false);
  }
}

async function predictAuto() {
  setButtonLoading("predictAutoBtn", "Predicting final output... Please wait", true);
  el("resultBox").textContent = "Predicting final output... Please wait";
  try {
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

    const data = await api("/predict-auto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showResult(data);
    await loadHistory();
    persistForm();
  } catch (err) {
    el("resultBox").textContent = err.message;
  } finally {
    setButtonLoading("predictAutoBtn", "Predicting final output... Please wait", false);
  }
}

function useGps() {
  if (!navigator.geolocation) return;
  setButtonLoading("gpsBtn", "Getting location...", true);
  el("locationStatus").textContent = "Getting location...";
  navigator.geolocation.getCurrentPosition(async (pos) => {
    el("latitude").value = pos.coords.latitude;
    el("longitude").value = pos.coords.longitude;

    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}&format=jsonv2`
      );
      if (res.ok) {
        const data = await res.json();
        const address = data.address || {};
        const detectedCity =
          address.city || address.town || address.village || address.county || address.state;
        if (detectedCity) {
          el("city").value = detectedCity;
        } else {
          el("city").value = `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`;
        }
      } else {
        el("city").value = `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`;
      }
    } catch {
      el("city").value = `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`;
    }

    persistForm();
    refreshPredictButtonState();
    el("locationStatus").textContent = "Location detected successfully.";
    setButtonLoading("gpsBtn", "Getting location...", false);
  }, (error) => {
    el("locationStatus").textContent = `Unable to get location: ${error.message}`;
    setButtonLoading("gpsBtn", "Getting location...", false);
  });
}

async function loadHistory() {
  if (!appState.token) return;
  const data = await api("/recent-recommendations?limit=20");
  const historyList = el("historyList");
  historyList.innerHTML = "";
  data.items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = `${item.created_at} - ${item.top_predictions.map((p) => p.crop).join(", ")}`;
    historyList.appendChild(li);
  });
}

function showHistory() {
  el("historySection").classList.remove("hidden");
  el("dashboardSection").classList.add("hidden");
}

function logout() {
  appState.token = "";
  appState.user = null;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  showAuth();
}

el("languageSelect").addEventListener("change", async (e) => {
  await loadLanguage(e.target.value);
  if (appState.token) {
    await saveDefaultLanguage();
  }
});
el("showLogin").addEventListener("click", () => {
  el("loginForm").classList.remove("hidden");
  el("signupForm").classList.add("hidden");
});
el("showSignup").addEventListener("click", () => {
  el("signupForm").classList.remove("hidden");
  el("loginForm").classList.add("hidden");
});
el("loginBtn").addEventListener("click", login);
el("sendCodeBtn").addEventListener("click", sendVerificationCode);
el("verifyBtn").addEventListener("click", verifyAccount);
el("saveDefaultLanguage").addEventListener("click", saveDefaultLanguage);
el("uploadBtn").addEventListener("click", uploadImage);
el("predictAutoBtn").addEventListener("click", predictAuto);
el("gpsBtn").addEventListener("click", useGps);
el("menuDashboard").addEventListener("click", () => {
  el("historySection").classList.add("hidden");
  el("dashboardSection").classList.remove("hidden");
});
el("menuHistory").addEventListener("click", showHistory);
el("menuLogout").addEventListener("click", logout);

["N", "P", "K", "ph", "city", "duration"].forEach((id) => {
  el(id)?.addEventListener("input", () => {
    persistForm();
    refreshPredictButtonState();
  });
});

(async () => {
  await loadLanguage(currentLang);
  el("languageSelect").value = currentLang;
  restoreForm();
  renderClimateDetails({});
  const lastResult = localStorage.getItem("last_result");
  if (lastResult) {
    const parsedResult = JSON.parse(lastResult);
    el("resultBox").textContent = JSON.stringify(parsedResult, null, 2);
    renderClimateDetails(parsedResult.weather_used || {});
  }
  refreshPredictButtonState();

  if (appState.token) {
    try {
      const me = await api("/auth/me");
      appState.user = me;
      localStorage.setItem("user", JSON.stringify(me));
      if (me.default_language) {
        await loadLanguage(me.default_language);
        el("languageSelect").value = me.default_language;
      }
      showDashboard();
      await loadHistory();
    } catch {
      logout();
    }
  } else {
    showAuth();
  }
})();
