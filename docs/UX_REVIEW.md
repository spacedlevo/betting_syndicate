# UX / Design / Mobile Review

**Date:** 2026-05-14 | **Reviewer:** Claude Code (Playwright + code audit)

**Pages covered:** Dashboard, Bets (list, new, update result, detail), Players (list, detail),
Ledger (list, contribute, payout), Seasons, Sports, Audit

---

## Overall Assessment

The site is clean and functional with good foundations: a CSS variable system, light/dark/system
theming, sticky nav, and responsive breakpoints. Core workflows (place bet, add contribution,
update result) are intuitive. Issues fall into three categories: CSS bugs that silently break
rendering, missing UX patterns (pagination, confirmations, feedback), and mobile table overflow
with no scroll affordance.

---

## Issues

### 1. Undefined CSS variables in bet form — Fixed

`app/templates/bets/form.html:65` — **Severity: High**

The "potential winnings" preview box used `var(--card-bg)` and `var(--border-color)`, neither of
which are defined in `style.css`. The box rendered with a transparent background and no border.

Replaced with the correct variables:

```html
background: var(--surface); border: 1px solid var(--border);
```

---

### 2. `alert-danger` class not defined — Fixed

`app/templates/dashboard.html:17` — **Severity: High**

The frozen-season banner used `class="alert alert-danger alert-frozen"` but `style.css` only
defines `alert-error`. The banner rendered without background colour or border, effectively
invisible in light mode. Changed to `alert-error`.

---

### 3. Decimal odds only — Won't fix

Severity: N/A. The odds input uses `<input type="number">` which prevents fractional odds. This is
intentional — the site uses decimal odds format throughout.

---

### 4. Bets list has no pagination — Fixed

`app/routes/bets.py`, `app/templates/bets/list.html` — **Severity: High**

`/bets` loaded every bet with no pagination, producing a 200+ row scroll. Added server-side
pagination (50 per page) matching the existing ledger pattern, with Previous/Next controls in the
template.

---

### 5. No horizontal scroll affordance on mobile tables — Fixed

`app/static/css/style.css`, `app/templates/players/list.html` — **Severity: Medium**

On mobile, the Players table cut off silently. Profit/Loss, Payout, and Actions columns were
invisible with no hint the table scrolled. Two fixes applied:

Right-fade shadow added in CSS:

```css
@media (max-width: 768px) {
    .table-container { position: relative; }
    .table-container::after {
        content: '';
        position: absolute;
        top: 0; right: 0;
        width: 2rem; height: 100%;
        background: linear-gradient(to right, transparent, var(--surface));
        pointer-events: none;
    }
}
```

Added `hide-mobile` to In Season, Balance, Bets Placed, Bet Balance, and Won columns in
`players/list.html` so Profit/Loss, Payout, and Actions are always visible without scrolling.

---

### 6. Ledger and Audit filter forms missing `.filter-form` class — Fixed

`app/templates/ledger/list.html:28`, `app/templates/audit/index.html:139` — **Severity: Medium**

Both filter forms used raw inline `style="display: flex; gap: 1rem;"` instead of the
`.filter-form` class that `style.css` defines responsive rules for. The filter row overflowed on
small screens. Added base flex styles directly to `.filter-form` in the CSS, removed inline
styles, and added the class to both forms.

---

### 7. No confirmation on destructive actions — Fixed

`app/templates/players/list.html:62`, `app/templates/seasons/list.html:43` — **Severity: Medium**

Remove player and Activate season both fired immediately with no confirmation. Added
`onclick="return confirm('...')"` to each submit button.

---

### 8. Chart colours don't adapt to dark mode — Fixed

`app/templates/dashboard.html` — **Severity: Medium**

Chart.js axis labels and grid lines defaulted to black in dark mode. Now reads CSS variables at
runtime:

```js
const cssVars = getComputedStyle(document.documentElement);
const textMuted = cssVars.getPropertyValue('--text-muted').trim();
const borderColor = cssVars.getPropertyValue('--border').trim();
```

Applied to tick labels, legend labels, and grid line colours.

---

### 9. Ledger entry badge colours were semantically misleading — Fixed

`app/templates/ledger/list.html`, `app/templates/players/detail.html` — **Severity: Low**

Entry types mapped to bet-result badge classes meant `payout` rendered red ("lost") despite being
a positive event. Added dedicated ledger badge classes to `style.css`:

| Entry Type | New Class | Colour |
| --- | --- | --- |
| `contribution` | `badge-contribution` | Blue |
| `bet_placed` | `badge-bet-placed` | Amber |
| `winnings` / `winnings_share` | `badge-winnings` | Green |
| `payout` | `badge-payout` | Purple |

---

### 10. `--info-color` CSS variable not defined — Fixed

`app/static/css/style.css` — **Severity: Low**

The FREE bet badge used `var(--info-color, #3b82f6)` with a hardcoded fallback, bypassing
theming. Added to all three theme blocks (`:root`, `[data-theme="dark"]`, and the system
preference media query):

```css
:root               { --info-color: #3b82f6; }
[data-theme="dark"] { --info-color: #60a5fa; }
```

---

### 11. No success feedback after form submissions — Fixed

`app/main.py`, `app/flash.py` (new), `app/routes/bets.py`, `app/routes/ledger_routes.py`,
`app/templates/base.html` — **Severity: Low**

After placing a bet, adding contributions, or recording a payout the app silently redirected.
Implemented a cookie-based flash message system using Starlette `SessionMiddleware` and a custom
`FlashMiddleware` that extracts and clears the flash before each request. A success banner now
appears at the top of the page after actions and disappears on the next navigation.

---

### 12. Audit page badge styles defined in a template `<style>` block — Fixed

`app/templates/audit/index.html` — **Severity: Low**

The audit page defined its own `<style>` block with badge colours and dark-mode overrides,
bypassing the CSS variable system. Moved all audit badge classes (`.badge-matched`,
`.badge-auto`, `.badge-unmatched`, `.badge-disregarded`, `.badge-monzo`, `.badge-tsb`,
`.badge-paypal`) and page-specific utility classes (`.audit-actions`, `.action-group`,
`.link-form`, `.link-select`, `.ledger-ref`, `.stat-card`, `.section-meta`) into `style.css`
using CSS variables throughout.

---

## Mobile Quick Reference

| Page | Status | Notes |
| --- | --- | --- |
| Dashboard | Good | Summary gradient and stats grid adapt well |
| Bets list | Fixed | Now paginated at 50 per page |
| Place Bet | Good | Clean single-column form; usable |
| Players | Fixed | Scroll affordance added; key columns always visible |
| Ledger | Fixed | Filter row now stacks correctly on mobile |
| Seasons | Good | Works well at all sizes |
| Sports | Good | Simple table; no issues |
| Audit | Fixed | Filter now stacks on mobile; styles moved to main CSS |

---

## Fix Summary

| # | Issue | Effort | Status |
| --- | --- | --- | --- |
| 1 | Undefined CSS variables (`--card-bg`) | Tiny | Fixed |
| 2 | `alert-danger` → `alert-error` | Tiny | Fixed |
| 3 | Decimal odds only | — | Won't fix |
| 4 | Bets list pagination | Medium | Fixed |
| 5 | Mobile table scroll affordance | Small | Fixed |
| 6 | Filter forms missing `.filter-form` class | Tiny | Fixed |
| 7 | Confirmation dialogs on destructive actions | Small | Fixed |
| 8 | Chart dark mode colours | Small | Fixed |
| 9 | Ledger badge semantic colours | Small | Fixed |
| 10 | Define `--info-color` variable | Tiny | Fixed |
| 11 | Flash messages after form submit | Medium | Fixed |
| 12 | Move audit styles to main CSS | Small | Fixed |
