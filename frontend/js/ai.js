import { state } from './state.js';
import { apiFetch, boardPayload } from './api.js';
import {
  persistCardCreate,
  persistCardPatch,
  persistCardDelete,
  persistCardMove,
} from './persist.js';
import { render } from './render.js';
import { toast } from './ui.js';

export function resolveColumnId(ref) {
  if (!ref) return null;
  const lower = String(ref).toLowerCase().trim();
  const byId = state.columns.find(col => col.id.toLowerCase() === lower);
  if (byId) return byId.id;
  const byTitle = state.columns.find(col => col.title.toLowerCase() === lower);
  if (byTitle) return byTitle.id;
  const byPartial = state.columns.find(
    col => col.title.toLowerCase().includes(lower) || col.id.toLowerCase().includes(lower)
  );
  return byPartial ? byPartial.id : null;
}

export async function applyActions(actions) {
  let changed = false;

  for (const action of actions || []) {
    try {
      switch (action.type) {
        case 'add_task': {
          const col = resolveColumnId(action.target_column || action.column || action.col);
          if (!action.title || !col) break;
          const card = await persistCardCreate({
            column_id: col,
            title: action.title,
            desc: action.desc || '',
            labels: action.labels || [],
            card_id: action.task_id || undefined,
          });
          const idx = state.cards.findIndex(item => item.id === card.id);
          if (idx === -1) state.cards.push(card);
          else state.cards[idx] = card;
          changed = true;
          break;
        }
        case 'move_task': {
          const card = state.cards.find(item => item.id === action.task_id);
          const col = resolveColumnId(action.target_column || action.column || action.col);
          if (!card || !col) break;
          card.col = col;
          await persistCardMove(card.id, col);
          changed = true;
          break;
        }
        case 'update_task': {
          const card = state.cards.find(item => item.id === action.task_id);
          if (!card) break;
          const patch = {};
          if (action.title !== undefined) patch.title = action.title;
          if (action.desc !== undefined) patch.desc = action.desc;
          if (action.labels !== undefined) patch.labels = action.labels;
          const col = action.target_column || action.column || action.col;
          if (col) {
            const resolved = resolveColumnId(col);
            if (resolved) patch.column_id = resolved;
          }
          const updated = await persistCardPatch(card.id, patch);
          Object.assign(card, updated);
          changed = true;
          break;
        }
        case 'delete_task': {
          const idx = state.cards.findIndex(item => item.id === action.task_id);
          if (idx === -1) break;
          await persistCardDelete(action.task_id);
          state.cards.splice(idx, 1);
          changed = true;
          break;
        }
        default:
          console.warn('Unknown action type:', action.type);
      }
    } catch (err) {
      console.warn('Failed to apply agent action:', action, err);
    }
  }

  return changed;
}

export function resolveAssistantMessage(result) {
  const message = (result.message || '').trim();
  if (message) return message;

  const parts = [];
  for (const action of result.actions || []) {
    if (action.type === 'comment' || action.type === 'summarize_board') {
      const text = (action.text || action.message || '').trim();
      if (text) parts.push(text);
    }
  }
  if (parts.length) return parts.join('\n');

  if ((result.actions || []).some(a => a.type === 'summarize_board')) {
    const total = state.cards.length;
    const byCol = state.columns.map(col => {
      const n = state.cards.filter(item => item.col === col.id).length;
      return `${col.title}: ${n}`;
    }).join(', ');
    return `Total tasks: ${total}\n${byCol}`;
  }

  return '';
}

export function openFromTextModal() {
  document.getElementById('from-text-modal').classList.add('open');
  const input = document.getElementById('from-text-input');
  input.value = '';
  input.focus();
}

export function closeFromTextModal(event) {
  if (event && event.target !== event.currentTarget) return;
  document.getElementById('from-text-modal').classList.remove('open');
}

export function handleFromTextKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    createTaskFromText();
  }
}

export async function createTaskFromText() {
  const input = document.getElementById('from-text-input');
  const text = input.value.trim();
  if (!text || state.fromTextBusy) return;

  state.fromTextBusy = true;
  const btn = document.getElementById('from-text-submit');
  btn.disabled = true;
  btn.textContent = 'Thinking…';

  try {
    const result = await apiFetch('/api/agent/from-text', {
      method: 'POST',
      body: JSON.stringify({ raw_text: text, board_state: boardPayload() }),
    });
    if (!result.actions?.length) {
      toast(result.message || 'Could not create task');
      return;
    }
    const changed = await applyActions(result.actions);
    if (changed) {
      render();
      closeFromTextModal();
      toast(result.message || 'Task created');
    } else {
      toast('Could not apply task — unknown column');
    }
  } catch (err) {
    toast(`Error: ${err.message || err}`);
  } finally {
    state.fromTextBusy = false;
    btn.disabled = false;
    btn.textContent = 'Create task';
  }
}

export async function runAiCommand(cmd) {
  if (state.aiBusy) return;
  state.aiBusy = true;
  try {
    const result = await apiFetch('/api/agent', {
      method: 'POST',
      body: JSON.stringify({ command: cmd, board_state: boardPayload() }),
    });
    const reply = resolveAssistantMessage(result);
    if (reply) addAiMsg('assistant', reply);
    const changed = await applyActions(result.actions);
    if (changed) {
      render();
    }
  } catch (err) {
    addAiMsg('assistant', `Error: ${err.message || err}`);
  } finally {
    state.aiBusy = false;
  }
}

export function closeAskAI() {
  if (!state.aiOpen) return;
  state.aiOpen = false;
  document.getElementById('ai-panel').classList.remove('open');
  document.getElementById('ask-ai-btn')?.classList.remove('active');
}

export function toggleAskAI() {
  if (state.aiOpen) {
    closeAskAI();
    return;
  }
  state.aiOpen = true;
  document.getElementById('ai-panel').classList.add('open');
  document.getElementById('ask-ai-btn')?.classList.add('active');
  if (state.aiOpen && document.getElementById('ai-messages').children.length === 0) {
    addAiMsg(
      'system',
      'Ask anything about your board — summaries, column contents, counts. To create tasks, use From text.'
    );
  }
  if (state.aiOpen) {
    setTimeout(() => document.getElementById('ai-input')?.focus(), 150);
  }
}

export function addAiMsg(type, text) {
  const msgs = document.getElementById('ai-messages');
  const el = document.createElement('div');
  el.className = `ai-msg ${type}`;
  el.textContent = text;
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
}

export function handleAiKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAiMessage(); }
}

export function sendAiMessage() {
  const input = document.getElementById('ai-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addAiMsg('user', text);
  runAiCommand(text);
}

export function askExample(el) {
  const text = (el.textContent || '').trim();
  if (!text || state.aiBusy) return;
  document.getElementById('ai-input').value = '';
  addAiMsg('user', text);
  runAiCommand(text);
}
