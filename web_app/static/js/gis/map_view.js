import { emptyFeatureCollection, escapeHtml } from "./api.js";

function createUnavailableMap() {
  const mapEl = document.getElementById("map");
  if (mapEl) {
    mapEl.innerHTML = `
      <div class="map-runtime-error">
        <strong>地图引擎加载失败</strong>
        <span>请检查网络，或确认 MapLibre 静态资源可以访问。</span>
      </div>
    `;
  }
  const emptyBounds = { toArray: () => [[0, 0], [0, 0]] };
  return {
    on(eventName, handler) {
      if (eventName === "load") window.setTimeout(handler, 0);
    },
    addControl() {},
    addSource() {},
    addLayer() {},
    getSource() { return null; },
    getLayer() { return null; },
    getBounds() { return emptyBounds; },
    getZoom() { return 0; },
    fitBounds() {},
    resize() {},
    getCanvas() { return { style: {} }; },
  };
}

function createMap() {
  if (!window.maplibregl) return createUnavailableMap();
  const instance = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: [
            "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
          ],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors",
        },
      },
      layers: [{ id: "osm", type: "raster", source: "osm" }],
    },
    center: [104.0668, 30.5728],
    zoom: 11,
  });

  instance.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  instance.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");
  return instance;
}

export const map = createMap();

export function sourceId(name) { return `src-${name}`; }
export function pointLayerId(name) { return `poi-${name}`; }
export function lineLayerId(name) { return `line-${name}`; }
export function fillLayerId(name) { return `fill-${name}`; }

export function addPopup(layerId) {
  if (map.__popupBoundLayers?.has(layerId)) return;
  map.__popupBoundLayers = map.__popupBoundLayers || new Set();
  map.__popupBoundLayers.add(layerId);

  map.on("click", layerId, (event) => {
    const feature = event.features && event.features[0];
    if (!feature) return;
    new maplibregl.Popup()
      .setLngLat(event.lngLat)
      .setHTML(popupHtml(feature.properties))
      .addTo(map);
  });
  map.on("mouseenter", layerId, () => { map.getCanvas().style.cursor = "pointer"; });
  map.on("mouseleave", layerId, () => { map.getCanvas().style.cursor = ""; });
}

function popupHtml(props) {
  return Object.entries(props || {})
    .filter(([key]) => key !== "__feature_index")
    .slice(0, 12)
    .map(([key, value]) => `<div><b>${escapeHtml(key)}</b>: ${escapeHtml(String(value))}</div>`)
    .join("") || "<div>无属性</div>";
}

export function setHighlights(geojson) {
  if (map.getSource("highlight-src")) {
    map.getSource("highlight-src").setData(geojson);
  } else {
    map.addSource("highlight-src", { type: "geojson", data: geojson });
    map.addLayer({
      id: "highlight-fill",
      type: "fill",
      source: "highlight-src",
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": "#facc15", "fill-opacity": 0.5 },
    });
    map.addLayer({
      id: "highlight-line",
      type: "line",
      source: "highlight-src",
      paint: { "line-color": "#f59e0b", "line-width": 4, "line-opacity": 0.95 },
    });
    map.addLayer({
      id: "highlight-point",
      type: "circle",
      source: "highlight-src",
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 8, 15, 14],
        "circle-color": "#facc15",
        "circle-opacity": 0.95,
        "circle-stroke-color": "#7c2d12",
        "circle-stroke-width": 2,
      },
    });
    addPopup("highlight-point");
  }
  fitGeoJson(geojson, 60);
}

export function fitGeoJson(geojson, padding) {
  const bounds = new maplibregl.LngLatBounds();
  (geojson.features || []).forEach((feature) => extendBounds(bounds, feature.geometry));
  if (!bounds.isEmpty()) map.fitBounds(bounds, { padding, maxZoom: 16, duration: 600 });
}

export function fitLayerBBoxes(layerPayload) {
  const bounds = new maplibregl.LngLatBounds();
  for (const item of layerPayload) {
    if (!item.bbox || item.bbox.length !== 4) continue;
    bounds.extend([item.bbox[0], item.bbox[1]]);
    bounds.extend([item.bbox[2], item.bbox[3]]);
  }
  if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 40, maxZoom: 12, duration: 600 });
}

function extendBounds(bounds, geometry) {
  if (!geometry) return;
  const c = geometry.coordinates;
  if (geometry.type === "Point") bounds.extend(c);
  else if (geometry.type === "LineString" || geometry.type === "MultiPoint") c.forEach((x) => bounds.extend(x));
  else if (geometry.type === "Polygon" || geometry.type === "MultiLineString") c.flat(1).forEach((x) => bounds.extend(x));
  else if (geometry.type === "MultiPolygon") c.flat(2).forEach((x) => bounds.extend(x));
}

export { emptyFeatureCollection };
