const API_BASE = window.location.origin;
const svg = document.getElementById('map');
const card = document.getElementById('card');
const emptyEl = document.getElementById('empty');
const metaEl = document.getElementById('meta');
const metaTarget = document.getElementById('meta-target');
const metaTime = document.getElementById('meta-time');
const runSelect = document.getElementById('run-select');
const tooltip = document.getElementById('tooltip');
const rangeButtons = document.getElementById('range-buttons');
const timelineSection = document.getElementById('timeline-section');
const timelineHopSelect = document.getElementById('timeline-hop');
const timelineBar = document.getElementById('timeline-bar');
const timelineRangeButtons = document.getElementById('timeline-range-buttons');

const MARGIN = { top: 40, right: 180, bottom: 40, left: 40 };
const NODE_R = 10;
const HOP_DX = 70;

/** 'single' | 'aggregate' */
let viewMode = 'single';
/** when viewMode === 'aggregate', hours back */
let aggregateHours = null;

/** Timeline: runs in current range (with hubs) */
let timelineRuns = [];
let timelineHours = 6;

function showEmpty(message = 'Brak danych. Uruchom kolektor (backend/collector.py).') {
  emptyEl.textContent = message;
  emptyEl.style.display = 'block';
  svg.style.display = 'none';
  metaEl.style.display = 'none';
}

function showError(message) {
  card.classList.add('error');
  emptyEl.textContent = message;
  emptyEl.style.display = 'block';
  svg.style.display = 'none';
  metaEl.style.display = 'none';
}

function clearError() {
  card.classList.remove('error');
}

/** Returns 'ok' | 'warn' | 'fail'. Green: 0% loss and avg ≤100ms. Yellow: loss 0.0001–1% and/or avg >100ms. Red: loss >1% or ??? */
function getNodeState(hub) {
  const loss = Number(hub['Loss%']) || 0;
  const avgMs = hub.Avg != null ? Number(hub.Avg) : null;
  const unknown = hub.host && hub.host.trim() === '???';
  if (unknown || loss > 1) return 'fail';
  if (loss > 0.00009 || (avgMs != null && avgMs > 100)) return 'warn';
  return 'ok';
}

function renderMap(run, isAggregate = false) {
  clearError();
  emptyEl.style.display = 'none';
  svg.style.display = 'block';
  metaEl.style.display = 'block';

  metaTarget.textContent = `Cel: ${run.target || '(wszystkie)'}`;
  if (isAggregate && run.from && run.to) {
    metaTime.textContent = `Zbiorczo: ${run.from} — ${run.to} (${run.runs_count} runów)`;
  } else {
    metaTime.textContent = `Pomiar: ${run.created_at}`;
  }

  const hubs = run.hubs || [];
  if (hubs.length === 0) {
    showEmpty(isAggregate ? 'Brak pomiarów w wybranym zakresie.' : 'Brak hopów w tym runie.');
    return;
  }

  const width = svg.viewBox.baseVal.width;
  const height = svg.viewBox.baseVal.height;
  const chartWidth = width - MARGIN.left - MARGIN.right;
  const chartHeight = height - MARGIN.top - MARGIN.bottom;

  const maxHops = hubs.length;
  const totalW = (maxHops - 1) * HOP_DX;
  const startX = MARGIN.left + (chartWidth - totalW) / 2 + NODE_R;
  const cy = MARGIN.top + chartHeight / 2;

  const nodes = hubs.map((h, i) => ({
    ...h,
    x: startX + i * HOP_DX,
    y: cy,
    state: getNodeState(h),
  }));

  let html = '';

  // Links: worst state of the two endpoints
  const linkState = (a, b) => ((a.state === 'fail' || b.state === 'fail') ? 'fail' : (a.state === 'warn' || b.state === 'warn') ? 'warn' : 'ok');
  for (let i = 0; i < nodes.length - 1; i++) {
    const a = nodes[i];
    const b = nodes[i + 1];
    const linkClass = 'link ' + linkState(a, b);
    html += `<line class="${linkClass}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" />`;
  }

  // Nodes
  nodes.forEach((node, i) => {
    const cls = 'node ' + node.state;
    const title = node.host || `Hop ${node.count}`;
    html += `<g class="${cls}" data-index="${i}" aria-label="${title}">`;
    html += `<circle r="${NODE_R}" cx="${node.x}" cy="${node.y}" />`;
    html += `</g>`;
  });

  // Last hop label (destination)
  const last = nodes[nodes.length - 1];
  if (last) {
    const labelX = last.x + NODE_R + 12;
    const labelY = last.y;
    const destText = last.host && last.host !== '???' ? last.host : (run.target || '???');
    html += `<text class="dest-label" x="${labelX}" y="${labelY}" dy="0.35em">${escapeHtml(destText)}</text>`;
  }

  svg.innerHTML = html;

  // Tooltip
  svg.querySelectorAll('.node').forEach((el) => {
    const index = parseInt(el.getAttribute('data-index'), 10);
    const hub = hubs[index];

    el.addEventListener('mouseenter', (e) => {
      const host = hub.host && hub.host !== '???' ? hub.host : `Hop ${hub.count} (nieznany)`;
      document.getElementById('tooltip-host').textContent = host;
      document.getElementById('tooltip-min').textContent = formatMs(hub.Best);
      document.getElementById('tooltip-avg').textContent = formatMs(hub.Avg);
      document.getElementById('tooltip-max').textContent = formatMs(hub.Wrst);
      const lossEl = document.getElementById('tooltip-loss');
      lossEl.textContent = `${hub['Loss%'] != null ? Number(hub['Loss%']).toFixed(1) : '—'}%`;
      lossEl.classList.toggle('ok', hub['Loss%'] === 0 || hub['Loss%'] == null);
      if (isAggregate && hub.runs_count != null) {
        const extra = document.getElementById('tooltip-extra');
        if (extra) {
          extra.textContent = `(${hub.runs_count} pomiarów)`;
          extra.style.display = 'block';
        }
      } else {
        const extra = document.getElementById('tooltip-extra');
        if (extra) extra.style.display = 'none';
      }

      tooltip.classList.add('visible');
      positionTooltip(e);
    });

    el.addEventListener('mousemove', positionTooltip);
    el.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
  });
}

function positionTooltip(e) {
  const x = e.clientX;
  const y = e.clientY;
  const gap = 12;
  const rect = tooltip.getBoundingClientRect();
  let left = x + gap;
  let top = y + gap;
  if (left + rect.width > window.innerWidth) left = x - rect.width - gap;
  if (top + rect.height > window.innerHeight) top = y - rect.height - gap;
  if (top < 0) top = gap;
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function formatMs(v) {
  if (v == null || (typeof v === 'number' && isNaN(v))) return '—';
  return `${Number(v).toFixed(2)} ms`;
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

async function loadRuns() {
  try {
    const r = await fetch(`${API_BASE}/api/runs?limit=50`);
    if (!r.ok) return;
    const runs = await r.json();
    runSelect.innerHTML = '<option value="">Latest</option>';
    const reached = runs.filter((run) => run.reached_destination);
    const unreached = runs.filter((run) => !run.reached_destination);
    if (reached.length) {
      const g1 = document.createElement('optgroup');
      g1.label = 'Doleciał do celu';
      reached.forEach((run) => {
        const opt = document.createElement('option');
        opt.value = run.id;
        opt.textContent = `#${run.id} ${run.target} — ${run.created_at}`;
        g1.appendChild(opt);
      });
      runSelect.appendChild(g1);
    }
    if (unreached.length) {
      const g2 = document.createElement('optgroup');
      g2.label = 'Nie doleciał do celu';
      g2.className = 'reached-no';
      unreached.forEach((run) => {
        const opt = document.createElement('option');
        opt.value = run.id;
        opt.className = 'reached-no';
        opt.textContent = `#${run.id} ${run.target} — ${run.created_at}`;
        g2.appendChild(opt);
      });
      runSelect.appendChild(g2);
    }
  } catch (_) {}
}

async function loadRun(runId) {
  viewMode = 'single';
  aggregateHours = null;
  rangeButtons.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
  const url = runId
    ? `${API_BASE}/api/runs/${runId}`
    : `${API_BASE}/api/latest`;
  try {
    const r = await fetch(url);
    if (!r.ok) {
      if (r.status === 404) showEmpty('Brak pomiarów. Uruchom kolektor.');
      else showError(`Błąd: ${r.status}`);
      return;
    }
    const run = await r.json();
    renderMap(run, false);
  } catch (err) {
    showError('Nie można połączyć z API. Uruchom serwer (backend/server.py).');
  }
}

function toISOLocal(d) {
  return d.toISOString().slice(0, 19).replace('T', ' ');
}

async function loadAggregate(hours) {
  viewMode = 'aggregate';
  aggregateHours = hours;
  runSelect.value = '';
  rangeButtons.querySelectorAll('button').forEach((b) => {
    b.classList.toggle('active', parseInt(b.dataset.hours, 10) === hours);
  });
  const end = new Date();
  const start = new Date(end.getTime() - hours * 60 * 60 * 1000);
  const from_ts = toISOLocal(start);
  const to_ts = toISOLocal(end);
  try {
    const r = await fetch(`${API_BASE}/api/aggregate?from=${encodeURIComponent(from_ts)}&to=${encodeURIComponent(to_ts)}`);
    if (!r.ok) {
      showError(`Błąd: ${r.status}`);
      return;
    }
    const data = await r.json();
    if (data.runs_count === 0) {
      showEmpty('Brak pomiarów w wybranym zakresie czasu.');
      return;
    }
    renderMap(data, true);
  } catch (err) {
    showError('Nie można połączyć z API. Uruchom serwer (backend/server.py).');
  }
}

function onRefresh() {
  if (viewMode === 'aggregate' && aggregateHours != null) {
    loadAggregate(aggregateHours);
  } else {
    loadRun(runSelect.value || undefined);
  }
}

runSelect.addEventListener('change', () => {
  if (runSelect.value) loadRun(runSelect.value);
  else if (viewMode === 'single') loadRun();
});
document.getElementById('refresh').addEventListener('click', onRefresh);

rangeButtons.querySelectorAll('button').forEach((btn) => {
  btn.addEventListener('click', () => loadAggregate(parseInt(btn.dataset.hours, 10)));
});

// --- Timeline ---
function buildTimelineHopOptions(runs) {
  const hopMap = new Map();
  for (const run of runs) {
    for (const hub of run.hubs || []) {
      const c = hub.count;
      if (!hopMap.has(c)) hopMap.set(c, hub.host && hub.host !== '???' ? hub.host : `Hop ${c}`);
    }
  }
  const sorted = [...hopMap.entries()].sort((a, b) => a[0] - b[0]);
  timelineHopSelect.innerHTML = '<option value="">— wybierz hop —</option>';
  for (const [count, label] of sorted) {
    const opt = document.createElement('option');
    opt.value = String(count);
    opt.textContent = `Hop ${count} — ${label}`;
    timelineHopSelect.appendChild(opt);
  }
}

function showTooltipForHub(hub, run, e) {
  const host = hub && hub.host && hub.host !== '???' ? hub.host : hub ? `Hop ${hub.count} (nieznany)` : '—';
  document.getElementById('tooltip-host').textContent = host;
  document.getElementById('tooltip-min').textContent = formatMs(hub && hub.Best);
  document.getElementById('tooltip-avg').textContent = formatMs(hub && hub.Avg);
  document.getElementById('tooltip-max').textContent = formatMs(hub && hub.Wrst);
  const lossEl = document.getElementById('tooltip-loss');
  lossEl.textContent = hub ? `${hub['Loss%'] != null ? Number(hub['Loss%']).toFixed(1) : '—'}%` : '—';
  lossEl.classList.toggle('ok', !hub || hub['Loss%'] === 0 || hub['Loss%'] == null);
  const extra = document.getElementById('tooltip-extra');
  if (run) {
    extra.textContent = run.created_at;
    extra.style.display = 'block';
  } else {
    extra.style.display = 'none';
  }
  tooltip.classList.add('visible');
  positionTooltip(e);
}

function renderTimelineBar() {
  const hopCount = timelineHopSelect.value ? parseInt(timelineHopSelect.value, 10) : null;
  if (hopCount == null || timelineRuns.length === 0) {
    timelineBar.innerHTML = '';
    return;
  }
  timelineBar.innerHTML = timelineRuns.map((run, i) => {
    const hub = (run.hubs || []).find((h) => h.count === hopCount);
    const state = hub ? getNodeState(hub) : 'nodata';
    return `<span class="segment ${state}" data-index="${i}"></span>`;
  }).join('');

  timelineBar.querySelectorAll('.segment').forEach((el) => {
    const i = parseInt(el.getAttribute('data-index'), 10);
    const run = timelineRuns[i];
    const hub = (run.hubs || []).find((h) => h.count === hopCount);
    el.addEventListener('mouseenter', (e) => showTooltipForHub(hub, run, e));
    el.addEventListener('mousemove', positionTooltip);
    el.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
  });
}

async function loadTimelineData(hours) {
  timelineHours = hours;
  timelineRangeButtons.querySelectorAll('button').forEach((b) => {
    b.classList.toggle('active', parseInt(b.dataset.hours, 10) === hours);
  });
  const savedHop = timelineHopSelect.value;
  const end = new Date();
  const start = new Date(end.getTime() - hours * 60 * 60 * 1000);
  const from_ts = toISOLocal(start);
  const to_ts = toISOLocal(end);
  try {
    const r = await fetch(`${API_BASE}/api/runs_range?from=${encodeURIComponent(from_ts)}&to=${encodeURIComponent(to_ts)}`);
    if (!r.ok) return;
    const data = await r.json();
    timelineRuns = data.runs || [];
    buildTimelineHopOptions(timelineRuns);
    if (savedHop && timelineHopSelect.querySelector(`option[value="${savedHop}"]`)) {
      timelineHopSelect.value = savedHop;
    }
    renderTimelineBar();
  } catch (_) {
    timelineRuns = [];
    timelineHopSelect.innerHTML = '<option value="">— wybierz hop —</option>';
    timelineBar.innerHTML = '';
  }
}

timelineHopSelect.addEventListener('change', renderTimelineBar);
timelineRangeButtons.querySelectorAll('button').forEach((btn) => {
  btn.addEventListener('click', () => loadTimelineData(parseInt(btn.dataset.hours, 10)));
});

// Init
loadRuns().then(() => loadRun());
loadTimelineData(timelineHours);
setInterval(() => {
  if (viewMode === 'aggregate' && aggregateHours != null) loadAggregate(aggregateHours);
  else if (!runSelect.value) loadRun();
  loadTimelineData(timelineHours);
}, 10000);
