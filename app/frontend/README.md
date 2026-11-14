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

Mock-driven planet explorer only: select → highlight → info card. No mission upload, scores, or game mechanics. BCI widget mounts later via `src/integrations/bciSlot.tsx`; Affan owns `src/bci/`.
