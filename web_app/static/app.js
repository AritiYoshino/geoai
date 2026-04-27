const palette = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2"];
let layerPayload = [];
let suppressSessionChange = false;
let suppressBankChange = false;

const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: [
          "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
          "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
          "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png"
        ],
        tileSize: 256,
        attribution: "© OpenStreetMap contributors"
      }
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }]
  },
  center: [104.0668, 30.5728],
  zoom: 11
});
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");
map.on("load", async () => {
  await loadLayers();
  await refreshSessions();
  await refreshTrace();
  await refreshExperience();
  await refreshBanks();
});

function sourceId(name) { return `src-${name}`; }
function pointLayerId(name) { return `poi-${name}`; }
function lineLayerId(name) { return `line-${name}`; }
function fillLayerId(name) { return `fill-${name}`; }

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || response.statusText);
  return data;
}

async function loadLayers() {
  const data = await api("/api/layers");
  setLayers(data.layers);
}

function setLayers(payload) {
  layerPayload = payload || [];
  for (const item of layerPayload) {
    const color = palette[item.layer_index % palette.length];
    const name = item.name;
    const src = sourceId(name);
    if (map.getSource(src)) {
      map.getSource(src).setData(item.geojson);
      continue;
    }
    map.addSource(src, { type: "geojson", data: item.geojson });
    map.addLayer({ id: fillLayerId(name), type: "fill", source: src, filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": color, "fill-opacity": 0.22 } });
    map.addLayer({ id: lineLayerId(name), type: "line", source: src, filter: ["any", ["==", ["geometry-type"], "LineString"], ["==", ["geometry-type"], "Polygon"]], paint: { "line-color": color, "line-width": 1.5, "line-opacity": 0.78 } });
    map.addLayer({ id: pointLayerId(name), type: "circle", source: src, filter: ["==", ["geometry-type"], "Point"], paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3, 15, 7], "circle-color": color, "circle-opacity": 0.75, "circle-stroke-color": "#fff", "circle-stroke-width": 1 } });
    addPopup(pointLayerId(name));
    addPopup(lineLayerId(name));
    addPopup(fillLayerId(name));
  }
  renderLayerControl();
  fitAllLayers();
}

function renderLayerControl() {
  const container = document.getElementById("layerList");
  container.innerHTML = "";
  for (const item of layerPayload) {
    const row = document.createElement("label");
    row.className = "layer-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.onchange = () => {
      const visibility = checkbox.checked ? "visible" : "none";
      [pointLayerId(item.name), lineLayerId(item.name), fillLayerId(item.name)].forEach((id) => {
        if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visibility);
      });
    };
    const text = document.createElement("span");
    text.textContent = `${item.name} (${item.feature_count})`;
    row.append(checkbox, text);
    container.appendChild(row);
  }
}

function addPopup(layerId) {
  map.on("click", layerId, (event) => {
    const feature = event.features && event.features[0];
    if (!feature) return;
    new maplibregl.Popup().setLngLat(event.lngLat).setHTML(popupHtml(feature.properties)).addTo(map);
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

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
}

function setHighlights(geojson) {
  if (map.getSource("highlight-src")) {
    map.getSource("highlight-src").setData(geojson);
  } else {
    map.addSource("highlight-src", { type: "geojson", data: geojson });
    map.addLayer({ id: "highlight-fill", type: "fill", source: "highlight-src", filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": "#facc15", "fill-opacity": 0.5 } });
    map.addLayer({ id: "highlight-line", type: "line", source: "highlight-src", paint: { "line-color": "#f59e0b", "line-width": 4, "line-opacity": 0.95 } });
    map.addLayer({ id: "highlight-point", type: "circle", source: "highlight-src", filter: ["==", ["geometry-type"], "Point"], paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 8, 15, 14], "circle-color": "#facc15", "circle-opacity": 0.95, "circle-stroke-color": "#7c2d12", "circle-stroke-width": 2 } });
    addPopup("highlight-point");
  }
  fitGeoJson(geojson, 60);
}

function fitAllLayers() {
  const all = { type: "FeatureCollection", features: [] };
  layerPayload.forEach((item) => all.features.push(...(item.geojson.features || [])));
  fitGeoJson(all, 40);
}

function fitGeoJson(geojson, padding) {
  const bounds = new maplibregl.LngLatBounds();
  (geojson.features || []).forEach((feature) => extendBounds(bounds, feature.geometry));
  if (!bounds.isEmpty()) map.fitBounds(bounds, { padding, maxZoom: 16, duration: 600 });
}

function extendBounds(bounds, geometry) {
  if (!geometry) return;
  const c = geometry.coordinates;
  if (geometry.type === "Point") bounds.extend(c);
  else if (geometry.type === "LineString" || geometry.type === "MultiPoint") c.forEach((x) => bounds.extend(x));
  else if (geometry.type === "Polygon" || geometry.type === "MultiLineString") c.flat(1).forEach((x) => bounds.extend(x));
  else if (geometry.type === "MultiPolygon") c.flat(2).forEach((x) => bounds.extend(x));
}

function addMessage(sender, content) {
  const log = document.getElementById("chatLog");
  const box = document.createElement("div");
  box.className = "message";
  box.innerHTML = `<div class="sender">${escapeHtml(sender)}</div><div class="content">${escapeHtml(content)}</div>`;
  log.appendChild(box);
  log.scrollTop = log.scrollHeight;
}

async function sendMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMessage("用户", message);
  addMessage("系统", "正在由多智能体协同分析...");
  document.getElementById("sendBtn").disabled = true;
  try {
    const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
    addMessage("AI 助手", data.answer);
    document.getElementById("traceBox").textContent = data.trace || "";
    document.getElementById("experienceBox").textContent = data.experience || "";
    setHighlights(data.highlights || { type: "FeatureCollection", features: [] });
    renderSessions(data.sessions, data.session);
  } catch (error) {
    addMessage("系统", `错误：${error.message}`);
  } finally {
    document.getElementById("sendBtn").disabled = false;
  }
}

async function refreshTrace() {
  const data = await api("/api/trace");
  document.getElementById("traceBox").textContent = data.trace || "";
}

async function refreshExperience() {
  const data = await api("/api/experience");
  document.getElementById("experienceBox").textContent = data.summary || "";
}

async function refreshSessions() {
  const data = await api("/api/sessions");
  renderSessions(data.sessions, data.current);
  renderSessionHistory(data.current);
}

function renderSessions(sessions, current) {
  const select = document.getElementById("sessionSelect");
  suppressSessionChange = true;
  select.innerHTML = "";
  (sessions || []).forEach((session) => {
    const option = document.createElement("option");
    option.value = session.id;
    option.textContent = `${session.title || "未命名会话"} [${session.updated_at || ""}]`;
    if (current && session.id === current.id) option.selected = true;
    select.appendChild(option);
  });
  suppressSessionChange = false;
}

function renderSessionHistory(session) {
  const log = document.getElementById("chatLog");
  log.innerHTML = "";
  (session?.messages || []).forEach((msg) => {
    addMessage(msg.role === "user" ? "用户" : "AI 助手", msg.content || "");
  });
}

async function refreshBanks() {
  const data = await api("/api/experience-banks");
  renderBanks(data.banks, data.active);
}

function renderBanks(banks, active) {
  const select = document.getElementById("bankSelect");
  suppressBankChange = true;
  select.innerHTML = "";
  (banks || []).forEach((bank) => {
    const option = document.createElement("option");
    option.value = bank.id;
    option.textContent = `${bank.name || "未命名经验库"} [${bank.id}]`;
    if (active && bank.id === active.id) option.selected = true;
    select.appendChild(option);
  });
  suppressBankChange = false;
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(`${button.dataset.tab}Tab`).classList.add("active");
  });
});

document.getElementById("sendBtn").addEventListener("click", sendMessage);
document.getElementById("chatInput").addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.key === "Enter") sendMessage();
});
document.getElementById("clearHighlightBtn").addEventListener("click", async () => {
  const data = await api("/api/highlights/clear", { method: "POST", body: "{}" });
  setHighlights(data.geojson);
});
document.getElementById("newSessionBtn").addEventListener("click", async () => {
  const data = await api("/api/sessions/new", { method: "POST", body: "{}" });
  await refreshSessions();
  renderSessionHistory(data.session);
});
document.getElementById("sessionSelect").addEventListener("change", async (event) => {
  if (suppressSessionChange) return;
  const data = await api("/api/sessions/switch", { method: "POST", body: JSON.stringify({ session_id: event.target.value }) });
  renderSessionHistory(data.session);
  await refreshTrace();
});
document.getElementById("okBtn").addEventListener("click", () => submitFeedback("correct"));
document.getElementById("badBtn").addEventListener("click", () => submitFeedback("incorrect"));
document.getElementById("fixBtn").addEventListener("click", async () => {
  const correction = prompt("请说明正确结果或以后应遵循的规则：");
  if (correction) await submitFeedback("correction", correction);
});

async function submitFeedback(type, correction = "") {
  const data = await api("/api/feedback", { method: "POST", body: JSON.stringify({ type, correction }) });
  addMessage("系统", `已记录反馈并更新经验库：${data.result}`);
  document.getElementById("experienceBox").textContent = data.experience || "";
}

document.getElementById("refreshExperienceBtn").addEventListener("click", refreshExperience);
document.getElementById("bankSelect").addEventListener("change", async (event) => {
  if (suppressBankChange) return;
  const data = await api("/api/experience-banks/switch", { method: "POST", body: JSON.stringify({ bank_id: event.target.value }) });
  addMessage("系统", `已切换经验库：${data.bank.name}`);
  document.getElementById("experienceBox").textContent = data.summary || "";
});
document.querySelectorAll(".bankCreateBtn").forEach((button) => {
  button.addEventListener("click", async () => {
    const name = prompt("请输入经验库名称：");
    if (!name) return;
    const data = await api("/api/experience-banks/create", { method: "POST", body: JSON.stringify({ name, template: button.dataset.template }) });
    renderBanks(data.banks, data.bank);
    document.getElementById("experienceBox").textContent = data.summary || "";
    addMessage("系统", `已创建并切换到经验库：${data.bank.name}`);
  });
});
