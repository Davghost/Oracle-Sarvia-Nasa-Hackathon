// The five-screen story: clouds, radar, where the water rose, what it may reach,
// and the way to the route tool. Map, layers and the impact map come from core.js.

const TOTAL = 5;
let stats = null, layers = {}, step = 1, mapView = 'compare';
let timelineIndex = 0, timelineTimer = null, timelineAnimationFrame = null;

// ----- before/during curtain: clip "before" left of the line and "during" right of it
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

// ----- observed NISAR timeline: discrete acquisitions, never interpolated
const hasTimeline = () => Boolean(layers.timeline && layers.timeline.length);
const timelineActive = () => step === 3 && hasTimeline() && mapView === 'timeline';

function setTimelineIndex(index, {animate = false} = {}) {
  if (!hasTimeline()) return;
  const observations = stats.timeline.observations;
  const previousIndex = timelineIndex;
  if (timelineAnimationFrame !== null) cancelAnimationFrame(timelineAnimationFrame);
  timelineAnimationFrame = null;
  timelineIndex = Math.max(0, Math.min(observations.length - 1, Number(index) || 0));
  const o = observations[timelineIndex];
  $('timeline-slider').value = String(timelineIndex);
  $('timeline-map-date').textContent = fmtDate(o.date);
  $('timeline-map-frame').textContent = `${timelineIndex + 1}/${observations.length}`;
  $('timeline-frame-count').textContent = `${fmtLongDate(o.date)} · observation ${timelineIndex + 1} of ${observations.length}`;
  [...$('timeline-ticks').children].forEach((t, i) => t.classList.toggle('on', i === timelineIndex));
  const signed = (v) => `${v > 0 ? '+' : ''}${v.toLocaleString('en-US', {maximumFractionDigits: 1})}`;
  $('timeline-reading').textContent = timelineIndex === 0
    ? `${fmtKm2(o.water_area_km2)} of open water mapped. This first observation is the reference for the others.`
    : `${fmtKm2(o.water_area_km2)} of open water mapped: ${signed(Number(o.new_vs_reference_km2 || 0))} km² new and ` +
      `${Number(o.receded_vs_reference_km2 || 0).toLocaleString('en-US', {maximumFractionDigits: 1})} km² gone since ${fmtDate(observations[0].date)}.`;
  const visible = timelineActive();
  if (animate && visible && previousIndex !== timelineIndex) {
    const outgoing = layers.timeline[previousIndex], incoming = layers.timeline[timelineIndex];
    layers.timeline.forEach((layer, i) => { if (i !== previousIndex && i !== timelineIndex) show(layer, false); });
    outgoing.setOpacity(1); incoming.setOpacity(0);
    show(outgoing, true); show(incoming, true);
    const started = performance.now(), duration = 900;
    const dissolve = (now) => {
      const t = Math.min(1, (now - started) / duration);
      outgoing.setOpacity(1 - t);
      incoming.setOpacity(t);
      if (t < 1) timelineAnimationFrame = requestAnimationFrame(dissolve);
      else { show(outgoing, false); incoming.setOpacity(1); timelineAnimationFrame = null; }
    };
    timelineAnimationFrame = requestAnimationFrame(dissolve);
  } else {
    layers.timeline.forEach((layer, i) => { layer.setOpacity(1); show(layer, visible && i === timelineIndex); });
  }
}

function setTimelinePlaying(playing) {
  if (timelineTimer) { clearTimeout(timelineTimer); timelineTimer = null; }
  const button = $('timeline-play');
  button.textContent = playing ? 'Ⅱ Pause' : '▶ Play';
  button.setAttribute('aria-label', playing ? 'Pause the flood sequence' : 'Play the flood sequence');
  $('timeline-panel').classList.toggle('playing', playing);
  if (!playing || !hasTimeline()) return;
  const last = stats.timeline.observations.length - 1;
  if (timelineIndex >= last) setTimelineIndex(0);
  const advance = () => {
    if (timelineIndex >= last) { setTimelinePlaying(false); return; }
    setTimelineIndex(timelineIndex + 1, {animate: true});
    timelineTimer = setTimeout(advance, 1900);
  };
  timelineTimer = setTimeout(advance, 500);
}

function setMapView(view) {
  mapView = view === 'timeline' && hasTimeline() ? 'timeline' : 'compare';
  setTimelinePlaying(false);
  $('timeline-view-button').setAttribute('aria-pressed', String(mapView === 'timeline'));
  $('compare-view-button').setAttribute('aria-pressed', String(mapView === 'compare'));
  setStep(step);
}

// ----- the story steps: each one sets the text and the layers on the map
function stepName(n) {
  const el = document.querySelector(`.step[data-step="${n}"]`);
  return el ? el.dataset.short : '';
}

function setStep(n) {
  step = Math.max(1, Math.min(TOTAL, n));
  if (step !== 3 && timelineTimer) setTimelinePlaying(false);
  document.querySelectorAll('.step').forEach(el => el.classList.toggle('on', +el.dataset.step === step));
  document.querySelectorAll('#progress button').forEach((b, i) => {
    b.classList.toggle('on', i + 1 === step);
    b.classList.toggle('done', i + 1 < step);
    if (i + 1 === step) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current');
  });
  $('steps').scrollTop = 0;
  $('prev').disabled = step === 1;
  $('next').hidden = step === TOTAL;
  $('next').textContent = `Next: ${stepName(step + 1)}`;

  const tl = timelineActive();
  const compare = step === 3 && !tl;
  const checking = step === 3 && $('validation-section').open;
  if (map.closePopup && step !== 4) map.closePopup();
  $('clouds').classList.toggle('lifted', step !== 1);
  $('mapwrap').dataset.step = step;
  show(layers.radar, step === 2);
  show(layers.before, step === 2 || compare || step === 5);
  show(layers.during, compare || step === 4 || step === 5);
  if (layers.timeline) layers.timeline.forEach((layer, i) => show(layer, tl && i === timelineIndex));
  show(layers.vegetation, step >= 2);
  show(layers.validation, checking);
  show(impact.layer, step === 4);
  show(impact.roads, (step === 4 && impact.cats.has('roads')) || step === 5);

  $('timeline-view-switch').hidden = !(step === 3 && hasTimeline());
  $('timeline-panel').hidden = !tl;
  $('timeline-map-caption').hidden = !tl;
  $('curtain').hidden = !compare;
  $('compare-instructions').hidden = !compare;
  $('legend').hidden = step < 2;
  $('before-legend').hidden = !(step === 2 || compare || step === 5);
  $('during-legend').hidden = !(compare || step === 4 || step === 5);
  $('timeline-legend').hidden = !tl;
  $('vegetation-legend').hidden = !layers.vegetation || step < 2;
  $('roads-legend').hidden = !impact.roads || !((step === 4 && impact.cats.has('roads')) || step === 5);
  $('validation-legend').hidden = !(checking && layers.validation);
  updateClip(compare);
  map.invalidateSize();
}

// ----- step 4: category rows and state chips double as the map filter
function renderImpactCounts() {
  const key = $('impact-states');
  key.innerHTML = '';
  let total = 0;
  STATE_ORDER.forEach(state => {
    const n = impactCount(state);
    total += n;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'state-chip';
    btn.dataset.state = state;
    btn.setAttribute('aria-pressed', String(impact.states.has(state)));
    btn.innerHTML = `<span class="dot"></span><span class="lbl" title="${ESC(STATE_INFO[state].label)}">${ESC(STATE_INFO[state].key)}</span><b>${fmtN(n)}</b>`;
    btn.addEventListener('click', () => {
      if (impact.states.has(state)) impact.states.delete(state); else impact.states.add(state);
      filterImpact();
    });
    key.append(btn);
  });
  $('impact-total').textContent = fmtN(total);
  document.querySelectorAll('#impact-cats .cat-row').forEach(row => row.setAttribute('aria-pressed', String(impact.cats.has(row.dataset.cat))));
  $('impact-roads-toggle').setAttribute('aria-pressed', String(impact.cats.has('roads')));
  show(impact.roads, step === 4 && impact.cats.has('roads'));
  $('roads-legend').hidden = !(impact.roads && step === 4 && impact.cats.has('roads'));
}

function toggleCategory(key) {
  if (impact.cats.has(key)) impact.cats.delete(key); else impact.cats.add(key);
  filterImpact();
}

function renderImpactPanel() {
  const d = impact.data;
  $('impact-date').textContent = fmtLongDate(d.radar_date);
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
  $('impact-roads-km').textContent = `${fmtN(d.roads.flooded_km)} km`;
  $('impact-roads-toggle').onclick = () => toggleCategory('roads');
  $('impact-roads').innerHTML = Object.entries(d.roads.by_class).map(([k, r]) =>
    `<tr><th scope="row">${ESC(ROAD_LABEL[k] || k)}</th><td class="num">${fmtN(r.flooded_km)} km</td><td class="num">${fmtN(Math.round(r.observed_km))} km</td></tr>`).join('');
  const b = d.buildings.by_state, comm = d.categories.community, c = d.categories;
  $('impact-buildings').textContent =
    `Communities are ${fmtN(comm.places.total)} named places and ${fmtN(comm.clusters.total)} clusters of ${d.parameters.min_cluster_buildings}+ buildings. ` +
    `Of ${fmtN(d.buildings.total)} mapped building footprints, ${fmtN(b.in_water)} are on detectable open water, ${fmtN(b.isolated)} are possibly cut off and ` +
    `${fmtN(b.near_water)} are within ${d.parameters.near_water_m} m of that water. Footprints are not people: OpenStreetMap has no population here.`;
  $('impact-coverage').textContent =
    `OpenStreetMap maps ${fmtN(c.school.mapped)} schools, ${fmtN(c.health.mapped)} health facilities and ${fmtN(comm.places.total)} named places here; ` +
    `rural mapping is incomplete, so a place missing here is not a place the flood spared. The radar covers ` +
    `${Math.round(d.coverage.radar_observed_fraction * 100)}% of the area; the south, including Maputo, is outside it. OSM extract of ${osmDateText()}.`;
  $('impact-panel').hidden = false;
}

// Popups in the story send the reader to the route tool with the place filled in.
impact.actions = (p, lat, lon) => {
  const links = [`<a class="primary" href="${ESC(routesLink([lon, lat]))}">Plan a route to here</a>`];
  const nh = p.nearest_health;
  if (nh) links.push(`<a class="quiet" href="${ESC(routesLink([lon, lat], [nh.lon, nh.lat]))}">Route from that facility</a>`);
  return links.join('');
};
impact.onFilter = renderImpactCounts;

function card(label, value) {
  const d = document.createElement('div');
  d.className = 'fact';
  const b = document.createElement('b'); b.textContent = value;
  const s = document.createElement('span'); s.textContent = label;
  d.append(b, s);
  return d;
}

async function loadTimeline() {
  layers.timeline = [];
  const tl = stats.timeline;
  if (!tl || !Array.isArray(tl.observations) || !tl.observations.length) return;
  const loaded = [];
  for (const o of tl.observations) {
    const spec = stats.layers[o.layer];
    if (spec) loaded.push(await addLayer(spec, 'timelinePane', {opacity: 1}));
  }
  if (loaded.length !== tl.observations.length) {
    setStatus('Some NISAR timeline frames are missing; the two-date comparison still works.');
    return;
  }
  layers.timeline = loaded;
  mapView = 'timeline';
  $('timeline-slider').max = String(loaded.length - 1);
  $('timeline-ticks').innerHTML = tl.observations.map(o => `<span title="${ESC(o.granule || '')}">${ESC(fmtDate(o.date))}</span>`).join('');
  $('timeline-method').textContent = `Four observations: ${tl.method} Common valid coverage: ${tl.common_coverage_pct}% (${fmtKm2(tl.common_coverage_area_km2)}).`;
  $('timeline-caveat').textContent = tl.limitation;
  setTimelineIndex(loaded.length - 1);
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    $('timeline-play').disabled = true;
    $('timeline-play').title = 'Use the slider; animation is off because of your motion preference.';
  }
}

function renderFigures() {
  $('date-before').textContent = $('tag-before').textContent = fmtDate(stats.scenes.before.date);
  $('date-during').textContent = $('tag-during').textContent = fmtDate(stats.scenes.during.date);
  $('big-km2').textContent = stats.flooded_area_km2 == null ? '…' :
    Number(stats.flooded_area_km2).toLocaleString('en-US', {maximumFractionDigits: 1});

  const method = stats.method || {};
  const loosen = Number(method.loosen_db), minDrop = Number(method.min_drop_db);
  $('estimate-method-note').textContent = Number.isFinite(loosen) && Number.isFinite(minDrop)
    ? `Main estimate: new detectable open water between ${fmtDate(stats.scenes.before.date)} and ${fmtDate(stats.scenes.during.date)}, with --loosen ${loosen} dB applied to pixels whose HH darkened by at least ${minDrop} dB more than the whole scene. The four-observation view uses a strict threshold and another reference date, so its numbers are not directly comparable.`
    : 'Main estimate: new detectable open water between the two radar passes. The sensitivity settings are not recorded in this contract.';
  const rg = stats.flooded_area_range_km2;
  if (rg) {
    const f = (v) => Number(v).toLocaleString('en-US', {maximumFractionDigits: 1});
    $('range-note').textContent = `Estimate. Other reasonable thresholds give ${f(rg[0])} to ${f(rg[1])} km² (sensitivity scenarios, not a confidence interval).`;
    $('range-note').hidden = false;
  }

  const ctx = stats.context_figures;
  if (ctx) {
    ctx.items.forEach(it => $('context-figures').appendChild(card(it.label, it.value)));
    $('context-source').textContent = 'Source: ' + ctx.source;
  }

  const v = stats.validation;
  if (v) {
    const systemOnly = v.system_only_area_km2 ?? v.nisar_new_water_aoi_km2 - v.intersection_area_km2;
    const referenceOnly = v.reference_only_area_km2 ?? v.ems_flood_area_aoi_km2 - v.intersection_area_km2;
    [
      ['Spatial agreement (IoU)', Number(v.iou).toFixed(2)],
      ['Mapped by both', fmtKm2(v.intersection_area_km2)],
      ['Only NISAR', fmtKm2(systemOnly)],
      ['Only Copernicus', fmtKm2(referenceOnly)],
    ].forEach(([label, value]) => $('validation-metrics').appendChild(card(label, value)));
    $('validation-note').textContent =
      `Compared with ${v.product}, ${v.reference}, acquired ${v.acquisition_utc}. ${v.interpretation} ` +
      `Overlap: ${Math.round(v.overlap_fraction_nisar * 100)}% of the NISAR area and ${Math.round(v.overlap_fraction_ems * 100)}% of the EMS area ` +
      `(NISAR ${fmtKm2(v.nisar_new_water_aoi_km2)}, EMS ${fmtKm2(v.ems_flood_area_aoi_km2)}). IoU is the intersection divided by the union. ` +
      'This covers EMSR857 AOI02 only: it does not validate the whole area and is not field confirmation. Open this section to see the differences on the map. ';
    const source = document.createElement('a');
    source.href = v.reference_url || 'https://mapping.emergency.copernicus.eu/activations/EMSR857/';
    source.target = '_blank';
    source.rel = 'noopener noreferrer';
    source.textContent = 'Copernicus EMSR857';
    $('validation-note').append('Source: ', source, '.');
    if (!layers.validation) {
      $('validation-map-note').textContent = 'Difference polygons are not available in this build.';
      $('validation-map-note').hidden = false;
    }
    $('validation-section').hidden = false;
    $('validation-section').addEventListener('toggle', () => setStep(step));
  }

  const rows = [
    ['Before', stats.scenes.before.date], ['During', stats.scenes.during.date],
    ['Track / frame', `${stats.scenes.during.track} / ${stats.scenes.during.frame}`],
    ['Direction', stats.scenes.during.direction],
    ['Polarizations', fmt(stats.scenes.during.polarizations && stats.scenes.during.polarizations.join(', '))],
    ['Data level', stats.maturity], ['Product', stats.product],
    ['New detectable open water', fmtKm2(stats.flooded_area_km2) + (stats.mock ? ' (mock)' : '')],
    ['Permanent water', Math.round(stats.permanent_water_km2) + ' km²' + (stats.mock ? ' (mock)' : '')],
  ];
  rows.forEach(([k, val]) => {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd'); dd.textContent = val;
    $('numbers').append(dt, dd);
  });
  stats.limitations.forEach(t => {
    const li = document.createElement('li'); li.textContent = t; $('limits').appendChild(li);
  });
}

function buildProgress() {
  for (let i = 1; i <= TOTAL; i++) {
    const li = document.createElement('li');
    const b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('aria-label', `Step ${i}: ${stepName(i)}`);
    b.innerHTML = `<span class="n">${i}</span><span class="label">${ESC(stepName(i))}</span>`;
    b.addEventListener('click', () => setStep(i));
    li.appendChild(b);
    $('progress').appendChild(li);
  }
}

(async () => {
  buildProgress();
  setStep(1);
  stats = await loadStats();
  layers = await loadWaterLayers(stats);
  vegetationLegend($('vegetation-legend'), stats.layers.vegetation);
  await loadTimeline();
  try {
    if (await loadImpact(stats)) { renderImpactPanel(); filterImpact(); }
  } catch (error) {
    console.error('impact map unavailable', error);   // the rest of the story still works
    setStatus('OSM impact layers are unavailable; the NISAR story still works.');
  }
  renderFigures();

  $('prev').addEventListener('click', () => setStep(step - 1));
  $('next').addEventListener('click', () => setStep(step + 1));
  document.addEventListener('keydown', (ev) => {
    // Arrow keys move the story, except while typing or dragging a slider.
    if (ev.target.closest('input, textarea, select')) return;
    if (ev.key === 'ArrowRight') setStep(step + 1);
    if (ev.key === 'ArrowLeft') setStep(step - 1);
  });
  $('slider').addEventListener('input', () => updateClip(step === 3 && !timelineActive()));
  map.on('move zoom resize', () => updateClip(step === 3 && !timelineActive()));
  $('timeline-slider').addEventListener('input', (ev) => { setTimelinePlaying(false); setTimelineIndex(ev.target.value); });
  $('timeline-play').addEventListener('click', () => setTimelinePlaying(!timelineTimer));
  $('timeline-view-button').addEventListener('click', () => setMapView('timeline'));
  $('compare-view-button').addEventListener('click', () => setMapView('compare'));
  $('legend-toggle').addEventListener('click', () => {
    const expanded = $('legend-toggle').getAttribute('aria-expanded') === 'true';
    $('legend-toggle').setAttribute('aria-expanded', String(!expanded));
    $('legend-content').hidden = expanded;
  });
  setStep(step);
})();
