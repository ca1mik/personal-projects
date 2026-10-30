// ============================================================
// ppdstr Dashboard JS — реальные данные из API бота + localStorage для контента/отзывов
// ============================================================

const API_URL_KEY = "ppdstr.apiUrl";
const STORAGE_CONTENT = "ppdstr.content";
const STORAGE_REVIEWS = "ppdstr.reviews";

const STATUS_BADGE = {
  new: "badge-new",
  contacted: "badge-contacted",
  consultation: "badge-consultation",
  waiting_reply: "badge-waiting",
  confirmed: "badge-confirmed",
  deposit: "badge-deposit",
  done: "badge-done",
  archive: "badge-archive",
};

const STATUS_OPTIONS = [
  { value: "new", label: "Новая" },
  { value: "contacted", label: "Связались" },
  { value: "consultation", label: "Консультация" },
  { value: "waiting_reply", label: "Ждём ответа" },
  { value: "confirmed", label: "Подтверждена" },
  { value: "deposit", label: "Предоплата" },
  { value: "done", label: "Сделано" },
  { value: "archive", label: "Архив" },
];

// --- HELPERS ---

function esc(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(str) {
  if (!str) return "—";
  return str.slice(0, 10);
}

function formatRub(value) {
  const n = Number(value);
  if (!n) return "0 ₽";
  return n.toLocaleString("ru-RU") + " ₽";
}

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2, 6)}`;
}

function readStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

// --- API ---

function getApiUrl() {
  const input = document.getElementById("apiUrlInput");
  const saved = localStorage.getItem(API_URL_KEY) || "";
  return (input ? input.value.trim() : saved) || "";
}

async function apiFetch(path, options = {}) {
  const base = getApiUrl().replace(/\/$/, "");
  if (!base) throw new Error("URL бота не указан");
  const res = await fetch(base + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// --- STATUS DOT ---

function setApiStatus(ok) {
  const dot = document.getElementById("apiStatusDot");
  const text = document.getElementById("apiStatusText");
  if (!dot || !text) return;
  if (ok === null) {
    dot.className = "status-dot";
    text.textContent = "проверка…";
  } else if (ok) {
    dot.className = "status-dot ok";
    text.textContent = "бот онлайн";
  } else {
    dot.className = "status-dot err";
    text.textContent = "нет связи";
  }
}

// --- FUNNEL RENDER ---

function renderFunnel(funnel, total) {
  const grid = document.getElementById("funnelGrid");
  if (!grid) return;
  if (!funnel || !funnel.length) {
    grid.innerHTML = '<div class="funnel-card"><div class="funnel-card__label">Нет данных</div></div>';
    return;
  }
  grid.innerHTML = funnel.map((item) => {
    const pctNum = total > 0 ? Math.round((item.count / total) * 100) : 0;
    return `
      <div class="funnel-card">
        <div class="funnel-card__fill" style="width:${pctNum}%"></div>
        <div class="funnel-card__label">${esc(item.label)}</div>
        <div class="funnel-card__count">${item.count}</div>
        <div class="funnel-card__pct">${item.pct || pctNum + "%"} от всех</div>
      </div>
    `;
  }).join("");
}

// --- STALE ALERT ---

function renderStaleAlert(stale) {
  const box = document.getElementById("staleAlert");
  if (!box) return;
  if (!stale || stale.length === 0) {
    box.style.display = "none";
    return;
  }
  box.style.display = "flex";
  box.innerHTML = `
    <span>⚠️</span>
    <span>
      <strong>${stale.length} заявок</strong> без движения более 7 дней:
      ${stale.slice(0, 3).map(s => `<strong>#${s.id}</strong> ${esc(s.name)} (${s.days_stale} д.)`).join(", ")}
      ${stale.length > 3 ? `и ещё ${stale.length - 3}` : ""}
    </span>
  `;
}

// --- LEADS TABLE ---

function statusBadge(status, label) {
  const cls = STATUS_BADGE[status] || "badge-new";
  return `<span class="badge ${cls}">${esc(label || status)}</span>`;
}

function statusSelect(requestId, currentStatus, apiUrl) {
  const options = STATUS_OPTIONS.map(
    (o) => `<option value="${o.value}" ${o.value === currentStatus ? "selected" : ""}>${o.label}</option>`
  ).join("");
  return `<select class="status-select" data-lead-id="${requestId}" data-api="${esc(apiUrl)}">${options}</select>`;
}

function renderLeads(leads, apiUrl) {
  const tbody = document.getElementById("leadsTableBody");
  if (!tbody) return;
  if (!leads || !leads.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">Заявок пока нет</td></tr>';
    return;
  }
  tbody.innerHTML = leads.map((lead) => `
    <tr>
      <td class="muted">#${lead.id}</td>
      <td>${statusBadge(lead.status, lead.status_label)}</td>
      <td class="muted">${formatDate(lead.created_at)}</td>
      <td>
        <div>${esc(lead.name)}</div>
        <div class="muted" style="font-size:11px">${esc(lead.contact)}</div>
      </td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(lead.idea)}">${esc(lead.idea)}</td>
      <td class="muted">${esc(lead.source === "website-form" ? "Сайт" : "Бот")}</td>
      <td>${statusSelect(lead.id, lead.status, apiUrl)}</td>
    </tr>
  `).join("");

  // Привязываем select к API
  tbody.querySelectorAll(".status-select").forEach((sel) => {
    sel.addEventListener("change", async () => {
      const lid = Number(sel.dataset.leadId);
      const newStatus = sel.value;
      try {
        await apiFetch("/api/booking-status", {
          method: "POST",
          body: JSON.stringify({ request_id: lid, status: newStatus }),
        });
        setSyncMsg(`✓ Статус заявки #${lid} обновлён`, true);
      } catch (e) {
        setSyncMsg(`Ошибка: ${e.message}`, false);
      }
    });
  });
}

// --- PAYMENTS TABLE ---

function renderPayments(payments) {
  const tbody = document.getElementById("paymentsTableBody");
  if (!tbody) return;
  if (!payments || !payments.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">Платежей пока нет</td></tr>';
    return;
  }
  tbody.innerHTML = payments.map((p) => {
    const statusClass = p.status === "paid" ? "pay-paid" : p.status === "created" ? "pay-created" : "pay-failed";
    const statusIcon = p.status === "paid" ? "✅ Оплачено" : p.status === "created" ? "⏳ Ожидание" : "❌ Ошибка";
    const channel = p.channel === "robokassa" ? "Robokassa" : "Telegram Stars";
    return `
      <tr>
        <td class="muted">#${p.id}</td>
        <td class="muted">${formatDate(p.paid_at || p.created_at)}</td>
        <td>${esc(channel)}</td>
        <td>${esc(p.offer_title)}</td>
        <td><strong>${formatRub(p.amount_rub)}</strong></td>
        <td class="${statusClass}">${statusIcon}</td>
      </tr>
    `;
  }).join("");
}

// --- SYNC MSG ---

function setSyncMsg(text, ok) {
  const el = document.getElementById("syncMsg");
  if (!el) return;
  el.textContent = text;
  el.className = "sync-msg" + (ok === true ? " ok" : ok === false ? " err" : "");
  if (ok !== null) {
    setTimeout(() => { el.textContent = ""; el.className = "sync-msg"; }, 5000);
  }
}

// --- MAIN LOAD FROM API ---

async function loadDashboard() {
  const apiUrl = getApiUrl();
  if (!apiUrl) {
    setApiStatus(false);
    setSyncMsg("Укажите URL бота выше", null);
    return;
  }

  setApiStatus(null);
  setSyncMsg("Загружаем данные…", null);

  try {
    const [stats, leadsData, paymentsData] = await Promise.all([
      apiFetch("/api/crm-stats"),
      apiFetch("/api/crm-leads?limit=50"),
      apiFetch("/api/crm-payments"),
    ]);

    setApiStatus(true);
    setSyncMsg("", null);

    // Сводка
    const s = stats;
    const counts = {};
    (s.funnel || []).forEach((f) => { counts[f.status] = f.count; });

    document.getElementById("statTotal").textContent = s.total ?? "—";
    document.getElementById("statNew").textContent = counts.new ?? "—";
    document.getElementById("statDeposit").textContent = counts.deposit ?? "—";
    document.getElementById("statDone").textContent = counts.done ?? "—";
    document.getElementById("statStale").textContent = s.stale_count ?? "—";
    document.getElementById("statRevenue").textContent = formatRub(paymentsData.total_paid_rub);

    // Конверсия
    document.getElementById("convContacted").textContent = s.conversion?.contacted_pct ?? "—";
    document.getElementById("convDeposit").textContent = s.conversion?.deposit_pct ?? "—";
    document.getElementById("convDone").textContent = s.conversion?.done_pct ?? "—";

    // Воронка
    renderFunnel(s.funnel, s.total);

    // Stale
    renderStaleAlert(s.stale_leads);

    // Лиды
    renderLeads(leadsData.leads, apiUrl);

    // Платежи
    renderPayments(paymentsData.payments);

  } catch (e) {
    setApiStatus(false);
    setSyncMsg(`Ошибка подключения: ${e.message}`, false);
    renderFunnel(null, 0);
    renderLeads(null, "");
    renderPayments(null);
  }
}

// --- CRM SYNC ---

async function triggerCrmSync() {
  setSyncMsg("Синхронизирую CRM…", null);
  try {
    const res = await apiFetch("/api/crm-sync", { method: "POST" });
    setSyncMsg(res.message || "CRM синхронизирован", true);
  } catch (e) {
    setSyncMsg(`Ошибка: ${e.message}`, false);
  }
}

// ============================================================
// LOCAL STORAGE — контент и отзывы
// ============================================================

function removeLocal(key, id) {
  const items = readStorage(key, []).filter((i) => i.id !== id);
  writeStorage(key, items);
  renderLocalSections();
}

function renderContentTable() {
  const items = readStorage(STORAGE_CONTENT, []);
  document.getElementById("statContent").textContent = `${items.length} единиц`;
  const tbody = document.getElementById("contentTableBody");
  if (!tbody) return;
  tbody.innerHTML = items.map((item) => `
    <tr>
      <td>${esc(item.title)}</td>
      <td class="muted">${esc(item.platform)}</td>
      <td><span class="badge badge-new">${esc(item.status)}</span></td>
      <td class="muted">${item.publishDate || "—"}</td>
      <td><button class="table-button" data-key="content" data-id="${item.id}" type="button">✕</button></td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="empty">Нет записей</td></tr>';
}

function renderReviewTable() {
  const items = readStorage(STORAGE_REVIEWS, []);
  document.getElementById("statReviews").textContent = `${items.length} записей`;
  const tbody = document.getElementById("reviewTableBody");
  if (!tbody) return;
  tbody.innerHTML = items.map((item) => `
    <tr>
      <td>${esc(item.name)}</td>
      <td class="muted">${esc(item.platform)}</td>
      <td><span class="badge badge-new">${esc(item.status)}</span></td>
      <td class="muted">${esc(item.healed)}</td>
      <td><button class="table-button" data-key="review" data-id="${item.id}" type="button">✕</button></td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="empty">Нет записей</td></tr>';
}

function renderLocalSections() {
  renderContentTable();
  renderReviewTable();
  bindLocalButtons();
}

function bindLocalButtons() {
  document.querySelectorAll(".table-button[data-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.key === "content" ? STORAGE_CONTENT : STORAGE_REVIEWS;
      removeLocal(key, btn.dataset.id);
    });
  });
}

function bindLocalForms() {
  document.getElementById("contentForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const items = readStorage(STORAGE_CONTENT, []);
    items.unshift({ id: makeId(), title: fd.get("title"), platform: fd.get("platform"), format: fd.get("format"), status: fd.get("status"), publishDate: fd.get("publishDate"), hook: fd.get("hook") });
    writeStorage(STORAGE_CONTENT, items);
    e.currentTarget.reset();
    renderLocalSections();
  });

  document.getElementById("reviewForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const items = readStorage(STORAGE_REVIEWS, []);
    items.unshift({ id: makeId(), name: fd.get("name"), platform: fd.get("platform"), status: fd.get("status"), healed: fd.get("healed"), notes: fd.get("notes") });
    writeStorage(STORAGE_REVIEWS, items);
    e.currentTarget.reset();
    renderLocalSections();
  });
}

// ============================================================
// INIT
// ============================================================

function init() {
  // Восстановить API URL из localStorage
  const savedUrl = localStorage.getItem(API_URL_KEY) || "";
  const input = document.getElementById("apiUrlInput");
  if (input && savedUrl) input.value = savedUrl;

  // Сохранять URL при изменении
  input?.addEventListener("change", () => {
    localStorage.setItem(API_URL_KEY, input.value.trim());
  });
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { localStorage.setItem(API_URL_KEY, input.value.trim()); loadDashboard(); }
  });

  document.getElementById("refreshBtn")?.addEventListener("click", () => {
    if (input) localStorage.setItem(API_URL_KEY, input.value.trim());
    loadDashboard();
  });
  document.getElementById("syncCrmBtn")?.addEventListener("click", triggerCrmSync);

  bindLocalForms();
  renderLocalSections();

  // Загрузить данные из API
  if (savedUrl) {
    loadDashboard();
  } else {
    setSyncMsg("Введите URL бота и нажмите «Обновить»", null);
  }

  // Автообновление каждые 60 сек
  setInterval(() => {
    if (getApiUrl()) loadDashboard();
  }, 60_000);
}

init();
