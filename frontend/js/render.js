import { state } from './state.js';
import { buildCol, setupColDrag, updateColSelects, openAddColModal } from './columns.js';
import { buildCard, setupDnd } from './cards.js';
import { cardIconDots } from './helpers.js';

export function render() {
  const board = document.getElementById('board');
  board.innerHTML = '';
  state.columns.forEach(col => {
    const cards = state.cards.filter(c => c.col === col.id);
    board.appendChild(buildCol(col, cards));
  });
  if (!state.boardLocked) {
    const addBtn = document.createElement('button');
    addBtn.className = 'add-col-btn';
    addBtn.innerHTML = cardIconDots('plus');
    addBtn.title = 'Add column';
    addBtn.setAttribute('aria-label', 'Add column');
    addBtn.onclick = openAddColModal;
    board.appendChild(addBtn);
  }
  setupDnd();
  if (!state.boardLocked) setupColDrag();
  updateColSelects();
}
