/* ===================================================
   GeoAI 对比实验系统 — 实验一前端逻辑
   负责：数据获取、图表渲染、运行控制、状态管理
   =================================================== */

// 注册 Chart.js datalabels 插件（如可用）
if (typeof ChartDataLabels !== 'undefined') {
  try { Chart.register(ChartDataLabels); } catch (e) { /* ignore */ }
}

// —————————————————————————————————————————————
// 1. 全局状态
// —————————————————————————————————————————————
const STATE = {
  data: null,           // 最新实验结果
  suite: null,          // 测试套件定义
  charts: {},           // 已创建的 Chart 实例 { radar, bar, heatmap, time }
  pollingTimer: null,   // 轮询定时器
  running: false,       // 实验是否正在运行
  selectedRunDir: '',    // 当前正在展示的历史实验目录
  exp2Data: null,
  exp2SelectedRunDir: '',
  exp2Running: false,
  exp3Data: null,
  exp3SelectedRunDir: '',
  exp3Running: false,
  exp4Data: null,
  exp4SelectedRunDir: '',
  exp4Running: false,
  thesisEvidence: null,
};

// —————————————————————————————————————————————
// 2. 页面加载入口
// —————————————————————————————————————————————
document.addEventListener('DOMContentLoaded', function () {
  // Tab 切换逻辑（保持原样）
  const tabBtns = document.querySelectorAll('.exp-tab-btn');
  const panels = {
    exp1: document.getElementById('exp1'),
    exp2: document.getElementById('exp2'),
    exp3: document.getElementById('exp3'),
    exp4: document.getElementById('exp4'),
    thesis: document.getElementById('thesis'),
  };
  tabBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabBtns.forEach(function (b) { b.classList.remove('active'); });
      this.classList.add('active');
      Object.values(panels).forEach(function (p) { p.classList.remove('active'); });
      const targetId = this.getAttribute('data-tab');
      if (panels[targetId]) panels[targetId].classList.add('active');
    });
  });

  // 实验一：运行按钮
  document.getElementById('exp1-run-btn').addEventListener('click', runExperiment1);
  document.getElementById('exp2-run-btn').addEventListener('click', runExperiment2);
  document.getElementById('exp3-run-btn').addEventListener('click', runExperiment3);
  document.getElementById('exp4-run-btn').addEventListener('click', runExperiment4);
  document.getElementById('exp1-export-btn').addEventListener('click', function () {
    exportExperimentData('exp1', STATE.selectedRunDir);
  });
  document.getElementById('exp2-export-btn').addEventListener('click', function () {
    exportExperimentData('exp2', STATE.exp2SelectedRunDir);
  });
  document.getElementById('exp3-export-btn').addEventListener('click', function () {
    exportExperimentData('exp3', STATE.exp3SelectedRunDir);
  });
  document.getElementById('exp4-export-btn').addEventListener('click', function () {
    exportExperimentData('exp4', STATE.exp4SelectedRunDir);
  });
  document.getElementById('thesis-refresh-btn').addEventListener('click', fetchThesisEvidence);
  document.getElementById('thesis-download-btn').addEventListener('click', downloadThesisEvidence);

  // 首次加载实验数据 + 经验库列表 + 历史记录
  fetchExperiment1Data();
  fetchExperienceBanks();
  fetchExperimentHistory();
  fetchExperiment2Data();
  fetchExperiment2History();
  fetchExperiment3Data();
  fetchExperiment3History();
  fetchExperiment4Data();
  fetchExperiment4History();
  fetchThesisEvidence();
});

// —————————————————————————————————————————————
// 3. 获取实验数据
// —————————————————————————————————————————————
async function fetchExperiment1Data() {
  showLoading(true);
  try {
    const data = await fetchJson('/api/experiment/exp1/data');

    // 检查是否为空状态
    if (data.status === 'no_data') {
      STATE.data = null;
      STATE.suite = data.test_suite || null;
      showEmpty(true);
      showLoading(false);
      return;
    }

    // 检查是否有错误
    if (data.status === 'error') {
      showError(data.error || '未知错误');
      showLoading(false);
      return;
    }

    STATE.data = data;
    STATE.selectedRunDir = data.run_dir || '';
    STATE.suite = null;
    renderExperiment1(data);
    showLoading(false);
    showEmpty(false);
  } catch (err) {
    console.error('获取实验数据失败:', err);
    showError(err.message || '网络错误，无法加载实验数据');
    showLoading(false);
  }
}

// —————————————————————————————————————————————
// 3b. 获取经验库列表
// —————————————————————————————————————————————
async function fetchExperienceBanks() {
  try {
    const data = await fetchJson('/api/experience-banks');
    const select = document.getElementById('exp1-bank-select');
    if (!select) return;
    // 保留第一个 "实验预设" 选项
    select.innerHTML = '<option value="default">实验预设</option>';
    if (data.banks && Array.isArray(data.banks)) {
      data.banks.forEach(function (bank) {
        if (bank.id === 'default') return; // 预设已在上方
        const opt = document.createElement('option');
        opt.value = bank.id;
        opt.textContent = bank.name + (bank.read_only ? ' 🔒' : '');
        if (bank.id === data.active?.id) opt.selected = true;
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.warn('获取经验库列表失败:', err);
  }
}

// —————————————————————————————————————————————
// 3c. 获取历史实验记录
// —————————————————————————————————————————————
async function fetchExperimentHistory() {
  try {
    const data = await fetchJson('/api/experiment/exp1/results');
    renderHistoryTable(data.runs || []);
  } catch (err) {
    console.warn('获取历史记录失败:', err);
  }
}

function renderHistoryTable(runs) {
  const tbody = document.getElementById('exp1-history-tbody');
  if (!tbody) return;
  if (!runs || runs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#94a3b8;">暂无历史实验记录</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  runs.forEach(function (run) {
    const tr = document.createElement('tr');
    const runDir = run.run_dir || '';
    const base = run.base || {};
    const ace = run.ace || {};
    // 优先使用 ACE 数据，否则用 Base（兼容 single-mode 遗留记录）
    const compRate = ace.task_completion_rate != null ? ace.task_completion_rate : base.task_completion_rate || 0;
    const accRate = ace.accuracy_rate != null ? ace.accuracy_rate : base.accuracy_rate || 0;
    const toolRate = ace.tool_success_rate != null ? ace.tool_success_rate : base.tool_success_rate || 0;
    const name = run.run_name || '未知';

    tr.className = runDir === STATE.selectedRunDir ? 'history-row active' : 'history-row';
    tr.title = '点击查看该次实验数据';
    tr.addEventListener('click', function () {
      loadHistoryRun(runDir);
    });

    const nameCell = document.createElement('td');
    nameCell.className = 'history-name-cell';
    nameCell.title = runDir;
    nameCell.textContent = name;

    const compCell = document.createElement('td');
    compCell.textContent = compRate.toFixed(1) + '%';

    const accCell = document.createElement('td');
    accCell.textContent = accRate.toFixed(1) + '%';

    const toolCell = document.createElement('td');
    toolCell.textContent = toolRate.toFixed(1) + '%';

    const actionsCell = document.createElement('td');
    actionsCell.className = 'history-actions';

    const viewBtn = document.createElement('button');
    viewBtn.className = 'exp-btn-sm';
    viewBtn.type = 'button';
    viewBtn.title = '查看';
    viewBtn.textContent = '查看';
    viewBtn.addEventListener('click', function (event) {
      event.stopPropagation();
      loadHistoryRun(runDir);
    });

    const renameBtn = document.createElement('button');
    renameBtn.className = 'exp-btn-sm';
    renameBtn.type = 'button';
    renameBtn.title = '重命名';
    renameBtn.textContent = '重命名';
    renameBtn.addEventListener('click', function (event) {
      event.stopPropagation();
      renameHistory(runDir, name);
    });

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'exp-btn-sm danger';
    deleteBtn.type = 'button';
    deleteBtn.title = '删除';
    deleteBtn.textContent = '删除';
    deleteBtn.addEventListener('click', function (event) {
      event.stopPropagation();
      deleteHistory(runDir);
    });

    actionsCell.append(viewBtn, renameBtn, deleteBtn);
    tr.append(nameCell, compCell, accCell, toolCell, actionsCell);
    tbody.appendChild(tr);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

async function fetchThesisEvidence() {
  const status = document.getElementById('thesis-status');
  if (status) status.textContent = '正在生成证据包...';
  try {
    const data = await fetchJson('/api/thesis/evidence');
    STATE.thesisEvidence = data;
    renderThesisEvidence(data);
    if (status) status.textContent = '已更新';
  } catch (err) {
    console.error('获取论文证据失败:', err);
    if (status) status.textContent = '加载失败：' + err.message;
  }
}

function renderThesisEvidence(data) {
  document.getElementById('thesis-generated-at').textContent = data.generated_at ? '生成时间：' + data.generated_at : '';
  renderThesisReadiness(data.readiness || {});
  renderThesisBenchmark(data.benchmark_alignment || {});
  renderThesisBaseline(data.baseline_comparison || {});
  renderThesisExperience(data.experience_analysis || {});
  renderThesisCodeEvolution(data.code_evolution || {});
  renderThesisAblation(data.ablation_summary || {}, data.missing_items || []);
}

function renderThesisReadiness(readiness) {
  document.getElementById('thesis-readiness-score').textContent = (readiness.score ?? 0).toFixed(1) + '%';
  const box = document.getElementById('thesis-readiness-checks');
  box.innerHTML = (readiness.checks || []).map(function (item) {
    return '<div class="thesis-check ' + (item.completed ? 'ok' : 'todo') + '">' +
      '<span>' + (item.completed ? '✓' : '!') + '</span>' +
      escapeHtml(item.name) +
      '</div>';
  }).join('');
}

function renderThesisBenchmark(alignment) {
  const tbody = document.getElementById('thesis-benchmark-tbody');
  tbody.innerHTML = (alignment.rows || []).map(function (row) {
    return '<tr>' +
      '<td><span class="tag">' + escapeHtml(row.label) + '</span></td>' +
      '<td>' + escapeHtml(row.geoanalyst_dimension) + '</td>' +
      '<td>' + row.task_count + '</td>' +
      '<td>' + (row.gap ? '<span class="tag orange">缺 ' + row.gap + '</span>' : '<span class="tag green">已覆盖</span>') + '</td>' +
      '</tr>';
  }).join('') || '<tr><td colspan="4" style="text-align:center;color:#94a3b8;">暂无实验一任务数据</td></tr>';
}

function renderThesisBaseline(comparison) {
  const tbody = document.getElementById('thesis-baseline-tbody');
  tbody.innerHTML = (comparison.rows || []).map(function (row) {
    const base = row.base == null ? '-' : row.base.toFixed(1) + '%';
    const ace = row.ace == null ? '-' : row.ace.toFixed(1) + '%';
    const delta = row.delta == null ? '-' : (row.delta >= 0 ? '+' : '') + row.delta.toFixed(1) + '%';
    return '<tr>' +
      '<td class="metric-name">' + escapeHtml(row.label) + '</td>' +
      '<td>' + base + '</td>' +
      '<td>' + ace + '</td>' +
      '<td>' + delta + '</td>' +
      '</tr>';
  }).join('') || '<tr><td colspan="4" style="text-align:center;color:#94a3b8;">请先运行实验一 both 模式</td></tr>';
}

function renderThesisExperience(analysis) {
  const categories = document.getElementById('thesis-category-list');
  categories.innerHTML = (analysis.category_counts || []).map(function (item) {
    return '<div class="thesis-list-item"><strong>' + escapeHtml(item.category) + '</strong><span>' + item.count + ' 条</span></div>';
  }).join('') || '<div class="thesis-list-empty">暂无经验库数据</div>';

  const top = document.getElementById('thesis-top-experience-list');
  top.innerHTML = (analysis.top_experiences || []).slice(0, 8).map(function (item) {
    return '<div class="thesis-list-item vertical">' +
      '<strong>' + escapeHtml(item.category || item.id) + ' · confidence=' + item.confidence.toFixed(2) + '</strong>' +
      '<span>' + escapeHtml(item.strategy || '') + '</span>' +
      '</div>';
  }).join('') || '<div class="thesis-list-empty">暂无高置信经验</div>';
}

function renderThesisCodeEvolution(evolution) {
  const box = document.getElementById('thesis-code-list');
  box.innerHTML = (evolution.items || []).slice(0, 10).map(function (item) {
    return '<div class="thesis-list-item vertical">' +
      '<strong>#' + escapeHtml(item.task_id) + ' · ' + escapeHtml(item.mode) + ' · ' + escapeHtml(item.stage) + '</strong>' +
      '<span>' + escapeHtml(item.task || '') + '</span>' +
      '<small>' + escapeHtml(item.answer_preview || item.error || '') + '</small>' +
      '</div>';
  }).join('') || '<div class="thesis-list-empty">暂无代码演化样例；建议运行包含 execute_spatial_code 的实验一任务。</div>';
}

function renderThesisAblation(ablation, missingItems) {
  const contributions = ablation.module_ablation?.contributions || [];
  document.getElementById('thesis-ablation-list').innerHTML = contributions.map(function (item, idx) {
    return '<div class="thesis-list-item"><strong>' + (idx + 1) + '. ' + escapeHtml(item.module) + '</strong><span>贡献分 ' + item.contribution_score + '</span></div>';
  }).join('') || '<div class="thesis-list-empty">请先运行实验二消融实验</div>';

  document.getElementById('thesis-missing-list').innerHTML = (missingItems || []).map(function (text) {
    return '<div class="thesis-list-item vertical warn"><strong>待补充</strong><span>' + escapeHtml(text) + '</span></div>';
  }).join('') || '<div class="thesis-list-item"><strong>当前证据包完整</strong><span>可进入论文整理阶段</span></div>';
}

function downloadThesisEvidence() {
  if (!STATE.thesisEvidence) return;
  const blob = new Blob([JSON.stringify(STATE.thesisEvidence, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'thesis_evidence.json';
  link.click();
  URL.revokeObjectURL(url);
}

async function loadHistoryRun(runDir) {
  if (!runDir) return;
  showLoading(true);
  showError(null);
  try {
    const params = new URLSearchParams({ run_dir: runDir });
    const data = await fetchJson('/api/experiment/exp1/data?' + params.toString());
    STATE.data = data;
    STATE.selectedRunDir = data.run_dir || runDir;
    renderExperiment1(data);
    showLoading(false);
    showEmpty(false);
    updateStatus('done', '已加载历史实验：' + (data.run_name || STATE.selectedRunDir));
    fetchExperimentHistory();
  } catch (err) {
    showLoading(false);
    showError('加载历史实验失败: ' + err.message);
  }
}

async function renameHistory(runDir, currentName) {
  const newName = prompt('请输入新的实验名称：', currentName || '');
  if (!newName || !newName.trim()) return;
  try {
    await fetchJson('/api/experiment/exp1/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir, name: newName.trim() }),
    });
    if (STATE.selectedRunDir === runDir && STATE.data) {
      STATE.data.run_name = newName.trim().slice(0, 60);
      renderExperiment1(STATE.data);
    }
    await fetchExperimentHistory();
    updateStatus('done', '已重命名历史实验。');
  } catch (err) {
    alert('重命名失败: ' + err.message);
  }
}

async function deleteHistory(runDir) {
  if (!confirm('确定要删除此实验记录吗？\n此操作不可恢复。')) return;
  try {
    await fetchJson('/api/experiment/exp1/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir }),
    });
    await fetchExperimentHistory();
    if (STATE.selectedRunDir === runDir) {
      STATE.selectedRunDir = '';
      await fetchExperiment1Data();
    }
    updateStatus('done', '已删除历史实验。');
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}

// —————————————————————————————————————————————
// 4. 渲染实验一结果
// —————————————————————————————————————————————
function renderExperiment1(data) {
  if (!data) return;
  showError(null);

  // 4a. 填充统计摘要卡片
  populateStatCards(data);

  // 4b. 更新最近运行时间
  const lastRunEl = document.getElementById('exp1-last-run');
  if (data.run_name) {
    lastRunEl.textContent = '当前显示: ' + data.run_name;
  } else if (data.timestamp) {
    const t = new Date(data.timestamp);
    lastRunEl.textContent = '上次运行: ' + t.toLocaleString('zh-CN');
  }

  // 4c. 渲染图表
  renderRadarChart(data);
  renderBarChart(data);
  renderHeatmap(data);
  renderTimeChart(data);

  // 4d. 可选：更新任务详情表
  updateTaskDetails(data);
}

// —————————————————————————————————————————————
// 5. 统计摘要卡片
// —————————————————————————————————————————————
function populateStatCards(data) {
  const base = data.base || {};
  const ace = data.ace || {};
  const impr = data.improvements || {};

  // 任务完成率提升
  const compImp = impr.task_completion_rate_pct;
  setStatCard(0, base.task_completion_rate, ace.task_completion_rate, compImp, '%', true);

  // 准确率提升
  const accImp = impr.accuracy_rate_pct;
  setStatCard(1, base.accuracy_rate, ace.accuracy_rate, accImp, '%', true);

  // 错误恢复率（ACE 特有）
  const recoveryRate = ace.error_recovery_rate || 0;
  setStatCard(2, 0, recoveryRate, null, '%', false);
}

function setStatCard(index, baseVal, aceVal, improvement, unit, higherIsBetter, reverseDirection) {
  const cards = document.querySelectorAll('.stat-card');
  if (!cards[index]) return;

  const valueEl = cards[index].querySelector('.stat-value');
  const labelEl = cards[index].querySelector('.stat-label');
  const compareEl = cards[index].querySelector('.stat-compare');

  if (!valueEl || !compareEl) return;

  // 格式化数字
  const fmtBase = (baseVal != null && !isNaN(baseVal)) ? baseVal.toFixed(1) + unit : '--' + unit;
  const fmtAce = (aceVal != null && !isNaN(aceVal)) ? aceVal.toFixed(1) + unit : '--' + unit;

  // 比较文本
  compareEl.innerHTML = '<span>Base: ' + fmtBase + '</span><span>ACE: ' + fmtAce + '</span>';

  // 提升值
  if (improvement != null) {
    let deltaClass = 'delta up';
    let arrow = '▲';
    let displayVal = '';

    if (reverseDirection) {
      // 反向指标（时间）：越低越好
      if (improvement > 0) { deltaClass = 'delta down'; arrow = '▼'; } // ACE更快
      else if (improvement < 0) { deltaClass = 'delta up'; arrow = '▲'; } // Base更快
      displayVal = Math.abs(improvement).toFixed(1) + 's';
    } else if (higherIsBetter) {
      displayVal = (improvement >= 0 ? '+' : '') + improvement.toFixed(1) + '%';
      if (improvement < 0) { deltaClass = 'delta down'; arrow = '▼'; }
    } else {
      displayVal = improvement.toFixed(1) + '%';
      arrow = '◆';
    }

    valueEl.innerHTML = displayVal + ' <span class="' + deltaClass + '">' + arrow + '</span>';
    valueEl.title = 'Base: ' + fmtBase + ' | ACE: ' + fmtAce;
  } else {
    // 无比较（如ACE独有的错误恢复率）
    const rateVal = (aceVal != null && !isNaN(aceVal)) ? aceVal.toFixed(1) + '%' : '--%';
    valueEl.innerHTML = rateVal;
  }
}

// —————————————————————————————————————————————
// 6. 雷达图
// —————————————————————————————————————————————
function renderRadarChart(data) {
  const canvas = document.getElementById('chart-radar');
  if (!canvas) return;

  // Destroy previous
  if (STATE.charts.radar) { STATE.charts.radar.destroy(); }

  const base = data.base || {};
  const ace = data.ace || {};

  // 维度定义（只取两者共有的指标）
  const dimensions = [
    { key: 'task_completion_rate', label: '任务完成率' },
    { key: 'tool_success_rate', label: '工具成功率' },
    { key: 'code_success_rate', label: '代码成功率' },
    { key: 'accuracy_rate', label: '结果准确率' },
    { key: 'experience_hit_rate', label: '经验命中率' },
    { key: 'error_recovery_rate', label: '错误恢复率' },
  ];

  const baseValues = dimensions.map(d => {
    return base[d.key] != null ? base[d.key] : 0;
  });
  const aceValues = dimensions.map(d => {
    return ace[d.key] != null ? ace[d.key] : 0;
  });

  STATE.charts.radar = new Chart(canvas, {
    type: 'radar',
    data: {
      labels: dimensions.map(d => d.label),
      datasets: [
        {
          label: 'Base LLM',
          data: baseValues,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239,68,68,0.12)',
          borderWidth: 2,
          pointBackgroundColor: '#ef4444',
          pointRadius: 3,
        },
        {
          label: 'ACE 增强',
          data: aceValues,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,0.12)',
          borderWidth: 2,
          pointBackgroundColor: '#22c55e',
          pointRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 12 }, padding: 16 } },
        datalabels: { display: false },
      },
      scales: {
        r: {
          beginAtZero: true,
          max: 100,
          ticks: { stepSize: 20, font: { size: 10 }, backdropColor: 'transparent' },
          grid: { color: 'rgba(148,163,184,0.2)' },
          angleLines: { color: 'rgba(148,163,184,0.2)' },
          pointLabels: { font: { size: 11, weight: 'bold' }, color: '#334155' },
        },
      },
    },
  });
}

// —————————————————————————————————————————————
// 7. 柱状图
// —————————————————————————————————————————————
function renderBarChart(data) {
  const canvas = document.getElementById('chart-bar');
  if (!canvas) return;

  if (STATE.charts.bar) { STATE.charts.bar.destroy(); }

  const base = data.base || {};
  const ace = data.ace || {};
  const impr = data.improvements || {};

  const metrics = [
    { key: 'task_completion_rate', label: '任务完成率' },
    { key: 'tool_success_rate', label: '工具成功率' },
    { key: 'code_success_rate', label: '代码成功率' },
    { key: 'accuracy_rate', label: '结果准确率' },
  ];

  const labels = metrics.map(m => m.label);
  const baseData = metrics.map(m => base[m.key] || 0);
  const aceData = metrics.map(m => ace[m.key] || 0);
  const imprData = metrics.map(m => {
    const pctKey = m.key + '_pct';
    return impr[pctKey] != null ? impr[pctKey] : 0;
  });

  STATE.charts.bar = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Base LLM',
          data: baseData,
          backgroundColor: 'rgba(239,68,68,0.7)',
          borderColor: '#ef4444',
          borderWidth: 1,
          borderRadius: 4,
        },
        {
          label: 'ACE 增强',
          data: aceData,
          backgroundColor: 'rgba(34,197,94,0.7)',
          borderColor: '#22c55e',
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      layout: {
        padding: { top: 24 },
      },
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 12 }, padding: 16 } },
        datalabels: {
          anchor: 'end',
          align: 'end',
          clamp: true,
          color: '#1e293b',
          font: { size: 9, weight: 'bold' },
          formatter: function (value, ctx) {
            const idx = ctx.dataIndex;
            const imp = imprData[idx];
            if (imp === 0) return value.toFixed(1) + '%';
            return value.toFixed(1) + '%  +' + imp.toFixed(1) + '%';
          },
          offset: 4,
        },
      },
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' }, afterFit: ctx => { ctx.height += 8; } },
      },
    },
  });
}

// —————————————————————————————————————————————
// 8. 热力图（任务级矩阵）
// —————————————————————————————————————————————
function renderHeatmap(data) {
  const canvas = document.getElementById('chart-heatmap');
  if (!canvas) return;

  if (STATE.charts.heatmap) { STATE.charts.heatmap.destroy(); }

  const details = data.task_details || [];
  if (details.length === 0) {
    // 无详细数据时显示占位文本
    const parent = canvas.parentElement;
    if (parent) {
      parent.innerHTML = '<div class="chart-placeholder" style="grid-column:1/-1;">'
        + '<div class="chart-icon">📋</div>'
        + '<div class="chart-label">任务级详情</div>'
        + '<div class="chart-hint">运行实验后可查看每个任务的详细通过状态</div>'
        + '</div>';
    }
    return;
  }

  // 按 task_id 分组成 Base 和 ACE
  const baseDetails = details.filter(d => d.mode === 'base');
  const aceDetails = details.filter(d => d.mode === 'ace');
  // 按 task_id 排序
  baseDetails.sort((a, b) => a.task_id - b.task_id);
  aceDetails.sort((a, b) => a.task_id - b.task_id);

  const taskIds = baseDetails.length > 0
    ? baseDetails.map(d => '#' + d.task_id)
    : aceDetails.map(d => '#' + d.task_id);

  const metrics = [
    { key: 'task_completed', label: '完成' },
    { key: 'tool_success', label: '工具' },
    { key: 'code_success', label: '代码' },
    { key: 'accuracy', label: '准确' },
  ];

  // 为 Base 和 ACE 分别构建矩阵数据
  const getData = (records) => {
    return metrics.map(metric => {
      return taskIds.map((_, i) => {
        const rec = records[i];
        return rec && rec[metric.key] ? 100 : 0;
      });
    });
  };

  const baseMatrix = getData(baseDetails);
  const aceMatrix = getData(aceDetails);

  // 用两个堆叠的 heatmap 表示（使用 matrix 插件或者手动绘制）
  // 由于 Chart.js 无原生 heatmap，我们用 grouped bar + 透明度模拟
  // 每个任务画两个 bar（Base/ACE），每种指标画一组
  // 更简单：绘制一个自定义矩阵，使用 canvas 2D
  drawHeatmapCanvas(canvas, baseMatrix, aceMatrix, metrics, taskIds);
}

function drawHeatmapCanvas(canvas, baseMatrix, aceMatrix, metrics, taskIds) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  const parent = canvas.parentElement;
  const w = parent ? parent.clientWidth : 600;
  const h = 340;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + 'px';
  canvas.style.height = h + 'px';
  ctx.scale(dpr, dpr);

  const pad = { top: 30, right: 16, bottom: 40, left: 60 };
  const headerH = 22;
  const legendW = 40;

  const rows = metrics.length;
  const cols = taskIds.length * 2; // Base + ACE per task

  const cellW = Math.max(12, (w - pad.left - pad.right - legendW) / cols);
  const cellH = Math.min(36, (h - pad.top - pad.bottom - headerH) / rows);

  const drawStartX = pad.left;
  const drawStartY = pad.top + headerH;

  // 清空
  ctx.clearRect(0, 0, w, h);

  // 绘制行标签（指标）
  ctx.font = '11px system-ui, sans-serif';
  ctx.fillStyle = '#475569';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  metrics.forEach((m, ri) => {
    ctx.fillText(m.label, pad.left - 8, drawStartY + ri * cellH + cellH / 2);
  });

  // 绘制列标签（任务ID + 模式）
  ctx.font = '9px system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  const colLabelY = pad.top;
  taskIds.forEach((tid, ci) => {
    const cx = drawStartX + ci * 2 * cellW + cellW;
    ctx.fillStyle = '#ef4444';
    ctx.fillText('B', cx - cellW / 2, colLabelY);
    ctx.fillStyle = '#22c55e';
    ctx.fillText('A', cx + cellW / 2, colLabelY);
    // 任务编号在更下方
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(tid, drawStartX + ci * 2 * cellW + cellW, colLabelY + 10);
  });

  // 绘制单元格
  const colors = [
    { pass: 'rgba(22,163,74,0.8)', fail: 'rgba(239,68,68,0.15)' },
    { pass: 'rgba(22,163,74,0.7)', fail: 'rgba(239,68,68,0.12)' },
  ];

  // Base 列
  metrics.forEach((m, ri) => {
    taskIds.forEach((_, ci) => {
      const val = baseMatrix[ri][ci];
      const x = drawStartX + ci * 2 * cellW;
      const y = drawStartY + ri * cellH;
      ctx.fillStyle = val >= 100 ? colors[0].pass : colors[0].fail;
      ctx.fillRect(x, y, cellW - 1, cellH - 1);
      if (val >= 100) {
        ctx.fillStyle = '#fff';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('✓', x + cellW / 2, y + cellH / 2);
      }
    });
  });

  // ACE 列
  metrics.forEach((m, ri) => {
    taskIds.forEach((_, ci) => {
      const val = aceMatrix[ri][ci];
      const x = drawStartX + ci * 2 * cellW + cellW;
      const y = drawStartY + ri * cellH;
      ctx.fillStyle = val >= 100 ? colors[1].pass : colors[1].fail;
      ctx.fillRect(x, y, cellW - 1, cellH - 1);
      if (val >= 100) {
        ctx.fillStyle = '#fff';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('✓', x + cellW / 2, y + cellH / 2);
      }
    });
  });

  // 网格线
  ctx.strokeStyle = 'rgba(255,255,255,0.4)';
  ctx.lineWidth = 0.5;
  for (let ri = 0; ri <= rows; ri++) {
    ctx.beginPath();
    ctx.moveTo(drawStartX, drawStartY + ri * cellH);
    ctx.lineTo(drawStartX + cols * cellW, drawStartY + ri * cellH);
    ctx.stroke();
  }
  for (let ci = 0; ci <= cols; ci++) {
    ctx.beginPath();
    ctx.moveTo(drawStartX + ci * cellW, drawStartY);
    ctx.lineTo(drawStartX + ci * cellW, drawStartY + rows * cellH);
    ctx.stroke();
  }
}

// —————————————————————————————————————————————
// 9. 时间成本分析图
// —————————————————————————————————————————————
function renderTimeChart(data) {
  const canvas = document.getElementById('chart-time');
  if (!canvas) return;

  if (STATE.charts.time) { STATE.charts.time.destroy(); }

  const details = data.task_details || [];
  const baseTimes = details.filter(d => d.mode === 'base').sort((a, b) => a.task_id - b.task_id);
  const aceTimes = details.filter(d => d.mode === 'ace').sort((a, b) => a.task_id - b.task_id);

  if (baseTimes.length === 0 && aceTimes.length === 0) {
    const parent = canvas.parentElement;
    if (parent) {
      parent.innerHTML = '<div class="chart-placeholder">'
        + '<div class="chart-icon">⏱️</div>'
        + '<div class="chart-label">时间成本分析</div>'
        + '<div class="chart-hint">运行实验后可查看每个任务的响应时间对比</div>'
        + '</div>';
    }
    return;
  }

  const labels = baseTimes.length > 0
    ? baseTimes.map(d => '#' + d.task_id)
    : aceTimes.map(d => '#' + d.task_id);

  const baseData = baseTimes.map(d => d.response_time);
  const aceData = aceTimes.map(d => d.response_time);

  STATE.charts.time = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Base LLM',
          data: baseData,
          backgroundColor: 'rgba(239,68,68,0.5)',
          borderColor: '#ef4444',
          borderWidth: 1,
          borderRadius: 3,
        },
        {
          label: 'ACE 增强',
          data: aceData,
          backgroundColor: 'rgba(34,197,94,0.5)',
          borderColor: '#22c55e',
          borderWidth: 1,
          borderRadius: 3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 12 }, padding: 16 } },
        datalabels: {
          anchor: 'end',
          align: 'end',
          color: '#64748b',
          font: { size: 9 },
          formatter: v => v ? v.toFixed(1) + 's' : '',
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: '响应时间 (秒)', font: { size: 11 } },
        },
      },
    },
  });
}

// —————————————————————————————————————————————
// 10. 更新任务详情表
// —————————————————————————————————————————————
function updateTaskDetails(data) {
  const details = data.task_details || [];
  if (details.length === 0) return;

  const tbody = document.querySelector('.testcase-table tbody');
  if (!tbody) return;

  // 按 task_id 分组
  const grouped = {};
  details.forEach(d => {
    if (!grouped[d.task_id]) grouped[d.task_id] = {};
    grouped[d.task_id][d.mode] = d;
  });

  // 为每一行添加结果列
  const rows = tbody.querySelectorAll('tr');
  // 检查是否已有结果列
  const headerRow = document.querySelector('.testcase-table thead tr');
  let hasResultCol = headerRow && headerRow.querySelector('th:nth-child(5)');

  if (!hasResultCol) {
    // 添加表头
    if (headerRow) {
      const th = document.createElement('th');
      th.style.width = '120px';
      th.textContent = '结果';
      headerRow.appendChild(th);
    }
  }

  rows.forEach(row => {
    const firstTd = row.querySelector('td');
    if (!firstTd) return;
    const taskId = parseInt(firstTd.textContent.trim(), 10);
    if (isNaN(taskId)) return;

    // 检查是否已有结果列
    let resultTd = row.querySelector('td:nth-child(5)');
    if (!resultTd) {
      resultTd = document.createElement('td');
      row.appendChild(resultTd);
    }

    const taskData = grouped[taskId];
    if (!taskData) {
      resultTd.textContent = '—';
      return;
    }

    const baseRec = taskData.base;
    const aceRec = taskData.ace;

    const baseAcc = baseRec && baseRec.accuracy;
    const aceAcc = aceRec && aceRec.accuracy;

    resultTd.innerHTML = ''
      + '<span style="display:flex;gap:8px;align-items:center;font-size:12px;">'
      + '<span class="' + (baseAcc ? 'task-result-pass' : 'task-result-fail') + '">B:' + (baseAcc ? '✓' : '✗') + '</span>'
      + '<span class="' + (aceAcc ? 'task-result-pass' : 'task-result-fail') + '">A:' + (aceAcc ? '✓' : '✗') + '</span>'
      + '</span>';
  });
}

// —————————————————————————————————————————————
// 11. 运行实验
// —————————————————————————————————————————————
async function runExperiment1() {
  if (STATE.running) return;

  const btn = document.getElementById('exp1-run-btn');
  const bankSelect = document.getElementById('exp1-bank-select');
  const bankId = bankSelect ? bankSelect.value : 'default';

  btn.disabled = true;
  btn.textContent = '⏳ 运行中...';
  STATE.running = true;
  updateStatus('running', '实验正在运行，请稍候...');

  // 隐藏之前的错误/空状态
  showError(null);
  showEmpty(false);

  try {
    const resp = await fetch('/api/experiment/exp1/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'both', bank_id: bankId }),
    });

    const result = await resp.json();
    if (!resp.ok) {
      updateStatus('error', result.message || '启动实验失败');
      btn.disabled = false;
      btn.textContent = '▶ 运行实验';
      STATE.running = false;
      return;
    }

    // 启动轮询
    startPolling();
  } catch (err) {
    updateStatus('error', '网络错误: ' + err.message);
    btn.disabled = false;
    btn.textContent = '▶ 运行实验';
    STATE.running = false;
  }
}

// —————————————————————————————————————————————
// 12. 轮询实验状态
// —————————————————————————————————————————————
function startPolling() {
  // 清除旧轮询
  if (STATE.pollingTimer) {
    clearInterval(STATE.pollingTimer);
  }

  let attempts = 0;
  const MAX_ATTEMPTS = 120; // 最多等 10 分钟（5秒间隔）

  STATE.pollingTimer = setInterval(async () => {
    attempts++;
    if (attempts > MAX_ATTEMPTS) {
      clearInterval(STATE.pollingTimer);
      STATE.pollingTimer = null;
      STATE.running = false;
      const btn = document.getElementById('exp1-run-btn');
      btn.disabled = false;
      btn.textContent = '▶ 运行实验';
      updateStatus('error', '实验超时，请检查服务器日志。');
      return;
    }

    try {
      const resp = await fetch('/api/experiment/exp1/data');
      const data = await resp.json();

      if (data.status === 'error') {
        // 实验出错
        clearInterval(STATE.pollingTimer);
        STATE.pollingTimer = null;
        STATE.running = false;
        const btn = document.getElementById('exp1-run-btn');
        btn.disabled = false;
        btn.textContent = '▶ 运行实验';
        updateStatus('error', data.error || '实验运行出错');
        showError(data.error || '实验运行出错');
        return;
      }

      if (data.status === 'no_data') {
        // 还没完成
        updateStatus('running', '实验运行中... (' + (attempts * 5) + '秒)');
        return;
      }

      // 有数据 —— 实验完成
      clearInterval(STATE.pollingTimer);
      STATE.pollingTimer = null;
      STATE.running = false;

      const btn = document.getElementById('exp1-run-btn');
      btn.disabled = false;
      btn.textContent = '▶ 运行实验';

      STATE.data = data;
      STATE.selectedRunDir = data.run_dir || '';
      renderExperiment1(data);
      updateStatus('done', '实验完成 ✓');
      showLoading(false);
      showEmpty(false);
      // 实验完成后刷新历史列表
      fetchExperimentHistory();

    } catch (err) {
      // 网络错误可能是服务器忙，继续等
      console.warn('轮询出错:', err);
    }
  }, 5000);
}

// —————————————————————————————————————————————
// 13. 实验二：消融实验
// —————————————————————————————————————————————
async function fetchExperiment2Data() {
  showExp2Loading(true);
  try {
    const data = await fetchJson('/api/experiment/exp2/data');
    if (data.status === 'no_data') {
      STATE.exp2Data = null;
      showExp2Empty(true);
      showExp2Loading(false);
      return;
    }
    if (data.status === 'error') {
      showExp2Error(data.error || data.message || '未知错误');
      showExp2Loading(false);
      return;
    }
    STATE.exp2Data = data;
    STATE.exp2SelectedRunDir = data.run_dir || '';
    renderExperiment2(data);
    showExp2Loading(false);
    showExp2Empty(false);
  } catch (err) {
    showExp2Error(err.message || '网络错误，无法加载实验二数据');
    showExp2Loading(false);
  }
}

async function fetchExperiment2History() {
  try {
    const data = await fetchJson('/api/experiment/exp2/results');
    renderExp2HistoryTable(data.runs || []);
  } catch (err) {
    console.warn('获取实验二历史记录失败:', err);
  }
}

async function runExperiment2() {
  if (STATE.exp2Running) return;
  const btn = document.getElementById('exp2-run-btn');
  btn.disabled = true;
  btn.textContent = '运行中...';
  STATE.exp2Running = true;
  updateExp2Status('running', '实验二正在运行...');
  showExp2Error(null);
  showExp2Empty(false);

  try {
    const result = await fetchJson('/api/experiment/exp2/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const summary = result.summary || result;
    STATE.exp2Data = summary;
    STATE.exp2SelectedRunDir = summary.run_dir || '';
    renderExperiment2(summary);
    await fetchExperiment2History();
    btn.disabled = false;
    btn.textContent = '▶ 运行实验';
    STATE.exp2Running = false;
    showExp2Loading(false);
    updateExp2Status('done', '实验二完成');
  } catch (err) {
    btn.disabled = false;
    btn.textContent = '▶ 运行实验';
    STATE.exp2Running = false;
    updateExp2Status('error', '实验二启动失败');
    showExp2Error(err.message);
  }
}

function renderExperiment2(data) {
  if (!data) return;
  showExp2Error(null);

  const variants = data.variants || {};
  const full = variants.full_ace || {};
  const contributions = data.contributions || [];
  const top = contributions[0] || {};

  document.getElementById('exp2-full-accuracy').textContent = formatPct(full.accuracy_rate);
  document.getElementById('exp2-full-completion').textContent = '完成率 ' + formatPct(full.task_completion_rate);
  document.getElementById('exp2-full-tool').textContent = '工具 ' + formatPct(full.tool_success_rate);
  document.getElementById('exp2-top-module').textContent = top.module || '--';
  document.getElementById('exp2-top-score').textContent = '贡献度 ' + formatNumber(top.contribution_score);
  document.getElementById('exp2-top-dim').textContent = top.dimension || '--';
  document.getElementById('exp2-context-consistency').textContent = formatPct(full.multi_turn_consistency_rate);
  document.getElementById('exp2-error-depth').textContent = '错误传播深度 ' + formatNumber(full.avg_error_propagation_depth);
  document.getElementById('exp2-recovery').textContent = '恢复率 ' + formatPct(full.error_recovery_rate);

  const lastRunEl = document.getElementById('exp2-last-run');
  lastRunEl.textContent = data.run_name ? '当前显示: ' + data.run_name : '';

  renderExp2MetricsChart(data);
  renderExp2ContributionChart(data);
  renderExp2ErrorChart(data);
  renderExp2Ranking(contributions);
  renderExp2TaskTable(data.task_details || []);
}

function renderExp2MetricsChart(data) {
  const canvas = document.getElementById('exp2-chart-metrics');
  if (!canvas) return;
  if (STATE.charts.exp2Metrics) STATE.charts.exp2Metrics.destroy();
  const items = Object.values(data.variants || {});
  STATE.charts.exp2Metrics = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: items.map(item => item.name),
      datasets: [
        { label: '准确率', data: items.map(item => item.accuracy_rate || 0), backgroundColor: 'rgba(34,197,94,0.72)' },
        { label: '工具成功率', data: items.map(item => item.tool_success_rate || 0), backgroundColor: 'rgba(59,130,246,0.65)' },
        { label: '多轮一致性', data: items.map(item => item.multi_turn_consistency_rate || 0), backgroundColor: 'rgba(168,85,247,0.58)' },
      ],
    },
    options: exp2ChartOptions('%'),
  });
}

function renderExp2ContributionChart(data) {
  const canvas = document.getElementById('exp2-chart-contrib');
  if (!canvas) return;
  if (STATE.charts.exp2Contrib) STATE.charts.exp2Contrib.destroy();
  const items = data.contributions || [];
  STATE.charts.exp2Contrib = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: items.map(item => item.module),
      datasets: [{
        label: '综合贡献度',
        data: items.map(item => item.contribution_score || 0),
        backgroundColor: ['#8b5cf6', '#06b6d4', '#22c55e', '#f59e0b'],
      }],
    },
    options: { ...exp2ChartOptions(''), indexAxis: 'y' },
  });
}

function renderExp2ErrorChart(data) {
  const canvas = document.getElementById('exp2-chart-error');
  if (!canvas) return;
  if (STATE.charts.exp2Error) STATE.charts.exp2Error.destroy();
  const items = Object.values(data.variants || {});
  STATE.charts.exp2Error = new Chart(canvas, {
    type: 'line',
    data: {
      labels: items.map(item => item.name),
      datasets: [
        {
          label: '错误恢复率',
          data: items.map(item => item.error_recovery_rate || 0),
          borderColor: '#16a34a',
          backgroundColor: 'rgba(22,163,74,0.12)',
          tension: 0.3,
          fill: true,
        },
        {
          label: '错误传播深度',
          data: items.map(item => item.avg_error_propagation_depth || 0),
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239,68,68,0.08)',
          tension: 0.3,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' }, datalabels: { display: false } },
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
        y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false } },
      },
    },
  });
}

function renderExp2Ranking(contributions) {
  const tbody = document.getElementById('exp2-ranking-tbody');
  if (!tbody) return;
  if (!contributions || contributions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#94a3b8;">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  contributions.forEach((item, index) => {
    const tr = document.createElement('tr');
    appendTextCell(tr, String(index + 1));
    appendTextCell(tr, item.module || '--');
    appendTextCell(tr, formatNumber(item.contribution_score));
    appendTextCell(tr, item.dimension || '--');
    tbody.appendChild(tr);
  });
}

function renderExp2TaskTable(details) {
  const tbody = document.getElementById('exp2-task-tbody');
  if (!tbody) return;
  const rows = (details || []).slice(0, 40);
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#94a3b8;">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  rows.forEach(item => {
    const tr = document.createElement('tr');
    appendTextCell(tr, String(item.task_id));
    appendTextCell(tr, item.task_type || '--');
    appendTextCell(tr, item.variant_name || '--');
    appendTextCell(tr, formatNumber(item.score));
    appendTextCell(tr, item.accuracy ? '通过' : '未通过');
    appendTextCell(tr, (item.missing_modules || []).join(', ') || '-');
    tbody.appendChild(tr);
  });
}

function renderExp2HistoryTable(runs) {
  const tbody = document.getElementById('exp2-history-tbody');
  if (!tbody) return;
  if (!runs || runs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#94a3b8;">暂无历史实验记录</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  runs.forEach(run => {
    const tr = document.createElement('tr');
    const runDir = run.run_dir || '';
    const full = run.variants?.full_ace || {};
    const top = (run.contributions || [])[0] || {};
    tr.className = runDir === STATE.exp2SelectedRunDir ? 'history-row active' : 'history-row';
    tr.addEventListener('click', () => loadExp2HistoryRun(runDir));
    appendTextCell(tr, run.run_name || '未知', 'history-name-cell', runDir);
    appendTextCell(tr, String(run.total_tasks || 0));
    appendTextCell(tr, formatPct(full.accuracy_rate));
    appendTextCell(tr, top.module || '--');

    const actionsCell = document.createElement('td');
    actionsCell.className = 'history-actions';
    actionsCell.append(
      exp2ActionButton('查看', () => loadExp2HistoryRun(runDir)),
      exp2ActionButton('重命名', () => renameExp2History(runDir, run.run_name || '')),
      exp2ActionButton('删除', () => deleteExp2History(runDir), 'danger')
    );
    tr.appendChild(actionsCell);
    tbody.appendChild(tr);
  });
}

async function loadExp2HistoryRun(runDir) {
  if (!runDir) return;
  showExp2Loading(true);
  try {
    const params = new URLSearchParams({ run_dir: runDir });
    const data = await fetchJson('/api/experiment/exp2/data?' + params.toString());
    STATE.exp2Data = data;
    STATE.exp2SelectedRunDir = data.run_dir || runDir;
    renderExperiment2(data);
    showExp2Loading(false);
    showExp2Empty(false);
    updateExp2Status('done', '已加载历史实验二：' + (data.run_name || STATE.exp2SelectedRunDir));
    fetchExperiment2History();
  } catch (err) {
    showExp2Loading(false);
    showExp2Error('加载历史实验二失败: ' + err.message);
  }
}

async function renameExp2History(runDir, currentName) {
  const newName = prompt('请输入新的实验名称：', currentName || '');
  if (!newName || !newName.trim()) return;
  try {
    await fetchJson('/api/experiment/exp2/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir, name: newName.trim() }),
    });
    if (STATE.exp2SelectedRunDir === runDir && STATE.exp2Data) {
      STATE.exp2Data.run_name = newName.trim().slice(0, 60);
      renderExperiment2(STATE.exp2Data);
    }
    await fetchExperiment2History();
    updateExp2Status('done', '已重命名实验二记录。');
  } catch (err) {
    alert('重命名失败: ' + err.message);
  }
}

async function deleteExp2History(runDir) {
  if (!confirm('确定要删除此实验二记录吗？\n此操作不可恢复。')) return;
  try {
    await fetchJson('/api/experiment/exp2/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir }),
    });
    await fetchExperiment2History();
    if (STATE.exp2SelectedRunDir === runDir) {
      STATE.exp2SelectedRunDir = '';
      await fetchExperiment2Data();
    }
    updateExp2Status('done', '已删除实验二记录。');
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}

function exp2ActionButton(label, onClick, extraClass) {
  const btn = document.createElement('button');
  btn.className = 'exp-btn-sm' + (extraClass ? ' ' + extraClass : '');
  btn.type = 'button';
  btn.textContent = label;
  btn.addEventListener('click', event => {
    event.stopPropagation();
    onClick();
  });
  return btn;
}

function appendTextCell(row, text, className, title) {
  const td = document.createElement('td');
  if (className) td.className = className;
  if (title) td.title = title;
  td.textContent = text;
  row.appendChild(td);
  return td;
}

function exp2ChartOptions(unit) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'bottom' }, datalabels: { display: false } },
    scales: {
      y: { beginAtZero: true, max: unit === '%' ? 100 : undefined, ticks: { callback: v => unit === '%' ? v + '%' : v } },
    },
  };
}

function updateExp2Status(type, message) {
  const el = document.getElementById('exp2-status');
  if (!el) return;
  el.className = 'exp-status' + (type ? ' ' + type : '');
  el.textContent = message || '';
}

function showExp2Loading(show) {
  const el = document.getElementById('exp2-loading');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showExp2Empty(show) {
  const el = document.getElementById('exp2-empty');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showExp2Error(message) {
  const el = document.getElementById('exp2-error');
  const textEl = document.getElementById('exp2-error-text');
  if (!el || !textEl) return;
  if (message) {
    el.style.display = 'flex';
    textEl.textContent = message;
  } else {
    el.style.display = 'none';
  }
}

function formatPct(value) {
  return value != null && !isNaN(value) ? Number(value).toFixed(1) + '%' : '--%';
}

function formatNumber(value) {
  return value != null && !isNaN(value) ? Number(value).toFixed(1) : '--';
}

// —————————————————————————————————————————————
// 14. 实验三：抗退化实验
// —————————————————————————————————————————————
async function fetchExperiment3Data() {
  showExp3Loading(true);
  try {
    const data = await fetchJson('/api/experiment/exp3/data');
    if (data.status === 'no_data') {
      STATE.exp3Data = null;
      showExp3Empty(true);
      showExp3Loading(false);
      return;
    }
    if (data.status === 'error') {
      showExp3Error(data.error || data.message || '未知错误');
      showExp3Loading(false);
      return;
    }
    STATE.exp3Data = data;
    STATE.exp3SelectedRunDir = data.run_dir || '';
    renderExperiment3(data);
    showExp3Loading(false);
    showExp3Empty(false);
  } catch (err) {
    showExp3Error(err.message || '网络错误，无法加载实验三数据');
    showExp3Loading(false);
  }
}

async function fetchExperiment3History() {
  try {
    const data = await fetchJson('/api/experiment/exp3/results');
    renderExp3HistoryTable(data.runs || []);
  } catch (err) {
    console.warn('获取实验三历史记录失败:', err);
  }
}

async function runExperiment3() {
  if (STATE.exp3Running) return;
  const btn = document.getElementById('exp3-run-btn');
  btn.disabled = true;
  btn.textContent = '运行中...';
  STATE.exp3Running = true;
  updateExp3Status('running', '实验三正在运行...');
  showExp3Error(null);
  showExp3Empty(false);

  try {
    const result = await fetchJson('/api/experiment/exp3/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const summary = result.summary || result;
    STATE.exp3Data = summary;
    STATE.exp3SelectedRunDir = summary.run_dir || '';
    renderExperiment3(summary);
    await fetchExperiment3History();
    btn.disabled = false;
    btn.textContent = '▶ 运行实验';
    STATE.exp3Running = false;
    showExp3Loading(false);
    updateExp3Status('done', '实验三完成');
  } catch (err) {
    btn.disabled = false;
    btn.textContent = '▶ 运行实验';
    STATE.exp3Running = false;
    updateExp3Status('error', '实验三启动失败');
    showExp3Error(err.message);
  }
}

function renderExperiment3(data) {
  const systems = data.systems || {};
  const base = systems.base_llm || {};
  const ace = systems.ace_dynamic || {};
  const recallGain = (ace.memory_recall_rate || 0) - (base.memory_recall_rate || 0);

  document.getElementById('exp3-ace-recall').textContent = formatPct(ace.memory_recall_rate);
  document.getElementById('exp3-base-recall').textContent = 'Base ' + formatPct(base.memory_recall_rate);
  document.getElementById('exp3-recall-gain').textContent = '提升 ' + formatNumber(recallGain);
  document.getElementById('exp3-ace-pref').textContent = formatPct(ace.preference_persistence_rate);
  document.getElementById('exp3-base-pref').textContent = 'Base ' + formatPct(base.preference_persistence_rate);
  document.getElementById('exp3-half-life').textContent = '半衰期 ' + formatNumber(ace.memory_half_life_rounds) + ' 轮';
  document.getElementById('exp3-ace-robustness').textContent = formatNumber(ace.robustness_score);
  document.getElementById('exp3-pollution').textContent = '污染率 ' + formatPct(ace.context_pollution_rate);
  document.getElementById('exp3-compression').textContent = '压缩率 ' + formatPct(ace.avg_compression_rate);
  document.getElementById('exp3-last-run').textContent = data.run_name ? '当前显示: ' + data.run_name : '';

  renderExp3DecayChart(data);
  renderExp3MemoryChart(data);
  renderExp3PollutionChart(data);
  renderExp3RoundTable(data.round_details || []);
}

function renderExp3DecayChart(data) {
  const canvas = document.getElementById('exp3-chart-decay');
  if (!canvas) return;
  if (STATE.charts.exp3Decay) STATE.charts.exp3Decay.destroy();
  const curve = data.decay_curve || [];
  STATE.charts.exp3Decay = new Chart(canvas, {
    type: 'line',
    data: {
      labels: curve.map(p => p.gap + '轮'),
      datasets: [
        { label: 'Base LLM', data: curve.map(p => p.base_llm || 0), borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', tension: 0.35 },
        { label: 'ACE', data: curve.map(p => p.ace_dynamic || 0), borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.12)', tension: 0.35 },
      ],
    },
    options: exp2ChartOptions('%'),
  });
}

function renderExp3MemoryChart(data) {
  const canvas = document.getElementById('exp3-chart-memory');
  if (!canvas) return;
  if (STATE.charts.exp3Memory) STATE.charts.exp3Memory.destroy();
  const base = data.systems?.base_llm || {};
  const ace = data.systems?.ace_dynamic || {};
  STATE.charts.exp3Memory = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: ['POI召回', '偏好持久', '经验复用', '鲁棒性'],
      datasets: [
        { label: 'Base LLM', data: [base.poi_recall_rate || 0, base.preference_persistence_rate || 0, base.experience_reuse_rate || 0, base.robustness_score || 0], backgroundColor: 'rgba(239,68,68,0.65)' },
        { label: 'ACE', data: [ace.poi_recall_rate || 0, ace.preference_persistence_rate || 0, ace.experience_reuse_rate || 0, ace.robustness_score || 0], backgroundColor: 'rgba(34,197,94,0.7)' },
      ],
    },
    options: exp2ChartOptions('%'),
  });
}

function renderExp3PollutionChart(data) {
  const canvas = document.getElementById('exp3-chart-pollution');
  if (!canvas) return;
  if (STATE.charts.exp3Pollution) STATE.charts.exp3Pollution.destroy();
  const base = data.systems?.base_llm || {};
  const ace = data.systems?.ace_dynamic || {};
  STATE.charts.exp3Pollution = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: ['上下文污染率', '压缩率', '记忆半衰期'],
      datasets: [
        { label: 'Base LLM', data: [base.context_pollution_rate || 0, base.avg_compression_rate || 0, base.memory_half_life_rounds || 0], backgroundColor: 'rgba(239,68,68,0.65)' },
        { label: 'ACE', data: [ace.context_pollution_rate || 0, ace.avg_compression_rate || 0, ace.memory_half_life_rounds || 0], backgroundColor: 'rgba(59,130,246,0.68)' },
      ],
    },
    options: exp2ChartOptions(''),
  });
}

function renderExp3RoundTable(details) {
  const tbody = document.getElementById('exp3-round-tbody');
  if (!tbody) return;
  const rows = (details || []).filter(r => r.phase === 'recall').slice(0, 30);
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#94a3b8;">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  rows.forEach(item => {
    const tr = document.createElement('tr');
    appendTextCell(tr, String(item.round));
    appendTextCell(tr, item.system_name || '--');
    appendTextCell(tr, item.phase || '--');
    appendTextCell(tr, item.memory_type || '--');
    appendTextCell(tr, String(item.target_gap || 0));
    appendTextCell(tr, formatPct(item.recall_rate));
    appendTextCell(tr, formatPct(item.context_pollution_rate));
    tbody.appendChild(tr);
  });
}

function renderExp3HistoryTable(runs) {
  const tbody = document.getElementById('exp3-history-tbody');
  if (!tbody) return;
  if (!runs || !runs.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#94a3b8;">暂无历史实验记录</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  runs.forEach(run => {
    const runDir = run.run_dir || '';
    const ace = run.systems?.ace_dynamic || {};
    const tr = document.createElement('tr');
    tr.className = runDir === STATE.exp3SelectedRunDir ? 'history-row active' : 'history-row';
    tr.addEventListener('click', () => loadExp3HistoryRun(runDir));
    appendTextCell(tr, run.run_name || '未知', 'history-name-cell', runDir);
    appendTextCell(tr, String(run.total_rounds || 0));
    appendTextCell(tr, formatPct(ace.memory_recall_rate));
    appendTextCell(tr, formatNumber(ace.robustness_score));
    const actionsCell = document.createElement('td');
    actionsCell.className = 'history-actions';
    actionsCell.append(
      exp2ActionButton('查看', () => loadExp3HistoryRun(runDir)),
      exp2ActionButton('重命名', () => renameExp3History(runDir, run.run_name || '')),
      exp2ActionButton('删除', () => deleteExp3History(runDir), 'danger')
    );
    tr.appendChild(actionsCell);
    tbody.appendChild(tr);
  });
}

async function loadExp3HistoryRun(runDir) {
  if (!runDir) return;
  showExp3Loading(true);
  try {
    const data = await fetchJson('/api/experiment/exp3/data?' + new URLSearchParams({ run_dir: runDir }).toString());
    STATE.exp3Data = data;
    STATE.exp3SelectedRunDir = data.run_dir || runDir;
    renderExperiment3(data);
    showExp3Loading(false);
    showExp3Empty(false);
    updateExp3Status('done', '已加载历史实验三：' + (data.run_name || STATE.exp3SelectedRunDir));
    fetchExperiment3History();
  } catch (err) {
    showExp3Loading(false);
    showExp3Error('加载历史实验三失败: ' + err.message);
  }
}

async function renameExp3History(runDir, currentName) {
  const newName = prompt('请输入新的实验名称：', currentName || '');
  if (!newName || !newName.trim()) return;
  try {
    await fetchJson('/api/experiment/exp3/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir, name: newName.trim() }),
    });
    await fetchExperiment3History();
    updateExp3Status('done', '已重命名实验三记录。');
  } catch (err) {
    alert('重命名失败: ' + err.message);
  }
}

async function deleteExp3History(runDir) {
  if (!confirm('确定要删除此实验三记录吗？\n此操作不可恢复。')) return;
  try {
    await fetchJson('/api/experiment/exp3/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir }),
    });
    await fetchExperiment3History();
    if (STATE.exp3SelectedRunDir === runDir) {
      STATE.exp3SelectedRunDir = '';
      await fetchExperiment3Data();
    }
    updateExp3Status('done', '已删除实验三记录。');
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}

function updateExp3Status(type, message) {
  const el = document.getElementById('exp3-status');
  if (!el) return;
  el.className = 'exp-status' + (type ? ' ' + type : '');
  el.textContent = message || '';
}

function showExp3Loading(show) {
  const el = document.getElementById('exp3-loading');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showExp3Empty(show) {
  const el = document.getElementById('exp3-empty');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showExp3Error(message) {
  const el = document.getElementById('exp3-error');
  const textEl = document.getElementById('exp3-error-text');
  if (!el || !textEl) return;
  if (message) {
    el.style.display = 'flex';
    textEl.textContent = message;
  } else {
    el.style.display = 'none';
  }
}

// —————————————————————————————————————————————
// 15. 实验四：长上下文扩展
// —————————————————————————————————————————————
async function fetchExperiment4Data() {
  showExp4Loading(true);
  try {
    const data = await fetchJson('/api/experiment/exp4/data');
    if (data.status === 'no_data') {
      STATE.exp4Data = null;
      showExp4Empty(true);
      showExp4Loading(false);
      return;
    }
    if (data.status === 'error') {
      showExp4Error(data.error || data.message || '未知错误');
      showExp4Loading(false);
      return;
    }
    STATE.exp4Data = data;
    STATE.exp4SelectedRunDir = data.run_dir || '';
    renderExperiment4(data);
    showExp4Loading(false);
    showExp4Empty(false);
  } catch (err) {
    showExp4Error(err.message || '网络错误，无法加载实验四数据');
    showExp4Loading(false);
  }
}

async function fetchExperiment4History() {
  try {
    const data = await fetchJson('/api/experiment/exp4/results');
    renderExp4HistoryTable(data.runs || []);
  } catch (err) {
    console.warn('获取实验四历史记录失败:', err);
  }
}

async function runExperiment4() {
  if (STATE.exp4Running) return;
  const btn = document.getElementById('exp4-run-btn');
  btn.disabled = true;
  btn.textContent = '运行中...';
  STATE.exp4Running = true;
  updateExp4Status('running', '实验四正在运行...');
  showExp4Error(null);
  showExp4Empty(false);

  try {
    const result = await fetchJson('/api/experiment/exp4/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const summary = result.summary || result;
    STATE.exp4Data = summary;
    STATE.exp4SelectedRunDir = summary.run_dir || '';
    renderExperiment4(summary);
    await fetchExperiment4History();
    btn.disabled = false;
    btn.textContent = '▶ 运行实验';
    STATE.exp4Running = false;
    showExp4Loading(false);
    updateExp4Status('done', '实验四完成');
  } catch (err) {
    btn.disabled = false;
    btn.textContent = '▶ 运行实验';
    STATE.exp4Running = false;
    updateExp4Status('error', '实验四启动失败');
    showExp4Error(err.message);
  }
}

function renderExperiment4(data) {
  const systems = data.systems || {};
  const full = systems.base_full || {};
  const truncated = systems.base_truncated || {};
  const ace = systems.ace_compressed || {};

  document.getElementById('exp4-ace-accuracy').textContent = formatPct(ace.long_sequence_accuracy);
  document.getElementById('exp4-base-full').textContent = 'Base full ' + formatPct(full.long_sequence_accuracy);
  document.getElementById('exp4-base-truncated').textContent = 'Base truncated ' + formatPct(truncated.long_sequence_accuracy);
  document.getElementById('exp4-ace-reference').textContent = formatPct(ace.cross_turn_reference_accuracy);
  document.getElementById('exp4-compression-rate').textContent = '压缩率 ' + formatPct(ace.context_compression_rate);
  document.getElementById('exp4-effective-tokens').textContent = '有效 tokens ' + formatInteger(ace.avg_effective_tokens);
  document.getElementById('exp4-ace-robustness').textContent = formatNumber(ace.robustness_score);
  document.getElementById('exp4-pollution').textContent = '污染率 ' + formatPct(ace.context_pollution_rate);
  document.getElementById('exp4-completion').textContent = '完成率 ' + formatPct(ace.completion_rate);
  document.getElementById('exp4-last-run').textContent = data.run_name ? '当前显示: ' + data.run_name : '';

  renderExp4AccuracyChart(data);
  renderExp4ReferenceChart(data);
  renderExp4CompressionChart(data);
  renderExp4IntervalTable(data.interval_stats || []);
}

function renderExp4AccuracyChart(data) {
  const canvas = document.getElementById('exp4-chart-accuracy');
  if (!canvas) return;
  if (STATE.charts.exp4Accuracy) STATE.charts.exp4Accuracy.destroy();
  const curve = data.length_curve || [];
  STATE.charts.exp4Accuracy = new Chart(canvas, {
    type: 'line',
    data: {
      labels: curve.map(p => Math.round((p.context_tokens || 0) / 1000) + 'K'),
      datasets: [
        { label: 'Base full', data: curve.map(p => p.base_full || 0), borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.08)', tension: 0.3 },
        { label: 'Base truncated', data: curve.map(p => p.base_truncated || 0), borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.08)', tension: 0.3 },
        { label: 'ACE compressed', data: curve.map(p => p.ace_compressed || 0), borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', tension: 0.3 },
      ],
    },
    options: exp2ChartOptions('%'),
  });
}

function renderExp4ReferenceChart(data) {
  const canvas = document.getElementById('exp4-chart-reference');
  if (!canvas) return;
  if (STATE.charts.exp4Reference) STATE.charts.exp4Reference.destroy();
  const items = Object.values(data.systems || {});
  STATE.charts.exp4Reference = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: items.map(item => item.name),
      datasets: [
        { label: '跨轮引用准确率', data: items.map(item => item.cross_turn_reference_accuracy || 0), backgroundColor: 'rgba(59,130,246,0.68)' },
        { label: '长序列准确率', data: items.map(item => item.long_sequence_accuracy || 0), backgroundColor: 'rgba(34,197,94,0.68)' },
      ],
    },
    options: exp2ChartOptions('%'),
  });
}

function renderExp4CompressionChart(data) {
  const canvas = document.getElementById('exp4-chart-compression');
  if (!canvas) return;
  if (STATE.charts.exp4Compression) STATE.charts.exp4Compression.destroy();
  const items = Object.values(data.systems || {});
  STATE.charts.exp4Compression = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: items.map(item => item.name),
      datasets: [
        { label: '上下文压缩率', data: items.map(item => item.context_compression_rate || 0), backgroundColor: 'rgba(168,85,247,0.65)' },
        { label: '污染率', data: items.map(item => item.context_pollution_rate || 0), backgroundColor: 'rgba(239,68,68,0.55)' },
      ],
    },
    options: exp2ChartOptions('%'),
  });
}

function renderExp4IntervalTable(intervals) {
  const tbody = document.getElementById('exp4-interval-tbody');
  if (!tbody) return;
  if (!intervals.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#94a3b8;">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  intervals.forEach(item => {
    const ace = item.ace_compressed || {};
    const full = item.base_full || {};
    const tr = document.createElement('tr');
    appendTextCell(tr, item.interval || '--');
    appendTextCell(tr, '~' + formatInteger(full.context_tokens));
    appendTextCell(tr, formatPct(full.accuracy));
    appendTextCell(tr, formatPct(ace.accuracy));
    appendTextCell(tr, formatInteger(ace.compressed_tokens));
    tbody.appendChild(tr);
  });
}

function renderExp4HistoryTable(runs) {
  const tbody = document.getElementById('exp4-history-tbody');
  if (!tbody) return;
  if (!runs || !runs.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#94a3b8;">暂无历史实验记录</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  runs.forEach(run => {
    const runDir = run.run_dir || '';
    const ace = run.systems?.ace_compressed || {};
    const tr = document.createElement('tr');
    tr.className = runDir === STATE.exp4SelectedRunDir ? 'history-row active' : 'history-row';
    tr.addEventListener('click', () => loadExp4HistoryRun(runDir));
    appendTextCell(tr, run.run_name || '未知', 'history-name-cell', runDir);
    appendTextCell(tr, String(run.total_rounds || 0));
    appendTextCell(tr, formatPct(ace.long_sequence_accuracy));
    appendTextCell(tr, formatNumber(ace.robustness_score));
    const actionsCell = document.createElement('td');
    actionsCell.className = 'history-actions';
    actionsCell.append(
      exp2ActionButton('查看', () => loadExp4HistoryRun(runDir)),
      exp2ActionButton('重命名', () => renameExp4History(runDir, run.run_name || '')),
      exp2ActionButton('删除', () => deleteExp4History(runDir), 'danger')
    );
    tr.appendChild(actionsCell);
    tbody.appendChild(tr);
  });
}

async function loadExp4HistoryRun(runDir) {
  if (!runDir) return;
  showExp4Loading(true);
  try {
    const data = await fetchJson('/api/experiment/exp4/data?' + new URLSearchParams({ run_dir: runDir }).toString());
    STATE.exp4Data = data;
    STATE.exp4SelectedRunDir = data.run_dir || runDir;
    renderExperiment4(data);
    showExp4Loading(false);
    showExp4Empty(false);
    updateExp4Status('done', '已加载历史实验四：' + (data.run_name || STATE.exp4SelectedRunDir));
    fetchExperiment4History();
  } catch (err) {
    showExp4Loading(false);
    showExp4Error('加载历史实验四失败: ' + err.message);
  }
}

async function renameExp4History(runDir, currentName) {
  const newName = prompt('请输入新的实验名称：', currentName || '');
  if (!newName || !newName.trim()) return;
  try {
    await fetchJson('/api/experiment/exp4/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir, name: newName.trim() }),
    });
    await fetchExperiment4History();
    updateExp4Status('done', '已重命名实验四记录。');
  } catch (err) {
    alert('重命名失败: ' + err.message);
  }
}

async function deleteExp4History(runDir) {
  if (!confirm('确定要删除此实验四记录吗？\n此操作不可恢复。')) return;
  try {
    await fetchJson('/api/experiment/exp4/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_dir: runDir }),
    });
    await fetchExperiment4History();
    if (STATE.exp4SelectedRunDir === runDir) {
      STATE.exp4SelectedRunDir = '';
      await fetchExperiment4Data();
    }
    updateExp4Status('done', '已删除实验四记录。');
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}

function updateExp4Status(type, message) {
  const el = document.getElementById('exp4-status');
  if (!el) return;
  el.className = 'exp-status' + (type ? ' ' + type : '');
  el.textContent = message || '';
}

function showExp4Loading(show) {
  const el = document.getElementById('exp4-loading');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showExp4Empty(show) {
  const el = document.getElementById('exp4-empty');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showExp4Error(message) {
  const el = document.getElementById('exp4-error');
  const textEl = document.getElementById('exp4-error-text');
  if (!el || !textEl) return;
  if (message) {
    el.style.display = 'flex';
    textEl.textContent = message;
  } else {
    el.style.display = 'none';
  }
}

function formatInteger(value) {
  return value != null && !isNaN(value) ? Math.round(Number(value)).toLocaleString('zh-CN') : '--';
}

async function fetchJson(url, options) {
  const resp = await fetch(url, options);
  const text = await resp.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      throw new Error('服务返回了无法解析的响应');
    }
  }
  if (!resp.ok || data.error) {
    throw new Error(data.error || data.message || ('HTTP ' + resp.status));
  }
  return data;
}

// —————————————————————————————————————————————
// 13. 状态/提示管理
// —————————————————————————————————————————————
function exportExperimentData(expId, runDir) {
  if (!runDir) {
    alert('请先运行实验，或从历史实验数据中选择一条记录。');
    return;
  }
  const params = new URLSearchParams({ run_dir: runDir });
  window.location.href = '/api/experiment/' + expId + '/export?' + params.toString();
}

function updateStatus(type, message) {
  const el = document.getElementById('exp1-status');
  if (!el) return;
  el.className = 'exp-status' + (type ? ' ' + type : '');
  el.textContent = message || '';
}

function showLoading(show) {
  const el = document.getElementById('exp1-loading');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showEmpty(show) {
  const el = document.getElementById('exp1-empty');
  if (el) el.style.display = show ? 'flex' : 'none';
}

function showError(message) {
  const el = document.getElementById('exp1-error');
  const textEl = document.getElementById('exp1-error-text');
  if (!el || !textEl) return;
  if (message) {
    el.style.display = 'flex';
    textEl.textContent = message;
  } else {
    el.style.display = 'none';
  }
}
