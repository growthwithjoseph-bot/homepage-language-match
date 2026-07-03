// Homepage Language Match — controller.
// Enter your domain + competitors → POST /runs → poll → GET /runs/{id}/report,
// then render per-competitor score cards + a semantic-vs-lexical scatter.

const statusEl = document.getElementById('status');
const progressEl = document.getElementById('progress');
const reportEl = document.getElementById('report');
const analyzeBtn = document.getElementById('analyzeBtn');

let currentRunId = null;
let pollTimer = null;
let lastReport = null;
let scatterSection = 'headline';   // 'headline' | 'paragraph'

function apiBase() {
  return location.protocol === 'file:' ? null : location.origin;
}

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));
}
function prettyDomain(url) {
  return String(url || '').replace(/^https?:\/\//, '').replace(/^www\./, '').replace(/\/$/, '');
}

// One distinct colour per competitor, shared between the scatter dot and its
// card, so you can match them at a glance. (Max 5 competitors -> 5 needed.)
const CMP_COLORS = ['#e11d48', '#16a34a', '#7c3aed', '#0891b2', '#d97706', '#2563eb'];
const cmpColor = (i) => CMP_COLORS[i % CMP_COLORS.length];

// --- "analysing" animation (dog chasing a ball through changing scenery) -----
const CRAWL_ANIM_HTML = `
  <div class="crawl-anim" id="crawlScene">
    <svg class="crawl-scene" viewBox="0 0 280 130" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs><clipPath id="csClip"><rect x="0" y="0" width="280" height="130" rx="12"/></clipPath></defs>
      <g clip-path="url(#csClip)">
        <g class="bgscene bg1"><rect width="280" height="130" fill="#d7eefe"/>
          <circle cx="242" cy="26" r="12" fill="#fde68a"/><rect y="104" width="280" height="26" fill="#8fe0a0"/>
          <rect x="46" y="84" width="6" height="28" fill="#7c5c3b"/><rect x="98" y="90" width="6" height="22" fill="#7c5c3b"/>
          <circle cx="49" cy="78" r="18" fill="#3fae60"/><circle cx="101" cy="84" r="13" fill="#3fae60"/></g>
        <g class="bgscene bg2"><rect width="280" height="130" fill="#dbeafe"/>
          <polygon points="6,114 66,48 128,114" fill="#9aa7bd"/><polygon points="52,66 66,48 80,66" fill="#fff"/>
          <polygon points="120,114 184,38 250,114" fill="#8593ab"/><polygon points="169,58 184,38 199,58" fill="#fff"/>
          <rect y="110" width="280" height="20" fill="#a7d9b4"/></g>
        <g class="bgscene bg3"><rect width="280" height="130" fill="#e2e8ff"/>
          <rect x="22" y="66" width="30" height="54" fill="#64748b"/><rect x="58" y="50" width="26" height="70" fill="#475569"/>
          <rect x="90" y="76" width="24" height="44" fill="#7c8aa0"/><rect x="168" y="56" width="28" height="64" fill="#52607a"/>
          <rect x="202" y="72" width="30" height="48" fill="#647089"/><rect x="236" y="46" width="22" height="74" fill="#465063"/>
          <rect y="118" width="280" height="12" fill="#c3ccd9"/></g>
        <g class="bgscene bg4"><rect width="280" height="130" fill="#d7eefe"/>
          <rect y="104" width="280" height="26" fill="#8fe0a0"/><polygon points="146,74 182,44 218,74" fill="#c1553f"/>
          <rect x="152" y="74" width="60" height="46" fill="#f4c58a"/><rect x="176" y="96" width="14" height="24" fill="#7c5c3b"/>
          <rect x="194" y="84" width="12" height="12" fill="#bfe3f5"/>
          <g fill="#f472b6"><circle cx="30" cy="112" r="3"/><circle cx="60" cy="116" r="3"/><circle cx="92" cy="112" r="3"/></g></g>
        <g class="bgscene bg5"><rect width="280" height="130" fill="#cfeafd"/>
          <circle cx="44" cy="28" r="13" fill="#fde68a"/><rect y="94" width="280" height="22" fill="#38bdf8"/>
          <rect y="114" width="280" height="16" fill="#f6df9c"/><rect x="232" y="80" width="5" height="36" fill="#8a6a44"/>
          <g fill="#3fae60"><ellipse cx="226" cy="80" rx="12" ry="5"/><ellipse cx="244" cy="80" rx="12" ry="5"/><ellipse cx="234" cy="74" rx="6" ry="11"/></g></g>
        <g transform="translate(0,44)"><g class="cs-ball"><g class="cs-ball-bounce">
          <circle cx="70" cy="68" r="8" fill="#f59e0b"/><circle cx="67" cy="65" r="2.5" fill="#fff" opacity=".8"/>
        </g></g></g>
        <g transform="translate(0,44)"><g class="cs-dog"><g class="cs-dog-bob" fill="#8b5e3c">
          <path class="cs-tail" d="M6 56 C -4 52 -4 44 2 44 C 4 48 8 52 10 54 Z"/>
          <rect class="cs-leg cs-leg-a" x="12" y="62" width="4.5" height="14" rx="2.2"/>
          <rect class="cs-leg cs-leg-b" x="22" y="62" width="4.5" height="14" rx="2.2"/>
          <rect class="cs-leg cs-leg-a" x="33" y="62" width="4.5" height="14" rx="2.2"/>
          <rect class="cs-leg cs-leg-b" x="41" y="62" width="4.5" height="14" rx="2.2"/>
          <ellipse cx="27" cy="57" rx="21" ry="11"/><circle cx="47" cy="48" r="9"/>
          <path d="M40 41 C 36 34 44 33 45 40 Z"/><rect x="53" y="48" width="9" height="7" rx="3.5"/>
          <circle cx="61" cy="49" r="2" fill="#3b2a1a"/><circle cx="49" cy="46" r="1.6" fill="#3b2a1a"/>
        </g></g></g>
      </g>
    </svg>
    <div class="crawl-caption">
      <span>Reading the homepages…</span>
      <span>Comparing headlines and paragraphs…</span>
      <span>Scoring the language match…</span>
    </div>
  </div>`;

function showAnim() {
  progressEl.hidden = false;
  if (!document.getElementById('crawlScene')) progressEl.innerHTML = CRAWL_ANIM_HTML;
}

// --- run lifecycle ----------------------------------------------------------
async function startAnalysis(own, comps) {
  const base = apiBase();
  if (!base) { statusEl.textContent = 'Open this page via the running server (make dev).'; return; }
  analyzeBtn.disabled = true;
  reportEl.hidden = true;
  statusEl.textContent = '';
  showAnim();
  try {
    const res = await fetch(`${base}/runs`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ own_domain: own, competitor_domains: comps }),
    });
    if (!res.ok) throw new Error(`start failed (${res.status})`);
    const { run_id } = await res.json();
    currentRunId = run_id;
    history.replaceState(null, '', `?run=${run_id}`);
    pollRun(run_id);
  } catch (err) {
    analyzeBtn.disabled = false;
    progressEl.hidden = true;
    statusEl.textContent = err.message;
  }
}

async function pollRun(runId) {
  const base = apiBase();
  if (pollTimer) clearTimeout(pollTimer);
  try {
    const info = await (await fetch(`${base}/runs/${runId}`)).json();
    if (info.status === 'error') {
      analyzeBtn.disabled = false;
      progressEl.innerHTML = '<div class="muted" style="padding:40px;text-align:center">Analysis failed — check the server logs.</div>';
      return;
    }
    if (info.status === 'done') {
      analyzeBtn.disabled = false;
      await loadReport(runId);
      progressEl.hidden = true;
      return;
    }
    showAnim();
  } catch (err) {
    statusEl.textContent = err.message;
  }
  pollTimer = setTimeout(() => pollRun(runId), 1500);
}

async function loadReport(runId) {
  const base = apiBase();
  const rep = await (await fetch(`${base}/runs/${runId}/report`)).json();
  currentRunId = runId;
  lastReport = rep;
  renderReport(rep);
}

// --- rendering --------------------------------------------------------------
function renderReport(rep) {
  const own = rep.own || {};
  const comps = rep.competitors || [];
  reportEl.innerHTML =
    `<div class="own-summary">
       <div class="lbl">Your homepage</div>
       <h2>${esc(own.title || prettyDomain(own.domain))}</h2>
       <div class="meta">${esc(prettyDomain(own.domain))} · ${own.headline_count || 0} headlines · ${own.paragraph_count || 0} paragraphs</div>
       ${extractedText(own)}
     </div>
     <p class="legend-line">Every score is a <b>0–100 similarity index</b> (not a percentage): <b>100</b> = essentially identical, <b>0</b> = unrelated. <b class="sem">Meaning</b> = same ideas, even in different words. <b class="lex">Wording</b> = the same actual words/phrases.</p>
     ${comps.length >= 1 ? scatterPanel() : ''}
     <div class="cmp-grid">${comps.map((c, i) => card(c, i)).join('') || '<p class="muted">No competitors.</p>'}</div>`;
  reportEl.hidden = false;
  if (comps.length) drawScatter();
  statusEl.textContent = `${prettyDomain(own.domain)} vs ${comps.length} competitor${comps.length === 1 ? '' : 's'}`;
}

function gauge(name, cls, val) {
  const na = val == null;
  const pct = na ? 0 : Math.max(0, Math.min(100, val));
  return `<div class="gauge ${cls}">
    <span class="g-name">${name}</span>
    <span class="g-track"><span style="width:${pct}%"></span></span>
    <span class="g-val ${na ? 'na' : ''}">${na ? 'n/a' : Math.round(val)}<span class="g-unit">/100</span></span>
  </div>`;
}

// A collapsible list of the exact headlines + paragraphs we pulled from a page,
// so the user can read what was actually analysed.
function extractedText(m) {
  const sec = (title, items) => `<div class="ex-sec"><h5>${title} <span class="muted">(${(items || []).length})</span></h5>`
    + ((items && items.length)
        ? `<ul>${items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>`
        : '<p class="muted">None found.</p>') + `</div>`;
  return `<details class="extracted">
    <summary>Read the text we analysed</summary>
    <div class="ex-body">${sec('Headlines', m.headlines)}${sec('Paragraphs', m.paragraphs)}</div>
  </details>`;
}

function card(c, i) {
  const s = c.scores || {};
  const chips = arr => arr && arr.length
    ? arr.map(p => `<span class="chip">${esc(p)}</span>`).join('')
    : '<span class="muted">— none —</span>';
  const whyLabel = c.explanation_ai ? 'Why · AI explains' : 'Why · how these compare';
  return `<div class="cmp-card">
    <h3><span class="swatch" style="background:${cmpColor(i)}"></span>${esc(prettyDomain(c.domain))}</h3>
    <div class="title">${esc(c.title || '')}</div>
    <div class="gauge-group"><h4>Headlines</h4>
      ${gauge('Meaning', 'sem', s.headline_semantic)}
      ${gauge('Wording', 'lex', s.headline_lexical)}
    </div>
    <div class="gauge-group"><h4>Paragraphs</h4>
      ${gauge('Meaning', 'sem', s.paragraph_semantic)}
      ${gauge('Wording', 'lex', s.paragraph_lexical)}
    </div>
    <div class="shared"><div class="lbl">Shared phrases (headlines):</div>${chips(c.shared_headlines)}</div>
    ${c.explanation ? `<div class="explain"><div class="lbl">${whyLabel}</div>${esc(c.explanation)}</div>` : ''}
    ${extractedText(c)}
  </div>`;
}

// --- scatter (semantic × lexical) -------------------------------------------
function scatterPanel() {
  const seg = (id, label) =>
    `<button data-section="${id}" class="${scatterSection === id ? 'active' : ''}">${label}</button>`;
  return `<div class="scatter-panel">
    <div class="scatter-head">
      <h3>Positioning — meaning vs wording</h3>
      <div class="seg">${seg('headline', 'Headlines')}${seg('paragraph', 'Paragraphs')}</div>
    </div>
    <p class="scatter-note">Both axes are a <b>0–100 similarity index</b> — not a percentage.
      Higher = more similar to your homepage. Dots show <code>(meaning, wording)</code>.</p>
    <div class="scatter" id="scatter"></div>
  </div>`;
}

function drawScatter() {
  const el = document.getElementById('scatter');
  if (!el || !lastReport) return;
  const pts = (lastReport.competitors || []).map((c, i) => ({
    name: prettyDomain(c.domain), color: cmpColor(i),
    x: c.scores?.[`${scatterSection}_semantic`],
    y: c.scores?.[`${scatterSection}_lexical`],
  })).filter(p => p.x != null && p.y != null);

  const W = 660, H = 380, m = { l: 54, r: 130, t: 20, b: 46 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  // Auto-fit each axis to the data (scores cluster in a narrow band), with padding.
  const fit = (vals) => {
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (hi - lo < 1) { lo -= 5; hi += 5; }             // avoid zero range
    const pad = (hi - lo) * 0.18;
    return [Math.max(0, lo - pad), Math.min(100, hi + pad)];
  };
  const [x0, x1] = fit(pts.map(p => p.x));
  const [y0, y1] = fit(pts.map(p => p.y));
  const px = v => m.l + ((v - x0) / (x1 - x0)) * iw;
  const py = v => m.t + ih - ((v - y0) / (y1 - y0)) * ih;

  // Gridlines + numeric tick labels on both axes so values are readable.
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const gridTicks = ticks.map(f => {
    const gx = m.l + f * iw, gy = m.t + ih - f * ih;
    const xv = Math.round(x0 + f * (x1 - x0)), yv = Math.round(y0 + f * (y1 - y0));
    const lines = (f > 0 && f < 1)
      ? `<line class="grid" x1="${gx}" y1="${m.t}" x2="${gx}" y2="${m.t + ih}"/>`
      + `<line class="grid" x1="${m.l}" y1="${gy}" x2="${m.l + iw}" y2="${gy}"/>` : '';
    return lines
      + `<text class="tick" x="${gx}" y="${m.t + ih + 16}" text-anchor="middle">${xv}</text>`
      + `<text class="tick" x="${m.l - 8}" y="${gy + 4}" text-anchor="end">${yv}</text>`;
  }).join('');

  const dots = pts.map(p => {
    const x = px(p.x), y = py(p.y);
    const label = `${esc(p.name)} (${Math.round(p.x)}, ${Math.round(p.y)})`;
    // Keep the label on-canvas: flip it left of the dot when near the right edge.
    const flip = x > m.l + iw - 96;
    const tx = flip ? x - 9 : x + 9, anchor = flip ? "end" : "start";
    return `<circle class="dot" cx="${x}" cy="${y}" r="5" fill="${p.color}"/>`
         + `<text class="dot-label" x="${tx}" y="${y + 4}" text-anchor="${anchor}" fill="${p.color}">${label}</text>`;
  }).join('');

  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}">
    <rect x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="#fff" stroke="var(--line)"/>
    ${gridTicks}
    <text class="axis-label" x="${m.l + iw / 2}" y="${H - 6}" text-anchor="middle">Meaning score →  (same ideas, 0–100)</text>
    <text class="axis-label" transform="translate(14,${m.t + ih / 2}) rotate(-90)" text-anchor="middle">Wording score →  (same words, 0–100)</text>
    ${dots}
  </svg>`;
}

// --- search history ---------------------------------------------------------
const MAX_COMPETITORS = 5;

function showTab(name) {
  document.querySelectorAll('.tab').forEach(t =>
    t.classList.toggle('active', t.dataset.tab === name));
  document.getElementById('tab-compare').hidden = name !== 'compare';
  document.getElementById('tab-history').hidden = name !== 'history';
  if (name === 'history') showHistory();
}

async function showHistory() {
  const base = apiBase();
  const el = document.getElementById('history');
  if (!base || !el) return;
  el.innerHTML = '<div class="muted">Loading history…</div>';
  try {
    const runs = (await (await fetch(`${base}/runs`)).json()).runs || [];
    if (!runs.length) {
      el.innerHTML = '<div class="muted">No comparisons yet — run one above.</div>';
      return;
    }
    el.innerHTML = '<h3 class="hist-h">Recent comparisons</h3>' + runs.map(r => {
      const comps = (r.competitors || []).map(prettyDomain).join(', ') || '—';
      const when = (r.created_at || '').replace('T', ' ').slice(0, 16);
      const badge = r.status === 'done' ? '' : `<span class="hi-status">${esc(r.status)}</span>`;
      return `<a class="hist-item" href="?run=${r.run_id}">
        <span class="hi-main"><b>${esc(prettyDomain(r.own_domain))}</b>
          <span class="hi-vs">vs</span> ${esc(comps)}</span>
        <span class="hi-meta">${esc(when)}${badge}</span>
      </a>`;
    }).join('');
  } catch (e) {
    el.innerHTML = '<div class="muted">Could not load history.</div>';
  }
}

// --- boot -------------------------------------------------------------------
document.getElementById('analyzeForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const own = document.getElementById('ownDomain').value.trim();
  if (!own) return;
  let comps = document.getElementById('compDomains').value
    .split(',').map(s => s.trim()).filter(Boolean);
  if (comps.length > MAX_COMPETITORS) {
    comps = comps.slice(0, MAX_COMPETITORS);
    statusEl.textContent = `Up to ${MAX_COMPETITORS} competitors — comparing the first ${MAX_COMPETITORS}.`;
  }
  startAnalysis(own, comps);
});

document.querySelectorAll('.tab').forEach(t =>
  t.addEventListener('click', () => showTab(t.dataset.tab)));

// Open a past comparison without a full reload: switch to the Compare tab.
document.getElementById('history').addEventListener('click', (e) => {
  const a = e.target.closest('.hist-item');
  if (!a) return;
  e.preventDefault();
  const id = new URL(a.href, location.origin).searchParams.get('run');
  history.replaceState(null, '', `?run=${id}`);
  currentRunId = parseInt(id, 10);
  showTab('compare');
  loadReport(currentRunId);
});

reportEl.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-section]');
  if (!btn) return;
  scatterSection = btn.dataset.section;
  reportEl.querySelectorAll('.seg button').forEach(b =>
    b.classList.toggle('active', b.dataset.section === scatterSection));
  drawScatter();
});

const qsRun = new URLSearchParams(location.search).get('run');
if (qsRun) {
  const base = apiBase();
  if (base) {
    fetch(`${base}/runs/${qsRun}`).then(r => r.json()).then(info => {
      currentRunId = parseInt(qsRun, 10);
      if (info.status === 'done') loadReport(currentRunId);
      else if (info.status && info.status !== 'error') { showAnim(); pollRun(currentRunId); }
      else statusEl.textContent = 'That run did not finish — start a new comparison.';
    }).catch(() => { statusEl.textContent = 'Could not load that run.'; });
  }
}
// Default view is the Compare tab; History is one click away.
