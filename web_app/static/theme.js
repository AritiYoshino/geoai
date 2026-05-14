/**
 * GeoAI 平台 — 主题管理器
 * 支持亮色/暗黑模式切换，持久化偏好设置
 */
;(function () {
  'use strict';

  const STORAGE_KEY = 'geoai-theme';
  const ATTR = 'data-theme';
  const MEDIA = '(prefers-color-scheme: dark)';

  /** 获取当前主题 */
  function getTheme() {
    return document.documentElement.getAttribute(ATTR) || 'light';
  }

  /** 设置主题 */
  function setTheme(theme) {
    document.documentElement.setAttribute(ATTR, theme);
    localStorage.setItem(STORAGE_KEY, theme);
    // 更新 toggle 按钮图标
    document.querySelectorAll('.theme-toggle').forEach(btn => {
      btn.textContent = theme === 'dark' ? '\u2600' : '\u263E';
      btn.setAttribute('aria-label', theme === 'dark' ? '切换亮色模式' : '切换暗黑模式');
    });
  }

  /** 切换主题 */
  function toggleTheme() {
    const next = getTheme() === 'dark' ? 'light' : 'dark';
    setTheme(next);
  }

  /** 初始化主题 */
  function initTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') {
      setTheme(saved);
    } else if (window.matchMedia(MEDIA).matches) {
      setTheme('dark');
    } else {
      setTheme('light');
    }

    // 监听系统主题变化
    window.matchMedia(MEDIA).addEventListener('change', e => {
      if (!localStorage.getItem(STORAGE_KEY)) {
        setTheme(e.matches ? 'dark' : 'light');
      }
    });
  }

  // 暴露全局接口
  window.__theme = { getTheme, setTheme, toggleTheme, initTheme };

  // DOM 就绪后自动初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }
})();
