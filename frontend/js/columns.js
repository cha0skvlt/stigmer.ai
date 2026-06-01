import {
  state,
  c,
  COLOR_PALETTE,
  COLUMN_PALETTE,
} from './state.js';
import { escHtml, sortCardsForColumn, formatColCount } from './helpers.js';
import { icon } from './icons.js';
import { apiFetch, loadBoard } from './api.js';
import { render } from './render.js';
import { buildCard } from './cards.js';

export function ensureDefaultColumns() {
  const defaults = COLUMN_PALETTE.map(col => ({ ...col }));
  const defaultById = Object.fromEntries(defaults.map(col => [col.id, col]));
  const existing = (state.columns || []).filter(col => col && col.id);
  if (existing.length === 0) {
    state.columns = defaults.map(col => ({ ...col }));
    return;
  }
  const seen = new Set();
  const merged = [];
  const legacyColors = { '#7c5cfc': COLOR_PALETTE.purple };
  for (const col of existing) {
    seen.add(col.id);
    const mergedCol = { ...defaultById[col.id], ...col };
    const hex = (mergedCol.color || '').toLowerCase();
    if (legacyColors[hex]) mergedCol.color = legacyColors[hex];
    merged.push(mergedCol);
  }
  for (const col of defaults) {
    if (!seen.has(col.id)) merged.push({ ...col });
  }
  state.columns = merged;
}

export function updateColSelects() {
  const sel = document.getElementById('card-col-input');
  sel.innerHTML = state.columns.map(c => `<option value="${c.id}">${c.title}</option>`).join('');
  if (state.currentColForAdd) sel.value = state.currentColForAdd;
}

export function buildCol(col, cards) {
  const el = document.createElement('div');
  el.className = state.boardLocked ? 'col' : 'col col-draggable';
  el.dataset.colId = col.id;
  if (!state.boardLocked) el.draggable = true;
  const titleClass = [
    'col-title',
    state.boardLocked ? '' : 'col-title-editable',
  ].filter(Boolean).join(' ');
  el.innerHTML = `
    <div class="col-header">
      <span class="${titleClass}" data-col-id="${col.id}">${escHtml(col.title)}</span>
      <span class="col-count">${formatColCount(cards.length)}</span>
      <button class="col-add" onclick="openAddCard('${col.id}')" title="Add task" aria-label="Add task">
        ${icon('plus', { size: 12 })}
      </button>
    </div>
    <div class="cards" data-col-id="${col.id}"></div>
  `;
  const cardsEl = el.querySelector('.cards');
  sortCardsForColumn(cards).forEach(card => cardsEl.appendChild(buildCard(card)));
  if (!state.boardLocked) {
    const footer = document.createElement('div');
    footer.className = 'col-footer';
    footer.innerHTML = `
      <button type="button" class="col-delete-btn" onclick="event.stopPropagation(); confirmDeleteColumn('${col.id}')" title="Delete column" aria-label="Delete column">
        ${icon('trash-2', { size: 14 })}
      </button>
    `;
    el.appendChild(footer);
  }
  return el;
}

function clearColDropMarkers() {
  document.querySelectorAll('.col-drag-over-before,.col-drag-over-after').forEach(el => {
    el.classList.remove('col-drag-over-before', 'col-drag-over-after');
  });
}

function getColInsertIndex(clientX) {
  const cols = [...document.querySelectorAll('#board > .col')];
  for (let i = 0; i < cols.length; i++) {
    const rect = cols[i].getBoundingClientRect();
    if (clientX < rect.left + rect.width / 2) return i;
  }
  return cols.length;
}

function updateColDropMarker(clientX) {
  clearColDropMarkers();
  const cols = [...document.querySelectorAll('#board > .col')];
  if (!cols.length) return;
  const insertIndex = getColInsertIndex(clientX);
  if (insertIndex < cols.length) {
    cols[insertIndex].classList.add('col-drag-over-before');
  } else {
    cols[cols.length - 1].classList.add('col-drag-over-after');
  }
}

function moveColumnToIndex(fromId, insertIndex) {
  const fromIdx = state.columns.findIndex(col => col.id === fromId);
  if (fromIdx === -1) return false;
  const [col] = state.columns.splice(fromIdx, 1);
  let target = insertIndex;
  if (fromIdx < target) target--;
  target = Math.max(0, Math.min(target, state.columns.length));
  state.columns.splice(target, 0, col);
  return fromIdx !== target;
}

function finishColDrag() {
  state.dragColIdFrom = null;
  clearColDropMarkers();
  document.getElementById('board')?.classList.remove('col-reorder-active');
}

export function setupBoardColDnD() {
  if (state.boardColDnDReady) return;
  state.boardColDnDReady = true;
  const wrap = document.querySelector('.board-wrap');
  wrap.addEventListener('dragover', e => {
    if (!state.dragColIdFrom) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    updateColDropMarker(e.clientX);
  }, true);
  wrap.addEventListener('drop', e => {
    if (!state.dragColIdFrom) return;
    e.preventDefault();
    e.stopPropagation();
    const insertIndex = getColInsertIndex(e.clientX);
    const fromIdx = state.columns.findIndex(col => col.id === state.dragColIdFrom);
    const colIdFrom = state.dragColIdFrom;
    const moved = moveColumnToIndex(colIdFrom, insertIndex);
    const finalIndex = moved ? state.columns.findIndex(col => col.id === colIdFrom) : fromIdx;
    finishColDrag();
    if (moved) {
      render();
      apiFetch(`/api/columns/${encodeURIComponent(colIdFrom)}/move`, {
        method: 'POST',
        body: JSON.stringify({ index: finalIndex }),
      })
        .catch(err => {
          console.warn('Failed to move column:', err);
          loadBoard();
        });
    } else {
      render();
    }
  }, true);
  wrap.addEventListener('dragleave', e => {
    if (!state.dragColIdFrom) return;
    if (!wrap.contains(e.relatedTarget)) clearColDropMarkers();
  }, true);
}

export function setupColDrag() {
  document.querySelectorAll('.col.col-draggable').forEach(colEl => {
    colEl.addEventListener('dragstart', e => {
      if (e.target.closest('.card') || e.target.closest('.col-add') || e.target.closest('.col-title-input')) {
        e.preventDefault();
        return;
      }
      state.dragColIdFrom = colEl.dataset.colId;
      state.dragId = null;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', 'column:' + state.dragColIdFrom);
      setTimeout(() => colEl.classList.add('col-dragging'), 0);
      document.getElementById('board')?.classList.add('col-reorder-active');
    });
    colEl.addEventListener('dragend', () => {
      colEl.classList.remove('col-dragging');
      finishColDrag();
    });
  });

  document.querySelectorAll('.col-title-editable').forEach(titleEl => {
    titleEl.addEventListener('dblclick', e => {
      e.stopPropagation();
      startColRename(titleEl.dataset.colId, titleEl);
    });
  });
}

function startColRename(colId, titleEl) {
  if (state.boardLocked) return;
  const col = state.columns.find(item => item.id === colId);
  if (!col || titleEl.tagName === 'INPUT') return;
  const input = document.createElement('input');
  input.className = 'col-title-input';
  input.value = col.title;
  titleEl.replaceWith(input);
  input.focus();
  input.select();
  const finish = (save) => {
    if (save) {
      const name = input.value.trim();
      if (name) col.title = name;
      render();
      apiFetch(`/api/columns/${encodeURIComponent(colId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: name || col.title }),
      })
        .catch(err => {
          console.warn('Failed to rename column:', err);
          loadBoard();
        });
    } else {
      render();
    }
  };
  input.addEventListener('blur', () => finish(true));
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { e.preventDefault(); finish(false); }
  });
}

export function confirmDeleteColumn(colId) {
  if (state.boardLocked) {
    return;
  }
  if (state.columns.length <= 1) {
    return;
  }
  const col = state.columns.find(c => c.id === colId);
  if (!col) return;
  const count = state.cards.filter(c => c.col === colId).length;
  state.pendingDeleteColId = colId;
  document.getElementById('confirm-delete-title').textContent = `Delete “${col.title}”?`;
  document.getElementById('confirm-delete-body').textContent =
    count > 0
      ? `This will permanently delete the column and all ${count} task(s) inside. This cannot be undone.`
      : 'This will permanently delete the column. This cannot be undone.';
  document.getElementById('confirm-delete-modal').classList.add('open');
}

export function closeConfirmDeleteModal(event) {
  if (event && event.target !== event.currentTarget) return;
  document.getElementById('confirm-delete-modal').classList.remove('open');
  state.pendingDeleteColId = null;
}

export async function executeDeleteColumn() {
  const colId = state.pendingDeleteColId;
  if (!colId) return;
  const col = state.columns.find(c => c.id === colId);
  const title = col?.title || colId;
  closeConfirmDeleteModal();
  try {
    await apiFetch(`/api/columns/${encodeURIComponent(colId)}`, { method: 'DELETE' });
    state.columns = state.columns.filter(c => c.id !== colId);
    state.cards = state.cards.filter(c => c.col !== colId);
    render();
  } catch (err) {
    console.warn('Failed to delete column:', err);
    loadBoard();
  }
}

export function openAddColModal() {
  if (state.boardLocked) {
    return;
  }
  document.getElementById('col-name-input').value = '';
  document.getElementById('col-modal').classList.add('open');
  setTimeout(() => document.getElementById('col-name-input').focus(), 50);
}

export async function saveColumn() {
  const name = document.getElementById('col-name-input').value.trim();
  if (!name) return;
  const id = name.toLowerCase().replace(/\s+/g, '-') + '-' + c();
  try {
    const col = await apiFetch('/api/columns', {
      method: 'POST',
      body: JSON.stringify({ slug: id, title: name, color: COLOR_PALETTE.neutral }),
    });
    state.columns.push(col);
    closeColModal();
    render();
  } catch (err) {
    console.warn('Failed to create column:', err);
  }
}

export function closeColModal() {
  document.getElementById('col-modal').classList.remove('open');
}
