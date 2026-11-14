const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18, attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

const fmt = (v, unit = '') => (v === null || v === undefined) ? 'to be confirmed' : v + unit;

async function addLayer(spec, style) {
  if (spec.type === 'geojson') {
    const data = await (await fetch(spec.url)).json();
    return L.geoJSON(data, {style}).addTo(map);
  }
  if (spec.type === 'image') {  // bounds: [[south, west], [north, east]]
    return L.imageOverlay(spec.url, spec.bounds, {opacity: style.fillOpacity}).addTo(map);
  }
  throw new Error('Unknown layer type: ' + spec.type);
}

(async () => {
  const s = await (await fetch('/api/stats')).json();
  document.getElementById('title').textContent = s.area_name;
  if (s.mock) document.getElementById('mock-flag').hidden = false;

  const [w, so, e, n] = s.bbox;
  map.fitBounds([[so, w], [n, e]]);

  const before = await addLayer(s.layers.before, {color: '#1f5fa8', weight: 1, fillOpacity: 0.6});
  const during = await addLayer(s.layers.during, {color: '#c0392b', weight: 1, fillOpacity: 0.6});

  const slider = document.getElementById('slider');
  const apply = () => {
    const k = slider.value / 100;
    during.setStyle && during.setStyle({fillOpacity: 0.6 * k, opacity: k});
  };
  slider.addEventListener('input', apply); apply();

  const rows = [
    ['Flooded area', fmt(s.flooded_area_km2, ' km²')],
    ['Permanent water', fmt(s.permanent_water_km2, ' km²')],
    ['Before', s.scenes.before.date], ['During', s.scenes.during.date],
    ['Track / frame', `${s.scenes.during.track} / ${s.scenes.during.frame}`],
    ['Direction', s.scenes.during.direction],
    ['Polarizations', fmt(s.scenes.during.polarizations && s.scenes.during.polarizations.join(', '))],
    ['Data level', s.maturity], ['Product', s.product],
  ];
  const dl = document.getElementById('numbers');
  rows.forEach(([k, v]) => {
    dl.insertAdjacentHTML('beforeend', `<dt>${k}</dt><dd>${v}</dd>`);
  });
  const ul = document.getElementById('limits');
  s.limitations.forEach(t => {
    const li = document.createElement('li');
    li.textContent = t;
    ul.appendChild(li);
  });
})();
