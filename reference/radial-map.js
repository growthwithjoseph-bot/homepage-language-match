// Reference radial coverage-map generator (ported from the Trendible prototype).
// Renders a /runs/{id}/map payload as a radial topic tree:
//   root (own domain) -> category nodes (inner ring) -> topic leaves (outer ring).
// Node colour = coverage state. Clicking a leaf calls onTopicClick(topicId).
//
// Usage:
//   renderRadialMap(document.getElementById('map'), mapPayload, onTopicClick);
//
// mapPayload shape (see SPEC §8):
//   { own_domain, competitors:[...], categories:[ {id,label,topics:[{id,label,state,you_pct,competitors_pct}]} ] }

const STATE_COLOR = {
  only_you:  '#15803d',
  you_lead:  '#22c55e',
  even:      '#94a3b8',
  comp_lead: '#fb923c',
  only_comp: '#ef4444',
};
const CATEGORY_COLOR = '#64748b';

function renderRadialMap(container, map, onTopicClick) {
  const cx = 560, cy = 560, rCat = 210, rLeaf = 345, rLabel = 357;
  const cats = map.categories || [];
  let total = 0; cats.forEach(c => total += (c.topics || []).length);
  const gapSlots = 1.0;
  const totalSlots = total + cats.length * gapSlots;
  const step = (Math.PI * 2) / totalSlots;

  let slot = 0, edges = '', leafDots = '', catNodes = '', labels = '';

  cats.forEach((cat) => {
    const angs = [];
    (cat.topics || []).forEach((t) => {
      const ang = -Math.PI / 2 + (slot + 0.5) * step; slot++; angs.push(ang);
      const lx = cx + rLeaf * Math.cos(ang), ly = cy + rLeaf * Math.sin(ang);
      const left = Math.cos(ang) < 0, deg = ang * 180 / Math.PI;
      const tx = cx + rLabel * Math.cos(ang), ty = cy + rLabel * Math.sin(ang);
      const rot = left ? deg + 180 : deg, anchor = left ? 'end' : 'start';
      const color = STATE_COLOR[t.state] || '#94a3b8';
      leafDots += `<circle class="tc-node" data-id="${t.id}" cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="5" fill="${color}" stroke="#fff" stroke-width="0" style="cursor:pointer;"/>`;
      labels += `<text class="tc-label" data-id="${t.id}" x="${tx.toFixed(1)}" y="${ty.toFixed(1)}" transform="rotate(${rot.toFixed(1)} ${tx.toFixed(1)} ${ty.toFixed(1)})" text-anchor="${anchor}" dominant-baseline="middle" font-size="10.5" fill="#94a3b8" style="cursor:pointer;">${t.label}</text>`;
    });
    if (!angs.length) return;
    const catAng = angs.reduce((a, b) => a + b, 0) / angs.length;
    const ccx = cx + rCat * Math.cos(catAng), ccy = cy + rCat * Math.sin(catAng);
    edges += `<line x1="${cx}" y1="${cy}" x2="${ccx.toFixed(1)}" y2="${ccy.toFixed(1)}" stroke="#475569" stroke-opacity="0.4" stroke-width="1.3"/>`;
    angs.forEach((ang) => {
      const lx = cx + rLeaf * Math.cos(ang), ly = cy + rLeaf * Math.sin(ang);
      const mx = cx + (rCat + 40) * Math.cos(ang), my = cy + (rCat + 40) * Math.sin(ang);
      edges += `<path d="M ${ccx.toFixed(1)} ${ccy.toFixed(1)} Q ${mx.toFixed(1)} ${my.toFixed(1)} ${lx.toFixed(1)} ${ly.toFixed(1)}" fill="none" stroke="#cbd5e1" stroke-opacity="0.45" stroke-width="0.8"/>`;
    });
    catNodes += `<circle cx="${ccx.toFixed(1)}" cy="${ccy.toFixed(1)}" r="6.5" fill="${CATEGORY_COLOR}"/>`;
    const offY = Math.sin(catAng) < 0 ? -12 : 18;
    catNodes += `<text x="${ccx.toFixed(1)}" y="${(ccy + offY).toFixed(1)}" text-anchor="middle" font-size="12" font-weight="700" fill="#334155" style="pointer-events:none;">${cat.label}</text>`;
    slot += gapSlots;
  });

  const root = (map.own_domain || 'domain').split('.')[0].toUpperCase();
  const rootSvg = `<circle cx="${cx}" cy="${cy}" r="34" fill="#475569"/>` +
    `<text x="${cx}" y="${cy - 2}" text-anchor="middle" font-size="12" font-weight="800" fill="#fff" style="pointer-events:none;">${root}</text>` +
    `<text x="${cx}" y="${cy + 13}" text-anchor="middle" font-size="8.5" fill="#cbd5e1" style="pointer-events:none;">topic coverage</text>`;

  container.innerHTML =
    `<svg viewBox="0 0 1120 1130" style="width:100%;height:auto;">` +
      `<g>${edges}</g>${leafDots}${labels}${catNodes}${rootSvg}` +
    `</svg>`;

  if (onTopicClick) {
    container.querySelectorAll('.tc-node, .tc-label').forEach(el => {
      el.addEventListener('click', () => onTopicClick(el.getAttribute('data-id')));
    });
  }
}

if (typeof module !== 'undefined') module.exports = { renderRadialMap, STATE_COLOR };
