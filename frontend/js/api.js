import { state } from './state.js';
import { clearUndoStack } from './undo.js';

export const API_KEY = localStorage.getItem('stigmer_api_key') || 'dev-key';

export function boardPayload() {
  return { columns: state.columns, cards: state.cards, labels: state.labels };
}

export function parseApiError(text) {
  try {
    const data = JSON.parse(text);
    if (data.detail) {
      return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }
  } catch (_) { /* not JSON */ }
  return text;
}

export async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(parseApiError(detail) || res.statusText);
  }
  return res.json();
}

export async function loadBoard() {
  try {
    const data = await apiFetch('/api/board');
    if (Array.isArray(data.columns)) {
      state.columns = data.columns;
      state.cards = data.cards || [];
      state.labels = data.labels || [];
      clearUndoStack();
      return true;
    }
  } catch (err) {
    console.warn('Backend unavailable, using local state:', err);
  }
  return false;
}
