import { state } from './state.js';
import { escHtml, cardIconDots, getCardById, sortCardsForColumn } from './helpers.js';
import { apiFetch, loadBoard } from './api.js';
import {
  persistCardCreate,
  persistCardPatch,
  persistCardDelete,
  persistCardMove,
} from './persist.js';
import { captureMoveState, pushUndo, pushMoveUndo } from './undo.js';
import { renderLabelPicker } from './labels.js';
import { render } from './render.js';
import { toast } from './ui.js';

function getLabel(id) {
  return state.labels.find(l => l.id === id);
}

export function buildCard(card) {
  const el = document.createElement('div');
  const classes = ['card'];
  if (card.pinned) classes.push('card-pinned');
  if (card.flame) classes.push('card-flame');
  el.className = classes.join(' ');
  el.dataset.cardId = card.id;
  el.draggable = !card.pinned;

  if (card.pinned) {
    const showDragDenied = e => {
      if (e.button !== 0) return;
      if (e.target.closest('.card-btn')) return;
      el.classList.add('card-drag-denied');
    };
    const hideDragDenied = () => el.classList.remove('card-drag-denied');
    el.addEventListener('mousedown', showDragDenied);
    el.addEventListener('mouseup', hideDragDenied);
    el.addEventListener('mouseleave', hideDragDenied);
  }

  const labelsHtml = [...(card.labels || [])]
    .map(id => getLabel(id))
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
    .map(def => `<span class="label label-${def.tone}">${escHtml(def.name)}</span>`)
    .join('');
  el.innerHTML = `
    ${labelsHtml ? `<div class="card-labels">${labelsHtml}</div>` : ''}
    <div class="card-title">${escHtml(card.title)}</div>
    <div class="card-meta">
      <div class="card-actions">
        <button class="card-btn card-btn-delete" onclick="event.stopPropagation(); confirmDeleteCard('${card.id}')" title="Delete">
          ${cardIconDots('delete')}
        </button>
        <button class="card-btn card-btn-edit" onclick="event.stopPropagation(); editCard('${card.id}')" title="Edit">
          ${cardIconDots('edit')}
        </button>
        <button class="card-btn card-btn-flame${card.flame ? ' active' : ''}" onclick="event.stopPropagation(); toggleCardFlame('${card.id}')" title="${card.flame ? 'Remove flame' : 'Mark as flame'}">
          ${cardIconDots('flame')}
        </button>
        <button class="card-btn card-btn-pin${card.pinned ? ' active' : ''}" onclick="event.stopPropagation(); toggleCardPin('${card.id}')" title="${card.pinned ? 'Unpin' : 'Pin to top'}">
          ${cardIconDots('pin')}
        </button>
      </div>
    </div>
  `;

  el.addEventListener('contextmenu', e => { e.preventDefault(); openCtx(e, card.id); });
  el.addEventListener('dblclick', e => {
    if (e.target.closest('.card-btn')) return;
    e.stopPropagation();
    editCard(card.id);
  });
  return el;
}

export function setupDnd() {
  document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('dragstart', e => {
      const data = getCardById(card.dataset.cardId);
      if (data?.pinned) {
        e.preventDefault();
        return;
      }
      state.dragId = card.dataset.cardId;
      state.dragColIdFrom = null;
      state.dragUndoSnapshot = captureMoveState(state.dragId);
      setTimeout(() => card.classList.add('dragging'), 0);
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', 'card:' + state.dragId);
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      state.dragUndoSnapshot = null;
      document.querySelectorAll('.drag-over-above,.drag-over-below').forEach(el => {
        el.classList.remove('drag-over-above', 'drag-over-below');
      });
      document.querySelectorAll('.col.drop-target').forEach(el => el.classList.remove('drop-target'));
    });
    card.addEventListener('dragover', e => {
      if (state.dragColIdFrom) return;
      e.preventDefault();
      if (!state.dragId || card.dataset.cardId === state.dragId) return;
      document.querySelectorAll('.drag-over-above,.drag-over-below').forEach(el => {
        el.classList.remove('drag-over-above', 'drag-over-below');
      });
      const rect = card.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      card.classList.add(e.clientY < midY ? 'drag-over-above' : 'drag-over-below');
    });
    card.addEventListener('drop', e => {
      if (state.dragColIdFrom) return;
      e.preventDefault();
      e.stopPropagation();
      if (!state.dragId || card.dataset.cardId === state.dragId) return;
      const targetId = card.dataset.cardId;
      const dragCard = getCardById(state.dragId);
      const targetCard = getCardById(targetId);
      if (!dragCard || !targetCard) return;
      if (dragCard.pinned && dragCard.col !== targetCard.col) {
        toast('Unpin the task to move it to another column');
        return;
      }
      const rect = card.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      const insertBefore = e.clientY < midY;
      dragCard.col = targetCard.col;
      const fromIdx = state.cards.indexOf(dragCard);
      state.cards.splice(fromIdx, 1);
      let toIdx = state.cards.indexOf(targetCard);
      if (!insertBefore) toIdx++;
      state.cards.splice(toIdx, 0, dragCard);
      pushMoveUndo(state.dragUndoSnapshot);
      state.dragUndoSnapshot = null;
      render();
      persistCardMove(dragCard.id, dragCard.col).catch(err => {
        console.warn('Failed to move card:', err);
        toast('Failed to move card');
        loadBoard();
      });
    });
  });

  document.querySelectorAll('.col').forEach(col => {
    const colId = col.dataset.colId;
    const cardsArea = col.querySelector('.cards');

    col.addEventListener('dragover', e => {
      if (state.dragColIdFrom) return;
      e.preventDefault();
      col.classList.add('drop-target');
    });
    col.addEventListener('dragleave', e => {
      if (!col.contains(e.relatedTarget)) col.classList.remove('drop-target');
    });
    cardsArea.addEventListener('drop', e => {
      if (state.dragColIdFrom) return;
      e.preventDefault();
      if (!state.dragId) return;
      const dragCard = getCardById(state.dragId);
      if (!dragCard) return;
      if (!e.target.closest('.card')) {
        if (dragCard.pinned && dragCard.col !== colId) {
          toast('Unpin the task to move it to another column');
          return;
        }
        dragCard.col = colId;
        pushMoveUndo(state.dragUndoSnapshot);
        state.dragUndoSnapshot = null;
        render();
        persistCardMove(dragCard.id, colId)
          .then(() => toast(`Moved to ${state.columns.find(c => c.id === colId)?.title}`))
          .catch(err => {
            console.warn('Failed to move card:', err);
            toast('Failed to move card');
            loadBoard();
          });
      }
      col.classList.remove('drop-target');
    });
  });
}

export function openAddCard(colId) {
  state.currentColForAdd = colId || state.columns[0]?.id;
  state.editingCardId = null;
  state.selectedLabels = [];
  document.getElementById('modal-title').textContent = 'New task';
  document.getElementById('card-title-input').value = '';
  document.getElementById('card-desc-input').value = '';
  document.getElementById('card-col-input').value = state.currentColForAdd;
  renderLabelPicker();
  document.querySelectorAll('.label-picker .label').forEach(el => el.classList.remove('selected'));
  document.getElementById('card-modal').classList.add('open');
  setTimeout(() => document.getElementById('card-title-input').focus(), 50);
}

export function editCard(id) {
  const card = state.cards.find(c => c.id === id);
  if (!card) return;
  state.editingCardId = id;
  state.selectedLabels = [...(card.labels || [])];
  document.getElementById('modal-title').textContent = 'Edit task';
  document.getElementById('card-title-input').value = card.title;
  document.getElementById('card-desc-input').value = card.desc || '';
  document.getElementById('card-col-input').value = card.col;
  renderLabelPicker();
  document.querySelectorAll('.label-picker .label').forEach(el => {
    el.classList.toggle('selected', (card.labels || []).includes(el.dataset.label));
  });
  document.getElementById('card-modal').classList.add('open');
}

function cloneCard(card) {
  return {
    id: card.id,
    title: card.title,
    desc: card.desc || '',
    col: card.col,
    labels: [...(card.labels || [])],
    pinned: !!card.pinned,
    flame: !!card.flame,
  };
}

export function saveCard() {
  const title = document.getElementById('card-title-input').value.trim();
  if (!title) { document.getElementById('card-title-input').focus(); return; }
  const col = document.getElementById('card-col-input').value;
  const desc = document.getElementById('card-desc-input').value.trim();

  if (state.editingCardId) {
    const card = state.cards.find(c => c.id === state.editingCardId);
    if (card) {
      const before = {
        title: card.title,
        desc: card.desc || '',
        col: card.col,
        labels: [...(card.labels || [])],
      };
      const arrayIndex = state.cards.indexOf(card);
      const patch = { title, column_id: col, desc, labels: [...state.selectedLabels] };
      card.title = title;
      card.col = col;
      card.desc = desc;
      card.labels = [...state.selectedLabels];
      persistCardPatch(card.id, patch)
        .then(serverCard => {
          Object.assign(card, serverCard);
          pushUndo({ type: 'edit', cardId: card.id, before, arrayIndex });
          render();
          toast('Task updated');
        })
        .catch(err => {
          console.warn('Failed to update task:', err);
          toast('Failed to update task');
          loadBoard();
        });
    }
  } else {
    persistCardCreate({
      column_id: col,
      title,
      desc,
      labels: [...state.selectedLabels],
    })
      .then(serverCard => {
        state.cards.push(serverCard);
        pushUndo({ type: 'create', cardId: serverCard.id });
        render();
        toast('Task added');
      })
      .catch(err => {
        console.warn('Failed to create task:', err);
        toast('Failed to create task');
      });
  }
  const wasEdit = !!state.editingCardId;
  closeCardModal();
  if (wasEdit) {
    render();
  }
}

function deleteCard(id) {
  const idx = state.cards.findIndex(c => c.id === id);
  if (idx === -1) return;
  const snapshot = cloneCard(state.cards[idx]);
  state.cards.splice(idx, 1);
  pushUndo({ type: 'delete', card: snapshot, insertIndex: idx });
  render();
  persistCardDelete(id)
    .then(() => toast('Task deleted'))
    .catch(err => {
      console.warn('Failed to delete task:', err);
      toast('Failed to delete task');
      loadBoard();
    });
}

export function confirmDeleteCard(id) {
  const card = state.cards.find(c => c.id === id);
  if (!card) return;
  state.pendingDeleteCardId = id;
  const preview = card.title.split('\n')[0].trim();
  const short = preview.length > 56 ? `${preview.slice(0, 53)}…` : preview;
  document.getElementById('confirm-delete-card-title').textContent = short ? `Delete “${short}”?` : 'Delete task?';
  document.getElementById('confirm-delete-card-body').textContent = 'This cannot be undone.';
  document.getElementById('confirm-delete-card-modal').classList.add('open');
}

export function closeConfirmDeleteCardModal(event) {
  if (event && event.target !== event.currentTarget) return;
  document.getElementById('confirm-delete-card-modal').classList.remove('open');
  state.pendingDeleteCardId = null;
}

export function executeDeleteCard() {
  const id = state.pendingDeleteCardId;
  closeConfirmDeleteCardModal();
  if (!id) return;
  deleteCard(id);
}

export function toggleCardPin(id) {
  const card = state.cards.find(c => c.id === id);
  if (!card) return;
  card.pinned = !card.pinned;
  render();
  persistCardPatch(id, { pinned: card.pinned })
    .then(() => toast(card.pinned ? 'Task pinned' : 'Task unpinned'))
    .catch(err => {
      console.warn('Failed to toggle pin:', err);
      toast('Failed to update task');
      loadBoard();
    });
}

export function toggleCardFlame(id) {
  const card = state.cards.find(c => c.id === id);
  if (!card) return;
  card.flame = !card.flame;
  render();
  persistCardPatch(id, { flame: card.flame })
    .then(() => toast(card.flame ? 'Task marked as flame' : 'Flame removed'))
    .catch(err => {
      console.warn('Failed to toggle flame:', err);
      toast('Failed to update task');
      loadBoard();
    });
}

export function toggleLabel(el) {
  const label = el.dataset.label;
  if (state.selectedLabels.includes(label)) {
    state.selectedLabels = state.selectedLabels.filter(l => l !== label);
    el.classList.remove('selected');
  } else {
    state.selectedLabels.push(label);
    el.classList.add('selected');
  }
}

export function closeCardModal() {
  document.getElementById('card-modal').classList.remove('open');
  state.editingCardId = null;
}

export function openCtx(e, cardId) {
  state.ctxCardId = cardId;
  const card = state.cards.find(c => c.id === cardId);
  const pinLabel = document.getElementById('ctx-pin-label');
  const flameLabel = document.getElementById('ctx-flame-label');
  if (pinLabel) pinLabel.textContent = card?.pinned ? 'Unpin' : 'Pin to top';
  if (flameLabel) flameLabel.textContent = card?.flame ? 'Remove flame' : 'Mark as flame';
  const menu = document.getElementById('ctx-menu');
  menu.style.left = Math.min(e.clientX, window.innerWidth - 180) + 'px';
  menu.style.top = Math.min(e.clientY, window.innerHeight - 200) + 'px';
  menu.classList.add('open');
  e.stopPropagation();
}

export function closeCtx() {
  document.getElementById('ctx-menu').classList.remove('open');
}

export function ctxEdit() {
  closeCtx();
  editCard(state.ctxCardId);
}

export function ctxTogglePin() {
  closeCtx();
  toggleCardPin(state.ctxCardId);
}

export function ctxToggleFlame() {
  closeCtx();
  toggleCardFlame(state.ctxCardId);
}

export function ctxDelete() {
  closeCtx();
  confirmDeleteCard(state.ctxCardId);
}

export function ctxMove(dir) {
  closeCtx();
  const card = state.cards.find(c => c.id === state.ctxCardId);
  if (!card) return;
  const before = captureMoveState(state.ctxCardId);
  const colIdx = state.columns.findIndex(c => c.id === card.col);
  const newIdx = colIdx + dir;
  if (newIdx < 0 || newIdx >= state.columns.length) return;
  card.col = state.columns[newIdx].id;
  pushMoveUndo(before);
  render();
  persistCardMove(card.id, card.col)
    .then(() => toast(`Moved to ${state.columns[newIdx].title}`))
    .catch(err => {
      console.warn('Failed to move card:', err);
      toast('Failed to move card');
      loadBoard();
    });
}

export function setupCtxClickClose() {
  document.addEventListener('click', closeCtx);
}
