import { debounce } from "./js/gis/api.js";
import { loadLayers, refreshSelectedLayers } from "./js/gis/layers.js";
import { map } from "./js/gis/map_view.js";
import {
  clearHighlights,
  createExperienceBank,
  deleteActiveBank,
  newSession,
  refreshAcePanel,
  refreshBanks,
  refreshExperience,
  refreshSessions,
  refreshTrace,
  renameActiveBank,
  sendMessage,
  switchExperienceBank,
} from "./js/gis/panels.js";

const shell = document.getElementById("appShell");
const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");
const sidebarToggleIcon = sidebarToggleBtn?.querySelector(".toggle-icon");

if (sidebarToggleIcon) sidebarToggleIcon.textContent = "<";
if (sidebarToggleBtn) {
  sidebarToggleBtn.title = "收起侧栏";
  sidebarToggleBtn.setAttribute("aria-label", "收起侧栏");
}

const refreshSelectedLayersDebounced = debounce(() => refreshSelectedLayers(), 450);

async function runStartupTask(taskName, task) {
  try {
    await task();
  } catch (error) {
    console.error(`${taskName} 初始化失败:`, error);
    if (taskName === "图层") {
      const layerList = document.getElementById("layerList");
      if (layerList) layerList.innerHTML = '<div class="inline-empty">图层加载失败，请刷新或检查服务日志。</div>';
    }
    if (taskName === "会话") {
      const sessionList = document.getElementById("sessionList");
      if (sessionList) sessionList.innerHTML = '<div class="inline-empty">会话加载失败</div>';
    }
  }
}

map.on("load", async () => {
  await Promise.all([
    runStartupTask("图层", () => loadLayers({ fit: true })),
    runStartupTask("会话", refreshSessions),
    runStartupTask("ACE 轨迹", refreshTrace),
    runStartupTask("ACE 面板", refreshAcePanel),
    runStartupTask("经验库摘要", refreshExperience),
    runStartupTask("经验库列表", refreshBanks),
  ]);
});

map.on("moveend", () => {
  refreshSelectedLayersDebounced();
});

function toggleSidebar() {
  shell.classList.toggle("sidebar-collapsed");
  const collapsed = shell.classList.contains("sidebar-collapsed");
  const label = collapsed ? "展开侧栏" : "收起侧栏";
  if (sidebarToggleBtn) {
    sidebarToggleBtn.title = label;
    sidebarToggleBtn.setAttribute("aria-label", label);
  }
  if (sidebarToggleIcon) sidebarToggleIcon.textContent = collapsed ? ">" : "<";
  window.setTimeout(() => map.resize(), 260);
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(`${button.dataset.tab}Tab`)?.classList.add("active");
  });
});

sidebarToggleBtn?.addEventListener("click", toggleSidebar);

document.getElementById("sendBtn")?.addEventListener("click", sendMessage);
document.getElementById("chatInput")?.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.key === "Enter") sendMessage();
});

document.getElementById("clearHighlightBtn")?.addEventListener("click", clearHighlights);
document.getElementById("newSessionBtn")?.addEventListener("click", newSession);
document.getElementById("refreshExperienceBtn")?.addEventListener("click", refreshExperience);
document.getElementById("renameBankBtn")?.addEventListener("click", renameActiveBank);
document.getElementById("deleteBankBtn")?.addEventListener("click", deleteActiveBank);
document.getElementById("bankSelect")?.addEventListener("change", switchExperienceBank);

document.querySelectorAll(".bankCreateBtn").forEach((button) => {
  button.addEventListener("click", () => createExperienceBank(button));
});
