import { api, emptyFeatureCollection } from "./api.js";
import {
  addPopup,
  fillLayerId,
  fitGeoJson,
  fitLayerBBoxes,
  lineLayerId,
  map,
  pointLayerId,
  sourceId,
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

export async function loadLayers(options = {}) {
  const data = await api("/api/layers");
  await setLayers(data.layers || [], options);
}

async function setLayers(payload, options = {}) {
  const previousGeneratedLayers = new Set(knownGeneratedLayers);
  layerPayload = payload || [];
  for (const item of layerPayload) {
    ensureLayerSource(item);
    if (item.is_generated) knownGeneratedLayers.add(item.name);
  }
  renderLayerControl();
  if (options.fit) fitLayerBBoxes(layerPayload);
  if (options.autoLoadGenerated) await autoLoadGeneratedLayers(previousGeneratedLayers);
}

function ensureLayerSource(item) {
  const style = item.visualization_style || {};
  const color = style.fill_color || style.color || palette[item.layer_index % palette.length];
  const lineColor = style.line_color || color;
  const name = item.name;
  const src = sourceId(name);
  if (!map.getSource(src)) {
    map.addSource(src, { type: "geojson", data: emptyFeatureCollection() });
  }

  if (!map.getLayer(fillLayerId(name))) {
    map.addLayer({
      id: fillLayerId(name),
      type: "fill",
      source: src,
      filter: ["any", ["==", ["geometry-type"], "Polygon"], ["==", ["geometry-type"], "MultiPolygon"]],
      layout: { visibility: "none" },
      paint: buildFillPaint(style, color),
    });
  }
  if (!map.getLayer(lineLayerId(name))) {
    map.addLayer({
      id: lineLayerId(name),
      type: "line",
      source: src,
      filter: [
        "any",
        ["==", ["geometry-type"], "LineString"],
        ["==", ["geometry-type"], "MultiLineString"],
        ["==", ["geometry-type"], "Polygon"],
        ["==", ["geometry-type"], "MultiPolygon"],
      ],
      layout: { visibility: "none" },
      paint: buildLinePaint(style, lineColor),
    });
  }
  if (!map.getLayer(pointLayerId(name))) {
    map.addLayer({
      id: pointLayerId(name),
      type: "circle",
      source: src,
      filter: ["==", ["geometry-type"], "Point"],
      layout: { visibility: "none" },
      paint: buildPointPaint(style, color),
    });
  }

  addPopup(pointLayerId(name));
  addPopup(lineLayerId(name));
  addPopup(fillLayerId(name));
}

function buildFillPaint(style, color) {
  if (style.kind === "hotspot") {
    const maxCount = Math.max(1, Number(style.max_count || 1));
    return {
      "fill-color": [
        "interpolate",
        ["linear"],
        ["to-number", ["get", style.value_field || "count"], 0],
        0, "#fee2e2",
        Math.max(1, maxCount * 0.35), "#f97316",
        maxCount, "#dc2626",
      ],
      "fill-opacity": style.fill_opacity ?? 0.58,
    };
  }
  return { "fill-color": color, "fill-opacity": style.fill_opacity ?? 0.22 };
}

function buildLinePaint(style, lineColor) {
  if (style.kind === "hotspot") {
    return {
      "line-color": style.line_color || "#991b1b",
      "line-width": style.line_width ?? 1.6,
      "line-opacity": style.line_opacity ?? 0.9,
    };
  }
  return {
    "line-color": lineColor,
    "line-width": style.line_width ?? 1.5,
    "line-opacity": style.line_opacity ?? 0.78,
  };
}

function buildPointPaint(style, color) {
  if (style.kind === "dbscan") {
    const field = style.cluster_field || "cluster_id";
    return {
      "circle-radius": [
        "case",
        ["==", ["to-number", ["get", field], -1], -1],
        ["interpolate", ["linear"], ["zoom"], 10, 2.5, 15, 4],
        ["interpolate", ["linear"], ["zoom"], 10, 4, 15, 9],
      ],
      "circle-color": clusterColorExpression(field),
      "circle-opacity": [
        "case",
        ["==", ["to-number", ["get", field], -1], -1],
        0.25,
        0.86,
      ],
      "circle-stroke-color": [
        "case",
        ["==", ["to-number", ["get", field], -1], -1],
        "#64748b",
        "#ffffff",
      ],
      "circle-stroke-width": [
        "case",
        ["==", ["to-number", ["get", field], -1], -1],
        0.5,
        1.2,
      ],
    };
  }
  return {
    "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3, 15, 7],
    "circle-color": color,
    "circle-opacity": 0.75,
    "circle-stroke-color": "#fff",
    "circle-stroke-width": 1,
  };
}

function clusterColorExpression(field) {
  const expression = ["match", ["to-number", ["get", field], -1], -1, "#94a3b8"];
  clusterColors.forEach((color, index) => {
    expression.push(index, color);
  });
  expression.push("#0f172a");
  return expression;
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
    await loadLayerData(item);
  }
}

function clearLayerData(layerName) {
  updateLayerSource(layerName, emptyFeatureCollection());
  setLayerVisibility(layerName, false);
  layerStatus.delete(layerName);
}

function updateLayerSource(layerName, geojson) {
  const source = map.getSource(sourceId(layerName));
  if (source) source.setData(geojson || emptyFeatureCollection());
}

function setLayerVisibility(layerName, visible) {
  const value = visible ? "visible" : "none";
  [pointLayerId(layerName), lineLayerId(layerName), fillLayerId(layerName)].forEach((id) => {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", value);
  });
}

function getCurrentBboxString() {
  const bounds = map.getBounds();
  return [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].join(",");
}

async function autoLoadGeneratedLayers(previousGeneratedLayers) {
  for (const item of layerPayload) {
    if (!item.is_generated || !item.auto_visible) continue;
    if (previousGeneratedLayers.has(item.name)) continue;
    selectedLayers.add(item.name);
    await loadLayerData(item, { fullExtent: true, fit: true });
  }
}
