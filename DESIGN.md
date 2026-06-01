# KABAN AI — Industrial UI Design System

Portable reference for reusing this visual language across products. **Source of truth for values:** `frontend/css/tokens.css`. Component rules: `frontend/css/components.css`, `overlays.css`, `responsive.css`.

---

## 1. Design philosophy

| Principle | Description |
|-----------|-------------|
| **One skeleton, two moods** | Layout, spacing, radii, typography, and icon set are identical. Only the palette skin changes between themes. |
| **Dark — cold graphite** | RIMOWA / hi-tech aluminium register: near-black surfaces, cool greys, purple interactive accent. |
| **Light — warm NieR sepia** | Faded paper register: muted warm canvas, no pure white, no glare. Interactive accent is sepia inversion, not purple. |
| **Monochrome structure** | Column headers, chrome, and most UI chrome are neutral. Hue is intentional and scarce. |
| **Token-only styling** | All hex, rgba, and px scales live in `tokens.css`. Other CSS files reference `var(--token)` only — no raw colours in components. |
| **Functional motion only** | Animations serve state (alarm flame, loader spin, button press). No decorative ambient motion. |
| **Single glow** | The only permitted `filter: drop-shadow` glow is the active flame alarm icon. Nothing else glows. |

### Branding (locked)

- Product name: **KABAN AI** (no rebrand).
- Header: **wordmark only** — `KABAN` in `--text-primary`, `AI` in `--text-secondary`, uppercase, `--tracking-wordmark` (0.14em). No logo mark in chrome (boar may remain favicon only).

---

## 2. Theme switching

```html
<html data-theme="dark">   <!-- default -->
<html data-theme="light">
```

Toggle by setting `data-theme` on `<html>`. Every semantic token must be redefined under `[data-theme="dark"]` and `[data-theme="light"]` — never branch on theme in component CSS except where structure truly differs (e.g. light card shadow uses a dedicated token).

---

## 3. Where colour is allowed

After the industrial pass, **colour on the board is limited to:**

| Layer | Colour source |
|-------|----------------|
| Column headers | `--text-secondary` only (no per-column hue) |
| Card titles / body | `--text-primary` / inherited neutral |
| Label pills | `--label-{tone}-fg` + `--label-{tone}-border` |
| Alarm | `--signal` on bug/urgent pills, orange/red labels, and active flame icon |
| Interactive | `--accent` (+ `--accent-fg` / `--accent-icon` in light) for focus, Ask AI, active controls, drop indicators |

**Reserved / neutral by design**

- `AI` tag uses default grey pill tones (`--label-purple-*` aliases default) — purple accent is not used on cards.
- Pinned state: border only (`--border-pinned`), not hue.

---

## 4. Dark theme palette

### 4.1 Surfaces & text

| Token | Hex | Use |
|-------|-----|-----|
| `--bg` | `#0b0c0e` | App / board canvas |
| `--surface-header` | `#121316` | Top bar |
| `--surface-1` | `#121316` | Column body |
| `--surface-2` | `#16181b` | Cards, inputs, buttons |
| `--surface-3` | `#1b1d21` | Hover / raised |
| `--hairline` | `#26282c` | 0.5px seams (`--border-hairline`) |
| `--hairline-col` | `#26282c` | Column outer border & internal dividers (`--border-col`) |
| `--edge-light` | `#34373d` | 1px top highlight on controls & cards |
| `--text-primary` | `#e6e6e8` | Titles, primary copy |
| `--text-secondary` | `#9a9ca2` | Column headers, secondary labels, icons at rest |
| `--text-muted` | `#5d5f65` | Counters, hints, de-emphasized chrome |

### 4.2 Accent & signal (dark)

| Token | Value | Use |
|-------|-------|-----|
| `--accent` | `#8b6fd6` | Focus rings, Ask AI icon, drop indicator, active emphasis |
| `--accent-fg` | `#e6e6e8` | Text on accent fills (when needed) |
| `--accent-edge` | `#a98ee8` | Lighter accent variant (overlays) |
| `--accent-icon` | `var(--accent)` | Icon tint on neutral buttons |
| `--accent-dim` | `color-mix(in srgb, var(--accent) 14%, transparent)` | Drop targets, subtle fills |
| `--signal` | `#f05551` | Brightest alarm on screen — flame, bug/urgent |
| `--signal-edge` | `#5a2723` | Pill border for signal-tied labels |
| `--danger-fg` | `#d07a6e` | Destructive actions |
| `--danger-border` | `#46322e` | Destructive control border |
| `--scrim` | `rgba(0, 0, 0, 0.72)` | Modal overlay |

### 4.3 Elevation (dark)

- Depth via **top edge-light** (`border-top: 1px solid var(--edge-light)`) + hairline sides.
- Card hover: border shifts to `--edge-light`.
- Pinned card: `--border-pinned` = `1px solid var(--edge-light)` on all sides.

---

## 5. Light theme palette (NieR sepia)

### 5.1 Surfaces & text

| Token | Hex | Use |
|-------|-----|-----|
| `--bg` | `#d4cebf` | Faded-paper canvas |
| `--surface-header` | `#ccc6b6` | Top bar (slightly deeper sepia) |
| `--surface-1` | `#d2cbb8` | Column zone (~1–2% darker than canvas) |
| `--surface-2` | `#e3ddce` | Cards — lighter paper, **not white** |
| `--surface-3` | `#ece6d8` | Hover |
| `--hairline` | `#bdb6a4` | General seams |
| `--hairline-col` | `#b0a996` | Column borders (slightly stronger than `--hairline`) |
| `--edge-light` | `#ebe5d6` | Warm highlight (not pure white) |
| `--text-primary` | `#3d3a34` | Titles (warm dark graphite) |
| `--text-secondary` | `#56524a` | Column headers, labels |
| `--text-muted` | `#928c7d` | Counters, hints |

### 5.2 Accent & signal (light)

| Token | Value | Use |
|-------|-------|-----|
| `--accent` | `#45413a` | Interactive fill (sepia inversion) |
| `--accent-fg` | `#d4cebf` | Cream text/glyph on accent fill |
| `--accent-edge` | `#5c5850` | Hover / secondary accent |
| `--accent-icon` | `var(--accent)` | Icon on neutral surfaces |
| `--accent-dim` | `color-mix(in srgb, var(--accent) 12%, transparent)` | Drop targets |
| `--signal` | `#a8412f` | Brick red alarm on paper |
| `--signal-edge` | `#6e3028` | Signal pill borders |
| `--border-pinned` | `1px solid var(--hairline)` | Visible pin ring on paper cards |
| `--danger-fg` | `#a8412f` | Aligned with signal brick |
| `--scrim` | `rgba(61, 58, 52, 0.36)` | Modal overlay |

### 5.3 Elevation (light)

- **No** reliance on white edge-light for card lift (invisible on paper).
- Cards: `box-shadow: var(--card-shadow-light)` → `0 1px 2px rgba(60, 50, 30, 0.12)`.
- Pinned: hairline border, not edge-light.

### 5.4 Light interactive inversion pattern

On hover/active/busy for primary AI affordances and column `+`:

```css
background: var(--accent);
color: var(--accent-fg);
/* icons inherit or use var(--accent-fg) */
```

Applies to: `.btn-ask-ai` (hover/active/busy), `.col-add:hover`.

---

## 6. Shared tokens (theme-independent)

### 6.1 Spacing (4px base)

| Token | px |
|-------|-----|
| `--space-1` | 4 |
| `--space-2` | 8 |
| `--space-3` | 12 |
| `--space-4` | 16 |
| `--space-5` | 24 |
| `--space-6` | 32 |
| `--space-8` | 48 |

### 6.2 Radii (sharp industrial)

| Token | px |
|-------|-----|
| `--radius-sm` | 3 |
| `--radius-md` | 5 |
| `--radius-lg` | 6 |

Maximum corner radius in the system: **6px**. No pills or large radii on structural chrome.

### 6.3 Typography

| Token | Value |
|-------|-------|
| `--font-body` | `'Inter', system-ui, sans-serif` |
| `--font-mono` | `ui-monospace, 'SF Mono', Menlo, monospace` |
| `--text-tag` | 11px → **10px** for label pills |
| `--text-xs` | 11px |
| `--text-sm` | 13px (body default) |
| `--text-base` | 14px |
| `--text-md` | 15px |
| Weights | **400** and **500** only |
| `--line-height-tight` | 1.45 |
| `--line-height-body` | 1.7 |
| `--tracking-wide` | 0.12em |
| `--tracking-wider` | 0.14em (column titles) |
| `--tracking-wordmark` | 0.14em |

**Column headers:** `--text-xs`, weight 500, uppercase, `--tracking-wider`, colour `--text-secondary`.

**Counters:** `--font-mono`, `--text-xs`, `--text-muted`, zero-padded two digits (`01`, `00`).

### 6.4 Motion

| Token | Value |
|-------|-------|
| `--dur-fast` | 120ms |
| `--dur` | 180ms |
| `--ease` | `cubic-bezier(0.4, 0, 0.2, 1)` |

| Animation | Duration | Easing | Purpose |
|-----------|----------|--------|---------|
| `flameAlarm` | 0.9s | ease-in-out, infinite | Active flame only: opacity 1 → 0.45 → 1, scale 1 → 1.08 |
| `iconSpin` | 1s | linear, infinite | Loader / busy state |
| Button press | — | — | `transform: scale(0.98)` on `:active` |

### 6.5 Icons

- **Lucide** stroke icons, inline SVG (`frontend/js/icons.js`).
- `stroke="currentColor"`, `stroke-width: 1.75` (`--icon-stroke`).
- Sizes: `--size-icon-sm` 14px, `--size-icon-md` 16px, `--size-icon-flame` 18px (alarm only).
- Tool control height: `--size-tool` 32px.

### 6.6 Borders & shadows

| Token | Definition |
|-------|------------|
| `--border-hairline` | `0.5px solid var(--hairline)` |
| `--border-col` | `0.5px solid var(--hairline-col)` |
| `--border-pinned` | Dark: `1px solid var(--edge-light)` all sides; Light: `1px solid var(--hairline)` |
| `--shadow-subtle` | `0 1px 2px rgba(0, 0, 0, 0.4)` (dark utility) |
| `--card-shadow-light` | `0 1px 2px rgba(60, 50, 30, 0.12)` |

### 6.7 Layout widths

| Token | Value |
|-------|-------|
| `--board-gap` | `var(--space-4)` |
| `--modal-width` | 400px |
| `--modal-width-wide` | 540px |
| `--modal-width-labels` | 480px |
| `--modal-max-height` | 760px |
| `--ai-panel-width` | 340px |
| `--card-pad` | `var(--space-3)` |

---

## 7. Label pill system (sole board chroma)

Outline pills: 1px border, transparent fill, `--text-tag` (10px), padding `--label-pad-y` / `--label-pad-x` (2px × 6px).

### 7.1 Dark theme label tones

| Tone | `--label-*-fg` | `--label-*-border` |
|------|----------------|---------------------|
| default / gray / purple (AI) | `#9a9ca2` | `#34373d` |
| green | `#6fb88a` | `#324a38` |
| blue | `#82a9d6` | `#334858` |
| orange | `var(--signal)` | `var(--signal-edge)` |
| red | `var(--signal)` | `var(--signal-edge)` |
| teal | `#72b8ab` | `#2e4540` |
| pink | `#d094b0` | `#45343e` |
| lime | `#9ab872` | `#3a482e` |
| indigo | `#929ed4` | `#333858` |

### 7.2 Light theme label tones

| Tone | `--label-*-fg` | `--label-*-border` |
|------|----------------|---------------------|
| default / gray / purple (AI) | `#56524a` | `#bdb6a4` |
| green | `#5a7050` | `#9aaa8c` |
| blue | `#4e6878` | `#98a8b0` |
| orange | `var(--signal)` | `var(--signal-edge)` |
| red | `var(--signal)` | `var(--signal-edge)` |
| teal | `#4a7068` | `#94b0a8` |
| pink | `#886070` | `#c0a8b0` |
| lime | `#687850` | `#a8b090` |
| indigo | `#585878` | `#a0a0b8` |

**Hierarchy rule:** `--signal` must remain the loudest chroma on the board (pills + flame). Other pill tones stay muted so alarm never drowns.

---

## 8. Component patterns

### 8.1 Header

- Background: `--surface-header`.
- Bottom: `--border-hairline`; top: 1px `--edge-light`.
- **Left:** wordmark. **Right:** two groups with hairline divider:
  - **Tools:** undo, theme, lock (`--size-tool` square buttons).
  - **Actions:** From text, Task, Ask AI.

### 8.2 Buttons (metal switch)

- Base: `--surface-2`, hairline border + top edge-light, `--text-secondary`.
- Hover: `--surface-3`, `--text-primary`.
- Active press: `scale(0.98)`.
- Focus / primary emphasis: `border-color: var(--accent)` where applicable.

### 8.3 Columns

- Surface: `--surface-1`, border `--border-col`, top edge-light.
- Title row: neutral uppercase + mono count + add control.
- Empty column: plain surface only (no placeholder copy).
- Footer (unlock mode): delete control separated by `--border-col` top.

### 8.4 Cards

**Reading order (top → bottom):**

1. Title (`--text-primary`)
2. Description body (if any)
3. Label row (`--text-tag` pills)
4. Footer icon actions (on hover; pin/flame may show when active)

**States:**

| State | Visual |
|-------|--------|
| Default | `--surface-2`, hairline + top edge-light (dark); shadow only (light) |
| Pinned | `--border-pinned` all sides — **only** border-encoded state |
| Hot / flame | **Icon only** — no red border on card |
| Flame active | `--signal` icon, `--size-icon-flame`, `flameAlarm`, `drop-shadow(0 0 4px var(--signal))` |

Padding: `--card-pad` (`--space-3`); height fits content (no artificial min-height).

### 8.5 Flame alarm (canonical CSS)

```css
@keyframes flameAlarm {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(1.08); }
}
/* Active flame icon only */
color: var(--signal);
filter: drop-shadow(0 0 4px var(--signal));
animation: flameAlarm 0.9s ease-in-out infinite;
```

Inactive cards: no flame animation.

---

## 9. Porting checklist

When applying this system to a new interface:

1. Copy token structure from `tokens.css` (shared `:root` + both `[data-theme]` blocks).
2. Enforce **no hex in component CSS** — lint or grep `#[0-9a-fA-F]` outside `tokens.css`.
3. Map all surfaces to `--bg` / `--surface-*` — never hardcode white in light theme.
4. Keep column chrome monochrome; put semantics in tags only.
5. Use dark purple / light sepia accent split — do not use purple accent on light sepia UI.
6. Reserve `--signal` for true alarms; one glow (flame) only.
7. Prefer Inter 400/500 + mono for numeric counters.
8. Lucide inline SVG, `currentColor`, 1.75 stroke.
9. Sharp radii ≤ 6px; 4px spacing grid.
10. Document product-specific overrides in that repo’s `tokens.css`, not scattered in components.

---

## 10. File map (this repo)

| File | Role |
|------|------|
| `frontend/css/tokens.css` | All palettes and scales |
| `frontend/css/components.css` | Board, header, columns, cards, buttons |
| `frontend/css/overlays.css` | Modals, AI panel, context menus |
| `frontend/css/responsive.css` | Breakpoint adjustments (tokens only) |
| `frontend/js/icons.js` | Lucide SVG paths |
| `README.md` | Short pointer to tokens (details here) |

---

## 11. Version note

Design system as shipped in **KABAN AI** industrial UI (passes: base monochrome, pass 1 signal/pin, pass 2 layout/flame/light aluminium iterations, pass 3 NieR sepia light + monochrome columns + accent discipline). For exact runtime values, always prefer `tokens.css` over this document if they diverge.
