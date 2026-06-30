// Topic Coverage frontend controller.
// Loads a /runs/{id}/map payload (or the bundled sample for offline dev),
// renders the radial map, and on topic click loads /runs/{id}/topics/{tid}
// into the detail panel.

const STATE_LABEL = {
  only_you: 'Only you', you_lead: 'You lead', even: 'Even',
  comp_lead: 'Competitor leads', only_comp: 'Only competitor',
};
// STATE_COLOR is defined globally by radial-map.js (loaded first).

const mapEl = document.getElementById('map');
const detailEl = document.getElementById('detail');
const statusEl = document.getElementById('status');
const runInput = document.getElementById('runId');

let currentRunId = null;
let usingSample = false;       // sample mode: no /topics endpoint
let topicsById = {};           // cache nodes from the map for sample-mode detail

function apiBase() {
  // When served by FastAPI we share its origin; over file:// there's no API.
  return location.protocol === 'file:' ? null : location.origin;
}

async function loadMap(runId) {
  statusEl.textContent = 'Loading…';
  topicsById = {};
  const base = apiBase();
  try {
    let map;
    if (base) {
      const res = await fetch(`${base}/runs/${runId}/map`);
      if (!res.ok) throw new Error(`map ${res.status}`);
      map = await res.json();
      usingSample = false;
    } else {
      map = await (await fetch('sample-map.json')).json();
      usingSample = true;
    }
    currentRunId = runId;
    indexTopics(map);
    renderRadialMap(mapEl, map, onTopicClick);
    const n = Object.keys(topicsById).length;
    statusEl.textContent = `${map.own_domain} vs ${(map.competitors || []).join(', ')} · ${n} topics`
      + (usingSample ? ' · sample data' : '');
  } catch (err) {
    // Fall back to the bundled sample if the API isn't reachable.
    try {
      const map = await (await fetch('sample-map.json')).json();
      usingSample = true;
      indexTopics(map);
      renderRadialMap(mapEl, map, onTopicClick);
      statusEl.textContent = 'API unavailable — showing sample data';
    } catch (e2) {
      mapEl.innerHTML = `<div class="muted">Could not load a map.<br>${err.message}</div>`;
      statusEl.textContent = '';
    }
  }
}

function indexTopics(map) {
  (map.categories || []).forEach(cat =>
    (cat.topics || []).forEach(t => { topicsById[String(t.id)] = { ...t, category: cat.label }; }));
}

async function onTopicClick(topicId) {
  highlightSelected(mapEl, topicId);
  const base = apiBase();
  if (base && !usingSample) {
    detailEl.innerHTML = '<div class="empty">Loading…</div>';
    try {
      const res = await fetch(`${base}/runs/${currentRunId}/topics/${topicId}`);
      if (!res.ok) throw new Error(`topic ${res.status}`);
      renderDetail(await res.json());
      return;
    } catch (e) { /* fall through to node-only detail */ }
  }
  // Sample / offline mode: render from the node we already have (no evidence).
  const node = topicsById[String(topicId)];
  if (node) {
    renderDetail({
      label: node.label, category: node.category, state: node.state,
      you_pct: node.you_pct, competitors_pct: node.competitors_pct,
      detected: { own: [], competitors: [] },
    }, true);
  }
}

function renderDetail(d, sampleMode) {
  const color = STATE_COLOR[d.state] || '#94a3b8';
  const terms = labelTerms(d.label);
  const own = d.detected && d.detected.own ? d.detected.own : [];
  const comps = d.detected && d.detected.competitors ? d.detected.competitors : [];

  detailEl.innerHTML = `
    <span class="chip" style="background:${color}">${STATE_LABEL[d.state] || d.state}</span>
    <h2>${esc(d.label)}</h2>
    <div class="cat">${esc(d.category || '')}</div>

    <div class="sharebar">
      ${d.you_pct > 0 ? `<div class="you" style="width:${d.you_pct}%">${d.you_pct}%</div>` : ''}
      ${d.competitors_pct > 0 ? `<div class="comp" style="width:${d.competitors_pct}%">${d.competitors_pct}%</div>` : ''}
    </div>
    <div class="sharelabels"><span>You</span><span>Competitors</span></div>

    <div class="section-title">Content detected on this topic</div>
    ${sampleMode ? '<p class="col-empty">Sample data — connect the API to see detected sentences.</p>' : ''}
    <div class="cols">
      <div>
        <h3>On your domain</h3>
        ${own.length ? own.map(e => evidence(e, terms)).join('')
          : '<p class="col-empty">No content detected on your domain for this topic.</p>'}
      </div>
      <div>
        <h3>On competitors</h3>
        ${comps.length ? comps.map(e => evidence(e, terms, true)).join('')
          : '<p class="col-empty">No content detected on competitors for this topic.</p>'}
      </div>
    </div>`;
}

function evidence(e, terms, showDomain) {
  return `<div class="ev">
    ${showDomain && e.domain ? `<div class="ev-domain">${esc(e.domain)}</div>` : ''}
    <p>${highlight(e.sentence || '', terms)}</p>
    ${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">See more →</a>` : ''}
  </div>`;
}

// --- term highlighting ------------------------------------------------------

const STOP = new Set(['the', 'and', 'for', 'with', 'your', 'guide', 'part', 'topic']);
function labelTerms(label) {
  return (label || '').split(/[^A-Za-z0-9]+/)
    .map(w => w.toLowerCase()).filter(w => w.length > 2 && !STOP.has(w));
}
function highlight(sentence, terms) {
  let out = esc(sentence);
  terms.forEach(t => {
    out = out.replace(new RegExp(`\\b(${escapeRe(t)}\\w*)\\b`, 'gi'), '<mark>$1</mark>');
  });
  return out;
}
function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
}

// --- boot -------------------------------------------------------------------

document.getElementById('loadBtn').addEventListener('click', () =>
  loadMap(parseInt(runInput.value, 10) || 1));

const qsRun = new URLSearchParams(location.search).get('run');
if (qsRun) runInput.value = qsRun;
loadMap(parseInt(runInput.value, 10) || 1);
