import { state } from './state.js';

export function getCardById(cardId) {
  return state.cards.find(c => c.id === cardId);
}

export function escHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export function sortCardsForColumn(cards) {
  return cards
    .map((card, index) => ({ card, index }))
    .sort((a, b) => {
      const ap = a.card.pinned ? 1 : 0;
      const bp = b.card.pinned ? 1 : 0;
      if (ap !== bp) return bp - ap;
      return a.index - b.index;
    })
    .map(entry => entry.card);
}

export function formatColCount(n) {
  return String(n).padStart(2, '0');
}
