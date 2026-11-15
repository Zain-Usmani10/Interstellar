# Interstellar frontend (Cursor)

Owner: `@sadattanzim01/cursor` — everything here except `src/bci/` (Affan).

## Run locally

```bash
cd app/frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`).

- Click **Earth** or **Mars** in the 3D scene (or the top buttons, or keys `1` / `2`).
- The selected planet highlights and an info card opens.
- Banner says **MOCK DATA** — fixtures only until backend contracts exist.
- `Esc` closes the card.

```bash
npm run build    # typecheck + production build
npm run preview  # serve the build
```

Requires Node 22 LTS (or another supported even-numbered LTS).

## Scope of this milestone

Mock-driven planet explorer only: select → highlight → info card. No mission upload, scores, or game mechanics.

## Optional brain widget

Affan owns `src/bci/`. Cursor mounts it from `src/integrations/bciSlot.tsx` only when:

1. `app/frontend/src/bci/BrainWidget.tsx` is present (Affan's PR), and
2. `VITE_BRAIN_ENABLED=true` is set when starting Vite.

```bash
VITE_BRAIN_ENABLED=true npm run dev
```

Core selection / highlight / info card still come from ordinary input (and later core WS `selection` events), not from classifier scores.
