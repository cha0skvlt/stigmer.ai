import { API_KEY, apiFetch, loadBoard } from './api.js';
import { state } from './state.js';
import { render } from './render.js';
import { updateColSelects } from './columns.js';

let boardWs = null;
let boardWsBackoffMs = 250;
let boardWsReloadTimer = null;

export function connectBoardWs() {
  try {
    if (boardWs) boardWs.close();
  } catch (_) {}

  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws/board?api_key=${encodeURIComponent(API_KEY)}`;
  boardWs = new WebSocket(url);

  boardWs.onopen = () => {
    boardWsBackoffMs = 250;
  };

  let pendingCardOps = new Map();
  let pendingColumns = false;
  let pendingLabels = false;
  let flushTimer = null;

  function scheduleFlush() {
    if (flushTimer) return;
    flushTimer = setTimeout(flush, 60);
  }

  async function flush() {
    flushTimer = null;

    const cardOps = pendingCardOps;
    const doColumns = pendingColumns;
    const doLabels = pendingLabels;

    pendingCardOps = new Map();
    pendingColumns = false;
    pendingLabels = false;

    try {
      if (doColumns) {
        const data = await apiFetch('/api/columns');
        state.columns = data.columns || state.columns;
        updateColSelects();
      }
      if (doLabels) {
        const data = await apiFetch('/api/labels');
        state.labels = data.labels || state.labels;
      }

      const entries = [...cardOps.entries()];
      if (entries.length) {
        const deletions = new Set(entries.filter(([, op]) => op === 'DELETE').map(([id]) => id));
        if (deletions.size) {
          state.cards = state.cards.filter(c => !deletions.has(c.id));
        }

        const toFetch = entries.filter(([, op]) => op !== 'DELETE').map(([id]) => id);
        if (toFetch.length) {
          const results = await Promise.allSettled(
            toFetch.map(id => apiFetch(`/api/cards/${encodeURIComponent(id)}`))
          );
          for (const res of results) {
            if (res.status !== 'fulfilled') continue;
            const card = res.value;
            const idx = state.cards.findIndex(c => c.id === card.id);
            if (idx === -1) state.cards.push(card);
            else state.cards[idx] = card;
          }
        }
      }

      render();
    } catch (err) {
      console.warn('Incremental sync failed, falling back to reload:', err);
      await loadBoard();
      render();
    }
  }

  boardWs.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type !== 'board.changed') return;
      const p = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload;
      const op = p.op;
      const table = p.table;
      const id = p.id;

      if (table === 'cards') {
        pendingCardOps.set(id, op);
        scheduleFlush();
        return;
      }
      if (table === 'card_labels') {
        pendingCardOps.set(id, 'UPDATE');
        scheduleFlush();
        return;
      }
      if (table === 'columns') {
        pendingColumns = true;
        scheduleFlush();
        return;
      }
      if (table === 'labels') {
        pendingLabels = true;
        scheduleFlush();
        return;
      }

      boardWsReloadTimer = setTimeout(async () => {
        boardWsReloadTimer = null;
        await loadBoard();
        render();
      }, 150);
    } catch (err) {
      console.warn('Bad ws message:', err);
    }
  };

  boardWs.onclose = () => {
    const wait = boardWsBackoffMs;
    boardWsBackoffMs = Math.min(boardWsBackoffMs * 2, 8000);
    setTimeout(connectBoardWs, wait);
  };

  boardWs.onerror = () => {
    try {
      boardWs.close();
    } catch (_) {}
  };
}
