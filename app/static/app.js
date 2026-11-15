const TOTAL = 4;
const map = L.map('map', {zoomSnap: 0.25});
L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png', {
 maxZoom: 18,
 attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Tiles: <a href="https://tile.openstreetmap.de/">OpenStreetMap.de</a>'
}).addTo(map);

['radarPane', 'beforePane', 'duringPane', 'roadsPane'].forEach((name, i) => {
  map.createPane(name).style.zIndex = 410 + i * 10;
});

const $ = (id) => document.getElementById(id);
const fmt = (v, unit = '') => (v === null || v === undefined) ? 'to be confirmed' : v + unit;
const fmtDate = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC'});

let stats = null, layers = {}, step = 1;

async function addLayer(spec, pane, style) {
  // The stats contract allows either vector GeoJSON or raster image overlays.
  if (!spec) return null;
  if (spec.type === 'geojson') {
    const data = await (await fetch(spec.url)).json();
    return L.geoJSON(data, {pane, style});
  }
  if (spec.type === 'image') {  // bounds: [[south, west], [north, east]]
    return L.imageOverlay(spec.url, spec.bounds, {pane});
  }
  throw new Error('Unknown layer type: ' + spec.type);
}

function show(layer, on) {
  if (!layer) return;
  if (on && !map.hasLayer(layer)) layer.addTo(map);
  if (!on && map.hasLayer(layer)) map.removeLayer(layer);
}

// ----- curtain: clip the "before" pane to the left of the line and "during" to the right
function updateClip(active) {
  const bp = map.getPane('beforePane'), dp = map.getPane('duringPane');
  if (!active) { bp.style.clip = ''; dp.style.clip = ''; return; }
  const ratio = $('slider').value / 100;
  const size = map.getSize();
  const nw = map.containerPointToLayerPoint([0, 0]);
  const se = map.containerPointToLayerPoint(size);
  const x = nw.x + (se.x - nw.x) * ratio;
  bp.style.clip = `rect(${nw.y}px,${x}px,${se.y}px,${nw.x}px)`;
  dp.style.clip = `rect(${nw.y}px,${se.x}px,${se.y}px,${x}px)`;
  $('divider').style.left = (ratio * 100) + '%';
}

function setStep(n) {
  // Each story step controls both explanatory content and visible map layers.
  step = Math.max(1, Math.min(TOTAL, n));
  document.querySelectorAll('.step').forEach(el => el.classList.toggle('on', +el.dataset.step === step));
  document.querySelectorAll('#progress button').forEach((b, i) => {
    b.classList.toggle('on', i + 1 === step);
    b.classList.toggle('done', i + 1 < step);
  });
  $('stepcount').textContent = `${step} / ${TOTAL}`;
  $('prev').disabled = step === 1;
  $('next').disabled = step === TOTAL;

  const compare = step === 3;
  show(layers.radar, step === 2);
  show(layers.before, step === 2 || compare);
  show(layers.during, compare || step === 4);
  show(layers.roads, step === 4);
  $('curtain').hidden = !compare;
  $('legend').hidden = step < 2;
  $('roads-legend').hidden = step !== 4 || !layers.roads;
  updateClip(compare);
  map.invalidateSize();
}

function card(label, value, mock) {
  const d = document.createElement('div');
  d.className = 'fact';
  const b = document.createElement('b'); b.textContent = value;
  const s = document.createElement('span'); s.textContent = label;
  if (mock) { const m = document.createElement('i'); m.className = 'mock'; m.textContent = 'MOCK'; s.appendChild(m); }
  d.append(b, s);
  return d;
}

(async () => {
  // Load the same contract from Flask or, in the static build, from docs/.
  stats = await (await fetch(window.STATS_URL || '/api/stats')).json();
  if (stats.mock) $('mock-flag').hidden = false;

  const [w, so, e, n] = stats.bbox;
  map.fitBounds([[so, w], [n, e]]);

  layers.radar = await addLayer(stats.layers.radar_rgb, 'radarPane', {});
  layers.before = await addLayer(stats.layers.before, 'beforePane', {color: '#1f78c8', weight: 1, fillColor: '#1f78c8', fillOpacity: 0.65});
  layers.during = await addLayer(stats.layers.during, 'duringPane', {color: '#e4572e', weight: 1, fillColor: '#e4572e', fillOpacity: 0.65});
  layers.roads = await addLayer(stats.layers.roads_blocked, 'roadsPane', {
    color: '#ffb000', weight: 3, opacity: 1,
  });

  // text that depends on the data
  $('date-before').textContent = fmtDate(stats.scenes.before.date);
  $('date-during').textContent = fmtDate(stats.scenes.during.date);
  $('big-km2').textContent = stats.flooded_area_km2 == null ? '…' : Math.round(stats.flooded_area_km2).toLocaleString('en-US');

  const rg = stats.flooded_area_range_km2;
  if (rg) {
    const f = (v) => Math.round(v).toLocaleString('en-US');
    $('range-note').textContent = `Conservative estimate. Treating the darker land of the first scene differently gives up to ${f(rg[1])} km² (range ${f(rg[0])} to ${f(rg[1])} km²).`;
    $('range-note').hidden = false;
  }

  const ctx = stats.context_figures;
  if (ctx) {
    ctx.items.forEach(it => $('context-figures').appendChild(card(it.label, it.value, false)));
    $('context-source').textContent = 'Source: ' + ctx.source;
  }

  const imp = stats.impact || {};
  const impEl = $('impact');
  if (imp.roads_blocked_km != null) impEl.appendChild(card('km of roads inside mapped flood (OSM estimate)', imp.roads_blocked_km.toLocaleString('en-US'), stats.mock));
  if (imp.buildings_affected != null) impEl.appendChild(card('buildings intersecting mapped flood (OSM estimate)', Math.round(imp.buildings_affected).toLocaleString('en-US'), stats.mock));
  if (imp.source) {
    const source = document.createElement('p');
    source.className = 'source';
    const attribution = document.createElement('a');
    attribution.href = 'https://www.openstreetmap.org/copyright';
    attribution.textContent = `${imp.source} contributors (ODbL)`;
    source.append('Impact data: ', attribution, '. OSM coverage is incomplete; counts are estimates.');
    impEl.appendChild(source);
  }
  impEl.appendChild(card('new flooded area', Math.round(stats.flooded_area_km2) + ' km²', stats.mock));
  impEl.appendChild(card('permanent water', Math.round(stats.permanent_water_km2) + ' km²', stats.mock));

  const validation = stats.validation;
  if (validation) {
    const metrics = $('validation-metrics');
    const km2 = (value) => `${Number(value).toLocaleString('en-US', {maximumFractionDigits: 1})} km²`;
    [
      ['NISAR new water in AOI02', km2(validation.nisar_new_water_aoi_km2)],
      ['EMS mapped flood in AOI02', km2(validation.ems_flood_area_aoi_km2)],
      ['Intersecting area', km2(validation.intersection_area_km2)],
      ['Spatial IoU', Number(validation.iou).toFixed(2)],
    ].forEach(([label, value]) => metrics.appendChild(card(label, value, false)));
    $('validation-note').textContent =
      `${validation.reference}, acquired ${validation.acquisition_utc}. ` +
      `${validation.interpretation} Overlap: ` +
      `${Math.round(validation.overlap_fraction_nisar * 100)}% of NISAR area; ` +
      `${Math.round(validation.overlap_fraction_ems * 100)}% of EMS area.`;
    $('validation-section').hidden = false;
  }

  const rows = [
    ['Before', stats.scenes.before.date], ['During', stats.scenes.during.date],
    ['Track / frame', `${stats.scenes.during.track} / ${stats.scenes.during.frame}`],
    ['Direction', stats.scenes.during.direction],
    ['Polarizations', fmt(stats.scenes.during.polarizations && stats.scenes.during.polarizations.join(', '))],
    ['Data level', stats.maturity], ['Product', stats.product],
  ];
  const dl = $('numbers');
  rows.forEach(([k, v]) => {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = v;
    dl.append(dt, dd);
  });
  stats.limitations.forEach(t => {
    const li = document.createElement('li'); li.textContent = t; $('limits').appendChild(li);
  });

  // progress bar buttons
  const nav = $('progress');
  for (let i = 1; i <= TOTAL; i++) {
    const b = document.createElement('button');
    b.type = 'button'; b.setAttribute('aria-label', 'Step ' + i);
    b.addEventListener('click', () => setStep(i));
    nav.appendChild(b);
  }
  $('prev').addEventListener('click', () => setStep(step - 1));
  $('next').addEventListener('click', () => setStep(step + 1));
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'ArrowRight') setStep(step + 1);
    if (ev.key === 'ArrowLeft') setStep(step - 1);
  });
  $('slider').addEventListener('input', () => updateClip(step === 3));
  map.on('move zoom resize', () => updateClip(step === 3));

  setStep(1);
})();
