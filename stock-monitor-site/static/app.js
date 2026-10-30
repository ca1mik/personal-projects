const form = document.getElementById('monitoringForm');
const tableBody = document.getElementById('tableBody');
const summaryPanel = document.getElementById('summaryPanel');
const banner = document.getElementById('banner');
const connectionBadge = document.getElementById('connectionBadge');

let stream;

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function asNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatDecimal(value, suffix = '') {
  const parsed = asNumber(value);
  if (parsed === null) {
    return '—';
  }
  return `${parsed.toFixed(4)}${suffix}`;
}

function renderSummary(state) {
  const rows = state.rows ?? [];
  const targetReached = rows.filter((row) => row.target_reached).length;
  const rollbackActive = rows.filter((row) => row.rollback_min && row.rollback_max).length;

  summaryPanel.innerHTML = `
    <div class="metric">
      <span class="metric-label">Время сервера</span>
      <strong>${escapeHtml(state.server_time)}</strong>
    </div>
    <div class="metric">
      <span class="metric-label">Источник</span>
      <strong>${escapeHtml(state.mode)}</strong>
    </div>
    <div class="metric">
      <span class="metric-label">Статус</span>
      <strong>${state.running ? 'мониторинг идет' : 'мониторинг остановлен'}</strong>
    </div>
    <div class="metric">
      <span class="metric-label">Тикеры / Сигналы</span>
      <strong>${rows.length} / ${targetReached}</strong>
    </div>
    <div class="metric">
      <span class="metric-label">Контроль отката</span>
      <strong>${rollbackActive}</strong>
    </div>
  `;

  banner.textContent =
    `Параметры: изменение ${state.settings.change_percent}% | время ${state.settings.window_minutes} мин | ` +
    `откат ${state.settings.rollback_percent}% | ${state.mode_note}`;
}

function buildRowMeta(row) {
  const parts = [];

  if (row.current_price) {
    parts.push(`текущая цена ${formatDecimal(row.current_price)}`);
  }
  if (row.next_window_start) {
    parts.push(`старт ${row.next_window_start}`);
  } else if (row.window_end) {
    parts.push(`следующий пересчет ${row.window_end}`);
  }
  if (row.status) {
    parts.push(row.status);
  }
  if (row.last_reset_reason) {
    parts.push(row.last_reset_reason);
  }

  return parts.join(' | ');
}

function renderRows(rows) {
  tableBody.innerHTML = '';

  if (!rows.length) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="6">Список акций пуст. Добавьте тикеры и запустите мониторинг.</td>
      </tr>
    `;
    return;
  }

  for (const row of rows) {
    const tr = document.createElement('tr');
    if (row.target_reached) {
      tr.classList.add('row-hit');
    }

    tr.innerHTML = `
      <td>
        <div class="ticker-main">${escapeHtml(row.ticker)}</div>
        <div class="row-meta">${escapeHtml(row.name)}</div>
        <div class="row-meta">${escapeHtml(buildRowMeta(row))}</div>
      </td>
      <td>${formatDecimal(row.change_percent, '%')}</td>
      <td>${formatDecimal(row.min_price)}</td>
      <td>${formatDecimal(row.max_price)}</td>
      <td>${formatDecimal(row.rollback_min)}</td>
      <td>${formatDecimal(row.rollback_max)}</td>
    `;

    tableBody.appendChild(tr);
  }
}

function syncForm(state) {
  if (document.activeElement && form.contains(document.activeElement)) {
    return;
  }

  form.elements.tickers.value = state.settings.tickers.join(', ');
  form.elements.change_percent.value = state.settings.change_percent;
  form.elements.window_minutes.value = state.settings.window_minutes;
  form.elements.rollback_percent.value = state.settings.rollback_percent;
}

function renderState(state) {
  renderSummary(state);
  renderRows(state.rows);
  syncForm(state);
}

async function fetchState() {
  const response = await fetch('/api/state');
  if (response.status === 401) {
    window.location.href = '/';
    return;
  }
  const state = await response.json();
  renderState(state);
}

function connectStream() {
  if (stream) {
    stream.close();
  }

  stream = new EventSource('/api/stream');
  connectionBadge.textContent = 'SSE: подключение...';

  stream.addEventListener('open', () => {
    connectionBadge.textContent = 'SSE: онлайн';
  });

  stream.addEventListener('state', (event) => {
    const payload = JSON.parse(event.data);
    renderState(payload);
  });

  stream.onerror = () => {
    connectionBadge.textContent = 'SSE: переподключение';
  };
}

function parseTickers(raw) {
  return raw
    .replace(/\n/g, ',')
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);
}

function extractErrorMessage(detail) {
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).filter(Boolean).join('\n');
  }
  return 'Не удалось выполнить запрос.';
}

async function handleStart(event) {
  event.preventDefault();

  const payload = {
    tickers: parseTickers(form.elements.tickers.value),
    change_percent: form.elements.change_percent.value,
    window_minutes: Number(form.elements.window_minutes.value),
    rollback_percent: form.elements.rollback_percent.value,
  };

  const response = await fetch('/api/start', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json();
    alert(extractErrorMessage(error.detail));
    return;
  }

  const data = await response.json();
  renderState(data.state);
}

async function handleStop() {
  const response = await fetch('/api/stop', {
    method: 'POST',
  });

  if (!response.ok) {
    alert('Не удалось остановить мониторинг.');
    return;
  }

  const data = await response.json();
  renderState(data.state);
}

form.addEventListener('submit', handleStart);
document.getElementById('stopBtn').addEventListener('click', handleStop);

fetchState().then(connectStream);
