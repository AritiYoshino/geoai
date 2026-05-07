export function registerChartPlugins() {
  if (typeof ChartDataLabels !== 'undefined') {
    try {
      Chart.register(ChartDataLabels);
    } catch (e) {
      // Chart.js may already have the plugin registered when the page is hot-reloaded.
    }
  }
}
