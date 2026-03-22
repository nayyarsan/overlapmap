// OverlapMap — app.js
// Loads scored_tracts.topojson, renders Leaflet choropleth,
// recolors polygons on weight slider changes.

'use strict';

// ── Config ──────────────────────────────────────────────────────────────────
const LAYERS = [
  { id: 'crime',   scoreKey: 'crime_score',   displayKey: 'crime_incidents_per_1k', label: 'Crime',       fmt: v => v != null ? v.toFixed(1) + '/1k' : 'N/A' },
  { id: 'fire',    scoreKey: 'fire_score',    displayKey: 'dominant_hazard_class',  label: 'Fire Risk',   fmt: v => v ?? 'N/A' },
  { id: 'env',     scoreKey: 'env_score',     displayKey: 'calenviro_score',        label: 'Environment', fmt: v => v != null ? v.toFixed(1) : 'N/A' },
  { id: 'school',  scoreKey: 'school_score',  displayKey: 'school_avg_rating',      label: 'Schools',     fmt: v => v != null ? v.toFixed(1) + '%' : 'N/A' },
  { id: 'transit', scoreKey: 'transit_score', displayKey: 'transit_freq_peak',      label: 'Transit',     fmt: v => v != null ? v.toFixed(1) : 'N/A' },
];

// Color scale: 0=red, 5=amber, 10=green
const COLOR_SCALE = chroma.scale(['#f44336', '#ff9800', '#8bc34a', '#4caf50'])
  .domain([0, 3.5, 6.0, 10]);

// ── State ────────────────────────────────────────────────────────────────────
let geojsonLayer = null;
let featuresCache = [];

function getWeights() {
  const weights = {};
  document.querySelectorAll('.layer-row').forEach(row => {
    const id  = row.dataset.layer;
    const cb  = row.querySelector('input[type="checkbox"]');
    const sl  = row.querySelector('input[type="range"]');
    weights[id] = cb.checked ? parseInt(sl.value, 10) : 0;
  });
  return weights;
}

function computeComposite(props, weights) {
  let total = 0, totalW = 0;
  for (const layer of LAYERS) {
    const w = weights[layer.id] || 0;
    const s = props[layer.scoreKey];
    if (w > 0 && s != null) {
      total  += w * s;
      totalW += w;
    }
  }
  return totalW > 0 ? total / totalW : null;
}

// ── Map setup ─────────────────────────────────────────────────────────────────
const map = L.map('map', { center: [34.05, -118.25], zoom: 10 });
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>',
  maxZoom: 19,
}).addTo(map);

// ── Data load ────────────────────────────────────────────────────────────────
fetch('./data/scored_tracts.topojson')
  .then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then(topo => {
    const key = Object.keys(topo.objects)[0];
    const geojson = topojson.feature(topo, topo.objects[key]);
    featuresCache = geojson.features;
    renderLayer();

    // Show data_updated date
    if (featuresCache.length > 0) {
      const dt = featuresCache[0].properties.data_updated;
      if (dt) document.getElementById('data-updated').textContent = `Data: ${dt}`;
    }
  })
  .catch(err => console.error('Failed to load TopoJSON:', err));

// ── Render ────────────────────────────────────────────────────────────────────
function renderLayer() {
  const weights = getWeights();

  if (geojsonLayer) {
    geojsonLayer.remove();
  }

  geojsonLayer = L.geoJSON(featuresCache, {
    style: feature => {
      const composite = computeComposite(feature.properties, weights);
      return {
        fillColor:   composite != null ? COLOR_SCALE(composite).hex() : '#888',
        fillOpacity: 0.7,
        color:       '#fff',
        weight:      0.4,
        opacity:     0.6,
      };
    },
    onEachFeature: (feature, layer) => {
      layer.on('click', () => showPopup(feature, layer, weights));
    },
  }).addTo(map);
}

// ── Popup ─────────────────────────────────────────────────────────────────────
function showPopup(feature, layer, weights) {
  const p = feature.properties;
  const composite = computeComposite(p, weights);
  const compositeStr = composite != null ? composite.toFixed(1) : 'N/A';
  const compositeColor = composite != null ? COLOR_SCALE(composite).hex() : '#888';

  const scoreBars = LAYERS.map(l => {
    const score = p[l.scoreKey];
    const raw   = p[l.displayKey];
    const pct   = score != null ? (score / 10 * 100).toFixed(0) : 0;
    const color = score != null ? COLOR_SCALE(score).hex() : '#ccc';
    return `
      <div class="score-bar-row">
        <span class="score-bar-label">${l.label}</span>
        <div class="score-bar-track">
          <div class="score-bar-fill" style="width:${pct}%;background:${color}"></div>
        </div>
        <span class="score-bar-val">${score != null ? score.toFixed(1) : 'N/A'}</span>
      </div>
      <div style="font-size:0.68rem;color:#888;margin:-2px 0 4px 78px">${l.fmt(raw)}</div>
    `;
  }).join('');

  const html = `
    <div class="om-popup">
      <h3>${p.tract_name || p.tract_id}</h3>
      <div class="composite-score" style="color:${compositeColor}">${compositeStr} / 10</div>
      ${scoreBars}
      <hr class="popup-divider" />
      <div class="popup-meta">
        <div>2BR Rent: ${p.rent_2br_median ? '$' + p.rent_2br_median.toLocaleString() + '/mo' : 'N/A'}</div>
        <div>Avg built: ${p.median_year_built ?? 'N/A'}</div>
      </div>
    </div>
  `;

  layer.bindPopup(html, { maxWidth: 300 }).openPopup();
}

// ── Slider / checkbox events ──────────────────────────────────────────────────
document.querySelectorAll('.layer-row').forEach(row => {
  const cb = row.querySelector('input[type="checkbox"]');
  const sl = row.querySelector('input[type="range"]');
  const vl = row.querySelector('.weight-val');

  cb.addEventListener('change', () => {
    row.classList.toggle('disabled', !cb.checked);
    renderLayer();
  });

  sl.addEventListener('input', () => {
    vl.textContent = sl.value;
    renderLayer();
  });
});
