import { api, emptyFeatureCollection } from "./api.js";
import {
  addPopup,
  bboxToExtent,
  createGeoJsonFeatures,
  fitGeoJson,
  fitLayerBBoxes,
  map,
  ol,
} from "./map_view.js";

const palette = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2"];
const clusterColors = [
  "#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2",
  "#c026d3", "#65a30d", "#d97706", "#0f766e", "#7c3aed", "#be123c",
];

let layerPayload = [];
const selectedLayers = new Set();
const layerStatus = new Map();
const knownGeneratedLayers = new Set();
const layerRegistry = new Map();

export async function loadLayers(options = {}) {
  const data = await api("/api/layers");
  await setLayers(data.layers || [], options);
}

async function setLayers(payload, options = {}) {
  const previousGeneratedLayers = new Set(knownGeneratedLayers);
  layerPayload = payload || [];
  for (const item of layerPayload) {
    ensureLayer(item);
    if (item.is_generated) knownGeneratedLayers.add(item.name);
  }
  renderLayerControl();
  if (options.fit) fitLayerBBoxes(layerPayload);
  if (options.autoLoadGenerated) await autoLoadGeneratedLayers(previousGeneratedLayers);
}

function ensureLayer(item) {
  if (!ol || layerRegistry.has(item.name)) return;
  const layer = item.layer_type === "raster" ? createRasterLayer(item) : createVectorLayer(item);
  layer.setVisible(false);
  map.addLayer(layer);
  layerRegistry.set(item.name, { layer, source: layer.getSource(), item });
  if (item.layer_type !== "raster") addPopup(layer);
}

function createRasterLayer(item) {
  const extent = bboxToExtent(item.bbox);
  const source = new ol.source.ImageStatic({
    url: item.raster_url,
    imageExtent: extent,
    projection: "EPSG:3857",
    crossOrigin: "anonymous",
  });
  return new ol.layer.Image({
    source,
    opacity: Number(item.visualization_style?.opacity ?? 0.78),
    zIndex: 300,
  });
}

function createVectorLayer(item) {
  const source = new ol.source.Vector();
  return new ol.layer.Vector({
    source,
    style: (feature) => vectorStyle(item, feature),
    zIndex: item.is_generated ? 500 : 100,
  });
}

function vectorStyle(item, feature) {
  const style = item.visualization_style || {};
  const geometryType = feature.getGeometry()?.getType() || "";
  if (style.kind === "dbscan") return dbscanStyle(feature, style);
  if (style.kind === "hotspot") return hotspotStyle(feature, style);
  if (style.kind === "choropleth") return choroplethStyle(feature, style);

  const color = style.fill_color || style.color || palette[item.layer_index % palette.length];
  const lineColor = style.line_color || color;
  return new ol.style.Style({
    image: new ol.style.Circle({
      radius: 5,
      fill: new ol.style.Fill({ color }),
      stroke: new ol.style.Stroke({ color: "#fff", width: 1 }),
    }),
    fill: geometryType.includes("Polygon")
      ? new ol.style.Fill({ color: withAlpha(color, style.fill_opacity ?? 0.22) })
      : undefined,
    stroke: new ol.style.Stroke({
      color: withAlpha(lineColor, style.line_opacity ?? 0.78),
      width: style.line_width ?? 1.5,
    }),
  });
}

function dbscanStyle(feature, style) {
  const field = style.cluster_field || "cluster_id";
  const clusterId = Number(feature.get(field) ?? -1);
  const isNoise = clusterId < 0;
  const color = isNoise ? "#94a3b8" : clusterColors[clusterId % clusterColors.length];
  return new ol.style.Style({
    image: new ol.style.Circle({
      radius: isNoise ? 3 : 6,
      fill: new ol.style.Fill({ color: withAlpha(color, isNoise ? 0.35 : 0.86) }),
      stroke: new ol.style.Stroke({ color: isNoise ? "#64748b" : "#ffffff", width: isNoise ? 0.5 : 1.2 }),
    }),
  });
}

function hotspotStyle(feature, style) {
  const maxCount = Math.max(1, Number(style.max_count || 1));
  const value = Math.max(0, Number(feature.get(style.value_field || "count") || 0));
  const t = Math.min(1, value / maxCount);
  const color = t > 0.35 ? "#f97316" : "#fee2e2";
  return new ol.style.Style({
    fill: new ol.style.Fill({ color: withAlpha(t >= 1 ? "#dc2626" : color, style.fill_opacity ?? 0.58) }),
    stroke: new ol.style.Stroke({
      color: withAlpha(style.line_color || "#991b1b", style.line_opacity ?? 0),
      width: style.line_width ?? 0,
    }),
  });
}

function choroplethStyle(feature, style) {
  const maxCount = Math.max(1, Number(style.max_count || 1));
  const value = Math.max(0, Number(feature.get(style.value_field || "poi_count") || 0));
  const t = Math.min(1, value / maxCount);
  const color = interpolateColor("#dbeafe", "#1d4ed8", t);
  return new ol.style.Style({
    fill: new ol.style.Fill({ color: withAlpha(color, style.fill_opacity ?? 0.72) }),
    stroke: new ol.style.Stroke({
      color: withAlpha(style.line_color || "#475569", style.line_opacity ?? 0.9),
      width: style.line_width ?? 1.2,
    }),
  });
}

function interpolateColor(startHex, endHex, t) {
  const start = hexToRgb(startHex);
  const end = hexToRgb(endHex);
  const mixed = start.map((value, index) => Math.round(value + (end[index] - value) * t));
  return `#${mixed.map((value) => value.toString(16).padStart(2, "0")).join("")}`;
}

function hexToRgb(hex) {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
}

function withAlpha(hex, alpha) {
  if (!hex || !hex.startsWith("#") || hex.length !== 7) return hex;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function renderLayerControl() {
  const container = document.getElementById("layerList");
  container.innerHTML = "";

  for (const item of layerPayload) {
    const row = document.createElement("div");
    row.className = "layer-card";

    const head = document.createElement("label");
    head.className = "layer-row";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selectedLayers.has(item.name);
    checkbox.onchange = async () => {
      if (checkbox.checked) {
        selectedLayers.add(item.name);
        await loadLayerData(item);
      } else {
        selectedLayers.delete(item.name);
        clearLayerData(item.name);
      }
      renderLayerControl();
    };

    const title = document.createElement("div");
    title.className = "layer-title";
    title.textContent = item.name;

    head.append(checkbox, title, createLayerSymbol(item));
    row.append(head);
    container.appendChild(row);
  }
}

function createLayerSymbol(item) {
  const style = item.visualization_style || {};
  const color = style.fill_color || style.color || palette[item.layer_index % palette.length];
  const lineColor = style.line_color || color;
  const geometryTypes = item.geometry_types || [];
  const symbol = document.createElement("div");
  symbol.className = "layer-symbol";
  symbol.title = `地图样式：${geometryTypes.join(", ") || "Unknown"}`;

  if (item.layer_type === "raster" || style.kind === "raster") {
    ["#fee2e2", "#fb923c", "#dc2626"].forEach((stopColor) => {
      const patch = document.createElement("span");
      patch.className = "layer-symbol-polygon layer-symbol-hotspot";
      patch.style.backgroundColor = stopColor;
      patch.style.borderColor = "transparent";
      symbol.appendChild(patch);
    });
    return symbol;
  }

  if (style.kind === "dbscan") {
    clusterColors.slice(0, 3).forEach((clusterColor) => {
      const point = document.createElement("span");
      point.className = "layer-symbol-point";
      point.style.backgroundColor = clusterColor;
      symbol.appendChild(point);
    });
    return symbol;
  }

  if (style.kind === "hotspot") {
    ["#fee2e2", "#fb923c", "#dc2626"].forEach((stopColor) => {
      const patch = document.createElement("span");
      patch.className = "layer-symbol-polygon layer-symbol-hotspot";
      patch.style.backgroundColor = stopColor;
      patch.style.borderColor = lineColor;
      symbol.appendChild(patch);
    });
    return symbol;
  }

  if (style.kind === "choropleth") {
    ["#dbeafe", "#60a5fa", "#1d4ed8"].forEach((stopColor) => {
      const patch = document.createElement("span");
      patch.className = "layer-symbol-polygon layer-symbol-hotspot";
      patch.style.backgroundColor = stopColor;
      patch.style.borderColor = style.line_color || "#475569";
      symbol.appendChild(patch);
    });
    return symbol;
  }

  const hasPolygon = geometryTypes.some((type) => type === "Polygon" || type === "MultiPolygon");
  const hasLine = geometryTypes.some((type) => type === "LineString" || type === "MultiLineString");
  const hasPoint = geometryTypes.some((type) => type === "Point" || type === "MultiPoint");

  if (hasPolygon) {
    const patch = document.createElement("span");
    patch.className = "layer-symbol-polygon";
    patch.style.backgroundColor = color;
    patch.style.borderColor = lineColor;
    patch.style.opacity = style.fill_opacity ?? 0.72;
    symbol.appendChild(patch);
  }
  if (hasLine) {
    const line = document.createElement("span");
    line.className = "layer-symbol-line";
    line.style.backgroundColor = lineColor;
    symbol.appendChild(line);
  }
  if (hasPoint || (!hasPolygon && !hasLine)) {
    const point = document.createElement("span");
    point.className = "layer-symbol-point";
    point.style.backgroundColor = color;
    symbol.appendChild(point);
  }

  return symbol;
}

async function loadLayerData(item, options = {}) {
  if (item.layer_type === "raster") {
    setLayerVisibility(item.name, true);
    layerStatus.set(item.name, "已加载栅格图层");
    if (options.fit && item.bbox?.length === 4) fitRasterBbox(item.bbox);
    renderLayerControl();
    return;
  }

  const bbox = options.fullExtent ? "" : getCurrentBboxString();
  const zoom = map.getZoom().toFixed(2);
  const params = new URLSearchParams({ layer_name: item.name, bbox, zoom });
  const data = await api(`/api/layer_data?${params.toString()}`);
  layerStatus.set(item.name, data.message || `已加载当前视野 ${data.returned_count} 个要素。`);

  if (data.deferred) {
    setLayerVisibility(item.name, false);
    updateLayerSource(item.name, emptyFeatureCollection());
    renderLayerControl();
    return;
  }

  updateLayerSource(item.name, data.geojson || emptyFeatureCollection());
  setLayerVisibility(item.name, true);
  if (options.fit) fitGeoJson(data.geojson || emptyFeatureCollection(), 70);
  renderLayerControl();
}

export async function refreshSelectedLayers() {
  for (const item of layerPayload) {
    if (!selectedLayers.has(item.name)) continue;
    if (item.layer_type === "raster") continue;
    await loadLayerData(item);
  }
}

function clearLayerData(layerName) {
  const registry = layerRegistry.get(layerName);
  if (registry?.item?.layer_type !== "raster") updateLayerSource(layerName, emptyFeatureCollection());
  setLayerVisibility(layerName, false);
  layerStatus.delete(layerName);
}

function updateLayerSource(layerName, geojson) {
  const registry = layerRegistry.get(layerName);
  if (!registry?.source?.clear) return;
  registry.source.clear();
  registry.source.addFeatures(createGeoJsonFeatures(geojson || emptyFeatureCollection()));
}

function setLayerVisibility(layerName, visible) {
  const registry = layerRegistry.get(layerName);
  if (registry?.layer) registry.layer.setVisible(visible);
}

function getCurrentBboxString() {
  const bounds = map.getBounds();
  return [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].join(",");
}

function fitRasterBbox(bbox) {
  const extent = bboxToExtent(bbox);
  if (extent) map.getView().fit(extent, { padding: [70, 70, 70, 70], maxZoom: 13, duration: 600 });
}

async function autoLoadGeneratedLayers(previousGeneratedLayers) {
  for (const item of layerPayload) {
    if (!item.is_generated || !item.auto_visible) continue;
    if (previousGeneratedLayers.has(item.name)) continue;
    selectedLayers.add(item.name);
    await loadLayerData(item, { fullExtent: true, fit: true });
  }
}
