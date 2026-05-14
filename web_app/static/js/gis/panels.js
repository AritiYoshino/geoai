import {
  api,
  emptyFeatureCollection,
  escapeHtml,
  formatMessageTime,
  prettyValue,
} from "./api.js";
import { loadLayers } from "./layers.js";
import { setHighlights } from "./map_view.js";

let currentSessionId = "";
let suppressBankChange = false;

function getMessageProfile(role, sender) {
  if (role === "user") return {name: "用户", avatar: "我", className: "user"};
  return {name: sender || "GeoAI", avatar: "AI", className: "assistant"};
}

function inferMessageRole(sender) {
  if (sender === "user" || sender === "用户" || sender === "我") return "user";
  if (sender === "system" || sender === "系统") return "system";
  return "assistant";
}

function addMessage(sender, content, options = {}) {
  const log = document.getElementById("chatLog");
  if (!log) return;
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

function addExportLinks(exports = []) {
  if (!exports.length) return;
  const log = document.getElementById("chatLog");
  if (!log) return;
  const box = document.createElement("div");
  box.className = "message message-assistant";
  const links = exports.map((item) => `
    <a class="text-btn" href="${escapeHtml(item.download_url || item.url)}" download>
      下载 ${escapeHtml(item.filename || "导出文件")}
    </a>
    <span>${escapeHtml(item.path || "")}</span>
  `).join("");
  box.innerHTML = `
    <div class="message-avatar" aria-hidden="true">AI</div>
    <div class="message-main">
      <div class="message-meta">
        <span class="message-name">GeoAI</span>
        <time class="message-time">${escapeHtml(formatMessageTime())}</time>
      </div>
      <div class="message-bubble">
        <div>导出文件已生成：</div>
        ${links}
      </div>
    </div>
  `;
  log.appendChild(box);
  log.scrollTop = log.scrollHeight;
}

export function renderAcePanel(panel = {}) {
  document.getElementById("aceTaskType").textContent = prettyValue(panel.task_type, "暂无任务类型");
  document.getElementById("aceExperienceHit").textContent = prettyValue(panel.retrieved_experiences, "暂无检索经验");
  document.getElementById("aceGeneratedCode").textContent = prettyValue(panel.generated_code, "本轮未生成空间代码");
  document.getElementById("aceExecutionStatus").textContent = prettyValue(panel.execution_status, "暂无执行状态");
  document.getElementById("aceDiagnosis").textContent = prettyValue(panel.error_diagnosis, "暂无错误诊断");
  document.getElementById("aceEvolution").textContent = prettyValue(panel.experience_update, "暂无经验库更新记录");
}

export async function sendMessage() {
  const input = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const message = input?.value.trim() || "";
  if (!message) return;

  input.value = "";
  input.dispatchEvent(new Event("input", {bubbles: true}));
  addMessage("用户", message, {role: "user"});
  addMessage("系统", "正在由多智能体协同分析...", {role: "system"});
  if (sendBtn) sendBtn.disabled = true;

  try {
    const data = await api("/api/chat", {method: "POST", body: JSON.stringify({message})});
    addMessage("GeoAI", data.answer, {role: "assistant"});
    addExportLinks(data.exports || []);
    document.getElementById("traceBox").textContent = data.trace || "";
    renderAcePanel(data.ace_panel || {});
    document.getElementById("experienceBox").textContent = data.experience || "";
    setHighlights(data.highlights || emptyFeatureCollection());
    await loadLayers({autoLoadGenerated: true});
    renderSessions(data.sessions, data.session);
  } catch (error) {
    addMessage("系统", `错误：${error.message}`, {role: "system"});
  } finally {
    if (sendBtn) sendBtn.disabled = false;
  }
}

export async function refreshTrace() {
  const data = await api("/api/trace");
  document.getElementById("traceBox").textContent = data.trace || "";
}

export async function refreshAcePanel() {
  const data = await api("/api/ace-panel");
  renderAcePanel(data.ace_panel || {});
}

export async function refreshExperience() {
  const data = await api("/api/experience");
  document.getElementById("experienceBox").textContent = data.summary || "";
}

export async function refreshSessions() {
  const data = await api("/api/sessions");
  renderSessions(data.sessions, data.current);
  renderSessionHistory(data.current);
  renderAcePanel(data.current?.last_ace_panel || {});
}

function renderSessions(sessions, current) {
  const container = document.getElementById("sessionList");
  if (!container) return;
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
  if (!log) return;
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
    body: JSON.stringify({session_id: sessionId}),
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
    body: JSON.stringify({session_id: session.id, title}),
  });
  renderSessions(data.sessions, data.current);
}

async function deleteSession(session) {
  const confirmed = confirm(`确定删除会话“${session.title || "未命名会话"}”吗？`);
  if (!confirmed) return;
  const data = await api("/api/sessions/delete", {
    method: "POST",
    body: JSON.stringify({session_id: session.id}),
  });
  renderSessions(data.sessions, data.current);
  renderSessionHistory(data.current);
  document.getElementById("traceBox").textContent = data.trace || "";
  renderAcePanel(data.ace_panel || {});
  setHighlights(emptyFeatureCollection());
}

export async function refreshBanks() {
  const data = await api("/api/experience-banks");
  renderBanks(data.banks, data.active);
}

function renderBanks(banks, active) {
  const select = document.getElementById("bankSelect");
  const renameBtn = document.getElementById("renameBankBtn");
  const deleteBtn = document.getElementById("deleteBankBtn");
  if (!select) return;

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
  if (renameBtn) {
    renameBtn.disabled = locked;
    renameBtn.title = locked ? "默认经验库不允许重命名" : "重命名当前经验库";
  }
  if (deleteBtn) {
    deleteBtn.disabled = locked;
    deleteBtn.title = locked ? "默认经验库不允许删除" : "删除当前经验库";
  }
}

export async function renameActiveBank() {
  const select = document.getElementById("bankSelect");
  const currentOption = select?.options[select.selectedIndex];
  if (!currentOption) return;
  const bankId = currentOption.value;
  const currentName = currentOption.textContent.replace(/\s*\[[^\]]+\]\s*$/, "");
  const name = prompt("请输入新的经验库名称：", currentName);
  if (name === null) return;
  const data = await api("/api/experience-banks/rename", {
    method: "POST",
    body: JSON.stringify({bank_id: bankId, name}),
  });
  renderBanks(data.banks, data.active);
  document.getElementById("experienceBox").textContent = data.summary || "";
  addMessage("系统", `已重命名经验库：${data.bank.name}`, {role: "system"});
}

export async function deleteActiveBank() {
  const select = document.getElementById("bankSelect");
  const currentOption = select?.options[select.selectedIndex];
  if (!currentOption) return;
  const bankId = currentOption.value;
  const bankName = currentOption.textContent.replace(/\s*\[[^\]]+\]\s*$/, "");
  const confirmed = confirm(`确定删除经验库“${bankName}”吗？`);
  if (!confirmed) return;
  const data = await api("/api/experience-banks/delete", {
    method: "POST",
    body: JSON.stringify({bank_id: bankId}),
  });
  renderBanks(data.banks, data.active);
  document.getElementById("experienceBox").textContent = data.summary || "";
  addMessage("系统", `已删除经验库，当前切换为：${data.active.name}`, {role: "system"});
}

export async function switchExperienceBank(event) {
  if (suppressBankChange) return;
  const data = await api("/api/experience-banks/switch", {
    method: "POST",
    body: JSON.stringify({bank_id: event.target.value}),
  });
  const banksPayload = await api("/api/experience-banks");
  renderBanks(banksPayload.banks, banksPayload.active);
  addMessage("系统", `已切换经验库：${data.bank.name}`, {role: "system"});
  document.getElementById("experienceBox").textContent = data.summary || "";
}

export async function createExperienceBank(templateOrButton) {
  const template = typeof templateOrButton === "string"
    ? templateOrButton
    : templateOrButton?.dataset?.template || "empty";
  const name = prompt("请输入经验库名称：");
  if (!name) return;
  const data = await api("/api/experience-banks/create", {
    method: "POST",
    body: JSON.stringify({name, template}),
  });
  renderBanks(data.banks, data.bank);
  document.getElementById("experienceBox").textContent = data.summary || "";
  addMessage("系统", `已创建并切换到经验库：${data.bank.name}`, {role: "system"});
}

export async function newSession() {
  const data = await api("/api/sessions/new", {method: "POST", body: "{}"});
  await refreshSessions();
  renderSessionHistory(data.session);
  renderAcePanel(data.session?.last_ace_panel || {});
  await refreshTrace();
}

export async function clearHighlights() {
  const data = await api("/api/highlights/clear", {method: "POST", body: "{}"});
  setHighlights(data.geojson);
}
