import { state } from './state.js';
import {
  closeCardModal,
  closeConfirmDeleteCardModal,
} from './cards.js';
import {
  closeColModal,
  closeConfirmDeleteModal,
} from './columns.js';
import { closeLabelsModal } from './labels.js';
import { closeFromTextModal, closeAskAI } from './ai.js';
import { closeCtx } from './cards.js';
import { render } from './render.js';
import { performUndo } from './undo.js';
import { openAddCard } from './cards.js';
import { openFromTextModal } from './ai.js';
import { icon } from './icons.js';

const THEME_STORAGE_KEY = 'stigmer-theme';

export function getStoredTheme() {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return stored === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

function updateThemeMeta() {
  const meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) return;
  const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  if (bg) meta.setAttribute('content', bg);
}

function updateThemeIcon(theme) {
  const themeEl = document.getElementById('theme-icon');
  if (themeEl) {
    themeEl.outerHTML = icon(theme === 'dark' ? 'moon' : 'sun', { size: 14, id: 'theme-icon' });
  }
}

function updateBrandAssets(theme) {
  const light = theme === 'light';
  const mark = document.getElementById('logo-mark');
  if (mark) mark.src = light ? '/img/logo-day.png' : '/img/logo-night.png';
  const favicon = document.getElementById('stigmer-favicon');
  if (favicon) favicon.href = light ? '/img/favicon-32-day.png' : '/img/favicon-32.png';
  const favicon16 = document.getElementById('stigmer-favicon-16');
  if (favicon16) favicon16.href = light ? '/img/favicon-16-day.png' : '/img/favicon-16.png';
}

export function applyTheme(theme) {
  const next = theme === 'light' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, next);
  } catch {
    /* private mode / blocked storage */
  }
  updateThemeMeta();
  updateThemeIcon(next);
  updateBrandAssets(next);
}

export function initTheme() {
  applyTheme(getStoredTheme());
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
}

function restoreBoardFocus() {
  const el = document.activeElement;
  if (el?.closest?.('.modal-overlay, .ai-panel, .ctx-menu')) {
    el.blur();
  }
  if (document.body.tabIndex < 0) document.body.tabIndex = -1;
  document.body.focus({ preventScroll: true });
}

export function closeAllPopups() {
  closeCardModal();
  closeColModal();
  closeLabelsModal();
  closeFromTextModal();
  closeConfirmDeleteModal();
  closeConfirmDeleteCardModal();
  closeCtx();
  closeAskAI();
  restoreBoardFocus();
}

export function closeModal(e) {
  if (e.target === e.currentTarget) {
    closeCardModal();
    closeColModal();
    closeLabelsModal();
    closeFromTextModal(e);
    closeConfirmDeleteModal(e);
    closeConfirmDeleteCardModal(e);
  }
}

function isTextFieldFocused() {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName;
  const isField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
  if (!isField) return false;
  if (el.closest('.modal-overlay.open, .ai-panel.open')) return true;
  if (el.classList.contains('col-title-input')) return true;
  return false;
}

function isShortcutSurface() {
  if (isTextFieldFocused()) return false;
  if (document.querySelector('.modal-overlay.open, .ctx-menu.open, .ai-panel.open')) return false;
  return true;
}

export function setupKeyboardShortcuts() {
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeAllPopups();
      return;
    }
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && isShortcutSurface()) {
      e.preventDefault();
      openAddCard();
      return;
    }
    if (e.key === 'Enter' && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey && isShortcutSurface()) {
      e.preventDefault();
      openFromTextModal();
      return;
    }
    if (e.key === 'n' && !e.ctrlKey && !e.metaKey && isShortcutSurface()) openAddCard();
    if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
      if (isTextFieldFocused()) return;
      e.preventDefault();
      performUndo();
    }
  });
}

function isDevToolsShortcut(e) {
  if (e.key === 'F12' || e.keyCode === 123) return true;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && (e.key === 'u' || e.key === 'U')) return true;
  if (mod && e.altKey && (e.key === 'u' || e.key === 'U' || e.key === 'i' || e.key === 'I')) return true;
  if (mod && e.shiftKey && ['i', 'I', 'j', 'J', 'c', 'C', 'k', 'K'].includes(e.key)) return true;
  return false;
}

export function setupDevToolsGuard() {
  document.addEventListener('keydown', e => {
    if (!isDevToolsShortcut(e)) return;
    e.preventDefault();
    e.stopPropagation();
  }, true);

  document.addEventListener('contextmenu', e => {
    if (e.target.closest('.card, .ctx-menu, input, textarea, select, .col-title-editable')) return;
    e.preventDefault();
  });

  document.addEventListener('selectstart', e => {
    const tag = e.target?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.target?.isContentEditable) return;
    e.preventDefault();
  });
}

export function updateLockButton() {
  const btn = document.getElementById('board-lock-btn');
  const iconEl = document.getElementById('lock-icon');
  if (!btn || !iconEl) return;
  btn.classList.toggle('active', !state.boardLocked);
  btn.title = state.boardLocked ? 'Unlock board layout' : 'Lock board layout';
  btn.setAttribute('aria-label', btn.title);
  iconEl.outerHTML = state.boardLocked
    ? icon('lock', { size: 14, id: 'lock-icon' })
    : icon('lock-open', { size: 14, id: 'lock-icon' });
}

export function toggleBoardLock() {
  state.boardLocked = !state.boardLocked;
  localStorage.setItem('stigmer_board_locked', state.boardLocked ? 'true' : 'false');
  updateLockButton();
  render();
}
