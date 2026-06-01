import { state, DOT_PICKER_COLORS } from './state.js';
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

export function renderDotPicker() {
  const picker = document.getElementById('dot-picker');
  if (!picker) return;
  const selected = state.selectedDotColor;
  picker.innerHTML = DOT_PICKER_COLORS.map(color => {
    const active = color === selected ? '2px solid var(--text)' : '2px solid transparent';
    return `<span style="width:20px;height:20px;border-radius:50%;background:${color};cursor:pointer;border:${active}" data-color="${color}" onclick="selectDot(this)"></span>`;
  }).join('');
}

export function selectDot(el) {
  state.selectedDotColor = el.dataset.color;
  renderDotPicker();
}

export function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  document.getElementById('theme-icon').innerHTML = next === 'dark'
    ? '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>'
    : '<circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>';
}

export function toast(msg) {
  const container = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 2500);
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
  const icon = document.getElementById('lock-icon');
  if (!btn || !icon) return;
  btn.classList.toggle('active', !state.boardLocked);
  btn.title = state.boardLocked ? 'Unlock board layout' : 'Lock board layout';
  btn.setAttribute('aria-label', btn.title);
  icon.innerHTML = state.boardLocked
    ? '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'
    : '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-1"/>';
}

export function toggleBoardLock() {
  state.boardLocked = !state.boardLocked;
  localStorage.setItem('kaban_board_locked', state.boardLocked ? 'true' : 'false');
  updateLockButton();
  render();
  toast(state.boardLocked ? 'Board layout locked — tasks still move' : 'Board layout unlocked — drag or double-click columns');
}
