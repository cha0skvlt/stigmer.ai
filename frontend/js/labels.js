import {
  state,
  c,
  DEFAULT_LABELS,
  LABEL_TONES,
  LABEL_TONE_NAMES,
} from './state.js';
import { escHtml } from './helpers.js';
import { icon } from './icons.js';
import { apiFetch, loadBoard } from './api.js';
import { render } from './render.js';

function labelToneOptionsHtml(selected) {
  return LABEL_TONES.map(
    tone => `<option value="${tone}"${tone === selected ? ' selected' : ''}>${LABEL_TONE_NAMES[tone]}</option>`
  ).join('');
}

export function syncLabelToneSelects(selected = 'purple') {
  const addSelect = document.getElementById('new-label-tone');
  if (addSelect) {
    addSelect.innerHTML = labelToneOptionsHtml(selected);
  }
}

export function ensureDefaultLabels() {
  const defaults = DEFAULT_LABELS;
  const existing = (state.labels || []).filter(lbl => lbl && lbl.id);
  if (existing.length === 0) {
    state.labels = defaults.map(lbl => ({ ...lbl }));
    return;
  }
  const defaultById = Object.fromEntries(defaults.map(lbl => [lbl.id, lbl]));
  const seen = new Set();
  const merged = [];
  for (const lbl of existing) {
    seen.add(lbl.id);
    const base = defaultById[lbl.id] || { tone: 'purple', emoji: '🏷️' };
    const tone = LABEL_TONES.includes(lbl.tone) ? lbl.tone : (base.tone || 'purple');
    merged.push({
      id: lbl.id,
      name: (lbl.name || base.name || lbl.id).trim(),
      tone,
      emoji: lbl.emoji || base.emoji || '🏷️',
    });
  }
  for (const lbl of defaults) {
    if (!seen.has(lbl.id)) merged.push({ ...lbl });
  }
  state.labels = merged;
  const validIds = new Set(state.labels.map(l => l.id));
  for (const card of state.cards) {
    card.labels = (card.labels || []).filter(id => validIds.has(id));
  }
}

function getLabel(id) {
  return state.labels.find(l => l.id === id);
}

function labelSlug(name) {
  const base = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'label';
  let id = base;
  if (state.labels.some(l => l.id === id)) id = `${base}-${c()}`;
  return id;
}

export function renderLabelPicker() {
  const picker = document.getElementById('label-picker');
  if (!picker) return;
  picker.innerHTML = [...state.labels]
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
    .map(def => {
      const sel = state.selectedLabels.includes(def.id) ? ' selected' : '';
      return `<span class="label label-${def.tone}${sel}" data-label="${def.id}" onclick="toggleLabel(this)">${escHtml(def.name)}</span>`;
    }).join('');
}

export function labelToneControlHtml(tone, onChangeAttr) {
  const t = LABEL_TONES.includes(tone) ? tone : 'purple';
  return `<span class="label-tone-wrap">
    <button type="button" class="label-tone-trigger label-text-${t}" onclick="openLabelToneSelect(this)">
      <span class="label-tone-text">${LABEL_TONE_NAMES[t] || t}</span>
      <svg class="label-tone-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
    </button>
    <select class="label-row-tone" ${onChangeAttr} aria-hidden="true" tabindex="-1">
      ${labelToneOptionsHtml(t)}
    </select>
  </span>`;
}

export function openLabelToneSelect(btn) {
  const select = btn.closest('.label-tone-wrap')?.querySelector('.label-row-tone');
  if (!select) return;
  if (typeof select.showPicker === 'function') {
    select.showPicker();
  } else {
    select.focus();
    select.click();
  }
}

export function fitLabelNameInput(input) {
  if (!input) return;
  input.removeAttribute('size');
}

function initLabelNameInputs(root) {
  const scope = root || document;
  scope.querySelectorAll('.label-row-name').forEach(input => {
    fitLabelNameInput(input);
    if (input.dataset.fitBound) return;
    input.dataset.fitBound = '1';
    input.addEventListener('input', () => fitLabelNameInput(input));
  });
}

export function renderLabelsManager() {
  const list = document.getElementById('labels-list');
  if (!list) return;
  list.innerHTML = [...state.labels]
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
    .map(def => `
    <div class="label-row" data-label-id="${def.id}">
      <span class="label label-${def.tone} label-name-pill">
        <input type="text" class="label-row-name" value="${escHtml(def.name)}" aria-label="Name"
          oninput="fitLabelNameInput(this)"
          onblur="saveLabelRow('${def.id}')"
          onkeydown="if(event.key==='Enter'){event.preventDefault();saveLabelRow('${def.id}');this.blur();}">
      </span>
      ${labelToneControlHtml(def.tone, `onchange="onLabelRowToneChange(this, '${def.id}')"`)}
      <button type="button" class="label-row-delete card-btn card-btn-delete" title="Delete" onclick="deleteLabel('${def.id}')">
        ${icon('trash-2', { size: 14 })}
      </button>
    </div>
  `).join('');
  initLabelNameInputs(list);
}

function syncLabelToneDisplay(wrap, tone) {
  if (!wrap || !LABEL_TONES.includes(tone)) return;
  const trigger = wrap.querySelector('.label-tone-trigger');
  const textEl = wrap.querySelector('.label-tone-text');
  if (trigger) {
    LABEL_TONES.forEach(t => trigger.classList.remove(`label-text-${t}`));
    trigger.classList.add(`label-text-${tone}`);
  }
  if (textEl) textEl.textContent = LABEL_TONE_NAMES[tone] || tone;
  const select = wrap.querySelector('.label-row-tone');
  if (select && select.value !== tone) select.value = tone;
}

function setLabelNamePillTone(pill, tone) {
  if (!pill || !LABEL_TONES.includes(tone)) return;
  LABEL_TONES.forEach(t => pill.classList.remove(`label-${t}`));
  pill.classList.add(`label-${tone}`);
}

export function onLabelRowToneChange(select, id) {
  const row = select.closest('.label-row');
  const tone = select.value;
  setLabelNamePillTone(row?.querySelector('.label-name-pill'), tone);
  syncLabelToneDisplay(select.closest('.label-tone-wrap'), tone);
  saveLabelRow(id);
}

export function updateAddRowTone() {
  const tone = document.getElementById('new-label-tone')?.value;
  if (!LABEL_TONES.includes(tone)) return;
  setLabelNamePillTone(document.getElementById('new-label-pill'), tone);
  syncLabelToneDisplay(document.getElementById('new-label-tone-wrap'), tone);
}

export function openLabelsModal() {
  renderLabelsManager();
  document.getElementById('labels-modal').classList.add('open');
  document.getElementById('new-label-name').value = '';
  syncLabelToneSelects('purple');
  updateAddRowTone();
  setTimeout(() => {
    const input = document.getElementById('new-label-name');
    initLabelNameInputs(document.getElementById('label-add-row'));
    input?.focus();
  }, 50);
}

export function closeLabelsModal() {
  document.getElementById('labels-modal').classList.remove('open');
}

export function saveLabelRow(id) {
  const row = document.querySelector(`.label-row[data-label-id="${id}"]`);
  if (!row) return;
  const def = getLabel(id);
  if (!def) return;
  const name = row.querySelector('.label-row-name').value.trim();
  if (!name) return;
  const tone = row.querySelector('.label-row-tone').value;
  def.name = name;
  def.tone = LABEL_TONES.includes(tone) ? tone : 'purple';
  persistLabels();
}

export function addLabelFromDraft() {
  const name = document.getElementById('new-label-name').value.trim();
  if (!name) { document.getElementById('new-label-name').focus(); return; }
  const tone = document.getElementById('new-label-tone').value;
  const id = labelSlug(name);
  state.labels.push({
    id,
    name,
    tone: LABEL_TONES.includes(tone) ? tone : 'purple',
    emoji: '🏷️',
  });
  document.getElementById('new-label-name').value = '';
  fitLabelNameInput(document.getElementById('new-label-name'));
  persistLabels();
  document.getElementById('new-label-name').focus();
}

export function handleNewLabelKey(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    addLabelFromDraft();
  }
}

export function saveLabelsModal() {
  document.querySelectorAll('.label-row[data-label-id]').forEach(row => {
    const def = getLabel(row.dataset.labelId);
    if (!def) return;
    const name = row.querySelector('.label-row-name')?.value.trim();
    if (!name) return;
    const tone = row.querySelector('.label-row-tone')?.value;
    def.name = name;
    def.tone = LABEL_TONES.includes(tone) ? tone : 'purple';
  });
  persistLabels();
  closeLabelsModal();
}

export function deleteLabel(id) {
  const def = getLabel(id);
  if (!def) return;
  if (state.labels.length <= 1) {
    return;
  }
  state.labels = state.labels.filter(l => l.id !== id);
  for (const card of state.cards) {
    card.labels = (card.labels || []).filter(lid => lid !== id);
  }
  state.selectedLabels = state.selectedLabels.filter(lid => lid !== id);
  persistLabels();
}

async function persistLabels() {
  renderLabelsManager();
  renderLabelPicker();
  render();
  try {
    await apiFetch('/api/labels', {
      method: 'PUT',
      body: JSON.stringify({ labels: state.labels }),
    });
  } catch (err) {
    console.warn('Failed to save labels:', err);
    await loadBoard();
    render();
  }
}
