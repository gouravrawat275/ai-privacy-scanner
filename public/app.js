const root = document.getElementById("root");
const state = {
  accessToken: sessionStorage.getItem("accessToken") || "",
  refreshToken: sessionStorage.getItem("refreshToken") || "",
  username: sessionStorage.getItem("username") || "",
  page: "scanner",
  cameraStream: null,
  lastScanFile: null,
  lastScan: null,
};

const pages = {
  scanner: ["Multi-Aspect Scanner", "Evaluate identifiers, location clues, consent, and sharing risk."],
  camera: ["Live Viewfinder", "Evaluate a camera frame before capturing or sharing it."],
  consent: ["Consent Registry", "Manage per-person sharing permissions and registered face templates."],
  vault: ["Cryptographic Vault", "Obscure sensitive regions with reversible AES-256-GCM protection."],
  patterns: ["Pattern Intelligence", "Review privacy signals that emerge across multiple scans."],
  dashboard: ["Intelligence Dashboard", "Your scan activity and current privacy posture."],
  architecture: ["Architecture & Claims", "How the system evaluates and protects image privacy."],
};

const navItems = [
  ["scanner", "⌕", "Scanner"],
  ["camera", "◎", "Live Viewfinder"],
  ["consent", "♙", "Consent Registry"],
  ["vault", "▣", "Cryptographic Vault"],
  ["patterns", "⌁", "Pattern Intelligence"],
  ["dashboard", "▤", "Dashboard"],
  ["architecture", "◇", "Architecture & Claims"],
];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function showAuth(message = "") {
  stopCamera();
  root.innerHTML = `<main class="auth-shell">
    <section class="brand-panel">
      <div class="brand-mark">PS</div><p class="eyebrow">PRIVACY DEFENSE SYSTEM</p>
      <h1>See what your images reveal.</h1>
      <p>Scan, redact, and protect images with a multi-aspect privacy audit.</p>
      <div class="feature-list"><span>01 &nbsp; Identity &amp; sensitive text detection</span>
      <span>02 &nbsp; Location and routine risk analysis</span>
      <span>03 &nbsp; Consent-aware sharing controls</span>
      <span>04 &nbsp; Reversible encrypted redaction</span></div>
    </section>
    <section class="auth-panel"><div class="auth-card">
      <p class="eyebrow">WELCOME</p><h2 id="auth-title">Sign in to your workspace</h2>
      <div class="auth-tabs"><button class="auth-tab active" data-auth-tab="login">Log in</button>
      <button class="auth-tab" data-auth-tab="register">Create account</button></div>
      <div id="auth-error" class="notice error ${message ? "" : "hidden"}" role="alert">${escapeHtml(message)}</div>
      <form id="login-form" class="form-stack">
        <label>Email or username<input name="username" type="email" autocomplete="username" required></label>
        <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
        <button class="button primary" type="submit">Log in <span>→</span></button>
      </form>
      <form id="register-form" class="form-stack hidden">
        <div class="form-row"><label>First name<input name="first_name" autocomplete="given-name" required></label>
        <label>Last name<input name="last_name" autocomplete="family-name" required></label></div>
        <label>Email<input name="email" type="email" autocomplete="email" required></label>
        <label>Password<input name="password" type="password" autocomplete="new-password" minlength="8" required></label>
        <label>Confirm password<input name="password_confirm" type="password" autocomplete="new-password" minlength="8" required></label>
        <p class="field-hint">8–20 characters with upper/lowercase, a number, and a special character.</p>
        <button class="button primary" type="submit">Create account <span>→</span></button>
      </form>
    </div><p class="auth-footnote">Images are processed for analysis and are not retained in scan history.</p></section>
  </main>`;
  root.querySelectorAll("[data-auth-tab]").forEach((button) => button.addEventListener("click", () => {
    const register = button.dataset.authTab === "register";
    root.querySelectorAll(".auth-tab").forEach((tab) => tab.classList.toggle("active", tab === button));
    root.querySelector("#login-form").classList.toggle("hidden", register);
    root.querySelector("#register-form").classList.toggle("hidden", !register);
    root.querySelector("#auth-title").textContent = register ? "Create your secure account" : "Sign in to your workspace";
    root.querySelector("#auth-error").classList.add("hidden");
  }));
  root.querySelector("#login-form").addEventListener("submit", login);
  root.querySelector("#register-form").addEventListener("submit", register);
}

function saveSession(result, username) {
  state.accessToken = result.access_token;
  state.refreshToken = result.refresh_token || "";
  state.username = username;
  sessionStorage.setItem("accessToken", state.accessToken);
  sessionStorage.setItem("refreshToken", state.refreshToken);
  sessionStorage.setItem("username", username);
  renderApp();
}

async function login(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const body = new URLSearchParams({ username: form.get("username"), password: form.get("password") });
  try {
    saveSession(await request("/login", { method: "POST", body }), form.get("username"));
  } catch (error) {
    showAuth(error.message);
  }
}

async function register(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const body = {
    first_name: form.get("first_name"), last_name: form.get("last_name"),
    email: form.get("email"), password: form.get("password"),
    password_confirm: form.get("password_confirm"),
  };
  try {
    saveSession(await request("/register", { method: "POST", body: JSON.stringify(body) }), body.email);
  } catch (error) {
    showAuth(error.message);
  }
}

async function request(path, options = {}, authenticated = true, rawResponse = false) {
  const headers = new Headers(options.headers || {});
  if (authenticated && state.accessToken) headers.set("Authorization", `Bearer ${state.accessToken}`);
  if (options.body && !(options.body instanceof FormData) && !(options.body instanceof URLSearchParams)) {
    headers.set("Content-Type", "application/json");
  }
  let response = await fetch(path, { ...options, headers });
  if (response.status === 401 && authenticated && state.refreshToken && !options.didRefresh) {
    const refreshed = await fetch("/refresh", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
    if (refreshed.ok) {
      const result = await refreshed.json();
      state.accessToken = result.access_token;
      sessionStorage.setItem("accessToken", result.access_token);
      headers.set("Authorization", `Bearer ${result.access_token}`);
      response = await fetch(path, { ...options, headers, didRefresh: true });
    }
  }
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.clone().json();
      detail = payload.detail || payload.error || detail;
    } catch {}
    throw new Error(detail);
  }
  return rawResponse ? response : response.json();
}

function logout() {
  stopCamera();
  for (const key of ["accessToken", "refreshToken", "username"]) sessionStorage.removeItem(key);
  state.accessToken = "";
  state.refreshToken = "";
  state.username = "";
  showAuth();
}

function renderApp() {
  if (!state.accessToken) return showAuth();
  const current = pages[state.page];
  root.innerHTML = `<div class="app-shell">
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-brand"><div class="logo-mark">PS</div><div><strong>PRIVACY SCANNER</strong><small>DEFENSE CONSOLE · 2.5</small></div></div>
      <div class="nav-label">WORKSPACE</div><nav class="nav-list">${navItems.map(([id, icon, title]) =>
        `<button class="nav-item ${id === state.page ? "active" : ""}" data-page="${id}"><span class="nav-icon">${icon}</span>${title}</button>`).join("")}</nav>
      <div class="sidebar-bottom"><div class="operator">OPERATOR &nbsp; ${escapeHtml(state.username)}</div>
      <button class="button small" id="logout-button">Log out</button></div>
    </aside>
    <main class="main"><header class="topbar"><div style="display:flex;align-items:center">
      <button class="mobile-menu" id="mobile-menu" aria-label="Open navigation">☰</button>
      <div><h1>${escapeHtml(current[0])}</h1><p>${escapeHtml(current[1])}</p></div></div>
      <span class="pill good">● &nbsp; SHIELD ACTIVE</span></header>
      <section class="page" id="page-content"><p class="loading">Loading workspace…</p></section>
    </main></div><div id="toast" class="toast hidden" role="status"></div>`;
  root.querySelectorAll("[data-page]").forEach((button) => button.addEventListener("click", () => {
    if (state.page === "camera" && button.dataset.page !== "camera") stopCamera();
    state.page = button.dataset.page;
    renderApp();
  }));
  root.querySelector("#logout-button").addEventListener("click", logout);
  root.querySelector("#mobile-menu").addEventListener("click", () => root.querySelector("#sidebar").classList.toggle("open"));
  renderPage();
}

function toast(message) {
  const element = root.querySelector("#toast");
  if (!element) return;
  element.textContent = message;
  element.classList.remove("hidden");
  setTimeout(() => element.classList.add("hidden"), 3500);
}

function pageError(error) {
  const content = root.querySelector("#page-content");
  if (content) content.innerHTML = `<div class="notice error">${escapeHtml(error.message)}</div>`;
}

function statusNotice(message, style = "success") {
  return `<div class="notice ${style}">${escapeHtml(message)}</div>`;
}

function imageInput(name = "image", label = "Choose an image (JPG, PNG, BMP)") {
  return `<label>${label}<input type="file" name="${name}" accept="image/png,image/jpeg,image/bmp" required></label>`;
}

function scopeSelect(name = "target_scope") {
  return `<label>Intended sharing scope<select name="${name}">
    <option value="social_media">Social media</option><option value="public">Public</option>
    <option value="internal_only">Internal only</option><option value="commercial">Commercial</option>
    <option value="educational">Educational</option></select></label>`;
}

async function renderPage() {
  try {
    if (state.page === "scanner") return scannerPage();
    if (state.page === "camera") return cameraPage();
    if (state.page === "consent") return consentPage();
    if (state.page === "vault") return vaultPage();
    if (state.page === "patterns") return patternsPage();
    if (state.page === "dashboard") return dashboardPage();
    return architecturePage();
  } catch (error) {
    pageError(error);
  }
}

function scannerPage() {
  root.querySelector("#page-content").innerHTML = `<div class="page-grid">
    <article class="card span-5"><h2>Run a privacy audit</h2><p>Original pixels are analyzed in memory. Scan history retains summary metadata only.</p>
      <form id="scan-form" class="stack">${imageInput()}<div class="form-grid">${scopeSelect()}
        <label>Consent policy<select name="consent_policy"><option value="STRICT">Strict — unknown faces are gated</option><option value="ALLOW_UNKNOWN">Allow unknown bystanders</option></select></label></div>
        <button class="button primary" type="submit">Run holistic scan →</button></form>
      <div id="scan-status"></div></article>
    <article class="card span-7"><h2>Scan result</h2><div id="scan-result"><p class="muted">Upload an image and run a scan to see the risk evaluation.</p></div></article>
    <article class="card span-12"><h2>Safe export</h2><p>Generate an irreversible redacted JPEG from the last uploaded image. Scan first so detections can guide redaction.</p>
      <div class="toolbar"><label>Redaction style<select id="redact-method"><option value="auto">Adaptive blur</option><option value="blur">Blur</option><option value="pixelate">Pixelate</option><option value="solid">Solid tile</option></select></label>
      <label>Padding <input id="redact-padding" type="number" min="0" max="0.35" step="0.05" value="0.15"></label>
      <button class="button" id="redact-button" disabled>Download redacted image</button></div><div id="redact-status"></div></article>
  </div>`;
  root.querySelector("#scan-form").addEventListener("submit", scanImage);
  root.querySelector("#redact-button").addEventListener("click", redactImage);
}

async function scanImage(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const file = form.get("image");
  state.lastScanFile = file;
  const status = root.querySelector("#scan-status");
  status.innerHTML = `<p class="loading">Running detection, OCR, consent, location, and pattern analysis…</p>`;
  try {
    const result = await request("/scan", { method: "POST", body: form });
    state.lastScan = result;
    root.querySelector("#redact-button").disabled = false;
    renderScanResult(result, file);
    status.innerHTML = statusNotice("Scan complete. No image pixels are stored in scan history.");
  } catch (error) {
    status.innerHTML = statusNotice(error.message, "error");
  }
}

function renderScanResult(result, file) {
  const risk = result.risk || {};
  const detections = result.detections || {};
  const location = result.visual_location || {};
  const consent = result.consent || {};
  const score = Number(risk.score || 0);
  const levelClass = score > 75 ? "bad" : score > 40 ? "warn" : "good";
  const breakdown = (risk.breakdown || []).map((item) =>
    `<tr><td>${escapeHtml(item.category)}</td><td>${escapeHtml(item.detail)}</td><td>+${escapeHtml(item.points)}</td></tr>`).join("");
  const suggestions = (risk.suggestions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const alerts = [
    consent.can_share === false ? `Sharing gate: ${consent.overall_decision || "PROHIBITED"}` : "Consent gate: approved",
    location.has_visual_location_risk ? `Visual location risk (${Math.round((location.overall_confidence || 0) * 100)}% confidence)` : "No visual location risk flagged",
  ];
  const ocr = detections.ocr || {};
  const ocrStatus = ocr.error
    ? statusNotice(`OCR could not run in this deployment: ${ocr.error}`, "warning")
    : ocr.enabled === false
      ? statusNotice("OCR is disabled because no OCR engine is installed.", "warning")
      : "";
  root.querySelector("#scan-result").innerHTML = `<div class="metric-grid">
    <div class="metric"><span>OVERALL RISK</span><strong>${escapeHtml(score)}<small>/100</small></strong><em><span class="pill ${levelClass}">${escapeHtml(risk.level || "Unknown")}</span></em></div>
    <div class="metric"><span>FACES</span><strong>${(detections.faces || []).length}</strong><em>Identity detections</em></div>
    <div class="metric"><span>PLATES</span><strong>${(detections.plates || []).length}</strong><em>Vehicle identifiers</em></div>
    <div class="metric"><span>OCR FINDINGS</span><strong>${((detections.ocr || {}).findings || []).length}</strong><em>Sensitive text patterns</em></div>
    </div><div class="spacer"></div><div id="scan-alerts">${alerts.map((item) => statusNotice(item, item.startsWith("Sharing gate") || item.includes("location risk") ? "warning" : "success")).join("")}${ocrStatus}</div>
    <div class="page-grid"><div class="span-6"><h3>Image &amp; detections</h3><canvas id="scan-canvas" class="image-preview"></canvas></div>
      <div class="span-6"><h3>Risk breakdown</h3>${breakdown ? `<div class="table-wrap"><table><thead><tr><th>Category</th><th>Finding</th><th>Score</th></tr></thead><tbody>${breakdown}</tbody></table></div>` : `<p class="muted">No base privacy flags found.</p>`}
      <h3>Suggestions</h3>${suggestions ? `<ul>${suggestions}</ul>` : `<p class="muted">No additional remediation suggested.</p>`}</div></div>
      <details><summary>Full scan response</summary><pre class="output">${escapeHtml(JSON.stringify(result, null, 2))}</pre></details>`;
  drawDetectionOverlay(file, result);
}

function drawDetectionOverlay(file, result) {
  const canvas = root.querySelector("#scan-canvas");
  if (!canvas || !file) return;
  const image = new Image();
  image.onload = () => {
    const maxWidth = 900;
    const scale = Math.min(1, maxWidth / image.width);
    canvas.width = image.width * scale;
    canvas.height = image.height * scale;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    const boxes = [
      ...((result.detections || {}).faces || []).map((d) => ({ bbox: d.bbox, label: "Face", color: "#ff727c" })),
      ...((result.detections || {}).plates || []).map((d) => ({ bbox: d.bbox, label: "Plate", color: "#f4bd62" })),
    ];
    for (const { bbox, label, color } of boxes) {
      if (!bbox || bbox.length < 4) continue;
      const [x, y, width, height] = bbox.map(Number);
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(2, 3 * scale);
      ctx.strokeRect(x * scale, y * scale, width * scale, height * scale);
      ctx.fillStyle = color;
      ctx.font = `${Math.max(12, 14 * scale)}px sans-serif`;
      ctx.fillText(label, x * scale, Math.max(14, y * scale - 5));
    }
    URL.revokeObjectURL(image.src);
  };
  image.src = URL.createObjectURL(file);
}

async function redactImage() {
  if (!state.lastScanFile) return;
  const form = new FormData();
  form.append("file", state.lastScanFile);
  form.append("method", root.querySelector("#redact-method").value);
  form.append("padding", root.querySelector("#redact-padding").value);
  form.append("blur_faces", "true");
  form.append("blur_plates", "true");
  const status = root.querySelector("#redact-status");
  status.innerHTML = `<p class="loading">Creating redacted export…</p>`;
  try {
    const response = await request("/redact", { method: "POST", body: form }, true, true);
    const blob = await response.blob();
    downloadBlob(blob, `privacy-safe-${state.lastScanFile.name.replace(/\.[^.]+$/, "")}.jpg`);
    status.innerHTML = statusNotice("Safe export is ready. Check it carefully before sharing.");
  } catch (error) {
    status.innerHTML = statusNotice(error.message, "error");
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}

function cameraPage() {
  root.querySelector("#page-content").innerHTML = `<div class="page-grid">
    <article class="card span-7"><h2>Camera viewfinder</h2><p>Your camera stays in this browser. A frame is sent to the scanner only when you select Evaluate frame.</p>
      <video id="camera-video" class="video-preview" autoplay muted playsinline></video>
      <div class="toolbar"><button class="button" id="camera-start">Start camera</button><button class="button" id="camera-stop" disabled>Stop camera</button><button class="button primary" id="camera-evaluate" disabled>Evaluate frame</button></div>
      <div class="spacer"></div><label>Or upload a frame<input id="camera-upload" type="file" accept="image/png,image/jpeg,image/bmp"></label>
      <button class="button" id="camera-upload-evaluate">Evaluate uploaded frame</button><div id="camera-status"></div></article>
    <article class="card span-5"><h2>Pre-capture evaluation</h2><div id="camera-result"><p class="muted">Start your camera and evaluate a frame to view risk and consent alerts.</p></div></article>
  </div>`;
  root.querySelector("#camera-start").addEventListener("click", startCamera);
  root.querySelector("#camera-stop").addEventListener("click", stopCamera);
  root.querySelector("#camera-evaluate").addEventListener("click", () => evaluateCameraFrame(null));
  root.querySelector("#camera-upload-evaluate").addEventListener("click", () => {
    const file = root.querySelector("#camera-upload").files[0];
    if (file) evaluateCameraFrame(file);
    else root.querySelector("#camera-status").innerHTML = statusNotice("Choose a frame first.", "warning");
  });
}

async function startCamera() {
  try {
    state.cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    root.querySelector("#camera-video").srcObject = state.cameraStream;
    root.querySelector("#camera-stop").disabled = false;
    root.querySelector("#camera-evaluate").disabled = false;
    root.querySelector("#camera-status").innerHTML = statusNotice("Camera is ready. Evaluation is manual; frames are not sent automatically.");
  } catch (error) {
    const status = root.querySelector("#camera-status");
    if (status) status.innerHTML = statusNotice(`Could not start camera: ${error.message}`, "error");
  }
}

function stopCamera() {
  if (state.cameraStream) state.cameraStream.getTracks().forEach((track) => track.stop());
  state.cameraStream = null;
  const video = root.querySelector("#camera-video");
  if (video) video.srcObject = null;
}

async function evaluateCameraFrame(upload) {
  const form = new FormData();
  if (upload) form.append("frame", upload);
  else {
    const video = root.querySelector("#camera-video");
    if (!video || !video.videoWidth) {
      const status = root.querySelector("#camera-status");
      if (status) status.innerHTML = statusNotice("Start the camera before evaluating.", "warning");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", .88));
    form.append("frame", blob, "viewfinder.jpg");
  }
  const resultNode = root.querySelector("#camera-result");
  const status = root.querySelector("#camera-status");
  if (!resultNode || !status) return;
  status.innerHTML = `<p class="loading">Evaluating frame…</p>`;
  try {
    const result = await request("/pre-capture/evaluate", { method: "POST", body: form }, false);
    const alerts = (result.alerts || []).map((alert) => `<li>${escapeHtml(alert)}</li>`).join("");
    resultNode.innerHTML = `<div class="metric-grid"><div class="metric"><span>RISK</span><strong>${escapeHtml(result.risk_score)}/100</strong><em>${escapeHtml(result.risk_level)}</em></div>
      <div class="metric"><span>FACES</span><strong>${escapeHtml(result.faces_count)}</strong><em>in frame</em></div>
      <div class="metric"><span>PLATES</span><strong>${escapeHtml(result.plates_count)}</strong><em>in frame</em></div>
      <div class="metric"><span>SHARING</span><strong>${result.can_share ? "OK" : "GATED"}</strong><em>consent decision</em></div></div>
      <h3>Operator alerts</h3>${alerts ? `<ul>${alerts}</ul>` : `<p class="muted">No pre-capture alerts.</p>`}
      <details><summary>Detection details</summary><pre class="output">${escapeHtml(JSON.stringify(result, null, 2))}</pre></details>`;
    root.querySelector("#camera-status").innerHTML = statusNotice("Frame evaluation complete.");
  } catch (error) {
    const currentStatus = root.querySelector("#camera-status");
    if (currentStatus) currentStatus.innerHTML = statusNotice(error.message, "error");
  }
}

async function consentPage() {
  const content = root.querySelector("#page-content");
  content.innerHTML = `<div class="page-grid"><article class="card span-7"><div class="section-head"><h2>Registered individuals</h2><button id="refresh-subjects" class="button small">Refresh</button></div><div id="subjects-list"><p class="loading">Loading consent registry…</p></div></article>
    <article class="card span-5"><h2>Enroll a person</h2><form id="subject-form" class="stack">
      <label>Full name or alias<input name="name" required></label>
      <label>Consent status<select name="consent_status"><option>GRANTED</option><option>DENIED</option><option>RESTRICTED</option><option>REVOKED</option></select></label>
      <label>Allowed scopes (comma-separated)<input name="allowed_scopes" value="public,social_media,internal_only"></label>
      <label>Valid until<input name="valid_until" type="date"></label>
      <label>Notes<textarea name="notes" rows="3"></textarea></label>
      <label>Reference face image<input name="reference_face" type="file" accept="image/png,image/jpeg"></label>
      <button class="button primary">Register subject</button></form><div id="subject-status"></div></article>
    <article class="card span-12"><h2>Consent policy</h2><p>For each detected face, the registry checks enrolled templates and the selected sharing scope. DENIED, REVOKED, expired, or scope-mismatched faces are gated. Unknown faces follow the selected strict or allow-unknown policy in the scanner.</p>
      <div class="toolbar"><button class="button" id="seed-subjects">Add sample profiles</button></div></article></div>`;
  root.querySelector("#subject-form").addEventListener("submit", registerSubject);
  root.querySelector("#refresh-subjects").addEventListener("click", loadSubjects);
  root.querySelector("#seed-subjects").addEventListener("click", seedSubjects);
  await loadSubjects();
}

async function loadSubjects() {
  const node = root.querySelector("#subjects-list");
  if (!node) return;
  try {
    const subjects = await request("/consent/subjects", {}, false);
    node.innerHTML = subjects.length ? subjects.map((subject) => {
      const current = subject.consent_status;
      return `<div class="subject-card"><div><h3>${escapeHtml(subject.name)} <span class="pill ${current === "GRANTED" ? "good" : current === "DENIED" || current === "REVOKED" ? "bad" : "warn"}">${escapeHtml(current)}</span></h3>
        <p>Scopes: ${escapeHtml((subject.allowed_scopes || []).join(", ") || "None")}</p>
        <p>Templates: ${escapeHtml(subject.template_count || 0)} · Updated ${escapeHtml((subject.updated_at || "").slice(0, 10))}</p><p class="mono muted">ID ${escapeHtml(subject.subject_id)}${subject.notes ? ` · ${escapeHtml(subject.notes)}` : ""}</p></div>
        <div class="toolbar"><select data-subject-status="${escapeHtml(subject.subject_id)}">${["GRANTED", "DENIED", "RESTRICTED", "REVOKED", "EXPIRED"].map((s) => `<option ${s === current ? "selected" : ""}>${s}</option>`).join("")}</select>
        <button class="button small" data-update-subject="${escapeHtml(subject.subject_id)}">Update</button><button class="button small danger" data-delete-subject="${escapeHtml(subject.subject_id)}">Delete</button></div></div>`;
    }).join("") : `<p class="muted">No people are registered yet. Enroll a profile or add sample records.</p>`;
    node.querySelectorAll("[data-update-subject]").forEach((button) => button.addEventListener("click", () => updateSubject(button.dataset.updateSubject)));
    node.querySelectorAll("[data-delete-subject]").forEach((button) => button.addEventListener("click", () => deleteSubject(button.dataset.deleteSubject)));
  } catch (error) {
    node.innerHTML = statusNotice(error.message, "error");
  }
}

async function registerSubject(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const scopes = form.get("allowed_scopes") || "";
  form.set("allowed_scopes", scopes.split(",").map((part) => part.trim()).filter(Boolean).join(","));
  try {
    await request("/consent/register", { method: "POST", body: form }, false);
    event.currentTarget.reset();
    root.querySelector("#subject-status").innerHTML = statusNotice("Subject enrolled.");
    await loadSubjects();
  } catch (error) {
    root.querySelector("#subject-status").innerHTML = statusNotice(error.message, "error");
  }
}

async function updateSubject(id) {
  const select = root.querySelector(`[data-subject-status="${CSS.escape(id)}"]`);
  try {
    await request(`/consent/subjects/${encodeURIComponent(id)}`, {
      method: "PUT", body: JSON.stringify({ consent_status: select.value }),
    }, false);
    toast("Consent status updated.");
    await loadSubjects();
  } catch (error) {
    toast(error.message);
  }
}

async function deleteSubject(id) {
  if (!confirm("Delete this consent profile and its face templates?")) return;
  try {
    await request(`/consent/subjects/${encodeURIComponent(id)}`, { method: "DELETE" }, false);
    toast("Consent profile deleted.");
    await loadSubjects();
  } catch (error) {
    toast(error.message);
  }
}

async function seedSubjects() {
  const demos = [
    ["Alex Walker (Self)", "GRANTED", "public,social_media,internal_only,commercial", "Primary account operator portrait"],
    ["Dr. Sarah Chen (Colleague)", "GRANTED", "social_media,internal_only", "Signed conference photo release"],
    ["Marcus Vance (Bystander)", "DENIED", "internal_only", "Requested not to appear in public social posts"],
  ];
  try {
    for (const [name, consent_status, allowed_scopes, notes] of demos) {
      const form = new FormData();
      form.set("name", name); form.set("consent_status", consent_status);
      form.set("allowed_scopes", allowed_scopes); form.set("notes", notes);
      await request("/consent/register", { method: "POST", body: form }, false);
    }
    await loadSubjects();
    toast("Sample profiles added.");
  } catch (error) {
    toast(error.message);
  }
}

function vaultPage() {
  root.querySelector("#page-content").innerHTML = `<div class="page-grid">
    <article class="card span-6"><h2>Protect &amp; obscure</h2><p>Original sensitive pixels are sealed inside an authenticated AES-256-GCM envelope in the output PNG. Keep your passphrase safe.</p>
      <form id="crypto-lock-form" class="stack">${imageInput()}
        <label>Protection passphrase<input name="passphrase" type="password" minlength="8" required></label>
        <label>Obscuration style<select name="blur_style"><option value="pixelate">Adaptive pixelation</option><option value="blur">Heavy blur</option><option value="solid_tile">Solid tile</option><option value="blackout">Blackout</option></select></label>
        <label><span><input name="auto_detect_regions" type="checkbox" checked> Automatically detect faces and plates</span></label>
        <button class="button primary">Apply cryptographic lock</button></form><div id="crypto-lock-status"></div>
      <div id="crypto-lock-download"></div></article>
    <article class="card span-6"><h2>Restore original pixels</h2><p>Upload a PrivacyLock PNG carrying the encrypted envelope and use the matching passphrase or key.</p>
      <form id="crypto-restore-form" class="stack">${imageInput("file", "Locked PrivacyLock PNG (or obscured image)")}
        <label>Passphrase<input name="passphrase" type="password"></label><label>Raw 256-bit AES key (Base64), if used<input name="key_b64"></label>
        <label>Envelope JSON, if separate<textarea name="envelope_json" rows="4"></textarea></label>
        <button class="button primary">Decrypt &amp; restore</button></form><div id="crypto-restore-status"></div></article>
    </div>`;
  root.querySelector("#crypto-lock-form").addEventListener("submit", cryptoLock);
  root.querySelector("#crypto-restore-form").addEventListener("submit", cryptoRestore);
}

async function cryptoLock(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  if (!form.get("auto_detect_regions")) form.set("auto_detect_regions", "false");
  const status = root.querySelector("#crypto-lock-status");
  status.innerHTML = `<p class="loading">Encrypting protected pixels…</p>`;
  try {
    const response = await request("/crypto/obscure", { method: "POST", body: form }, true, true);
    const blob = await response.blob();
    const name = form.get("file").name.replace(/\.[^.]+$/, "");
    const filename = `privacylock_${name}.png`;
    const key = response.headers.get("X-Key-Base64");
    const envelopeHeader = response.headers.get("X-Encrypted-Regions");
    root.querySelector("#crypto-lock-download").innerHTML = `<p>Locked ${escapeHtml(envelopeHeader || 0)} sensitive region(s). Protected PNG is ready.</p>
      <button class="button primary" id="download-locked">Download PrivacyLock PNG</button>
      ${key ? `<div class="notice warning">Save your generated AES key now: <code>${escapeHtml(key)}</code></div>` : ""}`;
    root.querySelector("#download-locked").addEventListener("click", () => downloadBlob(blob, filename));
    status.innerHTML = statusNotice("Cryptographic protection complete.");
  } catch (error) {
    status.innerHTML = statusNotice(error.message, "error");
  }
}

async function cryptoRestore(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const status = root.querySelector("#crypto-restore-status");
  status.innerHTML = `<p class="loading">Decrypting protected image…</p>`;
  try {
    const response = await request("/crypto/restore", { method: "POST", body: form }, true, true);
    downloadBlob(await response.blob(), `restored-${form.get("file").name.replace(/\.[^.]+$/, "")}.png`);
    status.innerHTML = statusNotice("Original pixels restored. Download started.");
  } catch (error) {
    status.innerHTML = statusNotice(error.message, "error");
  }
}

async function patternsPage() {
  const content = root.querySelector("#page-content");
  content.innerHTML = `<div class="page-grid"><article class="card span-12"><div class="section-head"><h2>Cross-session pattern analysis</h2><button class="button small" id="patterns-refresh">Refresh</button></div><div id="patterns-analysis"><p class="loading">Loading pattern history…</p></div></article>
    <article class="card span-12"><h2>Privacy model</h2><p>Pattern analysis keeps only non-identifying scan metadata: coarse location buckets, broad time windows, scene categories, and object labels. Raw image pixels and OCR contents are not included.</p></article></div>`;
  root.querySelector("#patterns-refresh").addEventListener("click", loadPatterns);
  await loadPatterns();
}

async function loadPatterns() {
  const node = root.querySelector("#patterns-analysis");
  if (!node) return;
  try {
    const data = await request("/patterns");
    const analysis = data.analysis || {};
    const history = data.history_summary || [];
    const patterns = (analysis.patterns || []).map((item) => `<li><strong>${escapeHtml((item.severity || "medium").toUpperCase())}:</strong> ${escapeHtml(item.detail)}</li>`).join("");
    const rows = history.map((entry) => `<tr><td>${escapeHtml((entry.timestamp || "").slice(0, 19).replace("T", " "))}</td><td>${escapeHtml(entry.location_bucket || "Unknown")}</td><td>${escapeHtml(entry.risk_score || 0)}</td><td>${escapeHtml(entry.scene_labels || "—")}</td><td>${escapeHtml(entry.bg_object_labels || "—")}</td></tr>`).join("");
    node.innerHTML = `<div class="metric-grid"><div class="metric"><span>PATTERN RISK</span><strong>${escapeHtml(analysis.pattern_score || 0)}/100</strong><em>${escapeHtml(analysis.pattern_level || "None")}</em></div>
      <div class="metric"><span>SCANS IN WINDOW</span><strong>${escapeHtml(analysis.total_scans_in_window || 0)}</strong><em>rolling 30 days</em></div>
      <div class="metric"><span>CORRELATED PATTERNS</span><strong>${(analysis.patterns || []).length}</strong><em>recurrence signals</em></div>
      <div class="metric"><span>RISK POSTURE</span><strong>${Number(analysis.pattern_score || 0) > 25 ? "ELEVATED" : "HEALTHY"}</strong><em>privacy posture</em></div></div>
      <h3>Detected patterns</h3>${patterns ? `<ul>${patterns}</ul>` : `<p class="muted">No correlated patterns detected yet.</p>`}
      <h3>Recent non-identifying metadata (${history.length})</h3>${rows ? `<div class="table-wrap"><table><thead><tr><th>Timestamp</th><th>Coarse location</th><th>Risk</th><th>Scene cues</th><th>Objects</th></tr></thead><tbody>${rows}</tbody></table></div>` : `<p class="muted">No pattern records yet. Run a scan to begin.</p>`}`;
  } catch (error) {
    node.innerHTML = statusNotice(error.message, "error");
  }
}

async function dashboardPage() {
  const node = root.querySelector("#page-content");
  node.innerHTML = `<div class="page-grid"><article class="card span-12"><h2>Privacy posture</h2><div id="dashboard-content"><p class="loading">Loading your dashboard…</p></div></article>
    <article class="card span-12"><h2>Shield status</h2><div class="metric-grid">
      <div class="metric"><span>ASPECT A</span><strong>ACTIVE</strong><em>Pattern intelligence</em></div>
      <div class="metric"><span>ASPECT B</span><strong>ACTIVE</strong><em>Visual location inference</em></div>
      <div class="metric"><span>ASPECT C</span><strong>ACTIVE</strong><em>Consent gating</em></div>
      <div class="metric"><span>ASPECT D/E</span><strong>ACTIVE</strong><em>Crypto vault &amp; viewfinder</em></div></div></article></div>`;
  try {
    const [history, patterns, subjects] = await Promise.all([
      request("/history?limit=15"), request("/patterns"), request("/consent/subjects", {}, false),
    ]);
    const stats = history.stats || {};
    const rows = (history.recent || []).map((scan) => `<tr><td>${escapeHtml((scan.timestamp || "").slice(0, 19).replace("T", " "))}</td>
      <td>${escapeHtml(scan.filename || "")}</td><td>${escapeHtml(scan.risk_score ?? 0)}</td><td><span class="pill">${escapeHtml(scan.risk_level || "Unknown")}</span></td><td>${escapeHtml(scan.num_faces || 0)}</td></tr>`).join("");
    node.querySelector("#dashboard-content").innerHTML = `<div class="metric-grid">
      <div class="metric"><span>IMAGES SCANNED</span><strong>${escapeHtml(stats.total_scans || 0)}</strong><em>total scans</em></div>
      <div class="metric"><span>MEAN RISK</span><strong>${escapeHtml(stats.avg_risk_score || 0)}/100</strong><em>average score</em></div>
      <div class="metric"><span>PATTERN RISK</span><strong>${escapeHtml(patterns.analysis?.pattern_score || 0)}/100</strong><em>${escapeHtml(patterns.analysis?.pattern_level || "None")}</em></div>
      <div class="metric"><span>CONSENT PROFILES</span><strong>${subjects.length}</strong><em>enrolled subjects</em></div></div>
      <h3>Risk severity breakdown</h3><div class="toolbar">${Object.entries(stats.by_level || {}).map(([level, count]) => `<span class="pill">${escapeHtml(level)} · ${escapeHtml(count)}</span>`).join("") || `<span class="muted">No scan history to summarize.</span>`}</div>
      <h3>Recent image scans</h3>${rows ? `<div class="table-wrap"><table><thead><tr><th>Timestamp</th><th>Filename</th><th>Risk</th><th>Level</th><th>Faces</th></tr></thead><tbody>${rows}</tbody></table></div>` : `<p class="muted">No scans yet. Visit Scanner to evaluate an image.</p>`}`;
  } catch (error) {
    node.querySelector("#dashboard-content").innerHTML = statusNotice(error.message, "error");
  }
}

function architecturePage() {
  root.querySelector("#page-content").innerHTML = `<div class="page-grid">
    <article class="card span-12"><h2>Five privacy dimensions</h2><p>The scanner combines per-image risk scoring with cross-session context and consent decisions. It is designed to provide decision support, not guarantee that an image is safe to share.</p></article>
    <article class="card span-4"><h3>Aspect A · Pattern risk</h3><p>Analyzes repeated coarse locations, broad time-of-day buckets, scene types, and background objects across scans to identify routines that a single image cannot reveal.</p></article>
    <article class="card span-4"><h3>Aspect B · Visual location</h3><p>Uses text and scene cues in image pixels to surface location clues independently of EXIF/GPS metadata.</p></article>
    <article class="card span-4"><h3>Aspect C · Consent</h3><p>Compares detected faces against enrolled templates and checks sharing scope, validity, and consent status to gate unapproved sharing.</p></article>
    <article class="card span-6"><h3>Aspect D · Reversible redaction</h3><p>Obscures selected pixels and seals originals in an authenticated AES-256-GCM envelope. Protect keys and passphrases; losing them prevents restoration.</p></article>
    <article class="card span-6"><h3>Aspect E · Pre-capture viewfinder</h3><p>Evaluates frames on demand so an operator can adjust framing before saving or sharing a photo. Camera frames are not uploaded until the operator requests evaluation.</p></article>
    <article class="card span-12"><h2>Important limitations</h2><p>Detection and OCR can miss content or produce false positives. Always inspect both the original and redacted result. Facial matching is approximate and does not replace explicit consent. Do not use this system as the sole safeguard for high-risk decisions.</p></article>
  </div>`;
}

if (state.accessToken) renderApp();
else showAuth();
