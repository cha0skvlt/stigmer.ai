import { state, undoStack } from './state.js';
import { getCardById } from './helpers.js';
import {
  persistCardCreate,
  persistCardDelete,
  persistCardMove,
  persistCardPatch,
} from './persist.js';
import { loadBoard } from './api.js';
import { render } from './render.js';
import { toast } from './ui.js';

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

export function captureMoveState(cardId) {
  const card = getCardById(cardId);
  if (!card) return null;
  return {
    cardId,
    col: card.col,
    arrayIndex: state.cards.indexOf(card),
  };
}

export function pushUndo(entry) {
  if (!state.undoRecording) return;
  undoStack.push(entry);
  updateUndoButton();
}

export function pushMoveUndo(before) {
  if (!before) return;
  const card = getCardById(before.cardId);
  if (!card) return;
  if (card.col === before.col && state.cards.indexOf(card) === before.arrayIndex) return;
  pushUndo({ type: 'move', ...before });
}

export function clearUndoStack() {
  undoStack.length = 0;
  updateUndoButton();
}

export function updateUndoButton() {
  const btn = document.getElementById('undo-btn');
  if (!btn) return;
  const canUndo = undoStack.length > 0;
  btn.disabled = !canUndo;
  btn.setAttribute('aria-disabled', canUndo ? 'false' : 'true');
}

function restoreCardOrder(cardId, arrayIndex) {
  const card = getCardById(cardId);
  if (!card) return;
  const fromIdx = state.cards.indexOf(card);
  if (fromIdx === -1) return;
  state.cards.splice(fromIdx, 1);
  const idx = Math.max(0, Math.min(arrayIndex, state.cards.length));
  state.cards.splice(idx, 0, card);
}

async function applyUndo(entry) {
  switch (entry.type) {
    case 'delete': {
      const created = await persistCardCreate({
        column_id: entry.card.col,
        title: entry.card.title,
        desc: entry.card.desc,
        labels: entry.card.labels,
        card_id: entry.card.id,
        pinned: entry.card.pinned,
        flame: entry.card.flame,
      });
      const idx = Math.min(entry.insertIndex, state.cards.length);
      state.cards.splice(idx, 0, created);
      await persistCardMove(created.id, created.col);
      break;
    }
    case 'edit': {
      const card = getCardById(entry.cardId);
      if (!card) throw new Error('Card not found');
      const patch = {
        title: entry.before.title,
        desc: entry.before.desc,
        column_id: entry.before.col,
        labels: [...entry.before.labels],
      };
      card.title = patch.title;
      card.col = patch.column_id;
      card.desc = patch.desc;
      card.labels = patch.labels;
      restoreCardOrder(entry.cardId, entry.arrayIndex);
      const updated = await persistCardPatch(entry.cardId, patch);
      Object.assign(card, updated);
      await persistCardMove(entry.cardId, entry.before.col);
      break;
    }
    case 'create': {
      const idx = state.cards.findIndex(c => c.id === entry.cardId);
      if (idx !== -1) state.cards.splice(idx, 1);
      await persistCardDelete(entry.cardId);
      break;
    }
    case 'move': {
      const card = getCardById(entry.cardId);
      if (!card) throw new Error('Card not found');
      card.col = entry.col;
      restoreCardOrder(entry.cardId, entry.arrayIndex);
      await persistCardMove(entry.cardId, entry.col);
      break;
    }
    default:
      throw new Error('Unknown undo entry');
  }
}

export async function performUndo() {
  if (undoStack.length === 0) return;
  const entry = undoStack.pop();
  updateUndoButton();
  state.undoRecording = false;
  try {
    await applyUndo(entry);
    render();
    toast('Undone');
  } catch (err) {
    console.warn('Undo failed:', err);
    toast('Undo failed');
    await loadBoard();
    render();
  } finally {
    state.undoRecording = true;
  }
}
