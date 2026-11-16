// Shared by the story (story.js) and the route tool (routes.js): the map and its
// basemaps, the NISAR data layers, the OSM impact map and formatting helpers.
// Plain script: its top-level names are visible to the page script loaded after it.

// The static GitHub Pages copy has no Flask backend for route calculations.
const STATIC = Boolean(window.STATS_URL);
const ROUTES_URL = window.SARVIA_ROUTES_URL || 'routes.html';
const LIVE_ROUTES_URL = 'https://sarvia.duckdns.org/routes';
const $ = (id) => document.getElementById(id);
const COLORS = {standing: '#1f5fae', newwater: '#e0442a', roads: '#f0a500', slate: '#1b2830', safe: '#1b8a4b'};

// ----- formatting
const ESC = (t) => String(t).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmt = (v, unit = '') => (v === null || v === undefined) ? 'to be confirmed' : v + unit;
const fmtN = (n) => Number(n).toLocaleString('en-US');
const fmtDate = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'short', timeZone: 'UTC'});
const fmtLongDate = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'});
const fmtKm2 = (v) => `${Number(v).toLocaleString('en-US', {maximumFractionDigits: 1})} km²`;
const metresText = (m) => m >= 1000 ? `${(m / 1000).toLocaleString('en-US', {maximumFractionDigits: 1})} km` : `${m} m`;
const km = (m) => m >= 1000 ? `${(m / 1000).toLocaleString('en-US', {maximumFractionDigits: 1})} km` : `${Math.round(m)} m`;
const minutes = (s) => {
  const total = Math.max(1, Math.round(s / 60));
  return total < 60 ? `${total} min` : `${Math.floor(total / 60)} h ${total % 60} min`;
};
const fmtPoint = ([lon, lat]) => `${Math.abs(lat).toFixed(4)}° ${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(4)}° ${lon < 0 ? 'W' : 'E'}`;
const lonLat = (lon, lat) => `${Number(lon).toFixed(6)}, ${Number(lat).toFixed(6)}`;

function setStatus(text) {
  const el = $('layer-status');
  if (!el) return;
  el.textContent = text;
  el.hidden = !text;
}

// ----- map and basemaps
// One world, no repeated copies and no empty margin: the view can go out to the
// whole world (Africa sits in the middle) but never past its edges.
const WORLD = L.latLngBounds([[-85, -180], [85, 180]]);
const map = L.map('map', {zoomSnap: 0.25, preferCanvas: true, zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false,
                          maxBounds: WORLD, maxBoundsViscosity: 1, worldCopyJump: false});
// the furthest zoom at which the world still fills the whole map, recomputed when the map resizes
const lockToWorld = () => map.setMinZoom(map.getBoundsZoom(WORLD, true));
lockToWorld();
map.on('resize', lockToWorld);
const mapConfig = Object.assign({
  satellite: true,
  hybrid: true,
  satellite_url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  hybrid_url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  hybrid_labels_url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
}, window.SARVIA_MAP_CONFIG || {});
mapConfig.attribution = Object.assign({satellite: '&copy; Esri', hybrid: '&copy; Esri | &copy; OpenStreetMap contributors'}, mapConfig.attribution || {});
const tileOptions = {maxZoom: 19, noWrap: true, updateWhenZooming: false, updateWhenIdle: true, keepBuffer: 2};

// id, full name, short label for the thumbnail picker, Leaflet layer
const BASEMAPS = [
  {id: 'light', name: 'Light map', short: 'Light', layer: L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png', {
    ...tileOptions, maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | Tiles: <a href="https://tile.openstreetmap.de/">OpenStreetMap.de</a>'})},
  {id: 'dark', name: 'Dark map', short: 'Dark', layer: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    ...tileOptions, attribution: '&copy; <a href="https://www.esri.com/">Esri</a> | &copy; OpenStreetMap contributors'})},
];
if (mapConfig.satellite && mapConfig.satellite_url) {
  BASEMAPS.push({id: 'satellite', name: 'Satellite imagery', short: 'Satellite', layer: L.tileLayer(mapConfig.satellite_url, {
    ...tileOptions, attribution: mapConfig.attribution.satellite || 'Satellite imagery provider'})});
}
if (mapConfig.hybrid && mapConfig.hybrid_url) {
  const parts = [L.tileLayer(mapConfig.hybrid_url, {...tileOptions, attribution: mapConfig.attribution.hybrid})];
  if (mapConfig.hybrid_labels_url) parts.push(L.tileLayer(mapConfig.hybrid_labels_url, tileOptions));
  BASEMAPS.push({id: 'hybrid', name: 'Hybrid (imagery + roads)', short: 'Hybrid', layer: L.layerGroup(parts)});
}
BASEMAPS.slice(2).forEach(b => (b.layer.eachLayer ? b.layer.getLayers() : [b.layer]).forEach(tile =>
  tile.on('tileerror', () => setStatus('An external map layer could not be loaded; check the provider settings.'))));
let currentBasemap = BASEMAPS[0];
currentBasemap.layer.addTo(map);

function setBasemap(id) {
  const next = BASEMAPS.find(b => b.id === id);
  if (!next || next === currentBasemap) return;
  map.removeLayer(currentBasemap.layer);
  next.layer.addTo(map);
  currentBasemap = next;
  map.fire('basemapchange', {basemap: next});
}

// a real tile over Chókwè, the heart of the flood, as the basemap thumbnail
function basemapThumb(b) {
  const tile = b.layer.getLayers ? b.layer.getLayers()[0] : b.layer;
  return tile && tile._url ? L.Util.template(tile._url, {s: 'a', z: 8, x: 151, y: 146}) : '';
}

['vegetationPane', 'radarPane', 'beforePane', 'duringPane', 'timelinePane', 'validationPane', 'roadsPane', 'impactPane'].forEach((name, i) => {
  map.createPane(name).style.zIndex = 405 + i * 10;
});

// ----- data layers from the stats contract
async function addLayer(spec, pane, style = {}) {
  // The stats contract allows vector GeoJSON, raster image overlays or tile layers.
  if (!spec) return null;
  if (spec.type === 'geojson') {
    const response = await fetch(spec.url);
    if (!response.ok) throw new Error(`Layer request failed (${response.status})`);
    return L.geoJSON(await response.json(), {pane, style});
  }
  if (spec.type === 'image') {  // bounds: [[south, west], [north, east]]
    const layer = L.imageOverlay(spec.url, spec.bounds, {pane, opacity: style.opacity == null ? 1 : style.opacity});
    layer.on('error', () => setStatus(`The ${spec.source || 'raster'} layer could not be loaded.`));
    return layer;
  }
  if (spec.type === 'tile') {
    const layer = L.tileLayer(spec.url, {
      ...tileOptions, pane, opacity: style.opacity == null ? 0.48 : style.opacity,
      attribution: spec.attribution || spec.source || 'External raster layer'});
    layer.on('tileerror', () => setStatus(`The ${spec.source || 'external'} layer could not be loaded.`));
    return layer;
  }
  throw new Error('Unknown layer type: ' + spec.type);
}

function show(layer, on) {
  if (!layer) return;
  if (on && !map.hasLayer(layer)) layer.addTo(map);
  if (!on && map.hasLayer(layer)) map.removeLayer(layer);
}

// image overlays fade with setOpacity, vector layers with their style
function setLayerOpacity(layer, v) {
  if (layer.setOpacity) layer.setOpacity(v);
  else if (layer.setStyle) layer.setStyle({opacity: v, fillOpacity: v * 0.72});
}

async function loadStats() {
  const stats = await (await fetch(window.STATS_URL || '/api/stats')).json();
  if (stats.mock) $('mock-flag').hidden = false;
  const [w, s, e, n] = stats.bbox;
  map.fitBounds([[s, w], [n, e]]);
  return stats;
}

// The water layers both pages use. Missing optional layers stay null.
async function loadWaterLayers(stats) {
  const layers = {};
  layers.radar = await addLayer(stats.layers.radar_rgb, 'radarPane', {});
  layers.before = await addLayer(stats.layers.before, 'beforePane', {color: COLORS.standing, weight: 1.5, fillColor: COLORS.standing, fillOpacity: 0.72, opacity: 0.72});
  layers.during = await addLayer(stats.layers.during, 'duringPane', {color: COLORS.newwater, weight: 2, fillColor: COLORS.newwater, fillOpacity: 0.78, opacity: 0.78});
  layers.validation = await addLayer(stats.layers.validation_difference, 'validationPane', (feature) => {
    const color = feature.properties.classification === 'system_only' ? COLORS.newwater : '#7b2cbf';
    return {color, weight: 1, fillColor: color, fillOpacity: 0.72};
  });
  layers.vegetation = null;
  if (stats.layers.vegetation) {
    try {
      layers.vegetation = await addLayer(stats.layers.vegetation, 'vegetationPane', {opacity: 0.46});
    } catch (error) {
      console.error('vegetation layer unavailable', error);
      setStatus('The vegetation layer is unavailable; the NISAR layers still work.');
    }
  }
  return layers;
}

function vegetationLegend(el, spec) {
  if (!el || !spec || !Array.isArray(spec.legend)) return;
  el.innerHTML = '<b>Estimated vegetation (NDVI)</b>';
  spec.legend.forEach(item => {
    if (!item || !item.label) return;
    const row = document.createElement('span');
    row.className = 'vegetation-key';
    row.innerHTML = `<i style="background:${ESC(item.color || '#9aa6ad')}"></i>${ESC(item.label)}`;
    el.appendChild(row);
  });
  const note = document.createElement('small');
  note.textContent = `${spec.source || 'Source not given'} · ${spec.date || 'date not given'}`;
  el.appendChild(note);
}

// ----- the impact map: schools, health, communities, bridges and flooded roads
// Colour stays data-only: red = on detectable open water, amber = potential isolation,
// slate = dry road access, grey = unknown. The pictogram tells the category.
const STATE_INFO = {
  in_water: {key: 'On open water', label: 'On detectable open water', short: 'on water', fill: COLORS.newwater, ink: '#fff'},
  isolated: {key: 'Possibly cut off', label: 'Possibly cut off on the mapped road network', short: 'possibly cut off', fill: COLORS.roads, ink: COLORS.slate},
  near_water: {key: 'Near open water', label: 'Near detectable open water', short: 'near water', fill: '#fff', ink: COLORS.newwater},
  accessible: {key: 'Dry road access', label: 'Dry road access', short: 'dry access', fill: COLORS.slate, ink: '#fff'},
  no_road: {key: 'No road link', label: 'No mapped road link', short: 'no road', fill: '#8e9ba3', ink: '#fff'},
  not_observed: {key: 'Not seen by radar', label: 'Outside radar coverage', short: 'not seen', fill: '#c3ccd1', ink: '#fff'},
};
const STATE_ORDER = Object.keys(STATE_INFO);
const URGENT_STATES = ['in_water', 'isolated', 'near_water'];
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
const kindLabel = (k) => KIND_LABEL[k] || (k ? k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, ' ') : '');
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

// cats: categories on the map ('roads' is the flooded-road layer); states: states shown.
// actions(p, lat, lon) returns the popup buttons; onAction(name, dataset) handles their clicks.
const impact = {data: null, markers: [], roads: null, layer: null, detail: false,
                cats: new Set(Object.keys(CATEGORY_INFO).concat('roads')), states: new Set(URGENT_STATES),
                actions: null, onAction: null, onFilter: null};

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

function impactTitle(p) {
  if (p.kind === 'building_cluster') return `Cluster of ${fmtN(p.buildings)} buildings`;
  if (p.category === 'bridge') return p.name ? `Bridge on ${p.name}` : `Bridge (${kindLabel(p.kind).toLowerCase()} road)`;
  return p.name || `Unnamed ${kindLabel(p.kind).toLowerCase()}`;
}

function stateExplanation(p) {
  const near = impact.data.parameters.near_water_m, snap = impact.data.parameters.road_snap_m;
  const approach = impact.data.parameters.bridge_approach_m;
  const area = p.geom === 'area' ? 'Part of its mapped area is' : (p.kind === 'building_cluster' ? 'These buildings are' : 'It is');
  if (p.category === 'bridge') {
    return {
      in_water: `Every mapped road leaving at least one end meets detectable open water within ${approach} m of the bridge. The bridge deck itself is not tested.`,
      isolated: 'Its mapped approaches have no detected water, but every mapped route from the main network to it crosses that water.',
      near_water: `Detectable open water within ${near} m of the bridge or on part of its approaches; at least one mapped road without detected water remains.`,
      accessible: 'A dry road links it to the main road network.',
      no_road: 'Its roads are not linked to the main road network in OpenStreetMap.',
      not_observed: 'The radar footprint does not cover this place.',
    }[p.state];
  }
  return {
    in_water: `${area} on open water detected by the radar.`,
    isolated: 'Out of the detected water, but every mapped route from the main network to it crosses that water: no mapped dry road access.',
    near_water: `Within ${near} m of detectable open water; a mapped road without detected water still links it to the main network.`,
    accessible: 'A dry road links it to the main road network.',
    no_road: p.road_m === null ? `No mapped drivable road within ${snap} m in OpenStreetMap.`
      : 'Its nearby roads are not linked to the main road network in OpenStreetMap (a gap in the map).',
    not_observed: 'The radar footprint does not cover this place, so nothing is known about the water here.',
  }[p.state];
}

function impactPopup(p, lat, lon) {
  const info = STATE_INFO[p.state];
  const lines = [];
  const kind = p.kind === 'building_cluster' ? 'Building footprints (OSM)' : kindLabel(p.kind);
  const osm = p.osm ? ` · <a href="https://www.openstreetmap.org/${ESC(p.osm)}" target="_blank" rel="noopener">OSM ${ESC(p.osm)}</a>` : '';
  lines.push(`<p class="pp-kind">${iconSvg(iconOf(p), p.state, 22)} ${ESC(kind)}${osm}</p>`);
  lines.push(`<p class="pp-state" data-state="${p.state}"><b>${ESC(info.label)}</b> ${ESC(stateExplanation(p))}</p>`);
  const facts = [];
  if (p.state !== 'not_observed') {
    facts.push(['Detectable open water', p.water_m === 0 ? 'on it' : p.water_m === null ? 'more than 5 km away' : `${metresText(p.water_m)} away`]);
  }
  if (p.category === 'bridge') {
    if (p.length_m) facts.push(['Length', metresText(p.length_m)]);
    if (p.approaches) facts.push(['Approach roads with detected water', `${p.approaches_flooded} of ${p.approaches}`]);
  } else if (p.road_m !== null && p.road_m !== undefined) {
    facts.push(['Nearest mapped road', metresText(p.road_m)]);
  }
  if (p.kind === 'building_cluster') facts.push(['Spread', `about ${metresText(p.extent_m)}`]);
  if (facts.length) lines.push('<dl class="pp-facts">' + facts.map(([k, v]) => `<dt>${ESC(k)}</dt><dd>${ESC(v)}</dd>`).join('') + '</dl>');
  const nh = p.nearest_health;
  if (nh) {
    lines.push(`<p class="pp-health">Nearest health facility with dry road access: <b>${ESC(nh.name || 'unnamed ' + kindLabel(nh.kind).toLowerCase())}</b>, ${nh.km.toLocaleString('en-US')} km in a straight line.</p>`);
  }
  const actions = impact.actions ? impact.actions(p, lat, lon) : '';
  if (actions) lines.push(`<p class="pp-actions">${actions}</p>`);
  lines.push(`<p class="pp-note">Potential-impact estimate from the open water the radar detected on ${ESC(fmtDate(impact.data.radar_date))}. Not confirmed damage. &copy; OpenStreetMap contributors</p>`);
  return `<div class="impact-popup"><h3>${ESC(impactTitle(p))}</h3>${lines.join('')}</div>`;
}

// Link to the route tool with a destination (and optionally a start) filled in.
function routesLink(to, from, base = ROUTES_URL) {
  const q = new URLSearchParams({to: lonLat(to[0], to[1])});
  if (from) q.set('from', lonLat(from[0], from[1]));
  return `${base}?${q}`;
}

function buildImpactLayer() {
  const renderer = L.canvas({pane: 'impactPane', padding: 0.4, tolerance: 6});
  const detail = map.getZoom() >= DETAIL_ZOOM;
  impact.markers = impact.data.features.features.map(f => {
    const p = f.properties, [lon, lat] = f.geometry.coordinates;
    // bubblingMouseEvents: a click on a place opens its card and does not also reach the map
    const m = new ShapeMarker([lat, lon], {renderer, state: p.state, icon: iconOf(p), detail, radius: markerRadius(p, detail), bubblingMouseEvents: false});
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

// Rebuild the marker group from the category and state filters.
function filterImpact() {
  if (!impact.layer) return;
  impact.layer.clearLayers();
  impact.markers.forEach(m => {
    if (impact.cats.has(m.feature.category) && impact.states.has(m.feature.state)) impact.layer.addLayer(m);
  });
  if (impact.onFilter) impact.onFilter();
}

// number of elements in a state, summed over the selected categories
function impactCount(state, cats = impact.cats) {
  return Object.keys(CATEGORY_INFO).filter(c => cats.has(c))
    .reduce((sum, c) => sum + impact.data.categories[c].by_state[state], 0);
}

async function loadImpact(stats) {
  const spec = stats.layers.impact_features;
  if (!spec || !stats.impact || !stats.impact.categories) return false;
  const featureResponse = await fetch(spec.url);
  if (!featureResponse.ok) throw new Error(`Impact features request failed (${featureResponse.status})`);
  impact.data = {...stats.impact, features: await featureResponse.json()};
  if (stats.layers.impact_roads) {
    const response = await fetch(stats.layers.impact_roads.url);
    if (!response.ok) throw new Error(`Impact roads request failed (${response.status})`);
    const roadWeight = () => (map.getZoom() >= DETAIL_ZOOM ? 3.5 : 1.6);
    impact.roads = L.geoJSON(await response.json(), {pane: 'roadsPane', style: () => ({color: COLORS.roads, weight: roadWeight(), opacity: 1})});
    map.on('zoomend', () => impact.roads.setStyle({weight: roadWeight()}));
    impact.roads.bindTooltip(l => {
      const p = l.feature.properties;
      return `${ESC(p.name || kindLabel(p.highway) + ' road')}: ${metresText(p.flooded_m)} on detectable open water`;
    }, {sticky: true});
  }
  buildImpactLayer();
  // Leaflet stops clicks inside popups from bubbling and re-renders popup content,
  // so popup buttons are handled in the capture phase on the map container.
  $('map').addEventListener('click', (ev) => {
    const btn = ev.target.closest('[data-action]');
    if (!btn || !impact.onAction) return;
    impact.onAction(btn.dataset.action, btn.dataset);
  }, true);
  return true;
}

function osmDateText() {
  return String((impact.data && impact.data.osm_timestamp) || '').slice(0, 10) || 'unknown date';
}
