if (!window.Vue) {
  document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("experimentApp");
    if (!app) return;
    app.removeAttribute("v-cloak");
    app.innerHTML = `
      <nav class="exp-nav">
        <div class="exp-nav-left">
          <span class="nav-logo">GeoAI</span>
          <span class="exp-nav-title">ACE 对比实验</span>
        </div>
        <div class="exp-nav-actions">
          <a href="/" class="exp-nav-back">首页</a>
        </div>
      </nav>
      <section class="exp-status-line error">
        实验前端依赖 Vue 未加载，页面应用无法挂载，因此不会绘制图表。请检查在线环境是否能访问
        https://unpkg.com/vue@3/dist/vue.global.prod.js，或将 Vue 改为本地静态资源。
      </section>
    `;
  });
  throw new Error("Vue failed to load; experiment charts cannot be rendered.");
}

const {createApp, nextTick, ref, computed, onMounted, watch} = window.Vue;

const EXPERIMENTS = [
  {id: "exp1", label: "exp1 总体性能对比", shortLabel: "实验一", title: "总体性能对比"},
  {id: "exp2", label: "exp2 连续学习", shortLabel: "实验二", title: "连续学习"},
  {id: "exp3", label: "exp3 消融实验", shortLabel: "实验三", title: "模块消融"},
  {id: "exp4", label: "exp4 上下文稳定性", shortLabel: "实验四", title: "上下文稳定性"},
];

const METRIC_LABELS = {
  task_success_rate: "成功率",
  success_rate: "成功率",
  average_runtime: "平均耗时",
  average_latency: "平均耗时",
  average_turns: "平均轮数",
  error_count: "错误数",
  repair_success_rate: "修复率",
  self_repair_rate: "修复率",
  experience_reuse_rate: "经验复用率",
  tool_selection_accuracy: "工具准确率",
  result_correctness: "结果正确率",
  final_context_token_count: "最终 token",
  final_effective_strategy_entry_count: "有效条目",
  final_duplicate_entry_ratio: "重复比例",
  context_sudden_shorten_count: "突然缩短",
  performance_sudden_drop_count: "性能下降",
};

const METRIC_ICONS = {
  task_success_rate: "✓",
  success_rate: "✓",
  average_runtime: "⏱",
  average_latency: "⏱",
  average_turns: "↻",
  error_count: "×",
  repair_success_rate: "⚙",
  self_repair_rate: "⚙",
  experience_reuse_rate: "◎",
  tool_selection_accuracy: "◇",
  result_correctness: "✓",
  final_context_token_count: "T",
  final_effective_strategy_entry_count: "#",
  final_duplicate_entry_ratio: "%",
  context_sudden_shorten_count: "↓",
  performance_sudden_drop_count: "!",
};

const GROUP_LABELS = {
  all: "全部",
  direct_llm: "Direct LLM",
  react_agent: "ReAct Agent",
  codeact_agent: "CodeAct Agent",
  ace_webgis: "ACE-WebGIS",
  base_agent: "Base Agent",
  rag_agent: "RAG Agent",
  ace_agent: "ACE Agent",
  full_ace: "Full ACE",
  without_critic: "Without Critic",
  without_evolution: "Without Evolution",
  without_experience_retrieval: "Without Experience Retrieval",
  without_code_agent: "Without Code Agent",
  without_context_manager: "Without Context Manager",
  monolithic_rewrite: "Monolithic Rewrite",
  dynamic_cheatsheet: "Dynamic Cheatsheet",
  ace_grow_and_refine: "ACE Grow-and-Refine",
};

const GROUP_DESCRIPTIONS = {
  all: "展示当前实验的全部任务 Trace 与总体图表。",
  direct_llm: "仅使用大模型直接回答，不调用 GIS 工具，也不使用经验库。",
  react_agent: "使用 Reason + Act 工具调用流程，可调用固定 GIS 工具，但不使用 ACE 经验。",
  codeact_agent: "允许生成并执行受控 GeoPandas / Python 代码，可做有限自修复。",
  ace_webgis: "完整 ACE-WebGIS 闭环：上下文、经验检索、工具/代码执行、诊断与演化。",
  base_agent: "复用主系统工具/代码接口，但不使用历史对话记忆、经验检索和经验写入。",
  rag_agent: "复用主系统工具/代码接口，并启用经验库检索；不把本轮诊断写回经验库。",
  ace_agent: "完整 ACE Agent：上下文记忆、经验检索、工具/代码执行、Critic 诊断和 Evolution 经验写入。",
  full_ace: "完整 ACE 消融基准组，保留 Critic、Evolution、经验检索、CodeAgent 与上下文管理。",
  without_critic: "禁用 CriticAgent，不做结构化错误诊断。",
  without_evolution: "禁用 EvolutionAgent，当次可执行但不沉淀新经验。",
  without_experience_retrieval: "执行时不检索历史经验，观察经验复用缺失影响。",
  without_code_agent: "禁用 CodeAgent，只能使用固定 GIS 工具。",
  without_context_manager: "禁用上下文管理，不使用历史会话上下文。",
  monolithic_rewrite: "每次任务后重写整个经验库，容易遗忘早期经验。",
  dynamic_cheatsheet: "维护动态速查表，持续保留近期规则；容量受限时可能覆盖早期策略。",
  ace_grow_and_refine: "ACE 增量式 grow-and-refine，保留核心技能并合并冗余经验。",
};

const CHART_NOTES = {
  exp1: "柱状图比较 Base Agent、RAG Agent 与 ACE Agent 在习题册/参考答案验证集上的任务成功率。",
  exp2: "折线图展示各 Batch 的成功率变化，对比 BASE 无记忆基线、RAG 静态经验检索与 ACE 连续学习，重点观察 ACE > RAG > BASE 的阶梯差异。",
  exp3: "柱状图比较完整 ACE 与不同消融组的成功率，观察 Critic、Evolution、经验检索、CodeAgent 和上下文管理的贡献。",
  exp4: "两张折线图比较 ACE 与两个对照框架在 100 步连续在线学习中的 context token 数和 accuracy，观察 token 骤降与准确率下降是否同步出现。",
};

const PALETTE = {
  direct_llm: "#94a3b8",
  react_agent: "#d97706",
  codeact_agent: "#7c3aed",
  ace_webgis: "#1769aa",
  base_agent: "#94a3b8",
  rag_agent: "#0f766e",
  ace_agent: "#1769aa",
  full_ace: "#1769aa",
  without_critic: "#dc2626",
  without_evolution: "#f97316",
  without_experience_retrieval: "#9333ea",
  without_code_agent: "#0f766e",
  without_context_manager: "#be123c",
  monolithic_rewrite: "#b91c1c",
  dynamic_cheatsheet: "#7c3aed",
  ace_grow_and_refine: "#1769aa",
};

function formatMetric(value) {
  if (typeof value !== "number") return value ?? "-";
  if (value <= 1) return `${Math.round(value * 100)}%`;
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function average(rows, getter) {
  if (!rows.length) return 0;
  return rows.reduce((sum, row) => sum + Number(getter(row) || 0), 0) / rows.length;
}

function metricValueClass(key, value) {
  if (typeof value !== "number") return "";
  const higherBetter = [
    "task_success_rate",
    "success_rate",
    "repair_success_rate",
    "self_repair_rate",
    "experience_reuse_rate",
    "tool_selection_accuracy",
    "result_correctness",
  ];
  if (higherBetter.includes(key)) {
    if (value >= 0.8) return "metric-value-success";
    if (value >= 0.5) return "metric-value-warning";
    return "metric-value-danger";
  }
  if (key === "error_count") return value <= 2 ? "metric-value-success" : value <= 8 ? "metric-value-warning" : "metric-value-danger";
  return "";
}

function chartColors() {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  return {
    grid: isDark ? "#1e2a41" : "#e2e8f0",
    text: isDark ? "#8b9bb5" : "#64748b",
    accent: isDark ? "#60a5fa" : "#1769aa",
    baseline: isDark ? "#fbbf24" : "#d97706",
  };
}

const Toast = {
  container: null,
  init() {
    if (this.container) return;
    this.container = document.createElement("div");
    this.container.className = "toast-container";
    document.body.appendChild(this.container);
  },
  show(message, type = "info", duration = 3000) {
    this.init();
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span>${message}</span><button class="toast-close" onclick="this.parentElement.remove()">&times;</button>`;
    this.container.appendChild(el);
    requestAnimationFrame(() => el.classList.add("show"));
    setTimeout(() => {
      el.classList.remove("show");
      setTimeout(() => el.remove(), 350);
    }, duration);
  },
};

createApp({
  setup() {
    const selectedExp = ref("exp1");
    const selectedGroup = ref("all");
    const result = ref(null);
    const loading = ref(false);
    const reportLoading = ref(false);
    const includeAiSummary = ref(false);
    const reportLinks = ref({html: "", markdown: ""});
    const experimentRuns = ref([]);
    const reports = ref([]);
    const selectedRunId = ref("");
    const statusMessage = ref("");
    const statusKind = ref("info");
    const selectedTraceIndex = ref(0);
    const mainChart = ref(null);
    const fallbackChart = ref(null);
    const chartInstance = ref(null);
    const chartTitle = ref("指标图表");

    const experiments = computed(() => EXPERIMENTS);
    const runMeta = computed(() => {
      if (!result.value) return "尚未加载";
      return `${result.value.name || result.value.experiment_id} | ${result.value.run_id || ""}`;
    });

    const groupOptions = computed(() => {
      if (!result.value) return [];
      const expId = result.value.experiment_id;
      if (expId === "exp2") {
        return [
          {value: "all", label: "全部"},
          {value: "base_agent", label: "BASE"},
          {value: "rag_agent", label: "RAG"},
          {value: "ace_agent", label: "ACE"},
        ];
      }
      const keys = Object.keys(result.value.groups || {});
      return [{value: "all", label: "全部"}, ...keys.map((key) => ({value: key, label: GROUP_LABELS[key] || key}))];
    });

    const selectedGroupDescription = computed(() => GROUP_DESCRIPTIONS[selectedGroup.value] || "查看该组的指标与任务轨迹。");

    const traces = computed(() => result.value?.traces || []);
    const filteredTraces = computed(() => {
      if (selectedGroup.value === "all") return traces.value;
      return traces.value.filter((trace) => trace.agent_type === selectedGroup.value);
    });

    const selectedTraceText = computed(() => {
      const trace = filteredTraces.value[selectedTraceIndex.value];
      if (!trace) return result.value ? "当前筛选条件下没有任务 Trace。" : "请选择或运行一个实验。";
      return JSON.stringify(trace, null, 2);
    });

    const frameworkEntries = computed(() => {
      if (result.value?.experiment_id !== "exp1") return [];
      return Object.entries(result.value.frameworks || {}).map(([key, item]) => ({
        key,
        name: item.name || key,
        meaning: item.meaning || "",
      }));
    });

    const chartNote = computed(() => CHART_NOTES[result.value?.experiment_id] || "选择实验后查看对应图表说明。");

    const metricCards = computed(() => {
      const pairs = result.value ? metricValues(result.value) : [
        ["success_rate", 0],
        ["average_runtime", 0],
        ["average_turns", 0],
        ["error_count", 0],
        ["repair_success_rate", 0],
        ["experience_reuse_rate", 0],
      ];
      return pairs.map(([key, value]) => ({
        key,
        value,
        label: METRIC_LABELS[key] || key,
        icon: METRIC_ICONS[key] || "◇",
        valueClass: metricValueClass(key, value),
      }));
    });

    function selectedGroupRows(res) {
      if (selectedGroup.value === "all") return res.traces || [];
      return (res.traces || []).filter((trace) => trace.agent_type === selectedGroup.value);
    }

    function selectedGroupSummary(res) {
      if (selectedGroup.value !== "all" && res.groups?.[selectedGroup.value]) return res.groups[selectedGroup.value];
      if (res.experiment_id === "exp3" && res.groups?.full_ace) return res.groups.full_ace;
      if (res.experiment_id === "exp1" && res.groups?.ace_webgis) return res.groups.ace_webgis;
      if (res.experiment_id === "exp1" && res.groups?.ace_agent) return res.groups.ace_agent;
      if (res.experiment_id === "exp4" && res.groups?.ace_grow_and_refine) return res.groups.ace_grow_and_refine;
      const groups = Object.values(res.groups || {});
      return groups[groups.length - 1] || {};
    }

    function metricValues(res) {
      const rows = selectedGroupRows(res);
      if (res.experiment_id === "exp2") {
        const focusGroup = selectedGroup.value === "all" ? "ace_agent" : selectedGroup.value;
        const aceRows = rows.filter((trace) => trace.agent_type === focusGroup);
        const last = (res.batch_metrics || []).at(-1) || {};
        return [
          ["success_rate", selectedGroup.value === "all" ? last.ace_success_rate : average(aceRows, (trace) => trace.success ? 1 : 0)],
          ["average_turns", average(aceRows, (trace) => trace.metrics?.turns || 0)],
          ["repair_success_rate", average(aceRows.filter((trace) => trace.metrics?.repair_attempted), (trace) => trace.metrics?.repair_success ? 1 : 0)],
          ["experience_reuse_rate", average(aceRows, (trace) => (trace.retrieved_experiences || []).length ? 1 : 0)],
          ["error_count", aceRows.filter((trace) => (trace.errors || []).length).length],
          ["average_runtime", average(aceRows, (trace) => trace.metrics?.runtime || 0)],
        ];
      }
      if (res.experiment_id === "exp4") {
        const summary = selectedGroupSummary(res);
        return [
          ["success_rate", summary.final_task_accuracy ?? average(rows, (trace) => trace.success ? 1 : 0)],
          ["final_context_token_count", summary.final_context_token_count ?? average(rows, (trace) => trace.metrics?.context_token_count || 0)],
          ["final_effective_strategy_entry_count", summary.final_effective_strategy_entry_count ?? 0],
          ["final_duplicate_entry_ratio", summary.final_duplicate_entry_ratio ?? 0],
          ["context_sudden_shorten_count", summary.context_sudden_shorten_count ?? 0],
          ["performance_sudden_drop_count", summary.performance_sudden_drop_count ?? 0],
        ];
      }
      const summary = selectedGroupSummary(res);
      return [
        ["task_success_rate", summary.task_success_rate ?? summary.success_rate ?? average(rows, (trace) => trace.success ? 1 : 0)],
        ["tool_selection_accuracy", summary.tool_selection_accuracy ?? summary.correct_tool_chain_rate ?? average(rows, (trace) => (trace.selected_tools || []).length ? 1 : 0)],
        ["average_runtime", summary.average_runtime ?? summary.average_latency ?? average(rows, (trace) => trace.metrics?.runtime || 0)],
        ["average_turns", summary.average_turns ?? average(rows, (trace) => trace.metrics?.turns || 0)],
        ["repair_success_rate", summary.repair_success_rate ?? summary.self_repair_rate ?? average(rows.filter((trace) => trace.metrics?.repair_attempted), (trace) => trace.metrics?.repair_success ? 1 : 0)],
        ["error_count", summary.error_count ?? rows.filter((trace) => (trace.errors || []).length).length],
      ];
    }

    async function requestJson(url, options) {
      let response;
      try {
        response = await fetch(url, options);
      } catch (error) {
        throw new Error("无法连接到后端服务，请确认 GeoAI WebGIS 已启动，并从 http://127.0.0.1:8000/experiment 打开实验界面。");
      }

      let payload = {};
      const text = await response.text();
      if (text) {
        try {
          payload = JSON.parse(text);
        } catch (error) {
          throw new Error(`后端返回了非 JSON 响应：${response.status} ${response.statusText}`);
        }
      }
      if (!response.ok) throw new Error(payload.error || response.statusText);
      return payload;
    }

    async function applyResult(res) {
      clearChart();
      result.value = res;
      selectedRunId.value = res.run_id || "";
      if (res.experiment_id) selectedExp.value = res.experiment_id;
      selectedGroup.value = "all";
      selectedTraceIndex.value = 0;
      reportLinks.value = {
        html: res.report?.html_url || "",
        markdown: res.report?.markdown_url || "",
      };
      scheduleRenderChart();
      await loadReportBank();
    }

    async function loadResult(resultId = null) {
      if (resultId && typeof resultId !== "string") resultId = null;
      loading.value = true;
      statusMessage.value = "正在读取实验结果...";
      statusKind.value = "info";
      try {
        const payload = await requestJson(`/api/experiment/result/${resultId || selectedRunId.value || selectedExp.value}`);
        await applyResult(payload.result);
        await loadExperimentBank();
        statusMessage.value = "";
      } catch (error) {
        result.value = null;
        selectedRunId.value = "";
        reports.value = [];
        clearChart();
        statusKind.value = "error";
        statusMessage.value = `没有可读取的 ${selectedExp.value} 结果，请先运行实验。`;
        Toast.show(`读取失败: ${error.message}`, "error");
        await loadExperimentBank();
      } finally {
        loading.value = false;
      }
    }

    async function switchExperiment(expId) {
      if (selectedExp.value === expId) return;
      selectedExp.value = expId;
      selectedRunId.value = "";
      reportLinks.value = {html: "", markdown: ""};
      await loadResult();
    }

    async function loadExperimentBank() {
      try {
        const payload = await requestJson(`/api/experiment/runs?experiment_id=${encodeURIComponent(selectedExp.value)}`);
        experimentRuns.value = payload.runs || [];
      } catch (error) {
        experimentRuns.value = [];
      }
    }

    async function loadReportBank() {
      const runId = result.value?.run_id || selectedRunId.value;
      if (!runId) {
        reports.value = [];
        return;
      }
      try {
        const payload = await requestJson(`/api/experiment/reports?run_id=${encodeURIComponent(runId)}`);
        reports.value = payload.reports || [];
      } catch (error) {
        reports.value = [];
      }
    }

    async function selectRun(runId) {
      selectedRunId.value = runId;
      await loadResult(runId);
    }

    async function renameRun(run) {
      const nextName = window.prompt("输入新的历史实验名称", run.name || run.run_id);
      if (nextName === null) return;
      try {
        await requestJson("/api/experiment/run/rename", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({run_id: run.run_id, name: nextName}),
        });
        await loadExperimentBank();
        if (result.value?.run_id === run.run_id) result.value.display_name = nextName;
        Toast.show("历史实验已重命名", "success");
      } catch (error) {
        Toast.show(`重命名失败: ${error.message}`, "error");
      }
    }

    async function deleteRun(run) {
      if (!window.confirm(`确认删除历史实验 ${run.run_id}？该 run 的 trace 和报告都会被删除。`)) return;
      try {
        await requestJson("/api/experiment/run/delete", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({run_id: run.run_id}),
        });
        await loadExperimentBank();
        if (result.value?.run_id === run.run_id) {
          result.value = null;
          selectedRunId.value = "";
          reports.value = [];
          clearChart();
        }
        Toast.show("历史实验已删除", "success");
      } catch (error) {
        Toast.show(`删除失败: ${error.message}`, "error");
      }
    }

    async function runExperiment() {
      loading.value = true;
      statusMessage.value = "实验运行中...";
      statusKind.value = "info";
      Toast.show(`实验 ${selectedExp.value} 已启动`, "info");
      try {
        const payload = await requestJson("/api/experiment/run", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({experiment_id: selectedExp.value}),
        });
        await applyResult(payload.result);
        await loadExperimentBank();
        statusMessage.value = "实验已完成，结果已刷新。";
        Toast.show("实验完成", "success");
      } catch (error) {
        statusKind.value = "error";
        statusMessage.value = `实验运行失败：${error.message}`;
        Toast.show(`运行失败: ${error.message}`, "error");
      } finally {
        loading.value = false;
      }
    }

    async function exportReport() {
      if (!result.value) return;
      if (!result.value.run_id) {
        Toast.show("当前结果缺少 run_id，请先从历史实验中重新读取该结果。", "error");
        return;
      }
      reportLoading.value = true;
      statusMessage.value = includeAiSummary.value ? "正在生成报告并调用 DeepSeek 总结..." : "正在生成实验报告...";
      statusKind.value = "info";
      try {
        const payload = await requestJson("/api/experiment/report", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            run_id: result.value.run_id,
            include_ai_summary: includeAiSummary.value,
          }),
        });
        reportLinks.value = {
          html: payload.report.html_url,
          markdown: payload.report.markdown_url,
        };
        result.value.report = payload.report;
        await loadReportBank();
        await loadExperimentBank();
        statusMessage.value = "实验报告已生成，可点击“查看报告”打开 HTML 版。";
        Toast.show("报告已生成", "success");
        window.open(payload.report.html_url, "_blank", "noopener,noreferrer");
      } catch (error) {
        statusKind.value = "error";
        statusMessage.value = `报告生成失败：${error.message}`;
        Toast.show(`报告生成失败: ${error.message}`, "error");
      } finally {
        reportLoading.value = false;
      }
    }

    async function renameReport(report) {
      const nextTitle = window.prompt("输入新的报告名称", report.title || report.report_id);
      if (nextTitle === null) return;
      try {
        await requestJson("/api/experiment/report/rename", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({run_id: report.run_id, title: nextTitle}),
        });
        await loadReportBank();
        Toast.show("报告已重命名", "success");
      } catch (error) {
        Toast.show(`报告重命名失败: ${error.message}`, "error");
      }
    }

    async function deleteReport(report) {
      if (!window.confirm(`确认删除报告 ${report.title}？`)) return;
      try {
        await requestJson("/api/experiment/report/delete", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({run_id: report.run_id, report_id: report.report_id}),
        });
        reportLinks.value = {html: "", markdown: ""};
        if (result.value?.report?.report_id === report.report_id) result.value.report = null;
        await loadReportBank();
        await loadExperimentBank();
        Toast.show("报告已删除", "success");
      } catch (error) {
        Toast.show(`报告删除失败: ${error.message}`, "error");
      }
    }

    function clearChart() {
      if (chartInstance.value) {
        try {
          chartInstance.value.destroy();
        } catch (error) {
          console.warn("Failed to destroy previous experiment chart.", error);
        }
        chartInstance.value = null;
      }
      if (fallbackChart.value) {
        fallbackChart.value.innerHTML = "";
        fallbackChart.value.classList.remove("active");
      }
      const canvas = getChartCanvas();
      if (canvas) {
        canvas.style.display = "";
      }
    }

    function getChartCanvas() {
      if (mainChart.value instanceof HTMLCanvasElement) return mainChart.value;
      return document.querySelector("#experimentApp .chart-container canvas");
    }

    function chartOptions(showLegend, mode = "unit") {
      const colors = chartColors();
      const scales = mode === "tokenAccuracy"
        ? {
            y: {
              min: 0,
              max: 1,
              position: "left",
              grid: {color: colors.grid},
              ticks: {color: colors.text, callback: (value) => `${Math.round(value * 100)}%`},
            },
            yTokens: {
              min: 0,
              position: "right",
              grid: {drawOnChartArea: false},
              ticks: {color: colors.text},
            },
            x: {
              grid: {color: colors.grid},
              ticks: {color: colors.text},
            },
          }
        : {
            y: {
              min: 0,
              max: 1,
              grid: {color: colors.grid},
              ticks: {color: colors.text, callback: (value) => `${Math.round(value * 100)}%`},
            },
            x: {
              grid: {color: colors.grid},
              ticks: {color: colors.text},
            },
          };
      return {
        responsive: true,
        maintainAspectRatio: false,
        scales,
        plugins: {
          legend: {display: showLegend, labels: {color: colors.text}},
          tooltip: {callbacks: {label: (item) => {
            const value = item.dataset.yAxisID === "yTokens" ? Math.round(item.parsed.y) : formatMetric(item.parsed.y);
            return `${item.dataset.label}: ${value}`;
          }}},
        },
      };
    }

    function renderChart() {
      clearChart();
      const canvas = getChartCanvas();
      if (!result.value || !canvas) return;
      const colors = chartColors();
      const expId = result.value.experiment_id;
      let config;

      if (expId === "exp2") {
        const rows = result.value.batch_metrics || [];
        const datasets = [];
        if (selectedGroup.value === "all" || selectedGroup.value === "base_agent") {
          datasets.push({label: "BASE", data: rows.map((row) => row.base_success_rate ?? row.baseline_success_rate), borderColor: colors.baseline, backgroundColor: "rgba(148,163,184,0.18)", tension: 0.3});
        }
        if (selectedGroup.value === "all" || selectedGroup.value === "rag_agent") {
          datasets.push({label: "RAG", data: rows.map((row) => row.rag_success_rate), borderColor: PALETTE.rag_agent, backgroundColor: "rgba(15,118,110,0.18)", tension: 0.3});
        }
        if (selectedGroup.value === "all" || selectedGroup.value === "ace_agent") {
          datasets.push({label: "ACE", data: rows.map((row) => row.ace_success_rate), borderColor: colors.accent, backgroundColor: "rgba(23,105,170,0.18)", tension: 0.3});
        }
        chartTitle.value = "Batch 成功率变化";
        config = {
          type: "line",
          data: {
            labels: rows.map((row) => `Batch ${row.batch_id}`),
            datasets,
          },
          options: chartOptions(true),
        };
      } else if (expId === "exp4") {
        const snapshots = result.value.snapshots || {};
        const visibleSnapshots = selectedGroup.value === "all"
          ? snapshots
          : Object.fromEntries(Object.entries(snapshots).filter(([name]) => name === selectedGroup.value));
        chartTitle.value = "Context token 与 Accuracy";
        config = {
          type: "exp4TwoCharts",
          data: {snapshots: visibleSnapshots},
        };
      } else {
        const groupEntries = Object.entries(result.value.groups || {}).filter(([name]) => selectedGroup.value === "all" || selectedGroup.value === name);
        const values = groupEntries.map(([name, row]) => ({
          name,
          value: row.task_success_rate ?? row.success_rate ?? 0,
        }));
        chartTitle.value = expId === "exp3" ? "消融组成功率" : "不同 Agent 成功率";
        config = {
          type: "bar",
          data: {
            labels: values.map((item) => GROUP_LABELS[item.name] || item.name),
            datasets: [{
              label: "成功率",
              data: values.map((item) => item.value),
              backgroundColor: values.map((item) => PALETTE[item.name] || colors.accent),
              borderRadius: 4,
            }],
          },
          options: chartOptions(false),
        };
      }

      renderFallbackChart(config);
    }

    function scheduleRenderChart() {
      nextTick(() => {
        window.requestAnimationFrame(() => renderChart());
      });
    }

    function renderFallbackChart(config) {
      const canvas = getChartCanvas();
      if (!fallbackChart.value || !canvas) return;
      canvas.style.display = "none";
      fallbackChart.value.classList.add("active");
      fallbackChart.value.innerHTML = config.type === "exp4TwoCharts"
        ? fallbackExp4Charts(config.data.snapshots || {})
        : config.type === "line"
        ? fallbackLineChart(config.data)
        : fallbackBarChart(config.data);
    }

    function fallbackExp4Charts(snapshots) {
      const labels = (Object.values(snapshots)[0] || []).map((row) => `${row.step}`);
      const tokenSeries = Object.entries(snapshots).map(([name, rows]) => ({
        label: GROUP_LABELS[name] || name,
        data: rows.map((row) => row.context_token_count),
        borderColor: PALETTE[name] || chartColors().accent,
      }));
      const accuracySeries = Object.entries(snapshots).map(([name, rows]) => ({
        label: GROUP_LABELS[name] || name,
        data: rows.map((row) => row.task_accuracy),
        borderColor: PALETTE[name] || chartColors().accent,
      }));
      return `
        <div class="exp4-chart-stack">
          <section>
            <h3>Context token 数</h3>
            ${fallbackLineChart({labels, datasets: tokenSeries}, {unit: "number"})}
          </section>
          <section>
            <h3>Accuracy</h3>
            ${fallbackLineChart({labels, datasets: accuracySeries}, {unit: "percent"})}
          </section>
        </div>
      `;
    }

    function fallbackLineChart(data, options = {}) {
      const width = 720;
      const height = 320;
      const left = 54;
      const right = 22;
      const top = 26;
      const bottom = 54;
      const plotW = width - left - right;
      const plotH = height - top - bottom;
      const labels = data.labels || [];
      const datasets = data.datasets || [];
      const allValues = datasets.flatMap((set) => set.data || []).map((value) => Number(value || 0));
      const unit = options.unit || "percent";
      const maxValue = unit === "percent" ? 1 : Math.max(1, ...allValues);
      const minValue = 0;
      const x = (index) => left + (labels.length <= 1 ? plotW / 2 : (plotW * index) / (labels.length - 1));
      const y = (value) => {
        const bounded = Math.max(minValue, Math.min(maxValue, Number(value || 0)));
        return top + plotH - ((bounded - minValue) / (maxValue - minValue || 1)) * plotH;
      };
      const ticks = unit === "percent"
        ? [0, 0.25, 0.5, 0.75, 1]
        : [0, 0.25, 0.5, 0.75, 1].map((ratio) => Math.round(maxValue * ratio));
      const grid = ticks.map((tick) => {
        const yy = y(tick);
        const label = unit === "percent" ? `${Math.round(tick * 100)}%` : String(tick);
        return `<line x1="${left}" y1="${yy}" x2="${width - right}" y2="${yy}" stroke="currentColor" opacity="0.12"/><text x="${left - 10}" y="${yy + 4}" text-anchor="end">${label}</text>`;
      }).join("");
      const series = datasets.map((set) => {
        const points = (set.data || []).map((value, index) => `${x(index)},${y(value)}`).join(" ");
        return `<polyline fill="none" stroke="${escapeAttr(set.borderColor || '#1769aa')}" stroke-width="3" points="${points}"/>`;
      }).join("");
      const xLabels = labels.map((label, index) => {
        const step = Number(label);
        return Number.isFinite(step) && step % 10 === 0 ? `<text x="${x(index)}" y="${height - 24}" text-anchor="middle">${escapeHtml(label)}</text>` : "";
      }).join("");
      const legend = datasets.map((set, index) => `<g transform="translate(${left + index * 120},12)"><rect width="12" height="12" rx="2" fill="${escapeAttr(set.borderColor || '#1769aa')}"/><text x="18" y="11">${escapeHtml(set.label || '')}</text></g>`).join("");
      return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="experiment line chart">${legend}<g>${grid}</g>${series}${xLabels}</svg>`;
    }

    function fallbackBarChart(data) {
      const width = 720;
      const height = 320;
      const left = 54;
      const right = 22;
      const top = 26;
      const bottom = 62;
      const plotW = width - left - right;
      const plotH = height - top - bottom;
      const labels = data.labels || [];
      const set = (data.datasets || [])[0] || {};
      const values = set.data || [];
      const colors = set.backgroundColor || [];
      const y = (value) => top + plotH - Math.max(0, Math.min(1, Number(value || 0))) * plotH;
      const barW = labels.length ? Math.min(72, plotW / labels.length * 0.58) : 0;
      const grid = [0, 0.25, 0.5, 0.75, 1].map((tick) => {
        const yy = y(tick);
        return `<line x1="${left}" y1="${yy}" x2="${width - right}" y2="${yy}" stroke="currentColor" opacity="0.12"/><text x="${left - 10}" y="${yy + 4}" text-anchor="end">${Math.round(tick * 100)}%</text>`;
      }).join("");
      const bars = labels.map((label, index) => {
        const cx = left + (plotW * (index + 0.5)) / labels.length;
        const yy = y(values[index]);
        const h = top + plotH - yy;
        const color = Array.isArray(colors) ? colors[index] : colors;
        return `<rect x="${cx - barW / 2}" y="${yy}" width="${barW}" height="${h}" rx="4" fill="${escapeAttr(color || '#1769aa')}"/><text x="${cx}" y="${yy - 8}" text-anchor="middle">${Math.round(Number(values[index] || 0) * 100)}%</text><text x="${cx}" y="${height - 28}" text-anchor="middle">${escapeHtml(label)}</text>`;
      }).join("");
      return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="experiment bar chart"><g>${grid}</g>${bars}</svg>`;
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[char]));
    }

    function escapeAttr(value) {
      return escapeHtml(value);
    }

    onMounted(() => {
      loadResult();
      const observer = new MutationObserver(() => {
        if (result.value) scheduleRenderChart();
      });
      observer.observe(document.documentElement, {attributes: true, attributeFilter: ["data-theme"]});
    });

    watch(selectedGroup, () => {
      selectedTraceIndex.value = 0;
      scheduleRenderChart();
    });

    watch(result, () => {
      scheduleRenderChart();
    });

    return {
      experiments,
      selectedExp,
      selectedGroup,
      result,
      loading,
      reportLoading,
      includeAiSummary,
      reportLinks,
      experimentRuns,
      reports,
      selectedRunId,
      statusMessage,
      statusKind,
      selectedTraceIndex,
      mainChart,
      fallbackChart,
      chartTitle,
      runMeta,
      traces,
      filteredTraces,
      selectedTraceText,
      frameworkEntries,
      chartNote,
      groupOptions,
      selectedGroupDescription,
      metricCards,
      formatMetric,
      loadResult,
      switchExperiment,
      selectRun,
      renameRun,
      deleteRun,
      runExperiment,
      exportReport,
      renameReport,
      deleteReport,
    };
  },
}).mount("#experimentApp");
