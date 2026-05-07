export const STATE = {
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
