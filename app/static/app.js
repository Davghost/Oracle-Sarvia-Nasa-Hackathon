// The static GitHub Pages copy has no Flask backend, so it drops the routing step.
const STATIC = Boolean(window.STATS_URL);
if (STATIC) document.getElementById('routing-step').remove();
const TOTAL = STATIC ? 4 : 5;
const COLORS = {standing: '#1f5fae', newwater: '#e0442a', roads: '#f0a500', slate: '#1b2830', safe: '#1b8a4b'};
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
let routePoints = [], routeLayers = [], routeMarkers = {origin: null, destination: null, launch: null, landing: null};
let routeController = null;

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
  show(layers.roads, step === 4);
  routeLayers.forEach(layer => show(layer, routing));
  Object.values(routeMarkers).forEach(marker => show(marker, routing));
  $('curtain').hidden = !compare;
  $('legend').hidden = step < 2;
  $('before-legend').hidden = !(step === 2 || compare || routing);   // boats use rivers and lakes too
  $('during-legend').hidden = !(compare || step === 4 || routing);
  $('roads-legend').hidden = step !== 4 || !layers.roads;
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
  layers.before = await addLayer(stats.layers.before, 'beforePane', {color: COLORS.standing, weight: 1, fillColor: COLORS.standing, fillOpacity: 0.65});
  layers.during = await addLayer(stats.layers.during, 'duringPane', {color: COLORS.newwater, weight: 1, fillColor: COLORS.newwater, fillOpacity: 0.65});
  layers.roads = await addLayer(stats.layers.roads_blocked, 'roadsPane', {
    color: COLORS.roads, weight: 3, opacity: 1,
  });

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
  }

  setStep(1);
})();
