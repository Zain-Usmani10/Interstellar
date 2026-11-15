# Interstellar frontend (Cursor)

Owner: `@sadattanzim01/cursor` — everything here except `src/bci/` (Affan).

## Run locally

Terminal A — backend (from repo root):

```bash
app/scripts/start-backend.sh simulator
```

Terminal B — UI:

```bash
cd app/frontend
npm install
npm run dev
```

Open `http://localhost:5173` (Vite proxies `/api` → `127.0.0.1:8000`).

- Click **Earth** / **Mars** (or keys `1` / `2`). Live mode posts a `SelectionIntent`, waits for WS `selection`, then loads `GET /api/v1/planets/{id}/info` (stale responses ignored).
- Without a backend the UI falls back to labelled offline mock.
- `Esc` / Close sends `navigation.back` on the same path.

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
