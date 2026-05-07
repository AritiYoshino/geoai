export async function api(path, options = {}) {
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

export function debounce(fn, wait) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

export function emptyFeatureCollection() {
  return { type: "FeatureCollection", features: [] };
}

export function escapeHtml(text) {
  return String(text).replace(/[&<>\"']/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[ch]
  ));
}

export function formatMessageTime(value) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return value || "";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export function prettyValue(value, emptyText = "暂无") {
  if (value === null || value === undefined || value === "") return emptyText;
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
