import { state } from './state.js';
import { sortCardsForColumn } from './helpers.js';
import { apiFetch } from './api.js';

export const STARTER_CARD = {
  id: 'stigmer-starter',
  col: 'ideas',
  title: [
    'Welcome to STIGMER AI',
    'Try "From text" — paste a note, get a task',
    'Use AI chat to move cards or summarize',
    'Drag cards across columns as work progresses',
    'Delete this card anytime',
  ].join('\n'),
  labels: ['purple'],
  desc: '',
};

export async function ensureStarterCard() {
  if (state.cards.length > 0) return;
  try {
    const card = await persistCardCreate({
      column_id: 'ideas',
      title: STARTER_CARD.title,
      desc: '',
      labels: ['purple'],
      card_id: STARTER_CARD.id,
    });
    state.cards.push(card);
  } catch (err) {
    console.warn('Failed to create starter card:', err);
  }
}

export function cardIdsForColumn(colId) {
  const visible = sortCardsForColumn(state.cards.filter(c => c.col === colId));
  return visible.map(c => c.id);
}

export async function persistCardMove(cardId, columnId) {
  const ids = cardIdsForColumn(columnId);
  const idx = ids.indexOf(cardId);
  const beforeCardId = idx !== -1 ? (ids[idx + 1] || null) : null;
  await apiFetch(`/api/cards/${encodeURIComponent(cardId)}/move`, {
    method: 'POST',
    body: JSON.stringify({
      column_id: columnId,
      before_card_id: beforeCardId,
    }),
  });
}

export async function persistCardPatch(cardId, patch) {
  return await apiFetch(`/api/cards/${encodeURIComponent(cardId)}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}

export async function persistCardCreate(payload) {
  return await apiFetch('/api/cards', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function persistCardDelete(cardId) {
  await apiFetch(`/api/cards/${encodeURIComponent(cardId)}`, { method: 'DELETE' });
}
