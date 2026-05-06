const palette = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2"];
let layerPayload = [];
let currentSessionId = "";
let suppressBankChange = false;
const selectedLayers = new Set();
const layerStatus = new Map();

const shell = document.getElementById("appShell");
const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");

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

const refreshSelectedLayersDebounced = debounce(() => refreshSelectedLayers(), 450);

map.on("load", async () => {
  await loadLayers();
  await refreshSessions();
  await refreshTrace();
  await refreshAcePanel();
  await refreshExperience();
  await refreshBanks();
});

map.on("moveend", () => {
  refreshSelectedLayersDebounced();
});

function sourceId(name) { return `src-${name}`; }
function pointLayerId(name) { return `poi-${name}`; }
function lineLayerId(name) { return `line-${name}`; }
function fillLayerId(name) { return `fill-${name}`; }

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (error) {
    throw new Error("无法连接到 Web 服务。请确认 main.py 正在运行。");
  }

  const contentType = response.headers.get("Content-Type") || "";
  const rawText = await response.text();
  let data = {};

  if (rawText) {
    if (contentType.includes("application/json")) {
      data = JSON.parse(rawText);
    } else if (!response.ok) {
      throw new Error(`服务返回了非 JSON 响应（HTTP ${response.status}）。`);
    }
  }

  if (!response.ok || data.error) throw new Error(data.error || response.statusText);
  return data;
}

async function loadLayers() {
  const data = await api("/api/layers");
  setLayers(data.layers || []);
}

function setLayers(payload) {
  layerPayload = payload || [];
  for (const item of layerPayload) {
    ensureLayerSource(item);
  }
  renderLayerControl();
  fitAllLayerBBoxes();
}

function ensureLayerSource(item) {
  const color = palette[item.layer_index % palette.length];
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
      filter: ["==", ["geometry-type"], "Polygon"],
      layout: { visibility: "none" },
      paint: { "fill-color": color, "fill-opacity": 0.22 }
    });
  }
  if (!map.getLayer(lineLayerId(name))) {
    map.addLayer({
      id: lineLayerId(name),
      type: "line",
      source: src,
      filter: ["any", ["==", ["geometry-type"], "LineString"], ["==", ["geometry-type"], "Polygon"]],
      layout: { visibility: "none" },
      paint: { "line-color": color, "line-width": 1.5, "line-opacity": 0.78 }
    });
  }
  if (!map.getLayer(pointLayerId(name))) {
    map.addLayer({
      id: pointLayerId(name),
      type: "circle",
      source: src,
      filter: ["==", ["geometry-type"], "Point"],
      layout: { visibility: "none" },
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3, 15, 7],
        "circle-color": color,
        "circle-opacity": 0.75,
        "circle-stroke-color": "#fff",
        "circle-stroke-width": 1
      }
    });
  }

  addPopup(pointLayerId(name));
  addPopup(lineLayerId(name));
  addPopup(fillLayerId(name));
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

    const titleWrap = document.createElement("div");
    titleWrap.className = "layer-title-wrap";

    const title = document.createElement("div");
    title.className = "layer-title";
    title.textContent = `${item.name} (${item.feature_count})`;

    const meta = document.createElement("div");
    meta.className = "layer-meta";
    meta.textContent = `${(item.geometry_types || []).join(", ")} | ${item.fields.length} 字段`;

    titleWrap.append(title, meta);
    head.append(checkbox, titleWrap);

    const hint = document.createElement("div");
    hint.className = "layer-hint";
    hint.textContent = buildLayerHint(item);

    row.append(head, hint);
    container.appendChild(row);
  }
}

function buildLayerHint(item) {
  const status = layerStatus.get(item.name) || "";
  if (status) return status;
  if (item.is_large_layer) {
    return `大图层，建议放大到 ${item.min_zoom} 级后再加载当前视野数据。`;
  }
  return "勾选后按当前地图视野按需加载。";
}

async function loadLayerData(item) {
  const bbox = getCurrentBboxString();
  const zoom = map.getZoom().toFixed(2);
  const params = new URLSearchParams({
    layer_name: item.name,
    bbox,
    zoom,
  });
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
  renderLayerControl();
}

async function refreshSelectedLayers() {
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

function emptyFeatureCollection() {
  return { type: "FeatureCollection", features: [] };
}

function addPopup(layerId) {
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

function escapeHtml(text) {
  return String(text).replace(/[&<>\"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]));
}

function setHighlights(geojson) {
  if (map.getSource("highlight-src")) {
    map.getSource("highlight-src").setData(geojson);
  } else {
    map.addSource("highlight-src", { type: "geojson", data: geojson });
    map.addLayer({
      id: "highlight-fill",
      type: "fill",
      source: "highlight-src",
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": "#facc15", "fill-opacity": 0.5 }
    });
    map.addLayer({
      id: "highlight-line",
      type: "line",
      source: "highlight-src",
      paint: { "line-color": "#f59e0b", "line-width": 4, "line-opacity": 0.95 }
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
        "circle-stroke-width": 2
      }
    });
    addPopup("highlight-point");
  }
  fitGeoJson(geojson, 60);
}

function fitAllLayerBBoxes() {
  const bounds = new maplibregl.LngLatBounds();
  for (const item of layerPayload) {
    if (!item.bbox || item.bbox.length !== 4) continue;
    bounds.extend([item.bbox[0], item.bbox[1]]);
    bounds.extend([item.bbox[2], item.bbox[3]]);
  }
  if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 40, maxZoom: 12, duration: 600 });
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

function getMessageProfile(role, sender) {
  if (role === "user") return { name: "用户", avatar: "你", className: "user" };
  return { name: sender || "GeoAI", avatar: "AI", className: "assistant" };
}

function formatMessageTime(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return value || "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function inferMessageRole(sender) {
  if (sender === "user" || sender === "用户" || sender === "鐢ㄦ埛") return "user";
  if (sender === "system" || sender === "系统" || sender === "绯荤粺") return "system";
  return "assistant";
}

function addMessage(sender, content, options = {}) {
  const log = document.getElementById("chatLog");
  const box = document.createElement("div");
  const role = options.role || inferMessageRole(sender);
  if (role === "system") {
    box.className = "message-status";
    box.innerHTML = `
      <span class="message-status-dot" aria-hidden="true"></span>
      <span>${escapeHtml(content)}</span>
      <time>${escapeHtml(formatMessageTime(options.time))}</time>
    `;
    log.appendChild(box);
    log.scrollTop = log.scrollHeight;
    return;
  }

  const profile = getMessageProfile(role, sender);
  box.className = `message message-${profile.className}`;
  box.innerHTML = `
    <div class="message-avatar" aria-hidden="true">${escapeHtml(profile.avatar)}</div>
    <div class="message-main">
      <div class="message-meta">
        <span class="message-name">${escapeHtml(profile.name)}</span>
        <time class="message-time">${escapeHtml(formatMessageTime(options.time))}</time>
      </div>
      <div class="message-bubble">${escapeHtml(content)}</div>
    </div>
  `;
  log.appendChild(box);
  log.scrollTop = log.scrollHeight;
}

function prettyValue(value, emptyText = "暂无") {
  if (value === null || value === undefined || value === "") return emptyText;
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function renderAcePanel(panel = {}) {
  document.getElementById("aceTaskType").textContent = prettyValue(panel.task_type, "暂无任务类型");
  document.getElementById("aceExperienceHit").textContent = prettyValue(panel.retrieved_experiences, "暂无检索经验");
  document.getElementById("aceGeneratedCode").textContent = prettyValue(panel.generated_code, "本轮未生成空间代码");
  document.getElementById("aceExecutionStatus").textContent = prettyValue(panel.execution_status, "暂无执行状态");
  document.getElementById("aceDiagnosis").textContent = prettyValue(panel.error_diagnosis, "暂无错误诊断");
  document.getElementById("aceEvolution").textContent = prettyValue(panel.experience_update, "暂无经验库更新记录");
}

async function sendMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMessage("用户", message, { role: "user" });
  addMessage("系统", "正在由多智能体协同分析...", { role: "system" });
  document.getElementById("sendBtn").disabled = true;
  try {
    const data = await api("/api/chat", { method: "POST", body: JSON.stringify({ message }) });
    addMessage("GeoAI", data.answer, { role: "assistant" });
    document.getElementById("traceBox").textContent = data.trace || "";
    renderAcePanel(data.ace_panel || {});
    document.getElementById("experienceBox").textContent = data.experience || "";
    setHighlights(data.highlights || emptyFeatureCollection());
    renderSessions(data.sessions, data.session);
  } catch (error) {
    addMessage("系统", `错误：${error.message}`, { role: "system" });
  } finally {
    document.getElementById("sendBtn").disabled = false;
  }
}

async function refreshTrace() {
  const data = await api("/api/trace");
  document.getElementById("traceBox").textContent = data.trace || "";
}

async function refreshAcePanel() {
  const data = await api("/api/ace-panel");
  renderAcePanel(data.ace_panel || {});
}

async function refreshExperience() {
  const data = await api("/api/experience");
  document.getElementById("experienceBox").textContent = data.summary || "";
}

async function refreshSessions() {
  const data = await api("/api/sessions");
  renderSessions(data.sessions, data.current);
  renderSessionHistory(data.current);
  renderAcePanel(data.current?.last_ace_panel || {});
}

function renderSessions(sessions, current) {
  const container = document.getElementById("sessionList");
  container.innerHTML = "";
  currentSessionId = current?.id || "";

  (sessions || []).forEach((session) => {
    const item = document.createElement("div");
    item.className = `session-item${session.id === currentSessionId ? " active" : ""}`;
    item.dataset.sessionId = session.id;
    item.innerHTML = `
      <div class="session-main">
        <div class="session-title">${escapeHtml(session.title || "未命名会话")}</div>
        <div class="session-meta">${escapeHtml(session.updated_at || "")}</div>
      </div>
      <div class="session-actions">
        <button class="mini-btn" type="button" data-action="rename" title="重命名">✎</button>
        <button class="mini-btn danger-btn" type="button" data-action="delete" title="删除">×</button>
      </div>
    `;
    item.addEventListener("click", (event) => {
      const action = event.target.dataset.action;
      if (action === "rename") {
        event.stopPropagation();
        renameSession(session);
        return;
      }
      if (action === "delete") {
        event.stopPropagation();
        deleteSession(session);
        return;
      }
      switchSession(session.id);
    });
    container.appendChild(item);
  });
}

function renderSessionHistory(session) {
  const log = document.getElementById("chatLog");
  log.innerHTML = "";
  (session?.messages || []).forEach((msg) => {
    addMessage(msg.role === "user" ? "用户" : "GeoAI", msg.content || "", {
      role: msg.role === "user" ? "user" : "assistant",
      time: msg.time,
    });
  });
}

async function switchSession(sessionId) {
  if (!sessionId || sessionId === currentSessionId) return;
  const data = await api("/api/sessions/switch", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId })
  });
  currentSessionId = data.session?.id || sessionId;
  renderSessionHistory(data.session);
  renderAcePanel(data.session?.last_ace_panel || {});
  await refreshSessions();
  await refreshTrace();
}

async function renameSession(session) {
  const title = prompt("请输入新的会话名称：", session.title || "");
  if (title === null) return;
  const data = await api("/api/sessions/rename", {
    method: "POST",
    body: JSON.stringify({ session_id: session.id, title })
  });
  renderSessions(data.sessions, data.current);
}

async function deleteSession(session) {
  const confirmed = confirm(`确定删除会话“${session.title || "未命名会话"}”吗？`);
  if (!confirmed) return;
  const data = await api("/api/sessions/delete", {
    method: "POST",
    body: JSON.stringify({ session_id: session.id })
  });
  renderSessions(data.sessions, data.current);
  renderSessionHistory(data.current);
  document.getElementById("traceBox").textContent = data.trace || "";
  renderAcePanel(data.ace_panel || {});
  setHighlights(emptyFeatureCollection());
}

async function refreshBanks() {
  const data = await api("/api/experience-banks");
  renderBanks(data.banks, data.active);
}

function renderBanks(banks, active) {
  const select = document.getElementById("bankSelect");
  const renameBtn = document.getElementById("renameBankBtn");
  const deleteBtn = document.getElementById("deleteBankBtn");
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

  const activeBank = active || (banks || []).find((bank) => bank.id === select.value);
  const locked = !!activeBank?.read_only;
  renameBtn.disabled = locked;
  deleteBtn.disabled = locked;
  renameBtn.title = locked ? "默认经验库不允许重命名" : "重命名当前经验库";
  deleteBtn.title = locked ? "默认经验库不允许删除" : "删除当前经验库";
}

async function renameActiveBank() {
  const select = document.getElementById("bankSelect");
  const currentOption = select.options[select.selectedIndex];
  if (!currentOption) return;
  const bankId = currentOption.value;
  const currentName = currentOption.textContent.replace(/\s*\[[^\]]+\]\s*$/, "");
  const name = prompt("请输入新的经验库名称：", currentName);
  if (name === null) return;
  const data = await api("/api/experience-banks/rename", {
    method: "POST",
    body: JSON.stringify({ bank_id: bankId, name })
  });
  renderBanks(data.banks, data.active);
  document.getElementById("experienceBox").textContent = data.summary || "";
  addMessage("系统", `已重命名经验库：${data.bank.name}`, { role: "system" });
}

async function deleteActiveBank() {
  const select = document.getElementById("bankSelect");
  const currentOption = select.options[select.selectedIndex];
  if (!currentOption) return;
  const bankId = currentOption.value;
  const bankName = currentOption.textContent.replace(/\s*\[[^\]]+\]\s*$/, "");
  const confirmed = confirm(`确定删除经验库“${bankName}”吗？`);
  if (!confirmed) return;
  const data = await api("/api/experience-banks/delete", {
    method: "POST",
    body: JSON.stringify({ bank_id: bankId })
  });
  renderBanks(data.banks, data.active);
  document.getElementById("experienceBox").textContent = data.summary || "";
  addMessage("系统", `已删除经验库，当前切换为：${data.active.name}`, { role: "system" });
}

function toggleSidebar() {
  shell.classList.toggle("sidebar-collapsed");
  const collapsed = shell.classList.contains("sidebar-collapsed");
  sidebarToggleBtn.title = collapsed ? "展开侧栏" : "收起侧栏";
  sidebarToggleBtn.setAttribute("aria-label", collapsed ? "展开侧栏" : "收起侧栏");
  window.setTimeout(() => map.resize(), 260);
}

function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(`${button.dataset.tab}Tab`).classList.add("active");
  });
});

sidebarToggleBtn.addEventListener("click", toggleSidebar);

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
  renderAcePanel(data.session?.last_ace_panel || {});
  await refreshTrace();
});

document.getElementById("refreshExperienceBtn").addEventListener("click", refreshExperience);
document.getElementById("renameBankBtn").addEventListener("click", renameActiveBank);
document.getElementById("deleteBankBtn").addEventListener("click", deleteActiveBank);

document.getElementById("bankSelect").addEventListener("change", async (event) => {
  if (suppressBankChange) return;
  const data = await api("/api/experience-banks/switch", {
    method: "POST",
    body: JSON.stringify({ bank_id: event.target.value })
  });
  const banksPayload = await api("/api/experience-banks");
  renderBanks(banksPayload.banks, banksPayload.active);
  addMessage("系统", `已切换经验库：${data.bank.name}`, { role: "system" });
  document.getElementById("experienceBox").textContent = data.summary || "";
});

document.querySelectorAll(".bankCreateBtn").forEach((button) => {
  button.addEventListener("click", async () => {
    const name = prompt("请输入经验库名称：");
    if (!name) return;
    const data = await api("/api/experience-banks/create", {
      method: "POST",
      body: JSON.stringify({ name, template: button.dataset.template })
    });
    renderBanks(data.banks, data.bank);
    document.getElementById("experienceBox").textContent = data.summary || "";
    addMessage("系统", `已创建并切换到经验库：${data.bank.name}`, { role: "system" });
  });
});
