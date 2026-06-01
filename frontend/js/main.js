import { loadBoard } from './api.js';
import { connectBoardWs } from './realtime.js';
import { ensureStarterCard } from './persist.js';
import { ensureDefaultColumns } from './columns.js';
import { ensureDefaultLabels, syncLabelToneSelects } from './labels.js';
import { setupBoardColDnD } from './columns.js';
import { setupCtxClickClose } from './cards.js';
import { render } from './render.js';
import { updateUndoButton } from './undo.js';
import {
  renderDotPicker,
  selectDot,
  toggleTheme,
  setupKeyboardShortcuts,
  setupDevToolsGuard,
  updateLockButton,
  toggleBoardLock,
  closeModal,
} from './ui.js';
import {
  addLabelFromDraft,
  closeLabelsModal,
  deleteLabel,
  fitLabelNameInput,
  handleNewLabelKey,
  onLabelRowToneChange,
  openLabelToneSelect,
  openLabelsModal,
  saveLabelRow,
  saveLabelsModal,
  updateAddRowTone,
} from './labels.js';
import {
  closeCardModal,
  closeConfirmDeleteCardModal,
  confirmDeleteCard,
  ctxDelete,
  ctxEdit,
  ctxMove,
  ctxToggleFlame,
  ctxTogglePin,
  editCard,
  executeDeleteCard,
  openAddCard,
  saveCard,
  toggleCardFlame,
  toggleCardPin,
  toggleLabel,
} from './cards.js';
import {
  closeColModal,
  closeConfirmDeleteModal,
  confirmDeleteColumn,
  executeDeleteColumn,
  openAddColModal,
  saveColumn,
} from './columns.js';
import {
  askExample,
  closeFromTextModal,
  createTaskFromText,
  handleAiKey,
  handleFromTextKey,
  openFromTextModal,
  sendAiMessage,
  toggleAskAI,
} from './ai.js';
import { performUndo } from './undo.js';

Object.assign(window, {
  addLabelFromDraft,
  askExample,
  closeCardModal,
  closeColModal,
  closeConfirmDeleteCardModal,
  closeConfirmDeleteModal,
  closeFromTextModal,
  closeLabelsModal,
  closeModal,
  confirmDeleteCard,
  confirmDeleteColumn,
  createTaskFromText,
  ctxDelete,
  ctxEdit,
  ctxMove,
  ctxToggleFlame,
  ctxTogglePin,
  deleteLabel,
  editCard,
  executeDeleteCard,
  executeDeleteColumn,
  fitLabelNameInput,
  handleAiKey,
  handleFromTextKey,
  handleNewLabelKey,
  onLabelRowToneChange,
  openAddCard,
  openAddColModal,
  openFromTextModal,
  openLabelToneSelect,
  openLabelsModal,
  performUndo,
  saveCard,
  saveColumn,
  saveLabelRow,
  saveLabelsModal,
  selectDot,
  sendAiMessage,
  toggleAskAI,
  toggleBoardLock,
  toggleCardFlame,
  toggleCardPin,
  toggleLabel,
  toggleTheme,
  updateAddRowTone,
});

async function init() {
  setupDevToolsGuard();
  syncLabelToneSelects('purple');
  setupBoardColDnD();
  setupCtxClickClose();
  setupKeyboardShortcuts();
  renderDotPicker();
  await loadBoard();
  connectBoardWs();
  ensureDefaultColumns();
  ensureDefaultLabels();
  await ensureStarterCard();
  updateLockButton();
  updateUndoButton();
  render();
}

init().catch(err => {
  console.error('Init failed:', err);
});
