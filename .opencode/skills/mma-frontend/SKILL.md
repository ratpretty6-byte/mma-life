---
name: mma-frontend
description: Frontend architecture for MMA Life Simulator. CSS class system, JS API client patterns, HTML template conventions, known browser quirks.
---

# MMA Life Simulator — Frontend Reference

## Architecture

Single-page app served from `templates/index.html` (no framework). The server sends the raw HTML, and JS fetches state via `/api/state` and re-renders the DOM.

Key globals in `index.html`:
- `state` — holds the full game state from `/api/state`
- `sid` — session ID from query string or auto-generated
- `api(endpoint, data)` — async POST helper returning JSON
- `refreshUI()` — re-renders the entire page from `state`
- `refreshFightTab()` — renders the fight tab (offers + fight week + fight UI)

## CSS Class System

### Layout Classes
```
.compare-grid        - 2-column grid (left vs right). Used in Tale of the Tape.
.compare-grid-3      - 3-column grid (left | label | right). Use for rows with 3 children.
.flex-row            - display:flex with gap:8px and center alignment.
.card                - dark card with 6px border-radius.
.card-title          - section title with accent color underline.
.tag                 - inline badge with 3px border-radius.
```

### Color Scheme (CSS Variables)
```
--accent: #ffa54a     (primary accent, used for player name/headers)
--bg: #0f0f1a        (page background)
--card-bg: #1a1a2a   (card backgrounds)
--text-muted: #888   (secondary text)
#4a9eff              (opponent name color, blue)
#4aff6a              (positive/green - higher stat, win streak)
#e62400              (negative/red - lower stat, loss streak)
```

### Difficulty Tags
```
.diff-hard    - red/orange for "Step Up" / "Tough Fight"
.diff-medium  - yellow for "Pick 'Em"
.diff-easy    - green for "Should Win"
```

## JS API Client Pattern

```javascript
// All API calls use the api() helper
async function api(path, data = {}) {
  const resp = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams(data)
  });
  return await resp.json();
}

// Always pass sid
const result = await api('/api/advance_day', { sid });
```

## State Refresh Pattern

After any state-changing API call:
```javascript
state = await api('/api/state', { sid });
refreshUI();
```
Only exception: fight simulation calls that return partial state in response.

## Component Hierarchy (refreshUI)

```
refreshUI()
  ├── createFighterUI()     — if no fighter
  └── mainGameUI()          — if fighter exists
       ├── updateHeader()   — fighter name, record, rank, day
       ├── refreshDashboardTab() — stats overview
       ├── refreshTrainingTab()   — drills, camps, schedule
       ├── refreshPromotionTab()  — promotions, offers, contracts (+ fight week)
       ├── refreshFightTab()      — opponents, comparison modal, fight week events, fight UI
       ├── refreshCareerTab()     — record, history, awards
       └── refreshSettingsTab()   — save/load, new game
```

## Fight Week Event UI

Defined in `REFRESH_FIGHT_EVENTS`:
```javascript
const REFRESH_FIGHT_EVENTS = {
  press_conference: { label: 'Press Conference', icon: '🎤', ... },
  open_workout:     { label: 'Open Workout', icon: '🏋️', ... },
  weigh_in:         { label: 'Weigh-In', icon: '⚖️', ... },
  faceoff:          { label: 'Faceoff', icon: '👀', ... },
  rest_day:         { label: 'Rest Day', icon: '🧊', ... },
};
```
Each event has a `doAction` JS function and a `button` label for the action button.

## Known Issues

1. **CSS grid alignment**: `.compare-grid` is 2-column. For rows with 3 children (label in middle), use `.compare-grid-3` with `grid-template-columns: 1fr auto 1fr`.
2. **Template literal injection**: Always use `escHtml()` around user-supplied names in template literals.
3. **State staleness**: `state` can be stale after back-to-back API calls. Always re-fetch `state = await api('/api/state', { sid })` before rendering.
4. **Modal stacking**: Only one modal should be open at a time. Check `closeAllModals()` is called before opening.
5. **API timeout**: Some endpoints (advanced_day, complete_fight) may take >1s. The api() helper has no timeout — ensure the server responds within 30s.
