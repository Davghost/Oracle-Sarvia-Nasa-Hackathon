// The static GitHub Pages copy has no Flask backend for route calculations.
const STATIC = Boolean(window.STATS_URL);
const $ = (id) => document.getElementById(id);
if (STATIC) {
  document.querySelectorAll('.server-only').forEach(el => el.remove());
}
const TOTAL = 5;
const COLORS = {standing: '#1f5fae', newwater: '#e0442a', roads: '#f0a500', slate: '#1b2830', safe: '#1b8a4b'};
const map = L.map('map', {
  zoomSnap: 0.25,
  preferCanvas: true,
  zoomAnimation: false,
  fadeAnimation: false,
  markerZoomAnimation: false
});
const defaultMapConfig = {
  satellite: true,
  hybrid: true,
  satellite_url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  hybrid_url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  hybrid_labels_url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
  attribution: {satellite: '&copy; Esri', hybrid: '&copy; Esri | &copy; OpenStreetMap contributors'}
};
const mapConfig = Object.assign({}, defaultMapConfig, window.SARVIA_MAP_CONFIG || {});
mapConfig.attribution = Object.assign({}, defaultMapConfig.attribution, mapConfig.attribution || {});
const tileOptions = {maxZoom: 19, updateWhenZooming: false, updateWhenIdle: true, keepBuffer: 2};
const osm = L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png', {
 ...tileOptions, maxZoom: 18,
 attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Tiles: <a href="https://tile.openstreetmap.de/">OpenStreetMap.de</a>'
}).addTo(map);
const dark = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
  ...tileOptions,
  attribution: '&copy; <a href="https://www.esri.com/">Esri</a> | &copy; OpenStreetMap contributors'
});
const baseMaps = {'OpenStreetMap claro': osm, 'Mapa escuro': dark};
const externalBaseMaps = {};
if (mapConfig.satellite && mapConfig.satellite_url) {
  externalBaseMaps['Imagem de satélite'] = L.tileLayer(mapConfig.satellite_url, {
    ...tileOptions, attribution: mapConfig.attribution.satellite || 'Satellite imagery provider'
  });
}
if (mapConfig.hybrid && mapConfig.hybrid_url) {
  const hybridLayers = [L.tileLayer(mapConfig.hybrid_url, tileOptions)];
  if (mapConfig.hybrid_labels_url) hybridLayers.push(L.tileLayer(mapConfig.hybrid_labels_url, tileOptions));
  externalBaseMaps['Híbrido (imagem + estradas)'] = L.layerGroup(hybridLayers);
}
Object.assign(baseMaps, externalBaseMaps);
const layerControl = L.control.layers(baseMaps, {}, {collapsed: false, position: 'topright'}).addTo(map);
const externalTileLayers = [];
Object.values(externalBaseMaps).forEach(layer => {
  if (layer.eachLayer) layer.eachLayer(child => externalTileLayers.push(child));
  else externalTileLayers.push(layer);
});
externalTileLayers.forEach(layer => layer.on('tileerror', () => {
  if ($('layer-status')) {
    $('layer-status').hidden = false;
    $('layer-status').textContent = 'Não foi possível carregar uma camada externa; verifique a configuração do provedor.';
  }
}));

['vegetationPane', 'radarPane', 'beforePane', 'duringPane', 'validationPane', 'roadsPane', 'impactPane'].forEach((name, i) => {
  map.createPane(name).style.zIndex = 405 + i * 10;
});

const fmt = (v, unit = '') => (v === null || v === undefined) ? 'to be confirmed' : v + unit;
const fmtDate = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC'});

let stats = null, layers = {}, step = 1;
let routePoints = [], routeLayers = [], routeMarkers = {origin: null, destination: null, launch: null, landing: null};
let routeController = null;

async function addLayer(spec, pane, style) {
  // The stats contract allows either vector GeoJSON or raster image overlays.
  if (!spec) return null;
  if (spec.type === 'geojson') {
    const response = await fetch(spec.url);
    if (!response.ok) throw new Error(`Layer request failed (${response.status})`);
    const data = await response.json();
    return L.geoJSON(data, {pane, style});
  }
  if (spec.type === 'image') {  // bounds: [[south, west], [north, east]]
    const layer = L.imageOverlay(spec.url, spec.bounds, {pane, opacity: style.opacity == null ? 1 : style.opacity});
    layer.on('error', () => {
      if ($('layer-status')) {
        $('layer-status').hidden = false;
        $('layer-status').textContent = `Falha ao carregar a camada ${spec.source || 'raster'}.`;
      }
    });
    return layer;
  }
  if (spec.type === 'tile') {
    const layer = L.tileLayer(spec.url, {
      ...tileOptions, pane, opacity: style.opacity == null ? 0.48 : style.opacity,
      attribution: spec.attribution || spec.source || 'External raster layer'
    });
    layer.on('tileerror', () => {
      if ($('layer-status')) {
        $('layer-status').hidden = false;
        $('layer-status').textContent = `Falha ao carregar a camada ${spec.source || 'externa'}.`;
      }
    });
    return layer;
  }
  throw new Error('Unknown layer type: ' + spec.type);
}

function show(layer, on) {
  if (!layer) return;
  if (on && !map.hasLayer(layer)) layer.addTo(map);
  if (!on && map.hasLayer(layer)) map.removeLayer(layer);
}

function vegetationLegend(spec) {
  const legend = $('vegetation-legend');
  if (!legend || !spec || !Array.isArray(spec.legend)) return;
  legend.innerHTML = '<b>NDVI/vegetação estimada</b>';
  spec.legend.forEach(item => {
    if (!item || !item.label) return;
    const row = document.createElement('span');
    row.className = 'vegetation-key';
    row.innerHTML = `<i style="background:${ESC(item.color || '#9aa6ad')}"></i>${ESC(item.label)}`;
    legend.appendChild(row);
  });
  const note = document.createElement('small');
  note.textContent = `${spec.source || 'Fonte não informada'} · ${spec.date || 'data não informada'}`;
  legend.appendChild(note);
  legend.hidden = false;
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
    if (i + 1 === step) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current');
  });
  $('steps').scrollTop = 0;
  $('prev').disabled = step === 1;
  $('next').disabled = step === TOTAL;
  $('next').textContent = step === TOTAL ? 'End of the story' : `Next: ${stepName(step + 1)}`;

  const compare = step === 3;
  const routing = step === 5;
  $('clouds').classList.toggle('lifted', step !== 1);
  $('mapwrap').dataset.step = step;
  show(layers.radar, step === 2);
  show(layers.before, step === 2 || compare);
  show(layers.during, compare || step === 4 || routing);
  show(layers.vegetation, step >= 2);
  show(layers.validation, step === 4);
  show(impact.layer, step === 4);
  show(impact.roads, step === 4 && impact.cats.has('roads'));
  if (step !== 4 && map.closePopup) map.closePopup();
  routeLayers.forEach(layer => show(layer, routing));
  Object.values(routeMarkers).forEach(marker => show(marker, routing));
  $('curtain').hidden = !compare;
  $('legend').hidden = step < 2;
  $('before-legend').hidden = !(step === 2 || compare || routing);   // boats use rivers and lakes too
  $('during-legend').hidden = !(compare || step === 4 || routing);
  if ($('vegetation-legend')) $('vegetation-legend').hidden = !layers.vegetation || step < 2;
  $('roads-legend').hidden = step !== 4 || !impact.roads;
  $('validation-legend').hidden = step !== 4 || !layers.validation;
  $('route-legend').hidden = !routing;
  updateClip(compare);
  map.invalidateSize();
}

function stepName(n) {
  const el = document.querySelector(`.step[data-step="${n}"]`);
  return el ? el.dataset.short : '';
}

function routeMessage(text, error = false) {
  const el = $('route-status');
  el.textContent = text;
  el.classList.toggle('error', error);
}

function parsePoint(value, name) {
  const parts = value.split(',').map(part => Number(part.trim()));
  if (parts.length !== 2 || parts.some(v => !Number.isFinite(v))) {
    throw new Error(`Type the ${name} as longitude, latitude, for example 33.00, -24.53, or click the map.`);
  }
  const [lon, lat] = parts;
  if (lon < -180 || lon > 180 || lat < -90 || lat > 90) {
    throw new Error(`The ${name} is not a valid longitude, latitude pair.`);
  }
  return {lon, lat};
}

const km = (m) => m >= 1000 ? `${(m / 1000).toLocaleString('en-US', {maximumFractionDigits: 1})} km` : `${Math.round(m)} m`;
const minutes = (s) => {
  const total = Math.max(1, Math.round(s / 60));
  return total < 60 ? `${total} min` : `${Math.floor(total / 60)} h ${total % 60} min`;
};
const fmtPoint = ([lon, lat]) => `${Math.abs(lat).toFixed(4)}° ${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(4)}° ${lon < 0 ? 'W' : 'E'}`;

const ICONS = {
  drive: '<path d="M5 16V11l2-5h10l2 5v5M5 16h14M5 16v2M19 16v2M7.5 13.5h.01M16.5 13.5h.01" />',
  boat: '<path d="M3 15h18l-2.5 4h-13zM12 15V4l6 9h-6M12 6 7 13h5" />',
  walk: '<path d="M13 4.5a1.5 1.5 0 1 0 0 .01M11 21l1.5-6 2.5 2v4M9 11l3-3 3 3 2 1M12 8l-1.5 5" />',
  launch: '<path d="M4 18c2 1.5 4 1.5 6 0s4-1.5 6 0 4 1.5 4 0M12 3v10M8 9l4 4 4-4" />',
  arrive: '<path d="M12 21s-6-5.5-6-10a6 6 0 0 1 12 0c0 4.5-6 10-6 10zM12 11h.01" />',
};
const icon = (name) => `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

let routeOptions = [], selectedOption = 0, lastResult = null, boatsEnabled = true, activeField = 'origin';

function clearRoutes() {
  routeLayers.forEach(layer => map.removeLayer(layer));
  routeLayers = [];
  ['launch', 'landing'].forEach(key => {
    if (routeMarkers[key]) map.removeLayer(routeMarkers[key]);
    routeMarkers[key] = null;
  });
  document.querySelectorAll('[data-route-key]').forEach(el => { el.hidden = true; });
}

const PIN = L.divIcon({
  className: 'pin-icon', iconSize: [28, 36], iconAnchor: [14, 34],
  html: '<svg viewBox="0 0 28 36" width="28" height="36" aria-hidden="true"><path d="M14 35s11-11.2 11-20A11 11 0 0 0 3 15c0 8.8 11 20 11 20z" fill="#1b2830" stroke="#fff" stroke-width="2"/><circle cx="14" cy="15" r="4.2" fill="#fff"/></svg>',
});
const BOAT_ICON = (label) => L.divIcon({
  className: 'boat-icon', iconSize: [30, 30], iconAnchor: [15, 15],
  html: `<span title="${label}">${icon('boat')}</span>`,
});

function placeMarker(key, latlng) {
  if (routeMarkers[key]) map.removeLayer(routeMarkers[key]);
  routeMarkers[key] = key === 'origin'
    ? L.circleMarker(latlng, {radius: 8, color: COLORS.slate, weight: 4, fillColor: '#fff', fillOpacity: 1}).bindTooltip('Team base')
    : L.marker(latlng, {icon: PIN, title: 'Destination', keyboard: false});
  routeMarkers[key].addTo(map);
}

function setActiveField(key) {
  activeField = key;
  document.querySelectorAll('.dir-row').forEach((row, i) => row.classList.toggle('active', (i === 0) === (key === 'origin')));
}

function clearRouteSelection() {
  clearRoutes();
  ['origin', 'destination'].forEach(key => {
    if (routeMarkers[key]) map.removeLayer(routeMarkers[key]);
    routeMarkers[key] = null;
  });
  routePoints = [];
  routeOptions = [];
  lastResult = null;
  $('route-origin').value = '';
  $('route-destination').value = '';
  $('route-options').innerHTML = '';
  $('route-itinerary').hidden = true;
  $('route-assumptions').textContent = '';
  setActiveField('origin');
  routeMessage("Click the map to set the team's base.");
}

function selectRoutePoint(event) {
  if (step !== 5) return;
  const point = `${event.latlng.lng.toFixed(6)}, ${event.latlng.lat.toFixed(6)}`;
  const key = activeField;
  $(`route-${key}`).value = point;
  placeMarker(key, event.latlng);
  if (key === 'origin') {
    setActiveField('destination');
    if (!$('route-destination').value) { routeMessage('Now click the destination, for example a place inside the flood.'); return; }
  }
  if ($('route-origin').value && $('route-destination').value) calculateRoute();
}

function swapPoints() {
  const a = $('route-origin').value, b = $('route-destination').value;
  $('route-origin').value = b;
  $('route-destination').value = a;
  ['origin', 'destination'].forEach(key => {
    if (routeMarkers[key]) { map.removeLayer(routeMarkers[key]); routeMarkers[key] = null; }
  });
  [['origin', b], ['destination', a]].forEach(([key, value]) => {
    try { const p = parsePoint(value, key); placeMarker(key, [p.lat, p.lon]); } catch { /* empty field */ }
  });
  if (a && b) calculateRoute();
}

function setBoats(on) {
  boatsEnabled = on;
  document.querySelectorAll('.mode-switch [role=radio]').forEach(btn => {
    btn.setAttribute('aria-checked', String((btn.dataset.boats === 'true') === on));
  });
  if ($('route-origin').value && $('route-destination').value) calculateRoute();
}

function driveLeg(route) {
  return {mode: 'drive', coordinates: route.coordinates, distance_m: route.distance_m, duration_s: route.duration_s, via: route.via};
}

function buildOptions(result) {
  const opts = [];
  const water = (m) => `Crosses ${km(m)} of flood water`;
  const r = result.rescue, n = result.normal, s = result.safe;
  if (r && r.uses_boat) {
    const parts = [[r.drive_m, 'by car'], [r.boat_m, 'by boat'], [r.walk_m, 'on foot']]
      .filter(([m]) => m >= 1).map(([m, how]) => `${km(m)} ${how}`);
    opts.push({key: 'rescue', title: 'Car and boat', route: r, legs: r.legs, detail: parts.join(', '),
               note: r.portage_m > 0 ? `Includes ${km(r.portage_m)} dragging the boat over dry strips` : ''});
  }
  if (s) {
    const same = n && s.distance_m === n.distance_m && n.flooded_m === 0;
    opts.push({key: 'safe', title: same ? 'Fastest road, dry' : 'Dry roads only', route: s, legs: [driveLeg(s)],
               detail: s.via.length ? `via ${s.via.join(', ')}` : ''});
  }
  (result.alternatives || []).forEach(alt => opts.push({key: 'alt', title: 'Other dry road', route: alt, legs: [driveLeg(alt)],
                                                        detail: alt.via.length ? `via ${alt.via.join(', ')}` : ''}));
  if (r && !r.uses_boat) opts.push({key: 'rescue', title: 'Car, then on foot', route: r, legs: r.legs, detail: ''});
  if (result.least_flooded) {
    const lf = result.least_flooded;
    opts.push({key: 'least', title: 'Least water by road', route: lf, legs: [driveLeg(lf)], warn: water(lf.flooded_m)});
  }
  if (n && n.flooded_m > 0) {
    opts.push({key: 'normal', title: 'Fastest road', route: n, legs: [driveLeg(n)], warn: `${water(n.flooded_m)}: not passable by car`, blocked: true});
  }
  const rec = {rescue: 'rescue', safe: 'safe', least_flooded: 'least'}[result.recommended];
  const first = opts.findIndex(o => o.key === rec);
  if (first > 0) opts.unshift(opts.splice(first, 1)[0]);
  if (opts.length && opts[0].key === rec) opts[0].recommended = true;
  return opts;
}

function renderOptions() {
  const list = $('route-options');
  list.innerHTML = '';
  routeOptions.forEach((opt, i) => {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'option';
    btn.setAttribute('aria-pressed', String(i === selectedOption));
    const time = document.createElement('span'); time.className = 'opt-time'; time.textContent = minutes(opt.route.duration_s);
    const dist = document.createElement('span'); dist.className = 'opt-dist'; dist.textContent = km(opt.route.distance_m);
    const title = document.createElement('span'); title.className = 'opt-title'; title.textContent = opt.title;
    btn.append(time, dist, title);
    if (opt.recommended) { const tag = document.createElement('span'); tag.className = 'opt-tag'; tag.textContent = 'Recommended'; title.append(' ', tag); }
    [['opt-detail', opt.detail], ['opt-detail', opt.note], ['opt-warn', opt.warn]].forEach(([cls, text]) => {
      if (!text) return;
      const el = document.createElement('span'); el.className = cls; el.textContent = text; btn.append(el);
    });
    btn.addEventListener('click', () => selectOption(i));
    li.append(btn);
    list.append(li);
  });
}

function renderItinerary(opt) {
  const steps = $('route-steps');
  steps.innerHTML = '';
  const add = (kind, title, detail) => {
    const li = document.createElement('li');
    li.className = `stepline ${kind}`;
    li.innerHTML = `<span class="step-icon">${icon(kind)}</span>`;
    const text = document.createElement('span'); text.className = 'step-text';
    const b = document.createElement('b'); b.textContent = title; text.append(b);
    if (detail) { const d = document.createElement('span'); d.textContent = detail; text.append(d); }
    li.append(text);
    steps.append(li);
  };
  opt.legs.forEach((leg, i) => {
    if (leg.mode === 'boat') {
      const prev = opt.legs[i - 1];
      const start = leg.coordinates[0];
      const title = prev ? 'Launch the boat at the water\'s edge'
        : lastResult.origin.in_water ? 'Start on the water' : 'Launch the boat next to the team\'s base';
      add('launch', title, fmtPoint(start));
      const portage = opt.route.portage_m > 0 ? `, including ${km(opt.route.portage_m)} dragging the boat` : '';
      add('boat', `Boat ${km(leg.distance_m)}`, `${minutes(leg.duration_s)}${portage}`);
    } else if (leg.mode === 'walk') {
      add('walk', `Walk ${km(leg.distance_m)}`, minutes(leg.duration_s));
    } else {
      add('drive', `Drive ${km(leg.distance_m)}`, `${minutes(leg.duration_s)}${leg.via && leg.via.length ? ` via ${leg.via.join(', ')}` : ''}`);
    }
  });
  const inWater = lastResult.destination.in_water;
  add('arrive', inWater ? 'Arrive in the flood water' : 'Arrive', fmtPoint(lastResult.destination.input));
  $('route-itinerary').hidden = false;
}

function drawLine(coords, style, casing) {
  const latlngs = coords.map(([lon, lat]) => [lat, lon]);
  if (casing) routeLayers.push(L.polyline(latlngs, {color: '#fff', weight: style.weight + 4, opacity: 0.95, interactive: false}).addTo(map));
  const line = L.polyline(latlngs, style).addTo(map);
  routeLayers.push(line);
  return line;
}

const LEG_STYLE = {
  drive: {color: COLORS.slate, weight: 6},
  boat: {color: COLORS.slate, weight: 5, dashArray: '10 9', lineCap: 'butt'},
  walk: {color: COLORS.slate, weight: 4, dashArray: '1 8'},
};

function selectOption(i, fit = false) {
  selectedOption = i;
  clearRoutes();
  const present = new Set();
  const bounds = L.latLngBounds([]);
  // other options first, in grey, clickable like on a road map
  routeOptions.forEach((opt, j) => {
    if (j === i) return;
    opt.legs.forEach(leg => {
      const line = drawLine(leg.coordinates, {color: '#7d8b93', weight: 5, opacity: 0.85}, true);
      line.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        selectOption(j);
        const card = document.querySelectorAll('#route-options .option')[j];
        if (card) card.scrollIntoView({block: 'nearest', behavior: 'smooth'});
      });
      line.bindTooltip(`${opt.title}: ${minutes(opt.route.duration_s)}`, {sticky: true});
    });
    present.add('other');
  });
  const opt = routeOptions[i];
  opt.legs.forEach(leg => {
    drawLine(leg.coordinates, {...LEG_STYLE[leg.mode], interactive: false}, true);
    present.add(leg.mode);
    leg.coordinates.forEach(([lon, lat]) => bounds.extend([lat, lon]));
  });
  if (opt.blocked || opt.key === 'least') {
    (lastResult.blocked_segments || []).forEach(seg => drawLine(seg.coordinates, {color: COLORS.newwater, weight: 7, interactive: false}));
    if ((lastResult.blocked_segments || []).length) present.add('blocked');
  }
  if (opt.route.launch) routeMarkers.launch = L.marker([opt.route.launch[1], opt.route.launch[0]], {icon: BOAT_ICON('Boat launch'), keyboard: false}).addTo(map);
  if (opt.route.landing) routeMarkers.landing = L.marker([opt.route.landing[1], opt.route.landing[0]], {icon: BOAT_ICON('Boat landing'), keyboard: false}).addTo(map);
  ['origin', 'destination'].forEach(key => { if (routeMarkers[key]) routeMarkers[key].bringToFront?.(); });
  document.querySelectorAll('[data-route-key]').forEach(el => { el.hidden = !present.has(el.dataset.routeKey); });
  document.querySelectorAll('#route-options .option').forEach((btn, j) => btn.setAttribute('aria-pressed', String(j === i)));
  renderItinerary(opt);
  if (fit && bounds.isValid()) map.fitBounds(bounds.pad(0.15), {maxZoom: 15});
}

function showRoutes(result) {
  lastResult = result;
  routeOptions = buildOptions(result);
  selectedOption = 0;
  renderOptions();
  if (routeOptions.length) selectOption(0, true);
  const a = result.boat_assumptions;
  $('route-assumptions').textContent = a
    ? `Boat legs assume ${a.boat_speed_kmh} km/h on open water and ${a.launch_minutes} minutes to launch; car speeds depend on the road type.`
    : 'Car speeds depend on the road type.';
  routeMessage(result.message || '', result.status !== 'ok');
}

async function calculateRoute() {
  if (routeController) routeController.abort();
  const progress = $('route-progress');
  const calculateButton = $('route-calculate');
  const cancelButton = $('route-cancel');
  const controller = new AbortController();
  routeController = controller;
  const timeout = setTimeout(() => controller.abort(), 20000);
  progress.hidden = false;
  progress.value = 15;
  calculateButton.disabled = true;
  cancelButton.hidden = false;
  try {
    const origin = parsePoint($('route-origin').value, "team's base");
    const destination = parsePoint($('route-destination').value, 'destination');
    placeMarker('origin', [origin.lat, origin.lon]);
    placeMarker('destination', [destination.lat, destination.lon]);
    routePoints = [$('route-origin').value, $('route-destination').value];
    routeMessage('Finding routes…');
    progress.value = 35;
    const response = await fetch('/api/route', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({origin, destination, alternatives: 2, boats: boatsEnabled}),
      signal: controller.signal
    });
    progress.value = 80;
    let result;
    try { result = await response.json(); } catch { result = {}; }
    if (routeController !== controller) return;            // a newer request replaced this one
    clearRoutes();
    $('route-options').innerHTML = '';
    $('route-itinerary').hidden = true;
    if (!response.ok) throw new Error(result.error || `The route service answered with HTTP ${response.status}.`);
    showRoutes(result);
    setStep(5);
  } catch (error) {
    if (routeController !== controller && error.name === 'AbortError') return;
    clearRoutes();
    let message = error.message;
    if (error.name === 'AbortError') message = 'Route search stopped: it was cancelled or took longer than 20 seconds.';
    else if (error instanceof TypeError) message = 'The route service could not be reached. Check that the Flask app is running.';
    routeMessage(message, true);
  } finally {
    clearTimeout(timeout);
    if (routeController === controller) {
      routeController = null;
      progress.value = 100;
      setTimeout(() => { progress.hidden = true; }, 250);
      calculateButton.disabled = false;
      cancelButton.hidden = true;
    }
  }
}

function cancelRoute() {
  if (routeController) routeController.abort();
}

// ----- step 4: the impact map (schools, health, communities, bridges, roads)
// Colour stays data-only: red = on new water, amber = cut off by flooded roads,
// slate = dry road access, grey = unknown. Shape tells the category.
const STATE_INFO = {
  in_water: {key: 'On new water', label: 'On new water', short: 'on water', fill: COLORS.newwater, ink: '#fff'},
  isolated: {key: 'Cut off', label: 'Cut off by flooded roads', short: 'cut off', fill: COLORS.roads, ink: COLORS.slate},
  near_water: {key: 'Near new water', label: 'Near new water', short: 'near water', fill: '#fff', ink: COLORS.newwater},
  accessible: {key: 'Dry road access', label: 'Dry road access', short: 'dry access', fill: COLORS.slate, ink: '#fff'},
  no_road: {key: 'No road link', label: 'No mapped road link', short: 'no road', fill: '#8e9ba3', ink: '#fff'},
  not_observed: {key: 'Not seen by radar', label: 'Outside radar coverage', short: 'not seen', fill: '#c3ccd1', ink: '#fff'},
};
const STATE_ORDER = Object.keys(STATE_INFO);
const CATEGORY_INFO = {
  school: {label: 'Schools', icon: 'school'},
  health: {label: 'Health', icon: 'health'},
  community: {label: 'Communities', icon: 'home'},
  bridge: {label: 'Bridges', icon: 'bridge'},
};
// 24 x 24 pictograms, filled: a mortarboard, a medical cross, a house, two houses, a bridge
const PICTO = {
  school: 'M12 3.5 1.5 9 12 14.5 20 10.3V16h2V9zM5.5 12.6v3.6c0 1.9 2.9 3.3 6.5 3.3s6.5-1.4 6.5-3.3v-3.6L12 16z',
  health: 'M9.5 3h5v6.5H21v5h-6.5V21h-5v-6.5H3v-5h6.5z',
  home: 'M12 3 2 11.2h3V20h5.2v-5.5h3.6V20H19v-8.8h3z',
  homes: 'M1.5 12.2 8 6.5l6.5 5.7h-2V20h-3v-4h-3v4h-3v-7.8zM15 9.3l3.8-3.3 4.2 3.7h-1.6V20h-5.5v-8.3z',
  bridge: 'M1 8h22v2.4h-1.6V19h-3.6v-2.5a5.8 5.8 0 0 0-11.6 0V19H2.6v-8.6H1z',
};
const PATHS = {};
const picto = (name) => PATHS[name] || (PATHS[name] = new Path2D(PICTO[name]));
const iconOf = (p) => p.kind === 'building_cluster' ? 'homes' : CATEGORY_INFO[p.category].icon;
const KIND_LABEL = {
  school: 'School', college: 'College', kindergarten: 'Kindergarten',
  hospital: 'Hospital', clinic: 'Clinic', doctors: 'Doctors', pharmacy: 'Pharmacy', dentist: 'Dentist',
  centre: 'Health centre', doctor: 'Doctor', laboratory: 'Laboratory', optometrist: 'Optometrist',
  city: 'City', town: 'Town', village: 'Village', hamlet: 'Hamlet', suburb: 'Suburb',
  building_cluster: 'Cluster of buildings',
};
const kindLabel =(k) => KIND_LABEL[k] || (k ? k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, ' ') : '');
const ROAD_LABEL = {primary: 'Primary and trunk', secondary: 'Secondary', tertiary: 'Tertiary', local: 'Local and service', track: 'Tracks'};

// Canvas markers. Zoomed out they are small dots in the colour of their state,
// so the map reads as a pattern; from DETAIL_ZOOM they become round badges
// carrying a pictogram of what the place is.
const DETAIL_ZOOM = 11;
L.Canvas.include({
  _updateShape(layer) {
    if (!this._drawing || layer._empty()) return;
    const p = layer._point, ctx = this._ctx, r = layer._radius, o = layer.options, s = STATE_INFO[o.state];
    ctx.beginPath();
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    ctx.fillStyle = s.fill;
    ctx.fill();
    ctx.lineWidth = o.detail ? 2 : 1;
    ctx.strokeStyle = o.state === 'near_water' ? COLORS.newwater : 'rgba(255,255,255,.95)';
    ctx.stroke();
    if (!o.detail) return;
    const k = (r * 1.25) / 24;
    ctx.save();
    ctx.translate(p.x - 12 * k, p.y - 12 * k);
    ctx.scale(k, k);
    ctx.fillStyle = s.ink;
    ctx.fill(picto(o.icon));
    ctx.restore();
  },
});
const ShapeMarker = L.CircleMarker.extend({
  _updatePath() { this._renderer._updateShape(this); },
});

const impact = {data: null, markers: [], roads: null, cats: new Set(Object.keys(CATEGORY_INFO).concat('roads')),
                states: new Set(['in_water', 'isolated', 'near_water']), layer: null};

function iconSvg(icon, state, size = 18) {
  const s = STATE_INFO[state] || STATE_INFO.accessible;
  const ring = state === 'near_water' ? COLORS.newwater : 'none';
  return `<svg viewBox="0 0 28 28" width="${size}" height="${size}" aria-hidden="true"><circle cx="14" cy="14" r="13" fill="${s.fill}" stroke="${ring}" stroke-width="2"/>` +
    `<path transform="translate(5.6 5.6) scale(.7)" fill="${s.ink}" d="${PICTO[icon]}"/></svg>`;
}

function markerRadius(p, detail) {
  if (!detail) return p.kind === 'building_cluster' ? 2.5 : 3.5;
  if (p.kind === 'building_cluster') return Math.min(14, 9 + Math.sqrt(p.buildings) / 8);
  return {city: 13, town: 12}[p.kind] || 10.5;
}

const metresText = (m) => m >= 1000 ? `${(m / 1000).toLocaleString('en-US', {maximumFractionDigits: 1})} km` : `${m} m`;
const ESC = (t) => String(t).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

function impactTitle(p) {
  if (p.kind === 'building_cluster') return `Cluster of ${p.buildings.toLocaleString('en-US')} buildings`;
  if (p.category === 'bridge') return p.name ? `Bridge on ${p.name}` : `Bridge (${kindLabel(p.kind).toLowerCase()} road)`;
  return p.name || `Unnamed ${kindLabel(p.kind).toLowerCase()}`;
}

function stateExplanation(p) {
  const near = impact.data.parameters.near_water_m, snap = impact.data.parameters.road_snap_m;
  const approach = impact.data.parameters.bridge_approach_m;
  const area = p.geom === 'area' ? 'Part of its mapped area is' : (p.kind === 'building_cluster' ? 'These buildings are' : 'It is');
  if (p.category === 'bridge') {
    return {
      in_water: `Every road leaving at least one end is on new water within ${approach} m of the bridge. The bridge deck itself is not tested.`,
      isolated: 'Its approaches are dry, but every road from the main network to it crosses new water.',
      near_water: `New water within ${near} m of the bridge or on part of its approaches; at least one dry way on and off remains.`,
      accessible: 'A dry road links it to the main road network.',
      no_road: 'Its roads are not linked to the main road network in OpenStreetMap.',
      not_observed: 'The radar footprint does not cover this place.',
    }[p.state];
  }
  return {
    in_water: `${area} on new flood water seen by the radar.`,
    isolated: 'Out of the water, but every road from the main network to it crosses new water: no dry way in by car.',
    near_water: `Within ${near} m of new water; a dry road still links it to the main network.`,
    accessible: 'A dry road links it to the main road network.',
    no_road: p.road_m === null ? `No mapped drivable road within ${snap} m in OpenStreetMap.`
      : 'Its nearby roads are not linked to the main road network in OpenStreetMap (a gap in the map).',
    not_observed: 'The radar footprint does not cover this place, so nothing is known about the water here.',
  }[p.state];
}

function impactPopup(p, lat, lon) {
  const info = STATE_INFO[p.state];
  const lines = [];
  const kind = p.kind === 'building_cluster' ? 'Building footprints (OSM)' : `${kindLabel(p.kind)}`;
  const osm = p.osm ? ` · <a href="https://www.openstreetmap.org/${ESC(p.osm)}" target="_blank" rel="noopener">OSM ${ESC(p.osm)}</a>` : '';
  lines.push(`<p class="pp-kind">${iconSvg(iconOf(p), p.state, 22)} ${ESC(kind)}${osm}</p>`);
  lines.push(`<p class="pp-state" data-state="${p.state}"><b>${ESC(info.label)}</b> ${ESC(stateExplanation(p))}</p>`);
  const facts = [];
  if (p.state !== 'not_observed') {
    facts.push(['New water', p.water_m === 0 ? 'on it' : p.water_m === null ? 'more than 5 km away' : `${metresText(p.water_m)} away`]);
  }
  if (p.category === 'bridge') {
    if (p.length_m) facts.push(['Length', metresText(p.length_m)]);
    if (p.approaches) facts.push(['Approach roads with new water', `${p.approaches_flooded} of ${p.approaches}`]);
  } else if (p.road_m !== null && p.road_m !== undefined) {
    facts.push(['Nearest mapped road', metresText(p.road_m)]);
  }
  if (p.kind === 'building_cluster') facts.push(['Spread', `about ${metresText(p.extent_m)}`]);
  if (facts.length) lines.push('<dl class="pp-facts">' + facts.map(([k, v]) => `<dt>${ESC(k)}</dt><dd>${ESC(v)}</dd>`).join('') + '</dl>');
  const nh = p.nearest_health;
  if (nh) {
    lines.push(`<p class="pp-health">Nearest health facility with dry road access: <b>${ESC(nh.name || 'unnamed ' + kindLabel(nh.kind).toLowerCase())}</b>, ${nh.km.toLocaleString('en-US')} km in a straight line.</p>`);
  }
  if (!STATIC) {
    const actions = [`<button type="button" class="primary pp-route" data-lon="${lon}" data-lat="${lat}">Rescue route to here</button>`];
    if (nh) actions.push(`<button type="button" class="quiet pp-from" data-lon="${lon}" data-lat="${lat}" data-from-lon="${nh.lon}" data-from-lat="${nh.lat}">Route from that facility</button>`);
    lines.push(`<p class="pp-actions">${actions.join('')}</p>`);
  }
  lines.push(`<p class="pp-note">Estimate from radar water on ${ESC(fmtDate(impact.data.radar_date))}. Not confirmed damage. &copy; OpenStreetMap contributors</p>`);
  return `<div class="impact-popup"><h3>${ESC(impactTitle(p))}</h3>${lines.join('')}</div>`;
}

function routeToPoint(lon, lat, from) {
  map.closePopup();
  setStep(5);
  const dest = `${Number(lon).toFixed(6)}, ${Number(lat).toFixed(6)}`;
  $('route-destination').value = dest;
  placeMarker('destination', [lat, lon]);
  if (from) {
    $('route-origin').value = `${Number(from[0]).toFixed(6)}, ${Number(from[1]).toFixed(6)}`;
    placeMarker('origin', [from[1], from[0]]);
  }
  if ($('route-origin').value) { calculateRoute(); return; }
  setActiveField('origin');
  clearRoutes();
  $('route-options').innerHTML = '';
  $('route-itinerary').hidden = true;
  routeMessage("Destination set from the impact map. Now click the map to set the team's base.");
  map.setView([lat, lon], Math.max(map.getZoom(), 11));
}

function buildImpactLayer() {
  const renderer = L.canvas({pane: 'impactPane', padding: 0.4, tolerance: 6});
  const detail = map.getZoom() >= DETAIL_ZOOM;
  impact.markers = impact.data.features.features.map(f => {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    const m = new ShapeMarker([lat, lon], {renderer, state: p.state, icon: iconOf(p), detail, radius: markerRadius(p, detail)});
    m.feature = p;
    m.bindPopup(() => impactPopup(p, lat, lon), {maxWidth: 300, className: 'impact-pop'});
    return m;
  });
  // the most urgent states are drawn last, on top
  const rank = (p) => STATE_ORDER.length - STATE_ORDER.indexOf(p.state);
  impact.markers.sort((a, b) => rank(a.feature) - rank(b.feature));
  impact.layer = L.layerGroup();
  impact.detail = detail;
  map.on('zoomend', () => {
    const d = map.getZoom() >= DETAIL_ZOOM;
    if (d === impact.detail) return;
    impact.detail = d;
    impact.markers.forEach(m => { m.options.detail = d; m.setRadius(markerRadius(m.feature, d)); });
  });
}

function filterImpact() {
  if (!impact.layer) return;
  impact.layer.clearLayers();
  impact.markers.forEach(m => {
    if (impact.cats.has(m.feature.category) && impact.states.has(m.feature.state)) impact.layer.addLayer(m);
  });
  show(impact.roads, step === 4 && impact.cats.has('roads'));
  renderImpactCounts();
}

function renderImpactCounts() {
  const cats = impact.data.categories;
  const selected = Object.keys(CATEGORY_INFO).filter(c => impact.cats.has(c));
  let total = 0;
  const key = $('impact-states');
  key.innerHTML = '';
  STATE_ORDER.forEach(state => {
    const n = selected.reduce((sum, c) => sum + cats[c].by_state[state], 0);
    total += n;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'state-chip';
    btn.dataset.state = state;
    btn.setAttribute('aria-pressed', String(impact.states.has(state)));
    btn.innerHTML = `<span class="dot"></span><span class="lbl" title="${ESC(STATE_INFO[state].label)}">${ESC(STATE_INFO[state].key)}</span><b>${n.toLocaleString('en-US')}</b>`;
    btn.addEventListener('click', () => {
      if (impact.states.has(state)) impact.states.delete(state); else impact.states.add(state);
      filterImpact();
    });
    key.append(btn);
  });
  $('impact-total').textContent = total.toLocaleString('en-US');
  document.querySelectorAll('#impact-cats .cat-row').forEach(row => row.setAttribute('aria-pressed', String(impact.cats.has(row.dataset.cat))));
  $('impact-roads-toggle').setAttribute('aria-pressed', String(impact.cats.has('roads')));
}

function toggleCategory(key) {
  if (impact.cats.has(key)) impact.cats.delete(key); else impact.cats.add(key);
  filterImpact();
}

function renderImpactPanel() {
  const d = impact.data, fmtN = (n) => n.toLocaleString('en-US');
  $('impact-date').textContent = new Date(d.radar_date + 'T00:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'});

  // one row per category: pictogram, name, the urgent numbers and a bar split by state
  const list = $('impact-cats');
  list.innerHTML = '';
  Object.entries(CATEGORY_INFO).forEach(([key, info]) => {
    const c = d.categories[key];
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'cat-row';
    btn.dataset.cat = key;
    const urgent = ['in_water', 'isolated'].filter(s => c.by_state[s] > 0)
      .map(s => `<span class="hl ${s}">${fmtN(c.by_state[s])} ${STATE_INFO[s].short}</span>`).join('') || '<span class="hl none">none on water or cut off</span>';
    const bar = STATE_ORDER.filter(s => c.by_state[s] > 0)
      .map(s => `<i class="seg ${s}" style="flex-grow:${c.by_state[s]}" title="${ESC(STATE_INFO[s].label)}: ${fmtN(c.by_state[s])}"></i>`).join('');
    btn.innerHTML = `<span class="cat-icon">${iconSvg(info.icon, 'accessible', 34)}</span>` +
      `<span class="cat-name">${ESC(info.label)}<small>${fmtN(c.total)} mapped</small></span>` +
      `<span class="cat-hl">${urgent}</span><span class="bar" aria-hidden="true">${bar}</span>`;
    btn.addEventListener('click', () => toggleCategory(key));
    li.append(btn);
    list.append(li);
  });
  $('impact-roads-km').textContent = `${d.roads.flooded_km.toLocaleString('en-US')} km`;
  $('impact-roads-toggle').onclick = () => toggleCategory('roads');

  $('impact-roads').innerHTML = '';
  Object.entries(d.roads.by_class).forEach(([k, r]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<th scope="row">${ESC(ROAD_LABEL[k] || k)}</th><td class="num">${r.flooded_km.toLocaleString('en-US')} km</td><td class="num">${Math.round(r.observed_km).toLocaleString('en-US')} km</td>`;
    $('impact-roads').append(tr);
  });

  const b = d.buildings.by_state, comm = d.categories.community, c = d.categories;
  $('impact-buildings').textContent =
    `Communities are ${fmtN(comm.places.total)} named places and ${fmtN(comm.clusters.total)} clusters of ${d.parameters.min_cluster_buildings}+ buildings. ` +
    `Of ${fmtN(d.buildings.total)} mapped building footprints, ${fmtN(b.in_water)} are on new water, ${fmtN(b.isolated)} are cut off and ` +
    `${fmtN(b.near_water)} are within ${d.parameters.near_water_m} m of new water. Footprints are not people: OpenStreetMap has no population here.`;
  $('impact-coverage').textContent =
    `OpenStreetMap maps ${fmtN(c.school.mapped)} schools, ${fmtN(c.health.mapped)} health facilities and ${fmtN(comm.places.total)} named places here; ` +
    `rural mapping is incomplete, so a place missing here is not a place the flood spared. The radar covers ` +
    `${Math.round(d.coverage.radar_observed_fraction * 100)}% of the area; the south, including Maputo, is outside it. ` +
    `OSM extract of ${String(d.osm_timestamp || '').slice(0, 10) || 'unknown date'}.`;
  $('impact-panel').hidden = false;
}

async function loadImpact() {
  const spec = stats.layers.impact_features;
  if (!spec || !stats.impact || !stats.impact.categories) return;
  const featureResponse = await fetch(spec.url);
  if (!featureResponse.ok) throw new Error(`Impact features request failed (${featureResponse.status})`);
  impact.data = {...stats.impact, features: await featureResponse.json()};
  if (stats.layers.impact_roads) {
    const response = await fetch(stats.layers.impact_roads.url);
    if (!response.ok) throw new Error(`Impact roads request failed (${response.status})`);
    const roads = await response.json();
    const roadWeight = () => (map.getZoom() >= DETAIL_ZOOM ? 3.5 : 1.6);
    impact.roads = L.geoJSON(roads, {pane: 'roadsPane', style: () => ({color: COLORS.roads, weight: roadWeight(), opacity: 1})});
    map.on('zoomend', () => impact.roads.setStyle({weight: roadWeight()}));
    impact.roads.bindTooltip(l => {
      const p = l.feature.properties;
      return `${ESC(p.name || kindLabel(p.highway) + ' road')}: ${metresText(p.flooded_m)} on new water`;
    }, {sticky: true});
    layerControl.addOverlay(impact.roads, 'Estradas em água nova (OSM)');
  }
  buildImpactLayer();
  layerControl.addOverlay(impact.layer, 'Impactos (OSM)');
  renderImpactPanel();
  filterImpact();
  // Leaflet stops clicks inside popups from bubbling and re-renders popup content,
  // so listen in the capture phase on the map container
  $('map').addEventListener('click', (ev) => {
    const btn = ev.target.closest('.pp-route, .pp-from');
    if (!btn) return;
    const from = btn.classList.contains('pp-from') ? [Number(btn.dataset.fromLon), Number(btn.dataset.fromLat)] : null;
    routeToPoint(Number(btn.dataset.lon), Number(btn.dataset.lat), from);
  }, true);
}

function card(label, value, mock) {
  const d = document.createElement('div');
  d.className = 'fact';
  const b = document.createElement('b'); b.textContent = value;
  const s = document.createElement('span'); s.textContent = label;
  if (mock) { const m = document.createElement('i'); m.className = 'mock'; m.textContent = 'mock'; s.appendChild(m); }
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
  layers.before = await addLayer(stats.layers.before, 'beforePane', {color: COLORS.standing, weight: 1.5, fillColor: COLORS.standing, fillOpacity: 0.72, opacity: 0.72});
  layers.during = await addLayer(stats.layers.during, 'duringPane', {color: COLORS.newwater, weight: 2, fillColor: COLORS.newwater, fillOpacity: 0.78, opacity: 0.78});
  if (layers.radar) layerControl.addOverlay(layers.radar, 'Radar NISAR (contexto)');
  if (layers.before) layerControl.addOverlay(layers.before, 'Água permanente (NISAR)');
  if (layers.during) layerControl.addOverlay(layers.during, 'Água nova (NISAR)');
  if (stats.layers.vegetation) {
    try {
      layers.vegetation = await addLayer(stats.layers.vegetation, 'vegetationPane', {opacity: 0.46});
      vegetationLegend(stats.layers.vegetation);
      layerControl.addOverlay(layers.vegetation, 'NDVI/vegetação estimada');
    } catch (error) {
      console.error('vegetation layer unavailable', error);
      if ($('layer-status')) {
        $('layer-status').hidden = false;
        $('layer-status').textContent = 'A camada de vegetação está indisponível; as camadas NISAR continuam funcionando.';
      }
    }
  }
  layers.validation = await addLayer(
    stats.layers.validation_difference,
    'validationPane',
    (feature) => {
      const color = feature.properties.classification === 'system_only' ? '#e0442a' : '#7b2cbf';
      return {color, weight: 1, fillColor: color, fillOpacity: 0.72};
    },
  );
  if (layers.validation) layerControl.addOverlay(layers.validation, 'Diferença NISAR x Copernicus');
  try {
    await loadImpact();
  } catch (error) {
    console.error('impact map unavailable', error);   // the rest of the story still works
    if ($('layer-status')) {
      $('layer-status').hidden = false;
      $('layer-status').textContent = 'Camadas de impacto OSM indisponíveis; a narrativa NISAR continua funcionando.';
    }
  }

  // text that depends on the data
  $('date-before').textContent = fmtDate(stats.scenes.before.date);
  $('date-during').textContent = fmtDate(stats.scenes.during.date);
  $('tag-before').textContent = fmtDate(stats.scenes.before.date);
  $('tag-during').textContent = fmtDate(stats.scenes.during.date);
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


  const validation = stats.validation;
  if (validation) {
    const metrics = $('validation-metrics');
    const km2 = (value) => `${Number(value).toLocaleString('en-US', {maximumFractionDigits: 1})} km²`;
    const systemOnlyArea = validation.system_only_area_km2 ??
      validation.nisar_new_water_aoi_km2 - validation.intersection_area_km2;
    const referenceOnlyArea = validation.reference_only_area_km2 ??
      validation.ems_flood_area_aoi_km2 - validation.intersection_area_km2;
    [
      ['NISAR new water in AOI02', km2(validation.nisar_new_water_aoi_km2)],
      ['EMS mapped flood in AOI02', km2(validation.ems_flood_area_aoi_km2)],
      ['Intersecting area', km2(validation.intersection_area_km2)],
      ['Detected only by NISAR', km2(systemOnlyArea)],
      ['Mapped only by Copernicus', km2(referenceOnlyArea)],
      ['Spatial IoU', Number(validation.iou).toFixed(2)],
    ].forEach(([label, value]) => metrics.appendChild(card(label, value, false)));
    $('validation-note').textContent =
      `${validation.product}, ${validation.reference}, acquired ${validation.acquisition_utc}. ` +
      `${validation.interpretation} Overlap: ` +
      `${Math.round(validation.overlap_fraction_nisar * 100)}% of NISAR area; ` +
      `${Math.round(validation.overlap_fraction_ems * 100)}% of EMS area. ` +
      'IoU is the intersection divided by the union; this comparison covers AOI02 only.';
    const source = document.createElement('a');
    source.href = validation.reference_url || 'https://mapping.emergency.copernicus.eu/activations/EMSR857/';
    source.target = '_blank';
    source.rel = 'noopener noreferrer';
    source.textContent = 'Copernicus EMSR857 source';
    $('validation-note').append(' Source: ', source);
    if (!layers.validation) {
      $('validation-map-note').textContent =
        'Difference polygons are not available in this build. Rebuild the static site after running the reference validation pipeline.';
      $('validation-map-note').hidden = false;
    }
    $('validation-section').hidden = false;
  }

  const rows = [
    ['Before', stats.scenes.before.date], ['During', stats.scenes.during.date],
    ['Track / frame', `${stats.scenes.during.track} / ${stats.scenes.during.frame}`],
    ['Direction', stats.scenes.during.direction],
    ['Polarizations', fmt(stats.scenes.during.polarizations && stats.scenes.during.polarizations.join(', '))],
    ['Data level', stats.maturity], ['Product', stats.product],
    ['New water', Math.round(stats.flooded_area_km2) + ' km²' + (stats.mock ? ' (mock)' : '')],
    ['Permanent water', Math.round(stats.permanent_water_km2) + ' km²' + (stats.mock ? ' (mock)' : '')],
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
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('aria-label', `Step ${i}: ${stepName(i)}`);
    const n = document.createElement('span'); n.className = 'n'; n.textContent = i;
    const label = document.createElement('span'); label.className = 'label'; label.textContent = stepName(i);
    b.append(n, label);
    b.addEventListener('click', () => setStep(i));
    li.appendChild(b);
    nav.appendChild(li);
  }
  $('prev').addEventListener('click', () => setStep(step - 1));
  $('next').addEventListener('click', () => setStep(step + 1));
  document.addEventListener('keydown', (ev) => {
    // Arrow keys move the story, except while typing or dragging the curtain.
    if (ev.target.closest('input, textarea, select')) return;
    if (ev.key === 'ArrowRight') setStep(step + 1);
    if (ev.key === 'ArrowLeft') setStep(step - 1);
  });
  $('slider').addEventListener('input', () => updateClip(step === 3));
  map.on('move zoom resize', () => updateClip(step === 3));
  if (!STATIC) {
    $('route-calculate').addEventListener('click', calculateRoute);
    $('route-cancel').addEventListener('click', cancelRoute);
    $('route-clear').addEventListener('click', clearRouteSelection);
    $('route-swap').addEventListener('click', swapPoints);
    document.querySelectorAll('.mode-switch [role=radio]').forEach(btn =>
      btn.addEventListener('click', () => setBoats(btn.dataset.boats === 'true')));
    ['origin', 'destination'].forEach(key => {
      $(`route-${key}`).addEventListener('focus', () => setActiveField(key));
      $(`route-${key}`).addEventListener('keydown', (ev) => { if (ev.key === 'Enter') calculateRoute(); });
    });
    setActiveField('origin');
    map.on('click', selectRoutePoint);
  } else {
    $('route-planner-controls').hidden = true;
    $('static-route-note').hidden = false;
  }

  $('legend-toggle').addEventListener('click', () => {
    const expanded = $('legend-toggle').getAttribute('aria-expanded') === 'true';
    $('legend-toggle').setAttribute('aria-expanded', String(!expanded));
    $('legend-content').hidden = expanded;
  });
  setStep(1);
})();
