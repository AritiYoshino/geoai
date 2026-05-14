import { emptyFeatureCollection, escapeHtml } from "./api.js";

const olRoot = window.ol;

function createUnavailableMap() {
  const mapEl = document.getElementById("map");
  if (mapEl) {
    mapEl.innerHTML = `
      <div class="map-runtime-error">
        <strong>地图引擎加载失败</strong>
        <span>请检查网络，或确认 OpenLayers 静态资源可以访问。</span>
      </div>
    `;
  }
  return {
    on(eventName, handler) {
      if (eventName === "load") window.setTimeout(handler, 0);
    },
    addLayer() {},
    removeLayer() {},
    getLayers() { return { getArray: () => [] }; },
    getView() { return { getZoom: () => 0, calculateExtent: () => [0, 0, 0, 0], fit() {} }; },
    resize() {},
    updateSize() {},
  };
}

function createMap() {
  if (!olRoot) return createUnavailableMap();
  const defaultControls = olRoot.control.defaults?.defaults
    ? olRoot.control.defaults.defaults()
    : olRoot.control.defaults();
  const instance = new olRoot.Map({
    target: "map",
    layers: [
      new olRoot.layer.Tile({
        source: new olRoot.source.OSM(),
      }),
    ],
    view: new olRoot.View({
      center: olRoot.proj.fromLonLat([104.0668, 30.5728]),
      zoom: 11,
    }),
    controls: defaultControls.extend([
      new olRoot.control.ScaleLine({ units: "metric" }),
    ]),
  });

  const originalOn = instance.on.bind(instance);
  instance.on = (eventName, handler) => {
    if (eventName === "load") {
      window.setTimeout(handler, 0);
      return undefined;
    }
    return originalOn(eventName, handler);
  };
  instance.resize = () => instance.updateSize();
  instance.getZoom = () => instance.getView().getZoom() || 0;
  instance.getBounds = () => {
    const extent = instance.getView().calculateExtent(instance.getSize());
    const lonLatExtent = olRoot.proj.transformExtent(extent, "EPSG:3857", "EPSG:4326");
    return {
      getWest: () => lonLatExtent[0],
      getSouth: () => lonLatExtent[1],
      getEast: () => lonLatExtent[2],
      getNorth: () => lonLatExtent[3],
    };
  };
  return instance;
}

export const map = createMap();

const popupEl = document.createElement("div");
popupEl.className = "ol-popup";
popupEl.style.cssText = "background:#fff;border:1px solid #cbd5e1;border-radius:6px;box-shadow:0 8px 24px rgba(15,23,42,.18);padding:8px 10px;max-width:320px;font-size:12px;";
const popupOverlay = olRoot ? new olRoot.Overlay({ element: popupEl, offset: [0, -10], positioning: "bottom-center" }) : null;
if (popupOverlay && map.addOverlay) map.addOverlay(popupOverlay);

const popupLayers = new Set();

export function sourceId(name) { return `src-${name}`; }
export function pointLayerId(name) { return `poi-${name}`; }
export function lineLayerId(name) { return `line-${name}`; }
export function fillLayerId(name) { return `fill-${name}`; }

export function addPopup(layer) {
  if (!layer || popupLayers.has(layer)) return;
  popupLayers.add(layer);
}

if (map.on && olRoot) {
  map.on("singleclick", (event) => {
    let picked = null;
    map.forEachFeatureAtPixel(event.pixel, (feature, layer) => {
      if (!popupLayers.has(layer)) return undefined;
      picked = feature;
      return true;
    });
    if (!picked || !popupOverlay) {
      if (popupOverlay) popupOverlay.setPosition(undefined);
      return;
    }
    popupEl.innerHTML = popupHtml(picked.getProperties());
    popupOverlay.setPosition(event.coordinate);
  });
}

function popupHtml(props) {
  return Object.entries(props || {})
    .filter(([key, value]) => key !== "geometry" && key !== "__feature_index" && value !== undefined)
    .slice(0, 12)
    .map(([key, value]) => `<div><b>${escapeHtml(key)}</b>: ${escapeHtml(String(value))}</div>`)
    .join("") || "<div>无属性</div>";
}

const geoJsonFormat = olRoot ? new olRoot.format.GeoJSON() : null;
let highlightSource = null;
let highlightLayer = null;

export function setHighlights(geojson) {
  if (!olRoot || !geoJsonFormat) return;
  if (!highlightSource) {
    highlightSource = new olRoot.source.Vector();
    highlightLayer = new olRoot.layer.Vector({
      source: highlightSource,
      style: highlightStyle,
      zIndex: 900,
    });
    map.addLayer(highlightLayer);
    addPopup(highlightLayer);
  }
  const features = geoJsonFormat.readFeatures(geojson || emptyFeatureCollection(), {
    dataProjection: "EPSG:4326",
    featureProjection: "EPSG:3857",
  });
  highlightSource.clear();
  highlightSource.addFeatures(features);
  fitGeoJson(geojson, 60);
}

function highlightStyle(feature) {
  const geomType = feature.getGeometry()?.getType();
  return new olRoot.style.Style({
    image: new olRoot.style.Circle({
      radius: 8,
      fill: new olRoot.style.Fill({ color: "rgba(250, 204, 21, 0.95)" }),
      stroke: new olRoot.style.Stroke({ color: "#7c2d12", width: 2 }),
    }),
    fill: geomType?.includes("Polygon") ? new olRoot.style.Fill({ color: "rgba(250, 204, 21, 0.45)" }) : undefined,
    stroke: new olRoot.style.Stroke({ color: "#f59e0b", width: 4 }),
  });
}

export function fitGeoJson(geojson, padding) {
  if (!olRoot || !geoJsonFormat || !geojson?.features?.length) return;
  const features = geoJsonFormat.readFeatures(geojson, {
    dataProjection: "EPSG:4326",
    featureProjection: "EPSG:3857",
  });
  const extent = olRoot.extent.createEmpty();
  features.forEach((feature) => olRoot.extent.extend(extent, feature.getGeometry().getExtent()));
  if (!olRoot.extent.isEmpty(extent)) {
    map.getView().fit(extent, { padding: [padding, padding, padding, padding], maxZoom: 16, duration: 600 });
  }
}

export function fitLayerBBoxes(layerPayload) {
  if (!olRoot) return;
  const extent = olRoot.extent.createEmpty();
  for (const item of layerPayload) {
    if (!item.bbox || item.bbox.length !== 4) continue;
    const transformed = olRoot.proj.transformExtent(item.bbox, "EPSG:4326", "EPSG:3857");
    olRoot.extent.extend(extent, transformed);
  }
  if (!olRoot.extent.isEmpty(extent)) {
    map.getView().fit(extent, { padding: [40, 40, 40, 40], maxZoom: 12, duration: 600 });
  }
}

export function bboxToExtent(bbox) {
  if (!olRoot || !bbox || bbox.length !== 4) return null;
  return olRoot.proj.transformExtent(bbox, "EPSG:4326", "EPSG:3857");
}

export function createGeoJsonFeatures(geojson) {
  if (!geoJsonFormat) return [];
  return geoJsonFormat.readFeatures(geojson || emptyFeatureCollection(), {
    dataProjection: "EPSG:4326",
    featureProjection: "EPSG:3857",
  });
}

export { emptyFeatureCollection, olRoot as ol };
