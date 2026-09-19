/* BrainerLab frontend — connectome explorer, lab, reports + scientific visualizations. No build step. */
const $ = s => document.querySelector(s);
const api = async (p, o = {}) => {
  const r = await fetch(p, { headers: { 'Content-Type': 'application/json', 'X-Role': 'researcher' }, ...o });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* tabs (any [data-tab] element: header nav, logo, hero CTAs, footer) */
const TABS = ['home', 'explore', 'species', 'datasets', 'lab', 'experiments', 'research', 'api', 'campus', 'about'];
function goto(tab, push = true) {
  if (!TABS.includes(tab)) return;
  document.querySelectorAll('[data-tab]').forEach(x => x.classList.remove('active'));
  document.querySelectorAll(`[data-tab="${tab}"]`).forEach(x => x.classList.add('active'));
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  $('#tab-' + tab).classList.add('active');
  if (push) history.replaceState(null, '', '#/' + tab);
}
document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => goto(b.dataset.tab));
addEventListener('hashchange', () => {
  const t = location.hash.replace('#/', '');
  if (TABS.includes(t)) goto(t, false);
});
function skel(sel, n = 3) {
  const el = $(sel); if (el) el.innerHTML = Array(n).fill('<div class="skel"></div>').join('');
}
document.addEventListener('click', e => {
  const g = e.target.closest('[data-goto-exp]');
  if (g) { e.preventDefault(); openExperiment(g.dataset.gotoExp); }
});

/* home + species + datasets */
async function init() {
  skel('#home-stats', 1); skel('#species-list', 3); skel('#dataset-list', 3); skel('#exp-list', 2);
  try {
    const [sp, ds] = await Promise.all([api('/api/species'), api('/api/datasets')]);
    renderStatStrip(sp, ds);
    renderSpecies(sp, ds);
    renderDatasets(ds);
    fillDatasetSelects(ds.datasets.filter(d => d.bundled_nodes != null));
  } catch (e) {
    for (const s of ['#home-stats', '#species-list', '#dataset-list'])
      $(s).innerHTML = `<p class="note">Failed to load: ${esc(e.message)} — <a href="#" onclick="init();return false">retry</a></p>`;
  }
  buildApiTable();
  const safe = (fn, sel) => { try { const r = fn(); if (r && r.catch) r.catch(e => { if (sel) $(sel).innerHTML = `<p class="note">Failed to load: ${esc(e.message)}</p>`; }); } catch (e) { if (sel) $(sel).innerHTML = `<p class="note">Failed to load: ${esc(e.message)}</p>`; } };
  safe(loadExplorer, '#node-info'); safe(refreshExpList, '#exp-list');
  safe(initHero); safe(initDemo);
  const m = location.pathname.match(/\/experiment\/(NL-EXP-\d+)/);
  if (m) openExperiment(m[1]);
  else {
    const t = location.hash.replace('#/', '');
    if (TABS.includes(t) && t !== 'home') goto(t, false);
  }
}
function fillDatasetSelects(bundled) {
  for (const sel of ['#exp-dataset', '#lab-dataset']) {
    const el = $(sel), cur = el.value;
    el.innerHTML = bundled.map(d => `<option value="${d.id}">${esc(d.id)} (v${esc(d.version)})</option>`).join('');
    if (cur && bundled.some(d => d.id === cur)) el.value = cur;
  }
}
async function refreshDatasets() {
  const ds = await api('/api/datasets');
  renderDatasets(ds);
  fillDatasetSelects(ds.datasets.filter(d => d.bundled_nodes != null));
}
function renderStatStrip(sp, ds) {
  const neurons = ds.datasets.reduce((a, d) => a + (d.bundled_nodes || 0), 0);
  const edges = ds.datasets.reduce((a, d) => a + (d.bundled_edges || 0), 0);
  const stat = (n, l) => `<div><div class="n">${n}</div><div class="l">${l}</div></div>`;
  $('#home-stats').innerHTML =
    stat(sp.species.length, 'SPECIES') + stat(ds.datasets.length, 'DATASETS') +
    stat(neurons, 'BUNDLED NEURONS') + stat(edges, 'BUNDLED EDGES');
}
function statusPill(s) {
  return s === 'active' ? '<span class="status-pill st-active">ACTIVE</span>'
    : `<span class="status-pill st-idle">${esc(s.toUpperCase().replace(/_/g, ' '))}</span>`;
}
function glyph(seed) {
  /* decorative schematic tick-strip; labelled as schematic, derived from row index only */
  let h = 0; for (const c of seed) h = (h * 31 + c.charCodeAt(0)) % 997;
  const xs = [8, 26, 48, 70, 92];
  const ys = xs.map((_, i) => 14 + ((h >> (i * 2)) % 3 - 1) * 7);
  const dots = xs.map((x, i) => `<circle cx="${x}" cy="${ys[i]}" r="${i === 2 ? 4 : 2.5}" fill="${i === 2 ? '#6FB1FF' : 'none'}" stroke="#A9B0B7" stroke-width="1.2"/>`).join('');
  const lines = xs.slice(1).map((x, i) => `<line x1="${xs[i]}" y1="${ys[i]}" x2="${x}" y2="${ys[i + 1]}" stroke="rgba(255,255,255,.22)" stroke-width="1"/>`).join('');
  return `<svg class="sp-glyph" width="104" height="30" viewBox="0 0 104 30" role="img" aria-label="circuit schematic"><title>schematic</title>${lines}${dots}</svg>`;
}
function renderSpecies(sp, ds) {
  $('#species-list').innerHTML = sp.species.map((s, i) => {
    const mine = ds.datasets.filter(d => d.species === s.id);
    const hasBundled = mine.some(d => d.bundled_nodes != null);
    return `<div class="sp-row">
      <div class="sp-idx">${String(i + 1).padStart(2, '0')}</div>
      <div>
        <div class="sp-taxon">${esc(s.taxon)}</div>
        <div class="sp-common">${esc(s.common_name)}</div>
        ${s.note ? `<div class="sp-note">${esc(s.note)}</div>` : ''}
        <div class="sp-ds">${mine.map(d =>
          `<div class="sp-ds-row"><b>${esc(d.name)}</b> · ${esc(d.neurons)} · ${esc(d.synapses)} · ${esc(d.status)}</div>`).join('') || '<div class="sp-ds-row">no registry datasets</div>'}</div>
      </div>
      <div class="sp-side">${statusPill(s.status)}${glyph(s.id)}
        <button class="btn-ghost" data-tab="${hasBundled ? 'explore' : 'datasets'}">${hasBundled ? 'Explore circuit →' : 'View datasets →'}</button>
      </div>
    </div>`;
  }).join('');
  document.querySelectorAll('#species-list [data-tab]').forEach(b => b.onclick = () => goto(b.dataset.tab));
}
function renderDatasets(ds) {
  $('#dataset-list').innerHTML = ds.datasets.map(d =>
    `<div class="ds-row"><div class="ds-top"><b>${esc(d.name)}</b><span class="tag">${esc(d.status)}</span>
    ${d.bundled_nodes != null ? `<span class="tag">bundled: ${d.bundled_nodes} nodes / ${d.bundled_edges} edges</span>` : ''}</div>
    <div class="ds-grid">
      <div><span class="k">SPECIES</span>${esc(d.species)}</div>
      <div><span class="k">VERSION</span>${esc(d.version)}</div>
      <div><span class="k">LICENCE</span>${esc(d.license)}</div>
      <div><span class="k">NEURONS</span>${esc(d.neurons)}</div>
      <div><span class="k">SYNAPSES</span>${esc(d.synapses)}</div>
      <div><span class="k">SOURCE</span>${esc(d.source || '—')}</div>
      <div><span class="k">PUBLICATION</span>${esc(d.publication || '—')}</div>
      <div><span class="k">COMPLETENESS</span>${esc(d.completeness)}</div>
    </div>
    <div class="note" style="margin-top:.4em">limits: ${esc(d.limitations)}</div>
    ${d.status === 'imported' ? `<div style="margin-top:.5em"><button class="btn-ghost" data-del="${d.id}">Delete import</button></div>` : ''}</div>`).join('');
  document.querySelectorAll('#dataset-list [data-del]').forEach(b => b.onclick = async () => {
    if (!confirm(`Delete imported dataset ${b.dataset.del}?`)) return;
    try { await api(`/api/datasets/import/${b.dataset.del}`, { method: 'DELETE' }); refreshDatasets(); loadExplorer(); }
    catch (e) { alert(e.message); }
  });
}
async function buildApiTable() {
  const rows = [['GET /api/species', 'species'], ['GET /api/datasets', 'registry + bundled counts'],
    ['GET /api/neurons?dataset_id=&q=&type=&region=', 'paginated neurons'],
    ['GET /api/connections?dataset_id=&source=&target=&kind=', 'paginated edges'],
    ['GET /api/graph/subgraph?dataset_id=&seeds=&depth=&direction=&kind=', 'capped subgraph (≤400)'],
    ['GET+POST /api/experiments', 'reproducible experiment records (author signed when logged in)'],
    ['GET /api/experiments?author=', 'filter experiments by author'],
    ['POST /api/simulations', 'run normal + modified arms'], ['GET /api/results/{id}', 'spikes + summaries'],
    ['GET /api/reports/{id}', 'experimental report'], ['GET /api/provenance/{id}', 'dataset→…→result chain'],
    ['POST /api/datasets/import', 'upload your own circuit JSON (≤1000 nodes, validated)'],
    ['DELETE /api/datasets/import/{id}', 'remove your imported dataset'],
    ['POST /api/ai/explain', 'labelled assistant (FACT/SIMULATION/HYPOTHESIS/INTERPRETATION)']];
  $('#api-table').innerHTML = '<tr><th>endpoint</th><th>use</th></tr>' + rows.map(r => `<tr><td class="mono">${r[0]}</td><td>${r[1]}</td></tr>`).join('');
}

/* explorer */
const net = { nodes: [], edges: [], pos: {}, sel: null, zoom: 1, ox: 0, oy: 0 };
function nodeColor(t) { return t === 'sensory' ? '#6FB1FF' : t === 'interneuron' ? '#9B8FFF' : t === 'motor' ? '#E0B26A' : '#5A636C'; }
async function fetchAll(path, key, cap) {
  const out = []; let offset = 0;
  for (let i = 0; i < 12 && out.length < cap; i++) {
    const r = await api(`${path}&limit=500&offset=${offset}`);
    if (!r[key].length) break;
    out.push(...r[key]);
    if (out.length >= r.total) break;
    offset += 500;
  }
  return out;
}
async function loadExplorer() {
  const id = $('#exp-dataset').value; if (!id) return;
  $('#exp-ds-tag').textContent = id;
  $('#node-info').textContent = 'Loading graph…';
  const [neurons, conns] = await Promise.all([
    fetchAll(`/api/neurons?dataset_id=${id}`, 'neurons', 3000),
    fetchAll(`/api/connections?dataset_id=${id}`, 'connections', 20000)]);
  const regs = [...new Set(neurons.map(x => x.region).filter(Boolean))];
  $('#exp-region').innerHTML = '<option value="">region: all</option>' + regs.map(r => `<option>${esc(r)}</option>`).join('');
  setGraph(neurons, conns);
}
function setGraph(nodes, edges) {
  const t = $('#exp-type').value, r = $('#exp-region').value;
  nodes = nodes.filter(n => (!t || n.type === t) && (!r || n.region === r));
  const show = new Set(nodes.map(n => n.id));
  edges = edges.filter(e => show.has(e.source) && show.has(e.target));
  net.nodes = nodes; net.edges = edges; net.sel = null; net.zoom = 1; net.ox = 0; net.oy = 0;
  net.deg = {};
  for (const e of edges) { net.deg[e.source] = (net.deg[e.source] || 0) + 1; net.deg[e.target] = (net.deg[e.target] || 0) + 1; }
  net.maxDeg = Math.max(1, ...Object.values(net.deg));
  net.hubs = new Set([...nodes].sort((a, b) => (net.deg[b.id] || 0) - (net.deg[a.id] || 0)).slice(0, 15).map(n => n.id));
  net.pos = {};
  nodes.forEach((n, i) => {
    net.pos[n.id] = n.x != null ? { x: 450 + n.x * 45, y: 280 - n.y * 45 }
      : { x: 450 + 220 * Math.cos(2 * Math.PI * i / Math.max(nodes.length, 1)), y: 280 + 220 * Math.sin(2 * Math.PI * i / Math.max(nodes.length, 1)) };
  });
  drawNet(); $('#node-info').textContent = `${nodes.length} nodes, ${edges.length} edges shown.`;
  if (v3.mode === '3d') buildScene3D();
}
function drawNet() {
  const cv = $('#net'), ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.save(); ctx.translate(net.ox, net.oy); ctx.scale(net.zoom, net.zoom);
  const show = new Set(net.nodes.map(n => n.id));
  const crowded = net.nodes.length > 70;
  const nb = new Set();
  if (net.sel) for (const e of net.edges) { if (e.source === net.sel) nb.add(e.target); else if (e.target === net.sel) nb.add(e.source); }
  for (const e of net.edges) {
    if (!show.has(e.source) || !show.has(e.target)) continue;
    const a = net.pos[e.source], b = net.pos[e.target]; if (!a || !b) continue;
    const hot = net.sel && (e.source === net.sel || e.target === net.sel);
    ctx.strokeStyle = hot ? '#6FB1FF' : (e.kind === 'electrical' ? 'rgba(255,255,255,.13)' : 'rgba(255,255,255,.09)');
    ctx.lineWidth = hot ? 1.6 : 1;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    if (hot) { // arrowhead
      const ang = Math.atan2(b.y - a.y, b.x - a.x);
      ctx.fillStyle = '#6FB1FF'; ctx.beginPath();
      ctx.moveTo(b.x - 8 * Math.cos(ang - .3), b.y - 8 * Math.sin(ang - .3));
      ctx.lineTo(b.x, b.y); ctx.lineTo(b.x - 8 * Math.cos(ang + .3), b.y - 8 * Math.sin(ang + .3)); ctx.fill();
    }
  }
  for (const n of net.nodes) {
    const p = net.pos[n.id], sel = n.id === net.sel;
    const rad = 5 + 8 * Math.sqrt((net.deg[n.id] || 0) / net.maxDeg);
    if (sel) { ctx.shadowColor = 'rgba(111,177,255,.7)'; ctx.shadowBlur = 10; }
    ctx.fillStyle = nodeColor(n.type);
    ctx.beginPath(); ctx.arc(p.x, p.y, sel ? rad + 3 : rad, 0, 7); ctx.fill();
    ctx.shadowBlur = 0;
    if (!crowded || sel || nb.has(n.id) || net.hubs.has(n.id)) {
      ctx.fillStyle = '#F2F4F3'; ctx.font = '11px "IBM Plex Mono",monospace'; ctx.fillText(n.id, p.x + rad + 4, p.y + 4);
    }
  }
  ctx.restore();
}
function canvasNode(ev) {
  const cv = $('#net'), r = cv.getBoundingClientRect();
  const scale = cv.width / r.width;
  const x = (ev.clientX - r.left) * scale, y = (ev.clientY - r.top) * scale;
  const tol = 16 * scale;
  let best = null, bd = tol * tol;
  for (const n of net.nodes) {
    const p = net.pos[n.id];
    const d = ((p.x * net.zoom + net.ox - x) ** 2 + (p.y * net.zoom + net.oy - y) ** 2);
    if (d < bd) { bd = d; best = n; }
  }
  return best;
}
$('#net').addEventListener('click', async ev => {
  const n = canvasNode(ev);
  if (!n) {
    net.sel = null; drawNet();
    $('#net-tip').style.display = 'none';
    $('#node-info').textContent = `${net.nodes.length} nodes, ${net.edges.length} edges shown. Click a node, or search.`;
    if (v3.mode === '3d') buildScene3D();
    return;
  }
  await selectNeuron(n.id);
});
$('#net').addEventListener('dblclick', ev => {
  const n = canvasNode(ev); if (n) subgraph(n.id);
});
async function selectNeuron(id) {
  const ds = $('#exp-dataset').value;
  const d = await api(`/api/neurons/${id}?dataset_id=${ds}`);
  net.sel = d.neuron.id; drawNet();
  const fmt = l => {
    if (!l.length) return '—';
    const shown = l.slice(0, 15).map(e => `<a href="#" data-n="${e.source === id ? e.target : e.source}">${e.source === id ? e.target : e.source}</a>`).join(', ');
    return shown + (l.length > 15 ? ` <span class="note">… +${l.length - 15} more</span>` : '');
  };
  $('#node-info').innerHTML = `<b class="mono">${esc(d.neuron.id)}</b> <span class="tag">${esc(d.neuron.type || '?')}</span><br>
    <span class="note">class ${esc(d.neuron.class || '—')} · region ${esc(d.neuron.region || '—')}</span><br>
    <span class="note">${esc(d.neuron.function || '')}</span><br>
    degree (chemical): in ${d.degree.chemical.in} / out ${d.degree.chemical.out}<br>
    in: ${fmt(d.in_chemical)}<br>out: ${fmt(d.out_chemical)}<br>
    <button id="nb-sub">subgraph 1-hop</button> <button id="nb-lab">→ use in Lab</button>`;
  $('#nb-sub').onclick = () => subgraph(id);
  $('#nb-lab').onclick = () => { $('#lab-silence').value = id; goto('lab'); };
  document.querySelectorAll('#node-info [data-n]').forEach(a => a.onclick = e => { e.preventDefault(); selectNeuron(a.dataset.n); });
}
$('#net').addEventListener('wheel', e => {
  e.preventDefault();
  const cv = $('#net'), r = cv.getBoundingClientRect();
  const scale = cv.width / r.width;
  const mx = (e.clientX - r.left) * scale, my = (e.clientY - r.top) * scale;
  const z0 = net.zoom, z1 = Math.min(4, Math.max(.3, z0 * (e.deltaY < 0 ? 1.12 : .89)));
  net.ox = mx - (mx - net.ox) * (z1 / z0);
  net.oy = my - (my - net.oy) * (z1 / z0);
  net.zoom = z1; drawNet();
}, { passive: false });
/* unified mouse + touch: 1-finger drag pans, 2-finger pinch zooms */
const ptrs = new Map();
$('#net').addEventListener('pointerdown', e => { $('#net').setPointerCapture(e.pointerId); ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY }); });
$('#net').addEventListener('pointermove', e => {
  if (!ptrs.has(e.pointerId)) return;
  const prev = ptrs.get(e.pointerId);
  if (ptrs.size === 1) { net.ox += e.clientX - prev.x; net.oy += e.clientY - prev.y; drawNet(); }
  else if (ptrs.size === 2) {
    const other = [...ptrs.entries()].find(([id]) => id !== e.pointerId);
    if (other) {
      const d0 = Math.hypot(prev.x - other[1].x, prev.y - other[1].y);
      const d1 = Math.hypot(e.clientX - other[1].x, e.clientY - other[1].y);
      if (d0 > 0) { net.zoom = Math.min(4, Math.max(.3, net.zoom * d1 / d0)); drawNet(); }
    }
  }
  ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
});
for (const ev of ['pointerup', 'pointercancel', 'pointerleave']) $('#net').addEventListener(ev, e => ptrs.delete(e.pointerId));
/* hover preview (mouse only, hidden while panning) */
$('#net').addEventListener('pointermove', e => {
  const tip = $('#net-tip');
  if (e.pointerType !== 'mouse' || ptrs.size) { tip.style.display = 'none'; return; }
  const n = canvasNode(e);
  if (!n) { tip.style.display = 'none'; return; }
  const r = $('#net').getBoundingClientRect();
  tip.style.display = 'block';
  tip.style.left = (e.clientX - r.left + 14) + 'px';
  tip.style.top = (e.clientY - r.top + 12) + 'px';
  tip.textContent = `${n.id} · ${n.type || '?'} · deg ${net.deg[n.id] || 0}`;
});
$('#net').addEventListener('pointerleave', () => $('#net-tip').style.display = 'none');
/* search autocomplete */
let sugTimer = null;
$('#exp-search').addEventListener('input', e => {
  clearTimeout(sugTimer);
  const q = e.target.value.trim(), box = $('#exp-suggest');
  if (q.length < 2) { box.style.display = 'none'; return; }
  sugTimer = setTimeout(async () => {
    try {
      const ds = $('#exp-dataset').value; if (!ds) return;
      const r = await api(`/api/neurons?dataset_id=${ds}&q=${encodeURIComponent(q)}&limit=8`);
      if (!r.neurons.length) { box.style.display = 'none'; return; }
      box.innerHTML = r.neurons.map(n => `<button data-sug="${esc(n.id)}"><span class="mono">${esc(n.id)}</span> <span class="mono">· ${esc(n.type || '?')}</span></button>`).join('');
      box.style.display = 'block';
      box.querySelectorAll('[data-sug]').forEach(b => b.onmousedown = ev => {
        ev.preventDefault(); box.style.display = 'none';
        $('#exp-search').value = b.dataset.sug;
        selectNeuron(b.dataset.sug).catch(() => $('#node-info').textContent = 'Neuron not found.');
      });
    } catch (err) { box.style.display = 'none'; }
  }, 180);
});
$('#exp-search').addEventListener('keydown', e => { if (e.key === 'Escape') $('#exp-suggest').style.display = 'none'; });
$('#exp-search').addEventListener('blur', () => setTimeout(() => $('#exp-suggest').style.display = 'none', 150));
$('#exp-dataset').onchange = loadExplorer;
$('#exp-reset').onclick = loadExplorer;
$('#exp-search').onchange = e => selectNeuron(e.target.value.trim().toUpperCase()).catch(() => $('#node-info').textContent = 'Neuron not found.');
$('#exp-subgraph').onclick = () => subgraph(net.sel || $('#exp-search').value.trim().toUpperCase());
async function subgraph(seed) {
  if (!seed) return;
  const ds = $('#exp-dataset').value;
  const g = await api(`/api/graph/subgraph?dataset_id=${ds}&seeds=${encodeURIComponent(seed)}&depth=${$('#exp-depth').value}&direction=${$('#exp-dir').value}`);
  const t = $('#exp-type').value, r = $('#exp-region').value;
  setGraph(g.nodes.filter(n => (!t || n.type === t) && (!r || n.region === r)), g.edges);
}

/* ---- 3D explorer (three.js lazy CDN, same data + same inspector) ---- */
const v3 = { mode: '2d', three: null, renderer: null, scene: null, camera: null, controls: null, mesh: null, ids: [], pos3: {}, keep: 0 };
async function ensureThree() {
  if (v3.three) return v3.three;
  const THREE = await import('three');
  const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
  v3.three = { THREE, OrbitControls };
  return v3.three;
}
function layout3D(nodes) {
  /* x/y from data when present (schematic, display-only); z layered by type.
     No x/y (e.g. some imports) -> circular fallback. Always illustrative. */
  const pos = {};
  nodes.forEach((n, i) => {
    let x, y;
    if (n.x != null && n.y != null) { x = n.x * 45; y = -n.y * 45; }
    else { const a = 2 * Math.PI * i / Math.max(nodes.length, 1); x = 200 * Math.cos(a); y = 200 * Math.sin(a); }
    const layer = n.type === 'sensory' ? 60 : n.type === 'motor' ? -60 : 0;
    let h = 0; for (const c of n.id) h = (h * 31 + c.charCodeAt(0)) % 97;
    pos[n.id] = { x, y, z: layer + (h - 48) * 0.6 };
  });
  return pos;
}
async function setView3D(on) {
  v3.mode = on ? '3d' : '2d';
  $('#view-2d').classList.toggle('active', !on);
  $('#view-3d').classList.toggle('active', on);
  $('#net').style.display = on ? 'none' : '';
  document.querySelector('.graph-panel .legend').style.display = on ? 'none' : '';
  $('#view3d').style.display = on ? '' : 'none';
  $('#graph-hint').textContent = on ? 'ORBIT: DRAG · ZOOM: WHEEL/PINCH · SELECT: CLICK' : 'ZOOM: WHEEL · PAN: DRAG · SELECT: CLICK';
  if (!on) return;
  try { await ensureThree(); } catch (e) {
    $('#node3d-label').textContent = '3D needs network access to the three.js CDN.';
    $('#node3d-label').style.display = 'block'; return;
  }
  initScene3D();
  buildScene3D();
}
$('#view-2d').onclick = () => setView3D(false);
$('#view-3d').onclick = () => setView3D(true);
function initScene3D() {
  if (v3.renderer) return;
  const { THREE, OrbitControls } = v3.three;
  const box = $('#view3d'), H = 560;
  const W = box.clientWidth || 800;
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(W, H);
  renderer.setClearColor(0x0a101e, 1);
  box.prepend(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, W / H, 1, 6000);
  camera.position.set(0, -120, 640);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = .08;
  scene.add(new THREE.AmbientLight(0xffffff, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(220, 320, 420); scene.add(key);
  const fill = new THREE.DirectionalLight(0x6fb1ff, .5); fill.position.set(-300, -180, 240); scene.add(fill);
  v3.keep = scene.children.length;
  let down = null;
  renderer.domElement.addEventListener('pointerdown', e => { down = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener('click', e => {
    if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 6) onPick3D(e);
    down = null;
  });
  Object.assign(v3, { renderer, scene, camera, controls });
  const loop = () => {
    requestAnimationFrame(loop);
    if (!$('#view3d').offsetParent || v3.mode !== '3d') return;
    controls.update();
    updateLabel3D();
    renderer.render(scene, camera);
  };
  loop();
  addEventListener('resize', () => {
    if (!v3.renderer || v3.mode !== '3d') return;
    const w = box.clientWidth || 800;
    v3.camera.aspect = w / H; v3.camera.updateProjectionMatrix();
    v3.renderer.setSize(w, H);
  });
}
function buildScene3D() {
  if (!v3.renderer || v3.mode !== '3d') return;
  const { THREE } = v3.three;
  while (v3.scene.children.length > v3.keep) {
    const o = v3.scene.children.pop();
    o.geometry?.dispose?.();
    if (Array.isArray(o.material)) o.material.forEach(m => m.dispose?.());
    else o.material?.dispose?.();
  }
  const nodes = net.nodes;
  if (!nodes.length) return;
  v3.pos3 = layout3D(nodes);
  v3.ids = nodes.map(n => n.id);
  const mesh = new THREE.InstancedMesh(new THREE.SphereGeometry(7, 18, 18),
    new THREE.MeshStandardMaterial({ roughness: .32, metalness: .55 }), nodes.length);
  const m = new THREE.Matrix4(), col = new THREE.Color();
  nodes.forEach((n, i) => {
    const p = v3.pos3[n.id], s = n.id === net.sel ? 1.55 : 1;
    m.makeScale(s, s, s); m.setPosition(p.x, p.y, p.z);
    mesh.setMatrixAt(i, m);
    mesh.setColorAt(i, col.set(nodeColor(n.type)));
  });
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  v3.scene.add(mesh);
  v3.mesh = mesh;
  const pts = [], cls = [];
  for (const e of net.edges) {
    const a = v3.pos3[e.source], b = v3.pos3[e.target];
    if (!a || !b) continue;
    pts.push(a.x, a.y, a.z, b.x, b.y, b.z);
    const hot = net.sel && (e.source === net.sel || e.target === net.sel);
    const c = hot ? [.5, .91, .86] : (e.kind === 'electrical' ? [.32, .35, .38] : [.2, .24, .27]);
    cls.push(...c, ...c);
  }
  const lg = new THREE.BufferGeometry();
  lg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  lg.setAttribute('color', new THREE.Float32BufferAttribute(cls, 3));
  v3.scene.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: .75 })));
  let R = 200;
  for (const id of v3.ids) { const p = v3.pos3[id]; R = Math.max(R, Math.hypot(p.x, p.y, p.z)); }
  const dist = Math.min(2200, R * 2.1);
  v3.camera.position.set(0, -dist * .22, dist);
  v3.controls.target.set(0, 0, 0);
}
function onPick3D(ev) {
  if (!v3.mesh) return;
  const { THREE } = v3.three;
  const r = v3.renderer.domElement.getBoundingClientRect();
  const mouse = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  const hit = new THREE.Raycaster().setFromCamera(mouse, v3.camera).intersectObject(v3.mesh)[0];
  if (hit && hit.instanceId != null) selectNeuron(v3.ids[hit.instanceId]).then(() => buildScene3D()).catch(() => {});
}
function updateLabel3D() {
  const el = $('#node3d-label'), p = net.sel && v3.pos3[net.sel];
  if (!p) { el.style.display = 'none'; return; }
  const { THREE } = v3.three;
  const v = new THREE.Vector3(p.x, p.y, p.z).project(v3.camera);
  if (v.z > 1) { el.style.display = 'none'; return; }
  const box = $('#view3d');
  el.style.display = 'block';
  el.style.left = ((v.x * .5 + .5) * box.clientWidth) + 'px';
  el.style.top = ((-v.y * .5 + .5) * 560) + 'px';
  el.textContent = net.sel;
}

/* lab */
function parseStim(txt) {
  return txt.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
    const [neuron, a, b, c] = l.split(/\s+/);
    return { neuron: neuron.toUpperCase(), t_start_ms: +a, t_end_ms: +b, amplitude: +c };
  });
}
function authHeaders() {
  return campus.token ? { 'Authorization': 'Bearer ' + campus.token } : {};
}
function validateLab() {
  if (!$('#lab-dataset').value) return 'Pick a dataset first.';
  for (const l of $('#lab-stim').value.split('\n').map(x => x.trim()).filter(Boolean)) {
    const p = l.split(/\s+/);
    if (p.length !== 4 || !p[0] || isNaN(+p[1]) || isNaN(+p[2]) || isNaN(+p[3]))
      return `Stimulus line invalid: "${l}" — format: NEURON t0 t1 amp (e.g. PLML 10 60 50).`;
  }
  const dur = +$('#lab-dur').value;
  if (!(dur >= 10 && dur <= 5000)) return 'Duration must be between 10 and 5000 ms.';
  return null;
}
$('#lab-run').onclick = async () => {
  const body = {
    species: 'caenorhabditis_elegans', dataset_id: $('#lab-dataset').value, model: $('#lab-model').value,
    research_question: $('#lab-rq').value || null, duration_ms: +$('#lab-dur').value, seed: +$('#lab-seed').value,
    stimulus: parseStim($('#lab-stim').value),
    manipulations: {
      silence: $('#lab-silence').value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean),
      activate: $('#lab-activate').value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean),
      remove_edges: $('#lab-remove').value.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
        const [source, target, kind] = l.split(/\s+/); return { source: source.toUpperCase(), target: target.toUpperCase(), kind: kind || 'chemical' };
      })
    }
  };
  try {
    const err = validateLab();
    if (err) { $('#lab-status').textContent = err; return; }
    $('#lab-status').textContent = 'Creating experiment…';
    const H = { 'Content-Type': 'application/json', 'X-Role': 'researcher', ...authHeaders() };
    const { experiment_id } = await api('/api/experiments', { method: 'POST', headers: H, body: JSON.stringify(body) });
    $('#lab-status').textContent = `Simulating ${experiment_id} (normal vs modified)…`;
    const sim = await api('/api/simulations', { method: 'POST', headers: H, body: JSON.stringify({ experiment_id }) });
    $('#lab-status').innerHTML = `OK <a href="#" data-goto-exp="${experiment_id}">${experiment_id}</a> — normal ${sim.normal_total} vs modified ${sim.modified_total} spikes (${sim.comparison.pct_total}%).${campus.token ? '' : ' <span class="note">Tip: login via Campus to sign your experiments.</span>'}`;
    const res = await api(`/api/results/${experiment_id}`);
    drawRaster(res.modified.spikes); compareTable(res.comparison);
    refreshExpList();
  } catch (e) { $('#lab-status').textContent = 'ERROR ' + e.message; }
};
function compareTable(c) {
  $('#lab-compare').innerHTML = `<p><b>Δ total ${c.delta_total}</b> (${c.pct_total}%) · behavior-proxy Δ ${c.behavior_delta}</p>
  <p class="note">Showing top 20 of ${c.per_neuron.length} neurons.</p>
  <table><tr><th>neuron</th><th>normal</th><th>modified</th><th>Δ</th></tr>` +
    c.per_neuron.slice(0, 20).map(r => `<tr><td class="mono">${r.neuron}</td><td>${r.normal}</td><td>${r.modified}</td><td>${r.delta}</td></tr>`).join('') + '</table>';
}
function drawRaster(spikes, el = '#raster') {
  const cv = $(el), ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  const ids = Object.keys(spikes).sort();
  const tmax = Math.max(1, ...ids.flatMap(id => spikes[id]));
  ids.forEach((id, i) => {
    const y = 10 + i * (cv.height - 34) / Math.max(ids.length, 1);
    ctx.fillStyle = '#8A9199'; ctx.font = '10px "IBM Plex Mono",monospace'; ctx.fillText(id, 2, y + 3);
    ctx.fillStyle = '#6FB1FF';
    for (const t of spikes[id]) ctx.fillRect(50 + t / tmax * (cv.width - 60), y - 2, 2, 4);
  });
  ctx.fillStyle = '#6E767E'; ctx.font = '10px "IBM Plex Mono",monospace';
  ctx.fillText(`0`, 50, cv.height - 4);
  const lbl = `${tmax} ms`;
  ctx.fillText(lbl, cv.width - ctx.measureText(lbl).width - 4, cv.height - 4);
  ctx.fillText('t (ms) →', 50, 10);
}

/* experiments */
async function refreshExpList() {
  const l = await api('/api/experiments?limit=100');
  $('#exp-list').innerHTML = '<div class="micro dim">SAVED (' + l.total + ')</div>' + l.experiments.map(e =>
    `<div><a href="#" class="mono" data-goto-exp="${e.experiment_id}">${e.experiment_id}</a> · ${esc(e.model)} · ${esc(e.dataset_id)} · ${esc(e.research_question || '')}</div>`).join('');
}
async function openExperiment(id) {
  goto('experiments');
  const [r, prov] = await Promise.all([api(`/api/experiments/${id}`), api(`/api/provenance/${id}`).catch(() => null)]);
  const c = r.results?.comparison;
  $('#exp-detail').innerHTML = `<h3 class="mono">${r.experiment_id} <span class="tag">computational simulation</span></h3>
    <p><b>Q:</b> ${esc(r.research_question || '—')}</p>
    ${r.author ? `<p><b>Author:</b> ${esc(r.author)}</p>` : ''}
    <p><span class="note mono" style="font-size:.78em">dataset ${esc(r.dataset_id)} v${esc(r.dataset_version)} · model ${esc(r.model)} ${esc(r.model_version)} · seed ${r.seed} · engine ${esc(r.engine_version)} · ${esc(r.created_utc)}</span></p>
    <p><b>Virtual manipulation:</b> <span class="mono" style="font-size:.82em">${esc(JSON.stringify(r.manipulations_virtual_only))}</span></p>
    ${c ? `<p><b>Result:</b> normal ${r.results.normal.summary.total_spikes} vs modified ${r.results.modified.summary.total_spikes} (${c.pct_total}%). behavior-proxy Δ ${c.behavior_delta}</p><canvas id="exp-raster" width="640" height="220" style="width:100%;background:#0A101E;border:1px solid rgba(130,175,255,.11);border-radius:16px"></canvas>` : '<p>Not simulated yet.</p>'}
    <p><button id="exp-run">Run simulation</button>
    <a href="/api/export/${id}.json">JSON</a> · <a href="/api/export/${id}.csv">CSV</a> ·
    <button id="exp-rep">View report</button></p>
    <h4 class="micro dim">PROVENANCE</h4><p>${prov ? prov.chain.map(s => `<b>${esc(s.stage)}</b> → ${esc(s.value)}`).join('<br>') : '—'}</p>`;
  if (c) drawRaster(r.results.modified.spikes, '#exp-raster');
  $('#exp-run').onclick = async () => { await api('/api/simulations', { method: 'POST', body: JSON.stringify({ experiment_id: id }) }); openExperiment(id); };
  $('#exp-rep').onclick = () => { $('#rep-id').value = id; loadReport(); goto('research'); };
  history.replaceState(null, '', `/experiment/${id}`);
}

/* research report */
async function loadReport() {
  const id = $('#rep-id').value.trim().toUpperCase();
  const r = await api(`/api/reports/${id}`);
  $('#report').innerHTML = `<h2 class="mono" style="font-size:1.05em">${esc(r.title)}</h2><p><span class="tag">${esc(r.disclaimer)}</span></p>
  ${['research_question', 'dataset', 'model', 'virtual_manipulation', 'stimulus', 'results', 'limitations', 'reproducibility', 'references'].map(k => `<h4>${k}</h4><pre>${esc(JSON.stringify(r[k], null, 1))}</pre>`).join('')}`;
}
$('#rep-load').onclick = loadReport;

/* ---- hero visualization: layered propagation schematic (illustrative) ---- */
function initHero() {
  const cv = $('#hero-viz'); if (!cv) return;
  const ctx = cv.getContext('2d');
  let W = 0, H = 0, nodes = [], edges = [], pulses = [];
  function build() {
    const r = cv.getBoundingClientRect();
    const dpr = Math.min(devicePixelRatio || 1, 1.5);
    const w = Math.max(320, Math.round(r.width * dpr)), h = Math.max(320, Math.round(r.height * dpr));
    if (w === W && h === H && nodes.length) return;
    W = w; H = h; cv.width = W; cv.height = H;
    const layers = W < H ? [3, 5, 7, 5, 3] : [4, 7, 9, 7, 4], gapX = W / (layers.length + 1);
    nodes = [];
    layers.forEach((n, li) => {
      for (let i = 0; i < n; i++) {
        const violet = (li * 7 + i * 3) % 11 === 0;
        nodes.push({ x: gapX * (li + 1), y: H * (i + 1) / (n + 1), li, violet, act: li === 0 ? 1 : 0 });
      }
    });
    edges = [];
    for (let a = 0; a < nodes.length; a++) for (let b = 0; b < nodes.length; b++) {
      if (nodes[b].li === nodes[a].li + 1 && Math.abs(nodes[a].y - nodes[b].y) < H / 4.2) edges.push([a, b]);
    }
    pulses = Array.from({ length: 22 }, (_, i) => ({ e: (i * 37) % edges.length, t: (i * 53 % 100) / 100, s: .002 + (i % 5) * .0006 }));
  }
  build();
  let rT = null;
  addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(build, 200); });
  const draw = (time) => {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = 'rgba(255,255,255,.07)'; ctx.lineWidth = 1;
    for (const [a, b] of edges) { ctx.beginPath(); ctx.moveTo(nodes[a].x, nodes[a].y); ctx.lineTo(nodes[b].x, nodes[b].y); ctx.stroke(); }
    /* faint background lattice */
    ctx.fillStyle = 'rgba(255,255,255,.045)';
    for (let gx = 20; gx < W; gx += 34) for (let gy = 16; gy < H; gy += 34) ctx.fillRect(gx, gy, 1, 1);
    for (const p of pulses) {
      const [a, b] = edges[p.e % edges.length];
      const A = nodes[a], B = nodes[b];
      const x = A.x + (B.x - A.x) * p.t, y = A.y + (B.y - A.y) * p.t;
      const lead = p.t > .82;
      ctx.fillStyle = lead ? '#9B8FFF' : 'rgba(230,235,236,.85)';
      if (lead) { ctx.shadowColor = 'rgba(155,143,255,.8)'; ctx.shadowBlur = 8; }
      ctx.beginPath(); ctx.arc(x, y, lead ? 3 : 2, 0, 7); ctx.fill();
      ctx.shadowBlur = 0;
      B.act = Math.min(1, B.act + (lead ? .05 : .012));
    }
    for (const n of nodes) {
      n.act *= .985;
      const hot = n.act > .3;
      ctx.fillStyle = hot ? '#9CC6FF' : (n.violet ? 'rgba(155,143,255,.5)' : 'rgba(24,27,32,1)');
      ctx.strokeStyle = hot ? '#9CC6FF' : 'rgba(255,255,255,.16)';
      if (hot) { ctx.shadowColor = 'rgba(143,232,221,.7)'; ctx.shadowBlur = 9; }
      ctx.beginPath(); ctx.arc(n.x, n.y, hot ? 4.5 : 3.4, 0, 7); ctx.fill(); ctx.stroke();
      ctx.shadowBlur = 0;
    }
    /* stimulus marker, left edge */
    ctx.fillStyle = '#6E767E'; ctx.font = '10px "IBM Plex Mono",monospace';
    ctx.fillText('STIMULUS ▸', 12, 20);
  };
  if (REDUCED) { draw(0); return; }
  const loop = () => {
    if (cv.offsetParent) {
      const dpr = Math.min(devicePixelRatio || 1, 1.5);
      if (Math.abs(cv.clientWidth * dpr - W) > 2) build();
      for (const p of pulses) p.t = (p.t + p.s) % 1; draw();
    }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}

/* ---- demo instrument: activity-driven circuit view (real result data) ---- */
const demo = { counts: null, raf: 0 };
async function initDemo() {
  try {
    const res = await api('/api/results/NL-EXP-000001');
    setDemoResult(res);
  } catch (e) { $('#demo-out').textContent = 'ERROR ' + e.message; }
  startDemoLoop();
}
function setDemoResult(res) {
  const c = res.comparison;
  $('#demo-result').textContent = `normal ${res.normal.summary.total_spikes} vs modified ${res.modified.summary.total_spikes} (${c.pct_total}%)`;
  $('#demo-viz-src').textContent = 'NL-EXP-000001 · MODIFIED ARM';
  $('#demo-out').textContent =
    `SIMULATION RESULT — normal ${res.normal.summary.total_spikes} vs modified (PVCL silenced) ${res.modified.summary.total_spikes} (${c.pct_total}%).\nForward-bias proxy Δ ${c.behavior_delta}. Seed 42, lif.`;
  const spikes = res.modified.spikes;
  demo.counts = Object.keys(spikes).sort().map(id => ({ id, n: spikes[id].length }));
}
function drawDemoFrame(t) {
  const cv = $('#demo-viz'); if (!cv) return;
  const ctx = cv.getContext('2d'), W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  if (!demo.counts) {
    ctx.fillStyle = '#6E767E'; ctx.font = '12px "IBM Plex Mono",monospace';
    ctx.fillText('AWAITING SIMULATION — PRESS RUN', 24, H / 2);
    return;
  }
  const N = demo.counts.length, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 46;
  const max = Math.max(1, ...demo.counts.map(d => d.n));
  const pos = demo.counts.map((d, i) => {
    const a = -Math.PI / 2 + 2 * Math.PI * i / N;
    return { ...d, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a), a };
  });
  /* stimulus → response axis */
  ctx.strokeStyle = 'rgba(255,255,255,.25)'; ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(24, 24); ctx.lineTo(cx, cy); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = '#A9B0B7'; ctx.font = '10px "IBM Plex Mono",monospace';
  ctx.fillText('STIMULUS: PLML/PLMR', 24, 18);
  /* ring edges between neighbours */
  ctx.strokeStyle = 'rgba(255,255,255,.1)';
  pos.forEach((p, i) => { const q = pos[(i + 1) % N]; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke(); });
  /* travelling pulses, density ∝ activity */
  const K = 14;
  for (let k = 0; k < K; k++) {
    const idx = Math.floor(((t / 34 + k / K) % 1) * N);
    const p = pos[idx], q = pos[(idx + 1) % N], f = ((t / 34 + k / K) % 1) * N % 1;
    const hot = p.n / max > .4;
    ctx.fillStyle = hot ? '#6FB1FF' : 'rgba(255,255,255,.35)';
    ctx.beginPath(); ctx.arc(p.x + (q.x - p.x) * f, p.y + (q.y - p.y) * f, hot ? 2.6 : 1.6, 0, 7); ctx.fill();
  }
  pos.forEach(p => {
    const act = p.n / max, hot = act > .35;
    if (hot) { ctx.shadowColor = 'rgba(111,177,255,.7)'; ctx.shadowBlur = 8; }
    ctx.fillStyle = hot ? '#6FB1FF' : '#14171B';
    ctx.strokeStyle = hot ? '#6FB1FF' : 'rgba(255,255,255,.18)';
    ctx.beginPath(); ctx.arc(p.x, p.y, 3 + act * 7, 0, 7); ctx.fill(); ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.fillStyle = act > .1 ? '#F2F4F3' : '#6E767E';
    ctx.font = '10px "IBM Plex Mono",monospace';
    ctx.fillText(`${p.id}·${p.n}`, p.x + 9, p.y + 3);
  });
}
function startDemoLoop() {
  if (REDUCED) { drawDemoFrame(0); return; }
  const loop = (t) => { if ($('#demo-viz').offsetParent) drawDemoFrame(t || 0); requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
}
$('#demo-run').onclick = async () => {
  try {
    $('#demo-out').textContent = 'Running reference simulation (normal vs modified)…';
    await api('/api/simulations', { method: 'POST', body: JSON.stringify({ experiment_id: 'NL-EXP-000001' }) });
    setDemoResult(await api('/api/results/NL-EXP-000001'));
  } catch (e) { $('#demo-out').textContent = 'ERROR ' + e.message; }
};

/* ---- user dataset import: picker + drag&drop + local preview ---- */
function impIsCsv(name) { return /\.(csv|tsv|txt)$/i.test(name || ''); }
async function impPreview() {
  const f = $('#imp-file').files[0];
  if (!f) return;
  $('#imp-filename').textContent = f.name;
  try {
    const text = await f.text();
    if (impIsCsv(f.name)) {
      const rows = text.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));
      $('#imp-status').textContent = `Preview: ~${rows.length} edge rows (${(f.size / 1024).toFixed(0)} KB, ${rows[0] && /source/i.test(rows[0]) ? 'header detected' : 'no header'}). Press Import.`;
      return;
    }
    const doc = JSON.parse(text);
    if (!doc || !Array.isArray(doc.nodes) || !Array.isArray(doc.edges)) throw new Error('need {"nodes": [...], "edges": [...]}');
    const ids = doc.nodes.slice(0, 3).map(n => n && n.id).join(', ');
    $('#imp-status').textContent = `Preview: ${doc.nodes.length} nodes / ${doc.edges.length} edges (${(f.size / 1024).toFixed(0)} KB) — e.g. ${ids}. Press Import.`;
  } catch (e) { $('#imp-status').textContent = 'ERROR ' + e.message; }
}
$('#imp-file').onchange = impPreview;
const impPanel = $('#imp-file').closest('.panel');
impPanel.ondragover = e => { e.preventDefault(); impPanel.style.borderColor = 'rgba(255,255,255,.35)'; };
impPanel.ondragleave = () => impPanel.style.borderColor = '';
impPanel.ondrop = e => { e.preventDefault(); impPanel.style.borderColor = ''; if (e.dataTransfer.files.length) { $('#imp-file').files = e.dataTransfer.files; impPreview(); } };
$('#imp-template-csv').onclick = () => {
  const csv = 'source,target,kind,weight\nA,B,chemical,3\nB,C,chemical,2\nA,C,electrical,1\n';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = 'brain-template.csv'; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
};
$('#imp-template').onclick = () => {
  const tpl = { nodes: [{ id: 'A', type: 'sensory' }, { id: 'B', type: 'interneuron' }, { id: 'C', type: 'motor' }],
    edges: [{ source: 'A', target: 'B', kind: 'chemical' }, { source: 'B', target: 'C', kind: 'chemical' }] };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(tpl, null, 2)], { type: 'application/json' }));
  a.download = 'brain-template.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
};
$('#imp-run').onclick = async () => {
  const f = $('#imp-file').files[0];
  if (!f) { $('#imp-status').textContent = 'Choose a file first.'; return; }
  try {
    $('#imp-status').textContent = 'Validating…';
    const text = await f.text();
    const meta = { name: $('#imp-name').value || f.name.replace(/\.(json|csv|tsv|txt)$/i, ''), species: $('#imp-species').value };
    let payload;
    if (impIsCsv(f.name)) {
      payload = { ...meta, csv: text };
      $('#imp-status').textContent = `Uploading edge-list (${(f.size / 1024).toFixed(0)} KB)…`;
    } else {
      const doc = JSON.parse(text);
      if (!doc || !Array.isArray(doc.nodes) || !Array.isArray(doc.edges)) throw new Error('file must contain {"nodes": [...], "edges": [...]}');
      payload = { ...meta, nodes: doc.nodes, edges: doc.edges };
      $('#imp-status').textContent = `Uploading ${doc.nodes.length} nodes / ${doc.edges.length} edges…`;
    }
    const r = await api('/api/datasets/import', { method: 'POST', body: JSON.stringify(payload) });
    $('#imp-status').textContent = `OK ${r.id} — ${r.nodes} nodes / ${r.edges} edges. Available in Explorer + Lab.`;
    await refreshDatasets(); loadExplorer();
  } catch (e) { $('#imp-status').textContent = 'ERROR ' + e.message; }
};

/* ai */
$('#ai-ask').onclick = async () => {
  const body = { question: $('#ai-q').value, dataset_id: $('#exp-dataset').value || undefined };
  if ($('#ai-neuron').value) body.neuron_id = $('#ai-neuron').value;
  if ($('#ai-exp').value) body.experiment_id = $('#ai-exp').value;
  try { $('#ai-out').textContent = (await api('/api/ai/explain', { method: 'POST', body: JSON.stringify(body) })).answer; }
  catch (e) { $('#ai-out').textContent = 'Error: ' + e.message; }
};

/* ---- campus: global universities + representation ---- */
const campus = { token: localStorage.getItem('campus_token') || null, user: localStorage.getItem('campus_user') || null };
async function capi(p, o = {}) {
  const { headers, ...rest } = o;
  const h = { 'Content-Type': 'application/json', ...(campus.token ? { 'Authorization': 'Bearer ' + campus.token } : {}), ...(headers || {}) };
  const r = await fetch(p, { ...rest, headers: h });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
function campusAuthBox() {
  const el = $('#campus-auth');
  if (!campus.token) {
    el.innerHTML = `<div class="micro dim">ACCOUNT</div>
      <p class="note">An account lets you join a university, appear in the leaderboard, and sign the experiments you create in the Lab.</p>
      <div class="toolbar"><input id="cu-name" placeholder="username" style="width:11em" maxlength="32" autocomplete="username">
      <input id="cu-pass" type="password" placeholder="password (6+)" style="width:11em" autocomplete="current-password">
      <button id="cu-reg" class="btn-primary">Register</button><button id="cu-login" class="btn-ghost">Login</button></div>
      <div id="cu-msg" class="note"></div>`;
    const creds = () => ({ username: $('#cu-name').value.trim(), password: $('#cu-pass').value });
    const done = (d) => { campus.token = d.token; campus.user = d.username; localStorage.setItem('campus_token', d.token); localStorage.setItem('campus_user', d.username); loadCampusPanels(); };
    $('#cu-reg').onclick = async () => { try { done(await capi('/api/campus/register', { method: 'POST', body: JSON.stringify(creds()) })); } catch (e) { $('#cu-msg').textContent = e.message; } };
    $('#cu-login').onclick = async () => { try { done(await capi('/api/campus/login', { method: 'POST', body: JSON.stringify(creds()) })); } catch (e) { $('#cu-msg').textContent = e.message; } };
  } else {
    el.innerHTML = `<div class="micro dim">ACCOUNT</div>
      <p>Representing as <b>${esc(campus.user)}</b></p>
      <button id="cu-out" class="btn-ghost">Logout</button>`;
    $('#cu-out').onclick = async () => {
      try { await capi('/api/campus/logout', { method: 'POST' }); } catch (e) { /* ignore */ }
      campusLogout();
    };
  }
}
function campusLogout(silent) {
  campus.token = null; campus.user = null;
  localStorage.removeItem('campus_token'); localStorage.removeItem('campus_user');
  if (!silent) loadCampusPanels();
}
async function loadCampusPanels() {
  campusAuthBox();
  try {
    const st = await capi('/api/campus/status');
    $('#campus-status').innerHTML = `${esc(st.universities)} UNIVERSITIES · ${esc(st.total_members ?? 0)} REPRESENTATIVES · MEMBERS STORE: ${esc(st.backend)} · EXPERIMENTS STORE: ${esc(st.experiments_backend || '?')}${st.shared ? '' : ' · <span style="color:var(--warn)">DEMO MODE — ' + esc(st.note || '') + '</span>'}`;
  } catch (e) { $('#campus-status').textContent = 'status unavailable'; }
  try {
    const me = campus.token ? await capi('/api/campus/me') : null;
    let mine = `<div class="micro dim">MY AFFILIATION</div>` + (me && me.university
      ? `<p><b>${esc(me.university.name)}</b><br><span class="note">${esc(me.university.country)} · ${esc(me.university.members)} representative(s)</span></p><button id="cu-leave" class="btn-ghost">Leave</button>`
      : `<p class="note">${campus.token ? 'No affiliation yet — join a university.' : 'Login to join a university.'}</p>`);
    if (me) {
      try {
        const mine2 = await capi(`/api/experiments?author=${encodeURIComponent(me.username)}&limit=20`);
        mine += `<div class="micro dim" style="margin-top:.8em">MY EXPERIMENTS (${mine2.total})</div>` +
          (mine2.experiments.map(e => `<div><a href="#" class="mono" data-goto-exp="${e.experiment_id}">${e.experiment_id}</a> <span class="note">· ${esc(e.model)} · ${esc(e.dataset_id)}</span></div>`).join('') || '<p class="note">None yet — create one in the Lab.</p>');
      } catch (e) { /* experiments unavailable; affiliation still shown */ }
    }
    $('#campus-mine').innerHTML = mine;
    const lv = $('#cu-leave'); if (lv) lv.onclick = async () => { await capi('/api/campus/leave', { method: 'POST' }); loadCampusPanels(); campusSearch(); };
  } catch (e) {
    if (String(e.message).startsWith('401')) {
      campusLogout(true); campusAuthBox();
      $('#campus-mine').innerHTML = `<div class="micro dim">MY AFFILIATION</div><p class="note">Session expired — login again.</p>`;
    } else $('#campus-mine').innerHTML = `<div class="micro dim">MY AFFILIATION</div><p class="note">${esc(e.message)}</p>`;
  }
  try {
    const b = await capi('/api/campus/leaderboard?limit=20');
    $('#campus-board').innerHTML = `<div class="micro dim">LEADERBOARD — BY REPRESENTATIVES</div>
      <table>${b.leaders.map((u, i) => `<tr><td class="mono">${i + 1}</td><td><a href="#" data-members="${u.id}" data-mname="${esc(u.name)}">${esc(u.name)}</a><br><span class="note">${esc(u.country)}</span></td><td class="mono">${u.members}</td></tr>`).join('') || '<tr><td class="note">No representatives yet — be the first.</td></tr>'}</table>`;
    bindMemberLinks('#campus-board');
  } catch (e) { $('#campus-board').innerHTML = `<div class="micro dim">LEADERBOARD</div><p class="note">unavailable</p>`; }
}
function bindMemberLinks(root) {
  document.querySelectorAll(root + ' [data-members]').forEach(a => a.onclick = e => { e.preventDefault(); showMembers(a.dataset.members, a.dataset.mname); });
}
async function showMembers(uid, name) {
  try {
    const m = await capi(`/api/campus/members?university_id=${encodeURIComponent(uid)}`);
    $('#campus-members-body').innerHTML = `<p><b>${esc(name)}</b> — ${m.total} representative(s)</p><p>${m.members.map(esc).join(', ') || '<span class="note">none</span>'}</p>`;
  } catch (e) { $('#campus-members-body').textContent = e.message; }
}
async function campusSearch() {
  const q = $('#campus-q').value.trim(), c = $('#campus-country').value;
  try {
    const r = await capi(`/api/campus/universities?q=${encodeURIComponent(q)}&country=${encodeURIComponent(c)}&limit=20`);
    $('#campus-results').innerHTML = `<div class="micro dim">${r.total} RESULT(S)</div>` + r.universities.map(u =>
      `<div class="uni-row"><div><b>${esc(u.name)}</b><br><span class="note">${esc(u.country)}${u.domain ? ' · ' + esc(u.domain) : ''} · <a href="#" data-members="${u.id}" data-mname="${esc(u.name)}">${u.members} rep(s)</a></span></div>
      <button class="btn-primary" data-join="${u.id}" ${campus.token ? '' : 'disabled title="login first"'}>Join</button></div>`).join('');
    document.querySelectorAll('#campus-results [data-join]').forEach(b => b.onclick = async () => {
      await capi('/api/campus/join', { method: 'POST', body: JSON.stringify({ university_id: b.dataset.join }) });
      loadCampusPanels(); campusSearch();
    });
    bindMemberLinks('#campus-results');
  } catch (e) { $('#campus-results').textContent = e.message; }
}
async function loadCampus() {
  try {
    const c = await capi('/api/campus/countries');
    const sel = $('#campus-country'), cur = sel.value;
    sel.innerHTML = '<option value="">all countries</option>' + c.countries.map(x => `<option value="${esc(x.country)}">${esc(x.country)} (${x.universities})</option>`).join('');
    if (cur) sel.value = cur;
  } catch (e) { /* ignore */ }
  loadCampusPanels();
}
$('#campus-search').onclick = campusSearch;
$('#campus-q').onkeydown = e => { if (e.key === 'Enter') campusSearch(); };
$('#campus-country').onchange = campusSearch;
document.querySelector('[data-tab="campus"]').addEventListener('click', loadCampus);

init().catch(e => document.querySelector('main').prepend(Object.assign(document.createElement('p'), { textContent: 'API error: ' + e.message })));
