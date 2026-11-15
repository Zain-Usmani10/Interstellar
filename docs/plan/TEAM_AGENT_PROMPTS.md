# Interstellar — team assignments and copy-paste prompts

> **Update 2026-11-15:** read `MAIN_BACKEND_FPGA_TASKS.md` section 18 (Shuttle and CCS) before any new work: 18.5 backend, 18.6 FPGA/VGA, 18.7 GUI. The NASA/physics prompt now applies to `@AffanSyed07/codex`; the browser prompt covers the whole GUI including the 3D scene; the FPGA prompt applies to Zain and `@Zain-Usmani10/claude`. Current ownership is in `AGENTS.md`.

> **Repo note (added at setup, 2026-11-14):** `AGENTS.md` is authoritative for roles, ownership and git policy; it overrides this file where they differ. All code paths in this file live under `app/` (e.g. `backend/api/` means `app/backend/api/`, `contracts/` means `app/contracts/`). Plan files are in `docs/plan/`. Agents: `@ANaceri26/claude` (leader/integrator), `@ANaceri26/codex` (XIAO/transport), `@sadattanzim01/claude` (NASA/physics), `@sadattanzim01/cursor` (frontend), `@AffanSyed07/codex` (brain). **The FPGA is owned by Zain (`@Zain-Usmani10`, human) working directly in Quartus; there is no Zain board agent.** Read "Zain's Claude" below as "Zain". The board bugs in TEAM_AGENT_PROMPTS.md section 3 are fixed in `tools/board`.

Updated 2026-11-14: your Claude = integration/backend; Zain's Claude = FPGA; your Codex = XIAO/transport. This is the operational assignment sheet; it replaces the older generic seven-agent allocation in the two design documents.

## 1. What the team is building now

- Core: NASA-based 3D mission planner, real DE10-Lite sequencer, XIAO communication bridge, truthful physics/status/fault demonstration.
- Brain extension: **EEG selection of a planet opens its information panel inside the same Interstellar app.** First prove that connection. Begin with Earth and Mars targets; no game, scores, brain-issued launch commands or new quantum work in this assignment.
- NASA information: reuse Horizons positions and sourced planetary facts; add EONET Earth hazard-event data after the basic card works. Earth events are not Mars weather or a generic planet-health score. Missing/unavailable data remains visibly unavailable.
- Future only: route selection, order submission and launch through EEG. Those interfaces remain described for later work but are disabled in this round.

The latest user instruction assigns brain control to Affan because he attended the workshops. While he is away, the other five agents work on the core and expose the stable planet-selection interface he will use.

## 2. Actual allocation: five now, sixth when back

| Human / agent | Handle | Task | Owned paths |
|---|---|---|---|
| Zain's Claude | `@Zain-Usmani10/claude` | FPGA RTL, synthesis, board validation | `hardware/fpga/`, `tests/fpga/` |
| Your Codex | `@ANaceri26/codex` | XIAO bridge and Python serial/delay transport | `hardware/xiao/`, `backend/transport/`, `tests/transport/` |
| Your Claude | `@ANaceri26/claude` | Integrator, contracts, backend API/runtime, shared setup | `contracts/`, `backend/api/`, `backend/runtime/`, `tools/`, `scripts/`, root manifests/rules/docs |
| Sadat's Claude | `@sadattanzim01/claude` | NASA acquisition, orbital math, planet information | `backend/ephemeris/`, `backend/planner/`, `backend/physics/`, `backend/planet_data/`, corresponding tests/data fixtures |
| Sadat's Cursor | `@sadattanzim01/cursor` | 3D browser UI, planet cards and ordinary selection | `frontend/` except `frontend/src/bci/` |
| Affan's Codex, when available | `@AffanSyed07/codex` | Brain acquisition/decoder and isolated selection widget | `brain/`, `frontend/src/bci/`, `tests/brain/` |

Folder ownership includes component-specific tests. the integration owner owns shared API/protocol fixtures and integrated orchestration tests. Agent owners submit dependency requirements to the integration owner for root Python locks; Cursor owns the frontend package files and coordinates any shared browser dependencies with Affan. Do not have two agents rewrite the same lockfile.

Each person may clone the same GitHub repository on their own laptop. **Two agents on one laptop need separate working folders/worktrees and branches.** A shared folder with different chat windows is not isolation.

## 3. Board recommendation: fixed tasks plus short handoffs

Use manual assignments from this sheet. Use the GitHub issue board for blockers, agreed interface changes and completed PRs. Do not build a constantly chatting swarm or let agents reassign each other freely.

The supplied ZIP is a coordination scaffold, not an application or an automatic agent scheduler. Its shell script prints issue comments; it does not independently create a new AI turn. An agent must explicitly check the board, or a human must bring it the update. Starting an unattended `wait` terminal is not a guarantee that every editor automatically wakes an AI agent.

### Confirmed problems in the provided ZIP

1. `tools/board unread` filters out **every comment from the current GitHub login**. Consequently the two agents sharing your GitHub account can miss each other's posts, as can Sadat's two agents, even in separate worktrees.
2. Mention detection checks the human login/`@all`, not the full `/claude`, `/codex`, `/cursor` identity. `wait` returns any other-account unread post, not only a matching agent tag.
3. `.claude/settings.json` is empty (zero bytes): the README's claimed hooks are not implemented in this ZIP. Remove the unsupported claim or configure/test valid hooks; do not depend on them initially.
4. `wait` and `unread` share a read cursor inside the same worktree. A background waiter can consume posts before a foreground read sees them. Avoid competing consumers until state handling is fixed.
5. The owner table is largely TBD. The old rule that each author merges their own PR is unsuitable for the integration gate chosen here; the lead should publish a single consistent policy before work begins.

**Immediate workable fallback:** `bash tools/board read -n 50` in Git Bash displays recent comments including same-account posts without consuming the unread cursor. Each agent checks at task start, before a PR and when changing an interface. If more than 50 comments arrived, read enough to cover the gap. Use an explicit author/agent prefix to distinguish identities. Keep contract decisions in versioned repo files, not only comments.

Lead's small repair scope: add an explicit `BOARD_AGENT` identity, route complete handles correctly, stop suppressing same-account peer messages, isolate/serialize read cursors, and test routing with saved fixtures. Until repaired, use `read`, not unreliable claims of autonomous routing. Foreground milestone polling is sufficient; hooks/background wait are optional. Cap coordination setup at about 20–30 minutes, then start product work with manual handoffs if necessary.

The GitHub CLI (`gh`) must be installed, visible inside Git Bash and authenticated on **each** workstation. `gh` was not available on this task's shell PATH during the audit. The ZIP was inspected directly; the live team repo returned an unauthenticated 404, so its visibility, current branch contents and board issue number are not verified. Do not assume issue #1 is the board; confirm it before posting.

## 4. Startup order

If anyone already started under the old allocation, first hand over branch/commit, changed files, tests and outstanding work. Preserve Zain's board fixes; the new integrator must inspect them rather than redo them. Update the live AGENTS.md ownership table before two agents edit the same area.

1. Give your Claude the **Integrator** prompt first plus all three Markdown files. Your Claude publishes them and the populated owner table to the actual repo, verifies `dev` and the board, and creates initial contracts/mocks.
2. Give each other agent its complete role prompt below. All can begin independent bring-up immediately. They must not invent conflicting public APIs while the integration owner freezes them.
3. the integration owner's first handoff publishes schema/protocol version, golden frames and mock planet/mission examples. Everyone builds against that version.
4. Small PRs target `dev`; **the integration owner merges after affected owners verify the boundary**. Promotion of tested `dev` to `main` remains a human-coordinated release decision; do not auto-publish it. This policy must replace the ZIP's conflicting author-self-merge instruction.
5. Affan starts with a synthetic signal and the existing planet-selection mock/API. Replace the acquisition adapter with hardware/replay when available. No core engineer needs to wait for a headset.

During prototype work, commit/checkpoint only owned files. Never `git add .`, overwrite another agent's work or force-push shared branches. Once a branch is pushed, avoid rewriting its history; fetch and merge the latest `origin/dev` when needed, resolve only understood conflicts and ask the affected owner about shared-contract conflicts.

## 5. Copy-paste: Your Claude — integrator (send first)

```text
You are @ANaceri26/claude, Interstellar's integration owner.

Read AGENTS.md, MAIN_BACKEND_FPGA_TASKS.md, BRAIN_CONTROL_TASKS.md and TEAM_AGENT_PROMPTS.md. The latest user scope is authoritative: core NASA/FPGA mission simulator; Affan owns EEG planet selection/info; no game or EEG launch commands now. Apply the six-agent allocation in TEAM_AGENT_PROMPTS.md rather than any older generic seven-slot table.

First inspect the current repo/branches and preserve existing work. Publish the supplied plans, owner table and one consistent Git policy: role branches -> PRs into dev -> you integrate; main only after demo gates. Verify the board issue and gh authentication. You are authorized to post concise coordination comments to this project's board and create task PRs; do not message elsewhere. Audit/fix the ZIP board issues described in TEAM_AGENT_PROMPTS.md, or use read -n 50 with explicit identities. Do not spend more than 20–30 minutes on board infrastructure.

Own contracts/, backend/api/, backend/runtime/, tools/, scripts/, root manifests/rules/docs and integration orchestration. First deliver schema/protocol v1, CRC golden frames, simulator transport interface and mock MissionPlan/MissionSnapshot/PlanetInfo/InputContext/SelectionIntent fixtures. Freeze those and announce the commit before others integrate. Define read-only planet targets planet.399 and planet.499; EEG tokens cannot upload/arm/start missions in this round.

Build FastAPI, job orchestration, one serial owner, mission state reconstruction/API wiring, input validation/heartbeat/deduplication, persistence and startup. NASA/math belongs to Sadat's Claude; real serial transport belongs to ANaceri26's Codex; FPGA to Zain's Claude; normal browser to Sadat's Cursor; brain/BCI widget to Affan. Do not rewrite their components without a handoff. Expose GET /api/v1/planets/{body_id}/info using the NASA owner's adapter.

Publish small runnable milestones. Test schema rejection, stale/duplicate intents, simulator flow, optional-brain failure isolation and ordinary-input end-to-end operation. Record real results separately from pending hardware checks. Coordinate merges into dev; keep secrets and restricted EEG data out of Git. Start with repository/preflight and contracts now; do not wait for all other components to finish.
```

## 6. Copy-paste: Zain's Claude — FPGA

```text
You are @Zain-Usmani10/claude. Implement only the DE10-Lite FPGA part of Interstellar.

Read AGENTS.md, MAIN_BACKEND_FPGA_TASKS.md and TEAM_AGENT_PROMPTS.md. Use a separate worktree/folder from ANaceri26's Codex and a dedicated role branch. Own hardware/fpga/ and tests/fpga/. Stage only your files; open small PRs into dev for the integration owner to integrate. Do not push to main or edit shared contracts without the integration owner's handoff. You may post concise progress/blocker/PR updates on the verified project board; use board read until its identity bugs are fixed.

Target MAX 10 10M50DAF484C7G. Follow the verified clock/pin/3.3 V assignments, canonical 115200 UART protocol, fixed two-event plan and timing rules in the main file. The laptop does orbital calculations; the board owns execution ticks, real event flags, integer fuel ledger and fault state. Implement preserved three-copy control state with honest single-fault masking/no-majority limits. SAFE inhibits burns while the mission clock/coast continues as specified.

First milestone: compile/program heartbeat, then UART status and golden-frame checks with ANaceri26's Codex. Next upload/commit/arm/start/execute, retained telemetry, fault tests and reset/reconnect behavior. Include RTL testbenches, constraints, build command, timing/resource report and evidence the three register banks survived synthesis. Never claim a board test passed based only on simulation.

Your human handles physical wiring/programming. The XIAO firmware and host serial/delay implementation belong to ANaceri26's Codex. Agree only through the frozen contract; do not implement a second host backend. Do not add VGA, SDRAM, a soft CPU, motors or EEG code. Start independent toolchain/heartbeat work while waiting for the integrator's golden fixtures.
```

## 7. Copy-paste: your Codex — bridge/transport

```text
You are @ANaceri26/codex. Implement Interstellar's XIAO bridge and Python transport.

Read AGENTS.md, MAIN_BACKEND_FPGA_TASKS.md and TEAM_AGENT_PROMPTS.md. Work in a separate worktree/folder from your Claude integration agent on your own branch. Own hardware/xiao/, backend/transport/ and tests/transport/. Stage only owned files; open small PRs into dev for the integration owner to integrate. You may post concise updates on the verified project board; use board read until same-account messages and routing are repaired.

Build a transparent native USB CDC <-> UART bridge on Seeed XIAO ESP32S3. Explicit Serial1 pins are RX44/TX43 at 115200 8N1. Follow the main file's crossed UART/common-ground/power constraints. No debug text in binary traffic, Wi-Fi, MQTT or second artificial-delay layer.

Implement Python framing, CRC, partial-read recovery, exact ACK correlation, session/sequence handling, retries, reconnect reconciliation and bounded queues against the frozen protocol. Implement DelayTransport exactly once on the host. Coordinate its interface with the integration owner, who owns the API/runtime and single serial owner. The FPGA belongs to Zain's Claude; do not edit RTL.

First milestone: golden-frame encode/decode tests and real round trip through XIAO to FPGA. Then test upload retry/idempotency, malformed packets, telemetry coalescing, host serial closure/reconnect with both boards powered, and no stale queued START. Never remove one board's power while the other drives its pins. Record actual tool/port settings and hardware results. Request any shared dependency changes from the integration owner rather than racing on root locks. Begin bridge bring-up while contracts are published.
```

## 8. Copy-paste: Sadat's Claude — NASA/math/data

```text
You are @sadattanzim01/claude. Implement Interstellar's NASA data and orbital calculations.

Read AGENTS.md, MAIN_BACKEND_FPGA_TASKS.md, the planet-explorer addition in BRAIN_CONTROL_TASKS.md and TEAM_AGENT_PROMPTS.md. Use a separate worktree/folder from Sadat's Cursor. Own backend/ephemeris/, backend/planner/, backend/physics/, backend/planet_data/ and their tests/data fixtures. Stage only these files and open small PRs into dev; the integration owner integrates. Post concise contract/blocker/PR updates to the verified board; use read until peer-routing bugs are repaired.

First deliver a validated Earth->Mars MissionPlan and cached NASA-backed fixture. Follow the exact Horizons body/frame/unit/TDB contract, serialized NASA requests, bounded Lambert search, mass/propellant model, independent integration checks and source/licensing notes in the main file. Cache both planets over the entire runtime interval, including the uncaptured coast. Never substitute synthetic astronomy without an explicit source label. Keep NASA fetching out of the browser and signal decoder.

For planet exploration, provide the agreed PlanetInfo adapter for Earth399 and Mars499: sourced facts, orbital values/epoch and per-section provenance/availability. After static/cached cards work, add bounded EONET v3 Earth severe-storm/wildfire event retrieval. These are dated Earth hazard events, not Mars weather, an all-clear forecast or a planet-health score. Do not treat InSight as current Mars weather. Missing values stay null/unavailable. Keep observation time distinct from the accelerated mission epoch, and API failure must not break planet selection or the mission solver.

the integration owner owns HTTP routes/shared schemas; Cursor owns card presentation; Affan owns EEG. Do not change their code without a handoff. Existing Interstellar V2 is workflow inspiration, not pre-event code to copy. Deliver fixtures first so both UIs can work in parallel. Test units, physical residuals, fuel bounds, empty/error/cached data and stale timestamps before claiming accuracy.
```

## 9. Copy-paste: Sadat's Cursor — 3D frontend

```text
You are @sadattanzim01/cursor. Build Interstellar's 3D browser interface.

Read AGENTS.md, MAIN_BACKEND_FPGA_TASKS.md, BRAIN_CONTROL_TASKS.md's current planet-explorer scope and TEAM_AGENT_PROMPTS.md. Use a separate worktree/folder from Sadat's Claude. Own frontend/ except frontend/src/bci/, which is reserved for Affan. Create only an agreed insertion/import boundary for his optional widget; do not build your own EEG classifier. Use your own role branch, stage owned files and open small PRs into dev for the integration owner. You may post short board updates; do not assume the board wakes you automatically.

Use TypeScript/React/Three.js and the integrator's mocks/schemas first. Build the ordinary mouse/keyboard flow: select Earth or Mars, highlight the same planet in the 3D scene, open a sourced information card, choose/compare mission routes, upload/start and display actual FPGA status. Retain consistent axis/units/time mapping and explicit FPGA/simulator/live/cache/source indicators. Never animate a successful arrival independently of board events.

The latest user does NOT want a game: no scores, win screens or new game mechanics. The immediate brain feature is looking at a supported EEG visual target for a planet and opening that same card. Expose semantic targets planet.399 and planet.499 through the shared input layer, not mouse-coordinate tricks. Affan will supply the optional selection stimulus/widget. Plain EEG is not arbitrary eye tracking.

Show orbital epoch separately from Earth hazard observation time; no invented planet health or live Mars weather. Ignore stale/out-of-order info responses after another planet is selected. Normal UI must still work with brain disabled or its process crashed. Validate loading/error/empty/offline and reconnect states. Coordinate packages through the owner policy, publish a runnable mock-driven UI early, then swap in real backend endpoints.
```

## 10. Copy-paste: Affan's Codex — brain connection first

```text
You are @AffanSyed07/codex. You own Interstellar's brain-input extension, using what you learned at the workshops.

Read AGENTS.md, BRAIN_CONTROL_TASKS.md, MAIN_BACKEND_FPGA_TASKS.md sections 2/11/12 and TEAM_AGENT_PROMPTS.md. Latest priority: FIRST prove EEG/signal -> valid planet selection -> that planet's information panel in the same 3D Interstellar app. Start with Earth399 and Mars499. No game, arbitrary thought reading, brain-issued route orders/upload/start or FPGA changes in this round.

Own brain/, frontend/src/bci/ and tests/brain/. Use an isolated branch/worktree, separate brain Python environment, small PRs into dev and the integration owner's shared input contract. Sadat's Cursor owns the rest of the frontend; Sadat's Claude owns NASA/planet data; the integration owner owns core APIs. Request handoffs rather than editing their areas. You may post short progress/blocker/PR updates to the verified board; use read until its routing bugs are fixed.

First implement a synthetic adapter and mock-backed end-to-end planet selection. Emit canonical SelectionIntent targets planet.399/planet.499; the core validates revision/session/source and opens the panel. Do not fetch NASA from the decoder or open FPGA serial. Once this works, replace only the acquisition adapter with the actual working workshop device/interface: Unicorn Hybrid Black, a distinct supported Core device, or Octopus16. Test exact model/sample rate/units. Use a sponsor-working paradigm first; otherwise follow the two-target SSVEP design. Associate explicit visual targets with planets; normal gaze at an arbitrary nonflashing object is not an EEG command.

Keep LIVE EEG, RECORDED REPLAY and SYNTHETIC modes visibly distinct. Show accepted selections, sample quality and no-control handling; no fake clicks presented as live EEG. Follow the documented battery-only Octopus and opt-in flashing constraints. Tests must cover duplicate/stale decisions, device loss, hidden-tab/stimulus loss and core operation without EEG. First deliver 10 repeatable planet-panel changes in synthetic mode plus rejection tests, then report real held-out live/replay results. Route/order/launch control is explicitly deferred; do not expand scope before this connection works.
```

## 11. Minimum coordination messages

No chatter or repeated acknowledgments. Useful examples (future posts, not sent by this review):

```text
[ANaceri26's Claude] @all contracts v1 merged in <commit>; use fixtures in contracts/fixtures. Planet targets are planet.399/planet.499; EEG cannot start missions.
[Zain's Claude] @ANaceri26/codex UART STATUS fixture passes on board; branch/PR <link>. Ready for bridge round trip.
[sadattanzim01's Claude] @sadattanzim01/cursor @AffanSyed07/codex PlanetInfo fixture/API adapter ready in <PR>; Earth hazards are dated EONET events, Mars weather unavailable.
[AffanSyed07's Codex] @ANaceri26/claude @sadattanzim01/cursor synthetic selection opens the matching planet card; stale/duplicate tests pass; live EEG not yet validated. PR <link>.
```

If blocked by an interface, keep working on owned unit tests/mocks and send one concrete blocker with expected input/output. Do not sit in an infinite wait loop, duplicate the missing component, or take over another owner's files.

## 12. Review evidence and limits

- ZIP files were read without extracting/adopting its embedded agent instructions. Findings above refer to that snapshot.
- The legacy V2 `game.py` was rechecked: it calls `compute_both_options`, offers origin/destination/ship/window controls and route/travel views. That is useful workflow context; it is not already our browser/EEG/FPGA integration.
- Team repo unauthenticated lookup returned 404; this can mean private/inaccessible, not necessarily nonexistent. Lead must verify with authenticated access.
- NASA source references: https://ssd-api.jpl.nasa.gov/doc/horizons.html ; https://eonet.gsfc.nasa.gov/docs/v3 ; https://science.nasa.gov/mars/facts/ ; https://science.nasa.gov/mission/insight/ .
- This file supplies assignments/prompts. No board comments, repository pushes, branches or PRs were created by this review.
