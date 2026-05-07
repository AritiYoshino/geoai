import { STATE } from './state.js';
import { registerChartPlugins } from './chart_setup.js';
import { experimentActions } from './logic.js';

function bindTabs() {
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
      Object.values(panels).forEach(function (p) {
        if (p) p.classList.remove('active');
      });
      const targetId = this.getAttribute('data-tab');
      if (panels[targetId]) panels[targetId].classList.add('active');
    });
  });
}

function bindActions() {
  document.getElementById('exp1-run-btn')?.addEventListener('click', experimentActions.runExperiment1);
  document.getElementById('exp2-run-btn')?.addEventListener('click', experimentActions.runExperiment2);
  document.getElementById('exp3-run-btn')?.addEventListener('click', experimentActions.runExperiment3);
  document.getElementById('exp4-run-btn')?.addEventListener('click', experimentActions.runExperiment4);
  document.getElementById('exp1-export-btn')?.addEventListener('click', function () {
    experimentActions.exportExperimentData('exp1', STATE.selectedRunDir);
  });
  document.getElementById('exp2-export-btn')?.addEventListener('click', function () {
    experimentActions.exportExperimentData('exp2', STATE.exp2SelectedRunDir);
  });
  document.getElementById('exp3-export-btn')?.addEventListener('click', function () {
    experimentActions.exportExperimentData('exp3', STATE.exp3SelectedRunDir);
  });
  document.getElementById('exp4-export-btn')?.addEventListener('click', function () {
    experimentActions.exportExperimentData('exp4', STATE.exp4SelectedRunDir);
  });
  document.getElementById('thesis-refresh-btn')?.addEventListener('click', experimentActions.fetchThesisEvidence);
  document.getElementById('thesis-download-btn')?.addEventListener('click', experimentActions.downloadThesisEvidence);
}

function loadInitialData() {
  experimentActions.fetchExperiment1Data();
  experimentActions.fetchExperienceBanks();
  experimentActions.fetchExperimentHistory();
  experimentActions.fetchExperiment2Data();
  experimentActions.fetchExperiment2History();
  experimentActions.fetchExperiment3Data();
  experimentActions.fetchExperiment3History();
  experimentActions.fetchExperiment4Data();
  experimentActions.fetchExperiment4History();
  experimentActions.fetchThesisEvidence();
}

export function initExperimentPage() {
  registerChartPlugins();
  bindTabs();
  bindActions();
  loadInitialData();
}
