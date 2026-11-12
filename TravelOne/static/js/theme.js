/* Copyright (c) 2026 黄豆666/huangdouplone
 * SPDX-License-Identifier: MIT */
/* TravelOne theme: auto (system), light, dark. Persisted per browser. */
(function () {
  const KEY = 'travelone.theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  let mode = localStorage.getItem(KEY);
  if (!['auto', 'light', 'dark'].includes(mode)) mode = 'auto';

  function resolved() {
    return mode === 'auto' ? (media.matches ? 'dark' : 'light') : mode;
  }

  function updateSeg() {
    document.querySelectorAll('[data-theme-set]').forEach((btn) => {
      const active = btn.dataset.themeSet === mode;
      btn.classList.toggle('on', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function apply() {
    const theme = resolved();
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    updateSeg();
    document.dispatchEvent(new CustomEvent('travelone:theme', { detail: { theme, mode } }));
  }

  document.addEventListener('click', (ev) => {
    const btn = ev.target.closest('[data-theme-set]');
    if (!btn) return;
    const next = btn.dataset.themeSet;
    if (!['auto', 'light', 'dark'].includes(next)) return;
    mode = next;
    localStorage.setItem(KEY, mode);
    apply();
  });

  const onChange = () => { if (mode === 'auto') apply(); };
  if (media.addEventListener) media.addEventListener('change', onChange);
  else if (media.addListener) media.addListener(onChange);

  window.TravelTheme = {
    apply,
    get mode() { return mode; },
    get theme() { return resolved(); },
    set(next) {
      if (!['auto', 'light', 'dark'].includes(next)) return;
      mode = next;
      localStorage.setItem(KEY, mode);
      apply();
    },
  };

  apply();
  document.addEventListener('DOMContentLoaded', apply);
})();