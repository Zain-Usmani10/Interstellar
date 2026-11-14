# Backend API v1 (HTTP + WebSocket)

Base: `http://127.0.0.1:8000`. Loopback only. JSON bodies. Shapes named below are the schemas in `schemas/`; examples are in `fixtures/`.

Status: the routes marked **mock** are served from the contract fixtures until the owning adapter lands. The response always says where data came from (`data_mode`, `controller_label`, `provenance`).

## Auth

- `GET` routes need no token.
- Mission mutations need header `X-Operator-Token`. The token is printed at backend start and returned by `GET /api/v1/session` to the allowed browser origin only.
- Input-session routes use the token returned by `POST /api/v1/input/sessions` in header `X-Input-Token`. That token works **only** on `/api/v1/input/*`. It can never call `/missions`.

## Routes

| Method and path | Request | Response |
|---|---|---|
| `GET /api/v1/health` | | `{status, contracts_version, transport: {mode, controller_label, open, stats}, brain_enabled, data_mode}` |
| `GET /api/v1/planets` | | `fixtures/planets.json` shape |
| `GET /api/v1/planets/{body_id}/info?scene_epoch_jd_tdb=` | `body_id` = `399` or `499` | `PlanetInfo`. 404 for other bodies. Partial/unavailable sections are normal. |
| `GET /api/v1/plans` | | `{plans: [{plan_id, objectives_won, data_mode, departure, arrival, dv_total_km_s, propellant_required_kg}]}` |
| `GET /api/v1/plans/{plan_id}` | | `MissionPlan` |
| `POST /api/v1/planning/jobs` | `{departure_start_utc, departure_end_utc, tof_min_days, tof_max_days, n_departures, n_durations, vehicle?}` | `202 {job_id}` |
| `GET /api/v1/planning/jobs/{id}` | | `{job_id, status: queued\|running\|done\|failed\|cancelled, progress, plan_ids, error}` |
| `DELETE /api/v1/planning/jobs/{id}` | | `{job_id, status}` |
| `POST /api/v1/missions` | `{plan_id}` | `201 MissionSnapshot`. 409 if another mission controls the board. |
| `GET /api/v1/missions/{id}` | | `MissionSnapshot` |
| `POST /api/v1/missions/{id}/commands` | `{command: "upload"\|"arm"\|"start"\|"abort"\|"clear"}` | `{command, applied, detail, snapshot}`. `applied` is true only after the controller's ACK. |
| `POST /api/v1/input/sessions` | `{source, adapter: {name, version, device}}` | `201 {input_session_id, token, capability: "planet_explore", context: InputContext}` |
| `POST /api/v1/input/sessions/{id}/heartbeat` | `InputHeartbeat` | `InputContext` |
| `DELETE /api/v1/input/sessions/{id}` | | `204` |
| `GET /api/v1/input/context` | header `X-Input-Token` | `InputContext` for that session |
| `POST /api/v1/input/intents` | `SelectionIntent` | `IntentResult` (HTTP 200 for both accepted and rejected; 422 only when the body is not a valid `SelectionIntent`, with `reason: "invalid_schema"`) |
| `WS /api/v1/events` | | Stream of events below |

`upload` runs OPEN_SESSION (if needed), LOAD_PLAN and COMMIT_PLAN in order and reports the first failure.

## WebSocket events

Every message: `{"type": ..., "server_seq": n, "data": ...}`. `server_seq` increases across all event types; ignore anything not newer than what you already applied. On (re)connect the server first sends the full current state.

| `type` | `data` |
|---|---|
| `hello` | `{contracts_version, controller_label, data_mode}` |
| `mission_snapshot` | `MissionSnapshot` |
| `selection` | `{selected_body_id, screen, context_revision, source, event_id}`: a planet was selected or the screen changed |
| `job_update` | planning job status object |
| `transport` | `{transport_state, detail}` |

## Selection behaviour (mouse, keyboard and EEG take the same path)

1. Register a session, keep heartbeats coming every 500 ms (older than 2 s = `stale_heartbeat`).
2. Send one `SelectionIntent` carrying the `context_id` and `revision` you last received.
3. Accepted `planet.399` / `planet.499`: `selected_body_id` is set, screen becomes `planet_info`, revision increases, a `selection` event goes to every WebSocket client. The browser then loads `GET /planets/{id}/info`.
4. `navigation.back` returns to `planet_choice`. `planet.more_details` keeps the screen and is broadcast for the UI to expand the card.
5. One intent per revision. A selection from any source bumps the revision, so a late intent from another source gets `stale_context`.

Selecting a planet never changes the mission destination, starts planning or sends anything to the controller.
