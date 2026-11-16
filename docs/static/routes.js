// The route tool: a full-size map with the controls in the left panel.
// Route planning (car and boat), places and their filters, a layer tree and map
// styles. Map, data layers and the impact map come from core.js.

let stats = null, layers = {};
let routeLayers = [], routeMarkers = {origin: null, destination: null, launch: null, landing: null};
let routeController = null, routeOptions = [], selectedOption = 0, lastResult = null;
let boatsEnabled = true, activeField = 'origin', lastPopupClose = 0;

// ----- route planner
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
  if (lon < -180 || lon > 180 || lat < -90 || lat > 90) throw new Error(`The ${name} is not a valid longitude, latitude pair.`);
  return {lon, lat};
}

const ICONS = {
  drive: '<path d="M5 16V11l2-5h10l2 5v5M5 16h14M5 16v2M19 16v2M7.5 13.5h.01M16.5 13.5h.01" />',
  boat: '<path d="M3 15h18l-2.5 4h-13zM12 15V4l6 9h-6M12 6 7 13h5" />',
  walk: '<path d="M13 4.5a1.5 1.5 0 1 0 0 .01M11 21l1.5-6 2.5 2v4M9 11l3-3 3 3 2 1M12 8l-1.5 5" />',
  launch: '<path d="M4 18c2 1.5 4 1.5 6 0s4-1.5 6 0 4 1.5 4 0M12 3v10M8 9l4 4 4-4" />',
  arrive: '<path d="M12 21s-6-5.5-6-10a6 6 0 0 1 12 0c0 4.5-6 10-6 10zM12 11h.01" />',
};
const icon = (name) => `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

const PIN = L.divIcon({
  className: 'pin-icon', iconSize: [28, 36], iconAnchor: [14, 34],
  html: '<svg viewBox="0 0 28 36" width="28" height="36" aria-hidden="true"><path d="M14 35s11-11.2 11-20A11 11 0 0 0 3 15c0 8.8 11 20 11 20z" fill="#1b2830" stroke="#fff" stroke-width="2"/><circle cx="14" cy="15" r="4.2" fill="#fff"/></svg>',
});
const BASE_ICON = L.divIcon({className: 'base-icon', iconSize: [22, 22], iconAnchor: [11, 11], html: '<span></span>'});
const BOAT_ICON = (label) => L.divIcon({className: 'boat-icon', iconSize: [30, 30], iconAnchor: [15, 15], html: `<span title="${label}">${icon('boat')}</span>`});

function clearRoutes() {
  routeLayers.forEach(layer => map.removeLayer(layer));
  routeLayers = [];
  ['launch', 'landing'].forEach(key => {
    if (routeMarkers[key]) map.removeLayer(routeMarkers[key]);
    routeMarkers[key] = null;
  });
  document.querySelectorAll('[data-route-key]').forEach(el => { el.hidden = true; });
  $('legend').hidden = true;
}

// Base and destination are draggable: dropping one recalculates the route.
function placeMarker(key, latlng) {
  if (routeMarkers[key]) map.removeLayer(routeMarkers[key]);
  const marker = L.marker(latlng, {
    icon: key === 'origin' ? BASE_ICON : PIN, draggable: !STATIC, keyboard: false,
    title: key === 'origin' ? 'Team base (drag to move)' : 'Destination (drag to move)', zIndexOffset: 1000,
  });
  marker.on('dragend', () => {
    const p = marker.getLatLng();
    $(`route-${key}`).value = lonLat(p.lng, p.lat);
    if ($('route-origin').value && $('route-destination').value) calculateRoute();
  });
  routeMarkers[key] = marker.addTo(map);
}

function setActiveField(key) {
  activeField = key;
  document.querySelectorAll('.dir-row').forEach((row, i) => row.classList.toggle('active', (i === 0) === (key === 'origin')));
}

function resetResults() {
  clearRoutes();
  routeOptions = [];
  lastResult = null;
  $('route-options').innerHTML = '';
  $('route-itinerary').hidden = true;
  $('route-assumptions').textContent = '';
}

function clearRouteSelection() {
  resetResults();
  ['origin', 'destination'].forEach(key => {
    if (routeMarkers[key]) map.removeLayer(routeMarkers[key]);
    routeMarkers[key] = null;
    $(`route-${key}`).value = '';
  });
  setActiveField('origin');
  routeMessage("Click the map to set the team's base.");
}

// Set one end of the route; calculates as soon as both ends are known.
function setRoutePoint(key, lon, lat, {calculate = true} = {}) {
  $(`route-${key}`).value = lonLat(lon, lat);
  placeMarker(key, [lat, lon]);
  $('panel-route').open = true;
  if (key === 'origin' && !$('route-destination').value) {
    setActiveField('destination');
    routeMessage('Now click the destination, for example a place inside the flood.');
    return;
  }
  if (key === 'destination' && !$('route-origin').value) {
    setActiveField('origin');
    resetResults();
    routeMessage("Destination set. Now click the map to set the team's base.");
    return;
  }
  setActiveField(key === 'origin' ? 'destination' : 'origin');
  if (calculate) calculateRoute();
}

function onMapClick(event) {
  if (STATIC || Date.now() - lastPopupClose < 300) return;   // that click only closed a popup
  setRoutePoint(activeField, event.latlng.lng, event.latlng.lat);
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
  $('route-hint').textContent = on ? 'car and boat' : 'car only';
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
    btn.addEventListener('click', () => selectOption(i, true));
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
      const title = prev ? 'Launch the boat at the water\'s edge'
        : lastResult.origin.in_water ? 'Start on the water' : 'Launch the boat next to the team\'s base';
      add('launch', title, fmtPoint(leg.coordinates[0]));
      const portage = opt.route.portage_m > 0 ? `, including ${km(opt.route.portage_m)} dragging the boat` : '';
      add('boat', `Boat ${km(leg.distance_m)}`, `${minutes(leg.duration_s)}${portage}`);
    } else if (leg.mode === 'walk') {
      add('walk', `Walk ${km(leg.distance_m)}`, minutes(leg.duration_s));
    } else {
      add('drive', `Drive ${km(leg.distance_m)}`, `${minutes(leg.duration_s)}${leg.via && leg.via.length ? ` via ${leg.via.join(', ')}` : ''}`);
    }
  });
  add('arrive', lastResult.destination.in_water ? 'Arrive in the flood water' : 'Arrive', fmtPoint(lastResult.destination.input));
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
  // the other options first, in grey, clickable like on a road map
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
  document.querySelectorAll('[data-route-key]').forEach(el => { el.hidden = !present.has(el.dataset.routeKey); });
  $('legend').hidden = present.size === 0;
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
  if (STATIC) return;
  if (routeController) routeController.abort();
  const progress = $('route-progress'), calculateButton = $('route-calculate'), cancelButton = $('route-cancel');
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
    routeMessage('Finding routes…');
    progress.value = 35;
    const response = await fetch('/api/route', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({origin, destination, alternatives: 2, boats: boatsEnabled}),
      signal: controller.signal,
    });
    progress.value = 80;
    let result;
    try { result = await response.json(); } catch { result = {}; }
    if (routeController !== controller) return;            // a newer request replaced this one
    resetResults();
    if (!response.ok) throw new Error(result.error || `The route service answered with HTTP ${response.status}.`);
    showRoutes(result);
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

// ----- popups of the impact map: start a route from or to a place
impact.actions = (p, lat, lon) => {
  const nh = p.nearest_health;
  if (STATIC) {
    return `<a class="primary" href="${ESC(routesLink([lon, lat], null, LIVE_ROUTES_URL))}">Plan a route in the live tool</a>`;
  }
  const btns = [`<button type="button" class="primary" data-action="to" data-lon="${lon}" data-lat="${lat}">Route to here</button>`];
  if (nh) btns.push(`<button type="button" class="quiet" data-action="from-health" data-lon="${lon}" data-lat="${lat}" data-from-lon="${nh.lon}" data-from-lat="${nh.lat}">Route from that facility</button>`);
  btns.push(`<button type="button" class="quiet" data-action="base" data-lon="${lon}" data-lat="${lat}">Set as team base</button>`);
  return btns.join('');
};
impact.onAction = (action, d) => {
  map.closePopup();
  if (action === 'to') setRoutePoint('destination', +d.lon, +d.lat);
  if (action === 'base') setRoutePoint('origin', +d.lon, +d.lat);
  if (action === 'from-health') {
    setRoutePoint('origin', +d.fromLon, +d.fromLat, {calculate: false});
    setRoutePoint('destination', +d.lon, +d.lat);
  }
};

// ----- places: state filter chips and search by name
function renderStateFilter() {
  const key = $('impact-states');
  key.innerHTML = '';
  STATE_ORDER.forEach(state => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'state-chip';
    btn.dataset.state = state;
    btn.setAttribute('aria-pressed', String(impact.states.has(state)));
    btn.innerHTML = `<span class="dot"></span><span class="lbl" title="${ESC(STATE_INFO[state].label)}">${ESC(STATE_INFO[state].key)}</span><b>${fmtN(impactCount(state))}</b>`;
    btn.addEventListener('click', () => {
      if (impact.states.has(state)) impact.states.delete(state); else impact.states.add(state);
      filterImpact();
    });
    key.append(btn);
  });
}

const normalise = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
let placeIndex = [];

function buildPlaceIndex() {
  placeIndex = impact.markers.filter(m => m.feature.name).map(m => ({
    marker: m, title: impactTitle(m.feature), key: normalise(`${m.feature.name} ${kindLabel(m.feature.kind)}`),
  })).sort((a, b) => a.title.localeCompare(b.title));
}

function searchPlaces() {
  const q = normalise($('place-search').value.trim());
  const list = $('place-results');
  list.innerHTML = '';
  if (q.length < 2) { list.hidden = true; return; }
  const hits = placeIndex.filter(p => p.key.includes(q)).slice(0, 8);
  hits.forEach(hit => {
    const p = hit.marker.feature;
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'place-hit';
    btn.innerHTML = `${iconSvg(iconOf(p), p.state, 22)}<span><b>${ESC(hit.title)}</b><small>${ESC(kindLabel(p.kind))} · ${ESC(STATE_INFO[p.state].short)}</small></span>`;
    btn.addEventListener('click', () => focusPlace(hit.marker));
    li.append(btn);
    list.append(li);
  });
  if (!hits.length) list.innerHTML = '<li class="place-none">No mapped place with that name. OpenStreetMap may not have it.</li>';
  list.hidden = false;
}

// Zoom to a place and open its card, even if the filters hide its marker.
function focusPlace(marker) {
  const ll = marker.getLatLng();
  map.setView(ll, Math.max(map.getZoom(), 14));
  L.popup({maxWidth: 300, className: 'impact-pop'}).setLatLng(ll)
    .setContent(impactPopup(marker.feature, ll.lat, ll.lng)).openOn(map);
}

// ----- layer tree: groups expand and collapse; every row switches on its own
// A node has either a Leaflet `layer` or its own get()/set(on).
let layerTree = [];

const nodeOn = (n) => n.children ? n.children.some(nodeOn) : (n.get ? n.get() : map.hasLayer(n.layer));
function setNode(n, on) {
  if (n.children) { n.children.forEach(c => setNode(c, on)); return; }
  if (n.set) n.set(on); else show(n.layer, on);
}

function swatch(n) {
  if (n.icon) return `<span class="lt-icon">${iconSvg(n.icon, 'accessible', 20)}</span>`;
  if (!n.color) return '';
  return `<i class="lp-sw${n.kind ? ' ' + n.kind : ''}" style="${n.kind === 'points' ? 'color' : 'background'}:${n.color}"></i>`;
}

function renderLayerTree() {
  const root = $('layer-tree');
  root.innerHTML = '';
  layerTree.forEach(group => {
    const g = document.createElement('li');
    g.className = 'lt-group';
    g.setAttribute('role', 'treeitem');
    g.setAttribute('aria-expanded', 'true');
    g.innerHTML =
      `<div class="lt-row lt-head"><button type="button" class="lt-caret" aria-label="Collapse ${ESC(group.label)}"></button>` +
      `<label class="lt-switch"><span class="lt-name">${ESC(group.label)}</span>` +
      '<input type="checkbox" role="switch"><span class="lp-knob" aria-hidden="true"></span></label></div><ul class="lt-children" role="group"></ul>';
    const caret = g.querySelector('.lt-caret');
    caret.addEventListener('click', () => {
      const open = g.getAttribute('aria-expanded') !== 'true';
      g.setAttribute('aria-expanded', String(open));
      caret.setAttribute('aria-label', `${open ? 'Collapse' : 'Expand'} ${group.label}`);
    });
    group.box = g.querySelector('.lt-head input');
    group.box.addEventListener('change', () => { setNode(group, !nodeOn(group)); syncLayerTree(); });
    const ul = g.querySelector('.lt-children');
    group.children.forEach(n => {
      const li = document.createElement('li');
      li.className = 'lt-item';
      li.setAttribute('role', 'treeitem');
      li.innerHTML = `<label class="lt-switch">${swatch(n)}<span class="lt-name">${ESC(n.label)}${n.note ? `<small>${ESC(n.note)}</small>` : ''}</span>` +
        '<b class="lt-count"></b><input type="checkbox" role="switch"><span class="lp-knob" aria-hidden="true"></span></label>' +
        (n.opacity ? `<input class="lp-opacity" type="range" min="15" max="100" value="100" aria-label="Opacity: ${ESC(n.label)}">` : '');
      n.li = li;
      n.box = li.querySelector('input[type=checkbox]');
      n.countEl = li.querySelector('.lt-count');
      n.box.addEventListener('change', () => { setNode(n, n.box.checked); syncLayerTree(); });
      const slider = li.querySelector('.lp-opacity');
      if (slider) slider.addEventListener('input', () => setLayerOpacity(n.layer, slider.value / 100));
      ul.append(li);
    });
    root.append(g);
  });
  syncLayerTree();
}

function syncLayerTree() {
  let on = 0;
  layerTree.forEach(group => {
    const kids = group.children.map(nodeOn);
    group.box.checked = kids.some(Boolean);
    group.box.indeterminate = kids.some(Boolean) && !kids.every(Boolean);
    group.children.forEach((n, i) => {
      n.box.checked = kids[i];
      n.li.classList.toggle('on', kids[i]);
      if (n.count) n.countEl.textContent = n.count();
      on += kids[i];
    });
  });
  $('layers-hint').textContent = `${on} on`;
}

function categoryNode(cat) {
  return {
    label: CATEGORY_INFO[cat].label, icon: CATEGORY_INFO[cat].icon,
    count: () => fmtN(STATE_ORDER.filter(s => impact.states.has(s)).reduce((sum, s) => sum + impact.data.categories[cat].by_state[s], 0)),
    get: () => impact.cats.has(cat) && map.hasLayer(impact.layer),
    set: (on) => {
      if (on) impact.cats.add(cat); else impact.cats.delete(cat);
      show(impact.layer, Object.keys(CATEGORY_INFO).some(c => impact.cats.has(c)));
      filterImpact();
    },
  };
}

function buildLayerTree() {
  const water = [];
  if (layers.before) water.push({label: 'Water already there', color: COLORS.standing, layer: layers.before, opacity: true});
  if (layers.during) water.push({label: 'New flood water', color: COLORS.newwater, layer: layers.during, opacity: true});
  if (layers.validation) water.push({label: 'NISAR vs Copernicus difference', note: 'Copernicus EMSR857, AOI02 only', color: '#7b2cbf', layer: layers.validation, opacity: true});
  if (layers.radar) water.push({label: 'NISAR radar image', color: '#6b7f3a', layer: layers.radar, opacity: true});
  layerTree = [{label: 'Flood water (NISAR)', children: water}];
  if (impact.data) {
    const ground = [];
    if (impact.roads) ground.push({label: 'Roads on open water', color: COLORS.roads, kind: 'line', layer: impact.roads,
                                   count: () => `${fmtN(impact.data.roads.flooded_km)} km`});
    Object.keys(CATEGORY_INFO).forEach(cat => ground.push(categoryNode(cat)));
    layerTree.push({label: 'Places and roads (OSM)', children: ground});
  }
  if (layers.vegetation) layerTree.push({label: 'Context', children: [{label: 'Estimated vegetation (NDVI)', color: '#4f8a3c', layer: layers.vegetation, opacity: true}]});
  renderLayerTree();
}

// ----- map styles
function renderBasemaps() {
  const wrap = $('basemaps');
  wrap.innerHTML = '';
  BASEMAPS.forEach(b => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'basemap';
    btn.setAttribute('role', 'radio');
    btn.title = b.name;
    btn.innerHTML = `<span class="lp-thumb" style="background-image:url('${basemapThumb(b)}')"></span><span>${ESC(b.short)}</span>`;
    btn.addEventListener('click', () => { setBasemap(b.id); syncBasemaps(); });
    btn.dataset.id = b.id;
    wrap.append(btn);
  });
  syncBasemaps();
}

function syncBasemaps() {
  document.querySelectorAll('#basemaps .basemap').forEach(btn => btn.setAttribute('aria-checked', String(btn.dataset.id === currentBasemap.id)));
  $('basemap-hint').textContent = currentBasemap.short;
}

// ----- panel: collapses to its header so the map gets the whole screen
function setPanel(open) {
  $('tool').classList.toggle('collapsed', !open);
  $('panel-toggle').setAttribute('aria-expanded', String(open));
  setTimeout(() => map.invalidateSize(), 220);
}

// ?to=lon,lat&from=lon,lat, sent by the story's impact map
function readLinkedRoute() {
  const q = new URLSearchParams(location.search);
  const parse = (v) => { try { return v ? parsePoint(v, 'point') : null; } catch { return null; } };
  const to = parse(q.get('to')), from = parse(q.get('from'));
  if (STATIC) {
    if (location.search) $('live-tool-link').href = LIVE_ROUTES_URL + location.search;
    if (to) map.setView([to.lat, to.lon], 13);
    return;
  }
  if (from) setRoutePoint('origin', from.lon, from.lat, {calculate: false});
  if (to) {
    setRoutePoint('destination', to.lon, to.lat);
    if (!from) map.setView([to.lat, to.lon], 12);
  }
}

(async () => {
  // the tool opens on satellite imagery with road names: what a team sees on the ground
  setBasemap(BASEMAPS.some(b => b.id === 'hybrid') ? 'hybrid' : 'light');
  renderBasemaps();
  $('panel-toggle').addEventListener('click', () => setPanel($('tool').classList.contains('collapsed')));
  stats = await loadStats();
  layers = await loadWaterLayers(stats);
  show(layers.before, true);
  show(layers.during, true);
  try {
    if (await loadImpact(stats)) {
      impact.cats = new Set(Object.keys(CATEGORY_INFO).concat('roads'));
      show(impact.layer, true);
      show(impact.roads, true);
      $('tool-date').textContent = fmtLongDate(impact.data.radar_date);
      $('route-osm-date').textContent = `Road network: OpenStreetMap extract of ${osmDateText()}. It is newer than the radar scenes and does not show the roads as they were on the flood date.`;
      buildPlaceIndex();
      impact.onFilter = () => {
        renderStateFilter();
        syncLayerTree();
        const shown = impact.layer.getLayers().length;
        $('places-hint').textContent = `${fmtN(shown)} on the map`;
      };
    } else {
      $('panel-places').hidden = true;
    }
  } catch (error) {
    console.error('impact map unavailable', error);
    setStatus('OSM impact layers are unavailable; routes and water layers still work.');
    $('panel-places').hidden = true;
  }
  if (!impact.data) $('tool-date').textContent = fmtLongDate(stats.scenes.during.date);
  buildLayerTree();
  if (impact.data) filterImpact();

  $('place-search').addEventListener('input', searchPlaces);
  $('place-search').addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') { const first = $('place-results').querySelector('.place-hit'); if (first) first.click(); }
    if (ev.key === 'Escape') { $('place-search').value = ''; searchPlaces(); }
  });
  map.on('popupclose', () => { lastPopupClose = Date.now(); });

  if (STATIC) {
    $('route-planner-controls').hidden = true;
    $('static-route-note').hidden = false;
    $('route-hint').textContent = 'live server only';
  } else {
    $('route-calculate').addEventListener('click', calculateRoute);
    $('route-cancel').addEventListener('click', () => routeController && routeController.abort());
    $('route-clear').addEventListener('click', clearRouteSelection);
    $('route-swap').addEventListener('click', swapPoints);
    document.querySelectorAll('.mode-switch [role=radio]').forEach(btn =>
      btn.addEventListener('click', () => setBoats(btn.dataset.boats === 'true')));
    ['origin', 'destination'].forEach(key => {
      $(`route-${key}`).addEventListener('focus', () => setActiveField(key));
      $(`route-${key}`).addEventListener('keydown', (ev) => { if (ev.key === 'Enter') calculateRoute(); });
    });
    setActiveField('origin');
    map.on('click', onMapClick);
  }
  readLinkedRoute();
})();
