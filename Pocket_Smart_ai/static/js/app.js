const page = document.body.dataset.page || "home";
const view = document.querySelector("#view");
const tokenKey = "pocketsmart_token";
let currentUser = null;

const plannerDetails = {
  "home-planner": {
    eyebrow: "SPACE PLANNER / 01",
    title: "Make room for what matters.",
    copy: "Build a room-by-room starter plan around your budget, style, and priorities.",
    endpoint: "/api/generate-home",
    button: "Build my home plan"
  },
  "party-planner": {
    eyebrow: "EVENT PLANNER / 02",
    title: "Bring the gathering together.",
    copy: "Give every rupee a job, from the first guest to the last detail.",
    endpoint: "/api/generate-party",
    button: "Build my event plan"
  },
  "jewelry-planner": {
    eyebrow: "STYLE PLANNER / 03",
    title: "Find the finishing piece.",
    copy: "Shape an occasion-ready jewelry shortlist around your budget and taste.",
    endpoint: "/api/generate-jewelry",
    button: "Build my jewelry edit"
  }
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function money(value, currency = "INR") {
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(value);
  } catch {
    return `${currency} ${Number(value).toLocaleString("en-IN")}`;
  }
}

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem(tokenKey) || ""}` };
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Something went wrong. Please try again.");
  return body;
}

function setNotice(message, kind = "error") {
  const notice = document.querySelector("#notice");
  if (!notice) return;
  notice.textContent = message;
  notice.className = `notice ${kind}`;
  notice.hidden = false;
}

function setBusy(form, busy) {
  const button = form.querySelector("button[type=submit]");
  if (!button) return;
  button.disabled = busy;
  button.dataset.originalText ||= button.textContent;
  button.textContent = busy ? "Putting it together…" : button.dataset.originalText;
}

function renderHeader() {
  document.querySelector("#page-label").textContent = page.replaceAll("-", " ").toUpperCase();
  document.querySelectorAll("[data-nav]").forEach(link => {
    link.classList.toggle("active", link.dataset.nav === page || (page === "home" && link.dataset.nav === "dashboard"));
  });
  document.querySelector("#account-area").innerHTML = currentUser
    ? `<div class="account-user"><span class="avatar">${escapeHtml(currentUser.name?.slice(0, 1).toUpperCase() || "P")}</span><span class="account-name">${escapeHtml(currentUser.name)}</span><button class="text-button" id="logout-button" type="button">Sign out</button></div>`
    : `<a class="account-link" href="/login">Sign in <span aria-hidden="true">↗</span></a>`;
  document.querySelector("#topbar-action").innerHTML = currentUser
    ? `<span class="signed-in"><span class="status-dot"></span>Signed in</span>`
    : `<a class="quiet-link" href="/register">Create account <span aria-hidden="true">↗</span></a>`;
  document.querySelector("#logout-button")?.addEventListener("click", () => {
    localStorage.removeItem(tokenKey);
    window.location.assign("/");
  });
}

function renderHome() {
  view.innerHTML = `
    <section class="welcome-strip">
      <div><p class="eyebrow">YOUR MONEY, WITH A PLAN</p><h1>Make a little budget<br>go a long way.</h1><p class="intro">Thoughtful plans for the things you want to do, make, and celebrate.</p></div>
      <div class="welcome-art" aria-hidden="true"><div class="art-ring ring-one"></div><div class="art-ring ring-two"></div><div class="art-ticket"><span>PLAN NO.</span><strong>001</strong><i></i><small>MADE TO FIT</small></div><div class="art-star">✳</div></div>
    </section>
    <section class="section-heading"><div><p class="eyebrow">CHOOSE YOUR NEXT MOVE</p><h2>Start with a plan</h2></div><span class="mono-note">01 — 03</span></section>
    <div class="planner-grid">
      <a class="planner-card card-home" href="/home-planner"><span class="card-index">01 / SPACE</span><span class="card-symbol">⌂</span><h3>Set up your home</h3><p>Prioritize rooms, essentials, and the details that make it yours.</p><span class="card-link">Plan a space <b>↗</b></span></a>
      <a class="planner-card card-party" href="/party-planner"><span class="card-index">02 / GATHER</span><span class="card-symbol">✳</span><h3>Plan an event</h3><p>Balance food, venue, and atmosphere for your guest list.</p><span class="card-link">Plan a gathering <b>↗</b></span></a>
      <a class="planner-card card-style" href="/jewelry-planner"><span class="card-index">03 / STYLE</span><span class="card-symbol">◇</span><h3>Build a jewelry edit</h3><p>Find occasion pieces that work with your look and your budget.</p><span class="card-link">Explore jewelry <b>↗</b></span></a>
    </div>
    <section class="bottom-note"><span class="note-marker">i</span><p>Recommendations are estimates for planning. Check final prices and availability with each seller.</p><a href="/history">View past plans <span aria-hidden="true">→</span></a></section>`;
}

function renderAuth(mode) {
  const registering = mode === "register";
  view.innerHTML = `<section class="auth-layout"><div class="auth-copy"><p class="eyebrow">${registering ? "A BETTER WAY TO BEGIN" : "WELCOME BACK"}</p><h1>${registering ? "Make the plan yours." : "Pick up where you left off."}</h1><p>${registering ? "Create an account to save your plans and come back to them whenever you need." : "Sign in to revisit your saved plans and keep moving."}</p><div class="auth-stamp"><span>PS</span><small>THOUGHTFUL BY DESIGN</small></div></div><form class="form-panel auth-form" id="auth-form"><p class="eyebrow">${registering ? "CREATE ACCOUNT" : "SIGN IN"}</p><h2>${registering ? "Your workspace starts here." : "Good to see you."}</h2>${registering ? `<label>Your name<input name="name" autocomplete="name" minlength="2" maxlength="80" required placeholder="A name to call you"></label>` : ""}<label>Email address<input name="email" type="email" autocomplete="email" required placeholder="you@example.com"></label><label>Password<input name="password" type="password" autocomplete="${registering ? "new-password" : "current-password"}" minlength="${registering ? "8" : "1"}" required placeholder="${registering ? "At least 8 characters" : "Your password"}"></label><div id="notice" class="notice" hidden></div><button class="button button-dark full-button" type="submit">${registering ? "Create account" : "Sign in"}<span aria-hidden="true">↗</span></button><p class="form-switch">${registering ? `Already have an account? <a href="/login">Sign in</a>` : `New to PocketSmart? <a href="/register">Create an account</a>`}</p></form></section>`;
  document.querySelector("#auth-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    setBusy(form, true);
    try {
      const values = Object.fromEntries(new FormData(form).entries());
      const data = await requestJson(`/api/auth/${registering ? "register" : "login"}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values)
      });
      localStorage.setItem(tokenKey, data.access_token);
      window.location.assign("/dashboard");
    } catch (error) {
      setNotice(error.message);
      setBusy(form, false);
    }
  });
}

function formInput(label, name, options = {}) {
  const { type = "text", required = false, placeholder = "", min = "", max = "", value = "" } = options;
  return `<label>${label}<input name="${name}" type="${type}" ${required ? "required" : ""} ${min ? `min="${min}"` : ""} ${max ? `max="${max}"` : ""} placeholder="${placeholder}" value="${value}"></label>`;
}

function plannerForm(planner) {
  if (planner === "home-planner") return `<div class="field-row">${formInput("Total budget", "budget", { type: "number", min: "1", required: true, placeholder: "e.g. 80000" })}<label>Currency<select name="currency"><option value="INR">INR · ₹</option><option value="USD">USD · $</option><option value="EUR">EUR · €</option><option value="GBP">GBP · £</option></select></label></div><label>Rooms to plan<select name="rooms" multiple size="4" required><option value="Living room">Living room</option><option value="Bedroom">Bedroom</option><option value="Kitchen">Kitchen</option><option value="Dining area">Dining area</option><option value="Study">Study</option><option value="Balcony">Balcony</option></select><small class="field-help">Use Ctrl or Command to choose more than one.</small></label>${formInput("Preferred style", "style", { placeholder: "e.g. modern, warm, minimal", value: "modern" })}<label>Notes<textarea name="notes" rows="3" placeholder="Must-haves, dimensions, or things you already own"></textarea></label>`;
  if (planner === "party-planner") return `<div class="field-row">${formInput("Total budget", "budget", { type: "number", min: "1", required: true, placeholder: "e.g. 50000" })}<label>Currency<select name="currency"><option value="INR">INR · ₹</option><option value="USD">USD · $</option><option value="EUR">EUR · €</option><option value="GBP">GBP · £</option></select></label></div><div class="field-row">${formInput("Number of guests", "guests", { type: "number", min: "1", required: true, placeholder: "e.g. 30" })}${formInput("Occasion", "event_type", { required: true, placeholder: "Birthday, dinner, wedding…" })}</div><div class="field-row">${formInput("Venue", "venue", { placeholder: "Home, outdoors, undecided…", value: "Not decided" })}${formInput("City", "city", { placeholder: "Where are you hosting?" })}</div><label>Preferences<textarea name="preferences" rows="3" placeholder="Food, accessibility, theme, or other details"></textarea></label>`;
  return `<div class="field-row">${formInput("Total budget", "budget", { type: "number", min: "1", required: true, placeholder: "e.g. 15000" })}<label>Currency<select name="currency"><option value="INR">INR · ₹</option><option value="USD">USD · $</option><option value="EUR">EUR · €</option><option value="GBP">GBP · £</option></select></label></div><div class="field-row">${formInput("Occasion", "occasion", { required: true, placeholder: "Wedding, festive, everyday…" })}${formInput("Style", "style", { placeholder: "e.g. classic, minimal", value: "elegant" })}</div>${formInput("Preferred metal", "metal", { placeholder: "Gold, silver, any…", value: "any" })}<label>Outfit notes<textarea name="outfit_description" rows="3" placeholder="Colors, pattern, formality, or styling notes"></textarea></label><label class="upload-field">Optional outfit image<input name="outfit_image" type="file" accept="image/jpeg,image/png,image/webp"><small class="field-help">JPG, PNG, or WEBP. Maximum 5 MB.</small></label>`;
}

function renderPlanner(planner) {
  const details = plannerDetails[planner];
  if (!currentUser) {
    view.innerHTML = `<section class="gate-panel"><p class="eyebrow">SAVE YOUR WORK</p><h1>Sign in to build a plan.</h1><p>Your planning results are saved to your account so you can find them again.</p><a class="button button-dark" href="/login">Sign in <span aria-hidden="true">↗</span></a><a class="under-link" href="/register">Create an account</a></section>`;
    return;
  }
  view.innerHTML = `<section class="planner-heading"><p class="eyebrow">${details.eyebrow}</p><h1>${details.title}</h1><p class="intro">${details.copy}</p></section><div class="planner-layout"><form id="planner-form" class="form-panel planner-form" ${planner === "jewelry-planner" ? `enctype="multipart/form-data"` : ""}><div class="form-heading"><div><p class="eyebrow">YOUR DETAILS</p><h2>Set your priorities</h2></div><span class="step-count">01 <i>/</i> 01</span></div>${plannerForm(planner)}<div id="notice" class="notice" hidden></div><button class="button button-dark full-button" type="submit">${details.button}<span aria-hidden="true">↗</span></button></form><aside class="planner-aside"><p class="eyebrow">A QUICK NOTE</p><h3>Good planning leaves room to adjust.</h3><p>Use this as a starting point. Compare final prices and availability before you commit.</p><div class="aside-rule"></div><span class="aside-number">${planner === "home-planner" ? "40" : planner === "party-planner" ? "45" : "55"}<small>%</small></span><span class="aside-caption">of a sample budget starts with the main priority</span></aside></div><section id="result" class="result-area" aria-live="polite"></section>`;
  document.querySelector("#planner-form").addEventListener("submit", submitPlanner);
}

function resultMarkup(result) {
  const allocations = Object.entries(result.allocations || {}).map(([name, amount]) => `<div class="allocation-line"><span>${escapeHtml(name.replaceAll("_", " "))}</span><strong>${money(amount, result.currency)}</strong></div>`).join("");
  const recommendations = (result.recommendations || []).map(item => {
    const url = /^https?:\/\//i.test(item.search_url || "") ? item.search_url : "#";
    return `<article class="recommendation"><div class="recommendation-top"><span class="eyebrow">${escapeHtml(item.category)}</span><span class="price">${money(item.estimated_price, item.currency || result.currency)}</span></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.reason)}</p><a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Search ${escapeHtml(item.platform)} <span aria-hidden="true">↗</span></a></article>`;
  }).join("");
  const tips = (result.tips || []).map(tip => `<li>${escapeHtml(tip)}</li>`).join("");
  return `<div class="result-heading"><div><p class="eyebrow">YOUR STARTER PLAN</p><h2>${escapeHtml(result.summary || "Your plan is ready")}</h2></div><span class="source-tag">${escapeHtml((result.source_mode || "planning estimate").replaceAll("-", " "))}</span></div><div class="result-columns"><section class="allocation-panel"><h3>Budget split</h3>${allocations}</section><section class="recommendations-panel"><h3>Ideas to explore</h3><div class="recommendation-grid">${recommendations || "<p>No recommendations returned.</p>"}</div></section></div>${tips ? `<div class="tips-row"><strong>Keep in mind</strong><ul>${tips}</ul></div>` : ""}`;
}

async function submitPlanner(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const resultArea = document.querySelector("#result");
  setBusy(form, true);
  resultArea.innerHTML = `<div class="loading-line"><span class="loading-dot"></span>Working on your plan…</div>`;
  try {
    let options;
    if (page === "jewelry-planner") {
      const data = new FormData(form);
      const image = data.get("outfit_image");
      if (!image?.size) data.delete("outfit_image");
      options = { method: "POST", headers: authHeaders(), body: data };
    } else {
      const values = Object.fromEntries(new FormData(form).entries());
      if (page === "home-planner") values.rooms = new FormData(form).getAll("rooms");
      if (page === "home-planner") values.budget = Number(values.budget);
      if (page === "party-planner") {
        values.budget = Number(values.budget);
        values.guests = Number(values.guests);
      }
      options = { method: "POST", headers: { ...authHeaders(), "Content-Type": "application/json" }, body: JSON.stringify(values) };
    }
    const result = await requestJson(plannerDetails[page].endpoint, options);
    resultArea.innerHTML = resultMarkup(result);
    resultArea.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    resultArea.innerHTML = "";
    setNotice(error.message);
  } finally {
    setBusy(form, false);
  }
}

async function renderHistory() {
  if (!currentUser) {
    view.innerHTML = `<section class="gate-panel"><p class="eyebrow">YOUR PLANS, TOGETHER</p><h1>Sign in to see your history.</h1><p>Saved plans stay linked to your account.</p><a class="button button-dark" href="/login">Sign in <span aria-hidden="true">↗</span></a></section>`;
    return;
  }
  view.innerHTML = `<section class="planner-heading"><p class="eyebrow">YOUR WORKSPACE / ARCHIVE</p><h1>Plans worth keeping.</h1><p class="intro">A record of the ideas you’ve already started.</p></section><div id="history-list" class="history-list"><div class="loading-line"><span class="loading-dot"></span>Loading your plans…</div></div>`;
  try {
    const { items } = await requestJson("/api/history", { headers: authHeaders() });
    const list = document.querySelector("#history-list");
    if (!items.length) {
      list.innerHTML = `<div class="empty-state"><span class="empty-mark">◷</span><h2>No saved plans yet.</h2><p>Your next plan will show up here.</p><a href="/dashboard">Explore planners <span aria-hidden="true">↗</span></a></div>`;
      return;
    }
    list.innerHTML = items.map(item => {
      let result = {};
      try { result = JSON.parse(item.result_json); } catch {}
      const label = ({ home: "Home setup", party: "Event plan", jewelry: "Jewelry edit" })[item.planner] || item.planner;
      const date = new Date(`${item.created_at.replace(" ", "T")}Z`).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
      return `<article class="history-row"><span class="history-type">${escapeHtml(label)}</span><div class="history-detail"><h2>${escapeHtml(result.summary || "Saved plan")}</h2><p>${date}</p></div><span class="history-budget">${result.budget ? money(result.budget, result.currency) : ""}</span></article>`;
    }).join("");
  } catch (error) {
    document.querySelector("#history-list").innerHTML = `<div class="notice error">${escapeHtml(error.message)}</div>`;
  }
}

async function init() {
  if (localStorage.getItem(tokenKey)) {
    try { currentUser = await requestJson("/api/auth/session-info", { headers: authHeaders() }); }
    catch { localStorage.removeItem(tokenKey); }
  }
  renderHeader();
  if (page === "register" || page === "login") renderAuth(page);
  else if (plannerDetails[page]) renderPlanner(page);
  else if (page === "history") await renderHistory();
  else renderHome();
}

init();
