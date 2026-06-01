export const COLOR_PALETTE = {
  neutral: '#888690',
  blue: '#58a6ff',
  amber: '#e3b341',
  purple: '#6750a4',
  red: '#f85149',
  green: '#3fb950',
  bronze: '#b8845a',
};

export const COLUMN_PALETTE = [
  { id: 'backlog', title: 'Backlog', color: COLOR_PALETTE.neutral },
  { id: 'ideas', title: 'Ideas', color: COLOR_PALETTE.blue },
  { id: 'todo', title: 'To Do', color: COLOR_PALETTE.amber },
  { id: 'inprogress', title: 'In Progress', color: COLOR_PALETTE.purple },
  { id: 'production', title: 'Production', color: COLOR_PALETTE.red },
  { id: 'done', title: 'Done', color: COLOR_PALETTE.green },
];

export const DOT_PICKER_COLORS = [
  COLOR_PALETTE.purple,
  COLOR_PALETTE.green,
  COLOR_PALETTE.blue,
  COLOR_PALETTE.amber,
  COLOR_PALETTE.red,
  COLOR_PALETTE.neutral,
];

export const DEFAULT_LABELS = [
  { id: 'green', name: 'Done', tone: 'green', emoji: '🟢' },
  { id: 'blue', name: 'Review', tone: 'blue', emoji: '🔵' },
  { id: 'orange', name: 'Urgent', tone: 'orange', emoji: '🟡' },
  { id: 'purple', name: 'AI', tone: 'purple', emoji: '🟣' },
  { id: 'red', name: 'Bug', tone: 'red', emoji: '🔴' },
  { id: 'teal', name: 'Design', tone: 'teal', emoji: '🔷' },
  { id: 'pink', name: 'Feature', tone: 'pink', emoji: '🩷' },
  { id: 'gray', name: 'Low', tone: 'gray', emoji: '⚪' },
  { id: 'lime', name: 'Quick', tone: 'lime', emoji: '⚡' },
  { id: 'indigo', name: 'Research', tone: 'indigo', emoji: '🔮' },
];

export const LABEL_TONES = [
  'green', 'blue', 'orange', 'purple', 'red',
  'teal', 'pink', 'gray', 'lime', 'indigo',
];

export const LABEL_TONE_NAMES = {
  green: 'Green',
  blue: 'Blue',
  orange: 'Orange',
  purple: 'Purple',
  red: 'Red',
  teal: 'Teal',
  pink: 'Pink',
  gray: 'Gray',
  lime: 'Lime',
  indigo: 'Indigo',
};

export let state = {
  columns: COLUMN_PALETTE.map(col => ({ ...col })),
  cards: [],
  labels: [],
  editingCardId: null,
  selectedLabels: [],
  selectedDotColor: COLOR_PALETTE.purple,
  currentColForAdd: null,
  undoRecording: true,
  dragId: null,
  dragColIdFrom: null,
  dragUndoSnapshot: null,
  boardColDnDReady: false,
  pendingDeleteCardId: null,
  pendingDeleteColId: null,
  ctxCardId: null,
  fromTextBusy: false,
  aiBusy: false,
  boardLocked: localStorage.getItem('kaban_board_locked') !== 'false',
  aiOpen: false,
};

export function c() { return Math.random().toString(36).slice(2, 9); }

export const undoStack = [];
