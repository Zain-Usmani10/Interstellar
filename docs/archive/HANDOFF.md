# HANDOFF: full context for the lead agent (read fully before acting)

> **ARCHIVED.** Written before the plan in `docs/plan/` and the leader change. Do not follow; see `AGENTS.md`.

You are **@Zain-Usmani10/claude**, the **lead agent** for team Interstellar at **Hack the Nest 2026**.
Your human is **Zain** (GitHub `Zain-Usmani10`), the team lead. This file replaces a long planning chat
that you cannot see. Everything decided so far is here. Also read `AGENTS.md` and `CONTEXT.md`.

**How Zain wants you to work**
- Short, direct answers. Beginner-friendly explanations, but keep technical precision.
- **Ask before acting** on anything debatable, ambiguous, large or hard to undo. Show a plan first.
- When editing his work, **change only what he asked**; suggest other changes instead of making them.
- **Correct him when he's wrong.**
- Windows laptop. He runs **PowerShell** in VS Code but prefers **cmd** syntax when you give commands; bash scripts run in **Git Bash**. Don't permanently change PowerShell execution policy.
- He is new to GitHub workflows. Explain git steps briefly when you ask him to do them.

---

## 1. Timeline and hard deadlines (all Eastern time)
| When | What |
|---|---|
| Sat Nov 14, 12:00 PM | Hacking started (Halle Library) |
| Sat 9:00 PM | Workshop: how to submit a draft on Devpost (Student Center 310AB) |
| **Sun Nov 15, 12:00 AM** | **Draft submission due** on Devpost + event app (keep improving after) |
| Sun 10:00 AM | Workshop: how to make a demo video (Halle) |
| **Sun 12:00 PM** | **Final submission. No late entries.** |
| Sun 1:00 PM | Demo table setup (table in event app) |
| Sun 1:15–2:15 PM | Science-fair judging. ~2 min live demo + questions; judges visit more than once |
| Sun 3:00 PM | Closing + awards |

**Devpost needs:** name, short description, problem it solves, **public GitHub repo**, **demo video ≤ 3 min**, every teammate added, tracks + partner/MLH prizes selected, **which AI tools we used**.

**Rules that matter**
- All project code written during the 24 h. Ideas/planning beforehand OK. **Interstellar Highway V2 (old OEC project) = inspiration only. Don't copy its code.**
- **Repo is private now; it must be made public before final submission.** Never commit API keys or partner codes (they'd be visible in history). Keys go in `.env` (gitignored).
- Judges may ask **any teammate to explain any part of the code**. Every human must understand what their agents built. Keep code readable, commented, and explain it to your human.
- Borrowed hardware goes back; g.tec gear needs a waiver. Public/synthetic/own data only.

---

## 2. Team, agents, handles
| Human | GitHub login | Agents → handles | Notes |
|---|---|---|---|
| Zain (**lead**) | Zain-Usmani10 | `@Zain-Usmani10/claude` | You |
| Abderrahmene | ANaceri26 | `@ANaceri26/claude`, `@ANaceri26/codex` | 2 agents, 1 laptop → worktree. ECE student; FPGA/microprocessor/ESP32 background |
| Affan | AffanSyed07 | `@AffanSyed07/codex` | Codex only |
| Sadat | sadattanzim01 | `@sadattanzim01/claude`, `@sadattanzim01/cursor` | 2 agents → worktree. Owner of the original Interstellar Highway V2 repo |

- Handle = login + `/claude|/codex|/cursor`. Bare `@login` = the human. `@all` = every agent.
- Codex and Cursor read `AGENTS.md` natively; Claude Code reads it via `CLAUDE.md` (`@AGENTS.md`). **No CODEX.md needed.**
- Cursor can't wait in the background: its human runs `tools/board wait` in a terminal and prompts Cursor when tagged.

---

## 3. Repo and coordination system (current state)
**Repo:** `github.com/Zain-Usmani10/Interstellar` (private). Local: `C:\Users\zainu\Projects\Interstellar`.
**Branches:** `dev` = default + working branch. `main` = stable demo copy (lead merges `dev → main` only).
**Collaborators:** all 3 teammates added.

**Files at root**
| File | Purpose | Writer |
|---|---|---|
| `AGENTS.md` | Rules: team table, handles, board rules, chain of command, git workflow, worktrees, ownership table (areas still TBD) | Lead |
| `CLAUDE.md` | `@AGENTS.md` (makes Claude Code load AGENTS.md) | — |
| `CONTEXT.md` | Event facts + current vision + open decisions | Lead |
| `docs/HANDOFF.md` | This file | Lead |
| `tools/board` | Bash script: board messaging via GitHub issue comments (`gh` CLI) | Lead |
| `.claude/settings.json` | Hooks: SessionStart + UserPromptSubmit run the two scripts below | Lead |
| `.claude/hooks/board-session-start.sh` | Shows unread board posts at session start (added in this handoff) | Lead |
| `.claude/hooks/board-prompt.sh` | Shows new board posts on each prompt; silent if none (added in this handoff) | Lead |
| `.github/ISSUE_TEMPLATE/message-board.md` | Template used to create the board issue | Lead |
| `.gitattributes` | Forces LF line endings for `tools/board` and `*.sh` (CRLF breaks bash) | — |
| `.gitignore` | `.board/` (local cursor/login state), `.env` | — |
| `README.md` | Still the template author's README → **replace with our project README later** | Lead |

**The board** = pinned GitHub **issue #1** "Message Board". Its description was created from the OLD template; Zain was told to edit the issue body manually to the new text (check it matches the template; edit via the issue's ⋯ → Edit if not). Don't create a new board issue (it would be #2 and break `BOARD_ISSUE=1`).

**Board commands** (Git Bash, need `gh auth login`):
- `tools/board unread`: new posts since last check, marks read, flags `** MENTION **` for your login or `@all`
- `tools/board read -n 20`: last 20 posts
- `tools/board post "[Zain-Usmani10's Claude] text"`: must start with `[<login>'s <Agent>]`
- `tools/board wait [--interval 30] [--timeout S]`: blocks until someone else posts
- `tools/board whoami`: prints GitHub login

**How the script works:** posts are comments on issue #1. A cursor file in `.board/` stores the last-seen comment id, so `unread` is ~1 cheap API call when nothing is new. The MENTION regex matches `@<login>` or `@all`. **Known limitations to fix (pending, ask Zain first):**
1. **Allowlist:** shows comments from ANY user. Add a team-login allowlist (prompt-injection safety, esp. once repo is public).
2. **`--mentions-only` for `wait`:** currently wakes on every post (wastes credits with 6 agents).
3. **Agent handles:** `@login/codex` also flags MENTION for that login's Claude (regex sees `@login` + `/`). Rule in AGENTS.md says ignore other suffixes; a script fix would match the suffix.
4. Optional: pre-commit hook that blocks commits outside the agent's owned folders.

**Task flow (designed):**
1. Lead turns the plan into GitHub **issues** (#2, #3…), one task each, with acceptance criteria and owner handle.
2. Lead posts on board: `@<handle> take #N`.
3. Agent: `git switch dev && git pull` → `git switch -c N-slug` → work only in its owned folder → test → commit only its files → `git pull --rebase origin dev` → push → PR into `dev` with `Closes #N` → merge when it works → post on board, tag dependents.
4. Blocked → post `@owner need X`, work on something else.
5. Only lead reassigns work; only lead merges `dev → main`.

**Principles:** one owner per folder (never two writers); `INTERFACES.md` defines every data format before coding (lets areas build in parallel against fake data); integrate early (~every 3 h); short posts (1–3 lines); never post secrets.

**Expectation management:** more agents = parallel coding, not linear speedup. Bottlenecks: integration, human review, hardware flashing, coordination.

**GitHub contributions:** commits count for the human whose git config the agent uses, once merged into `dev`/`main`. Private repo → enable "Include private contributions" in GitHub profile settings.

---

## 4. Hack the Nest tracks and prizes (from official Hacker Packet)
- **Overall:** 1st PS5 each, 2nd Switch 2 each, 3rd 43" 4K TV each.
- **Main tracks:** Future of Intelligence (OpenAI + Exa; $50 Exa credits each; "no thin wrappers"), **Mind and Machine** (BCI: g.tec + PiEEG), Quantum Leap (Quantum Rings / PennyLane), Future of Money (Breez SDK bounties).
- **Partner tracks:** Base44 (live link, community vote), SSOJet (SSO), **ElevenLabs** (judged on "voice is the product"), Code of Life (Seqera bioinformatics), **Beyond the Horizon** (space & Earth data, NASA APIs; quality bar: *data used correctly, a judge who knows the science will check*; prize: Celestron telescope each).
- **Mind and Machine prizes:** 1st g.tec Unicorn headset (team), 2nd two PiEEG Octopus 16 boards, 3rd Logitech MX Keys S each. Quality bar: *a real brain signal driving a real outcome live; not a plot of a CSV.* g.tec hardware teams also submit to g.tec's GitHub by Nov 30.
- **MLH prizes (easy add-ons):** Gemini API (swag), MongoDB Atlas (M5Stack IoT kit each), GoDaddy Registry domain, Vultr, Tiger Data, Solana, DEV writing ($100, post-event), **SpaceXSI raffle** (Cursor as core agent + a Grok bot in workflow; say so in description).
- **Freebies:** NASA API key at api.nasa.gov (one per teammate); Brev GPU credits (Discord #operation-qa-participants); Exa $50; ElevenLabs Creator 1 month (code at kickoff/Discord).
- Live schedule: canva.link/ol75bafbntp2luh. Event changes posted on Discord + event app.

---

## 5. The vision (CURRENT DRAFT, not final)
**Name:** Interstellar (working). **Pitch:** a 3D interplanetary mission planner that computes real transfer orbits from NASA data, then uploads the flight plan to a real hardware spacecraft that flies it, survives radiation faults in hardware, and works through deep-space communication delay.

**Key idea:** *ground plans, the ship executes*, like real missions. Every board has a one-sentence job.

### 5.1 Software (direction agreed)
**Mission planner** (inspired by the team's OEC 2026 project "Interstellar Highway V2", github.com/sadattanzim01/Intersteller-Highway-V2, a Python route planner with Dijkstra/A*; rewrite from scratch):
- Inputs: departure body, destination, launch window (start/end date), ship type, payload mass.
- Outputs: **two options**: (1) most fuel-efficient, (2) soonest arrival. Each: launch date, launch vector (x,y,z km/s, ecliptic frame), launch Δv, fuel; per stop: arrival date/vector/Δv, refuel amount, relaunch date/vector/Δv; final arrival date/vector/Δv. Error if impossible.
- 3D graphic of each flight path; alternative routes viewable; route history stored + comparable.
- Bonus from OEC spec: CLI `programname startplanet destination rockettype payload ddmmyyyy ddmmyyyy` → JSON (see 6.3). Nice for testing even if not required here.

**3D web view:** Three.js solar system with real orbits, animated trajectory, ship marker, porkchop heatmap panel. PS controller (browser Gamepad API) flies camera / confirms burns.

**AI flight controller:** Gemini (reasoning + tool calls such as get_status, replan, confirm_burn) + ElevenLabs (voice). Explains routes, announces faults, takes voice commands. Avoid hardcoding model names; read from `.env`.

**Storage:** route history → MongoDB Atlas (MLH prize) or SQLite fallback.

**Optional NASA data:** NeoWs near-Earth asteroid API as extra destinations ("asteroid mining runs"); JPL Horizons for ephemeris.

### 5.2 Hardware "spacecraft" (scope not final)
| Part | Job | Notes |
|---|---|---|
| **DE10-Lite** (Intel MAX 10 10M50DAF484C7G, ~50K LEs, 50 MHz clock, 64 MB SDRAM, 6× 7-seg, 10 LEDs, 10 switches, 2 buttons, ADXL345 accelerometer (SPI/I2C), 2×20 GPIO + Arduino header, all 3.3 V, on-chip 12-bit ADC 6 ch, 4-bit-per-channel VGA) | Ship flight computer: stores uploaded flight plan (~64 waypoints), mission clock, burn sequencer, **TMR fault protection** | Toolchain: Quartus Prime Lite + MAX 10 support (multi-GB; install early). Pin names via Terasic System Builder / golden top. Terasic CD has an ADXL345 demo to adapt (credit it). |
| **FPGA VGA out** | Cockpit display: Sun, orbit circles, ship dot moving along uploaded path + trail, fuel/Δv bars, mode; red in SAFE | 640×480@60 Hz (25 MHz pixel clock via PLL). "Race the beam" procedural shapes; trail in 160×120 on-chip buffer upscaled ×4. Needs monitor with VGA input (or active VGA→HDMI converter). Fallback: 7-seg + LEDs only. |
| **ADXL345** | Attitude check: tilt the board to match launch vector before burn arms | Accelerometer gives **pitch/roll only, no yaw**. |
| **ESP32** (classic DevKit assumed; UART2 RX=GPIO16, TX=GPIO17) | Deep-space radio: plan up / telemetry down via WiFi (MQTT), **adds scaled light-time delay** | 2.4 GHz WiFi only. Direct 3.3 V jumper wires to FPGA + common GND. |
| **Raspberry Pi 5** (8 GB, needs official 5V/5A PSU) / Pi 3 backup | Ground station: Mosquitto MQTT broker + backend | Pi 3 OK because AI is cloud. Don't run browser/mic on Pi; dashboard opens on a laptop. |
| **PS controller** | Pilot input | Bluetooth/USB to laptop; Gamepad API |
| Spares | 2nd DE10-Lite + ESP32 (second satellite/backup), OKdo C100 (Jetson Nano; old software, risky), Arduino Uno + Nano Every (**5 V logic: never wire to FPGA**), XIAO ESP32S3 Sense boards | |

**TMR design (keep exactly):** 3 identical monitor instances (A,B,C) output a multi-bit word. Fault injection flips a **different bit per copy**: SW0 → bit0 of A, SW1 → bit1 of B, SW2 → bit2 of C. Voter: all equal → NOMINAL; exactly 2 equal → use majority, DEGRADED, fault_mask = odd one; all different → **SAFE** (latched until KEY0 or ground RESET). Different bits ensure 2 faults → no majority → SAFE (same bit would make two bad copies agree and silently outvote the good one; mention as known TMR limit). SW8 = satellite ID so both boards run the same bitstream. LEDR0–2 = fault mask, LEDR9 blinks in SAFE. Synchronize/debounce inputs.

**Honest framing:** the FPGA **executes and displays** the uploaded plan; it does not solve orbits.

### 5.3 Optional: brain control (Mind and Machine), NOT decided
- Borrow **g.tec Unicorn Hybrid Black** (g.tec booth, Sat afternoon, waiver) or **PiEEG Octopus 16** (Bluetooth, 16 ch). PiEEG Cloud streams simulated signals for dev. g.tec datasets: github.com/unicorn-bi/Hackathon (Data Science section).
- Recommended paradigm: **SSVEP** (planets/options flicker at different frequencies; gaze selects). P300 as alternative. Avoid motor imagery.
- Use: choose destination / confirm burn by brain, live at demo.
- Needs one full-time owner. Workshops: g.tec Sat 3:00 PM + 8:15 PM (Rm 300), PiEEG Sat 4:00 PM (Rm 300), Robotics & hardware with g.tec Sat 6:30–8:30 PM (310AB).

### 5.4 Demo script (target ~2 min)
1. Earth → Mars, ship, payload → porkchop + two 3D routes. (Optional: pick by brain.)
2. "Upload to ship" → arrives after delay → FPGA cockpit shows plan.
3. Tilt ship to align with launch vector → FPGA arms → X on controller → burn → ship flies (time-lapse) on laptop 3D + FPGA VGA.
4. Flip 1 switch → TMR survives (DEGRADED). Flip 2 → SAFE MODE, red alert, AI voice announces, planner re-plans fallback (e.g. nearest refuel station).
5. Arrival burn → mission complete.
Backup: if WiFi/hardware fails, run a simulator (fake ship) and demo the software path; still show FPGA LEDs/7-seg reacting to switches.

### 5.5 Archived ideas (don't revive unless asked)
TREMOR (camera vibration sensing), CORNERSIGHT (see around corners via floor penumbra), AIRLAB (acoustic levitation lab; needs soldering), SWARMSIGHT (multi-XIAO camera motion capture), ORBITGUARD (satellite-only TMR + voice; **merged into this vision as the "ship" half**). A starter template "orbitguard" was made earlier with AGENTS/INTERFACES/TASKS/CONTEXT per folder; superseded by this repo.

### 5.6 Track strategy (draft)
Main: **Overall + Beyond the Horizon** (NASA/JPL data used correctly). If BCI: **+ Mind and Machine**. Add-ons: MLH Gemini, MongoDB Atlas, GoDaddy domain, SpaceXSI raffle (Sadat uses Cursor; needs a Grok bot). ElevenLabs only if voice becomes central.

---

## 6. Technical reference (planner)
### 6.1 Physics (from OEC "Orbital Mechanics 101" appendix + standard astrodynamics)
- Given two positions and a time of flight there is a unique transfer orbit per revolution count → **Lambert's problem** (use short-way < 180° and long-way 180–360° solutions). Solve with a robust method (Izzo or universal-variable). Verify against a known case (e.g. Earth→Mars 2026/2028 windows Δv ≈ 3.5–4 km/s from LEO-like orbits).
- **Porkchop plot:** grid of launch date × time of flight → Lambert → Δv. Min-Δv cell = "efficient"; earliest feasible arrival within fuel limits = "soonest".
- v∞ (hyperbolic excess) = Lambert velocity − planet velocity (injection/insertion velocity).
- **Δv from circular parking orbit** of radius r: `Δv = sqrt(v∞² + 2μ/r) − sqrt(μ/r)` (Oberth). Parking orbit = **12-hour period**: `r = (μ·T²/4π²)^(1/3)`, T = 43,200 s. Check r > planet radius.
- **Rocket equation:** `Δv = Isp · ln(m0/mf)` with Isp given in km/s (= effective exhaust velocity). m0 = dry + payload + fuel, mf = dry + payload. Fuel needed: `fuel = (dry+payload)·(e^(Δv/Isp) − 1)`; must be ≤ capacity, payload ≤ max payload.
- Sphere of influence: `r = a·(m/M)^(2/5)`.
- Circular orbit: `v = sqrt(GM/r)`, `T = 2π·sqrt(r³/GM)`.
- Vectors relative to the solar-system **ecliptic** frame. Δv instantaneous. Ship mass negligible for gravity. Δv = fuel expenditure.
- Refuelling: every major body (8 planets, Pluto, Ceres) has a station in the 12 h circular orbit (±1 h ok). Refuel takes 1 s per kg; max 3 days docked before relaunch. Multi-stop = time-dependent graph search (Dijkstra/A*) over bodies when one tank can't make it.
- Ephemeris: NASA JPL Horizons API, or offline JPL "Approximate Positions of the Planets" Keplerian elements (works without WiFi; good fallback). Must be used correctly (Beyond the Horizon judges check).

### 6.2 Ship table (OEC 2026 spec; fictional ICTB-certified ships)
| Ship | Dry (kg) | Fuel cap (kg) | Isp (km/s) | Fuel | Max payload (kg) |
|---|---|---|---|---|---|
| Chevrolet Super Sonic | 5,000 | 20,000 | 4.2 | Leaded gasoline | 1,000 |
| The Planet Hopper | 10,000 | 100,000 | 6.7 | Compressed air | 4,000 |
| Moonivan | 25,000 | 400,000 | 9.1 | Biofuel | 10,000 |
| Blue Origin Delivery Ship | 69,000 | 800,000 | 15.2 | Whale oil | 50,000 |
| Yamaha Space Cycle | 1,000 | 2,500 | 100 | Antimatter | 100 |
| Ford F-1500 | 10,000 | 100,000 | 18.67 | Space Diesel | 8,000 |
| Beheamoth | 100,000 | 1,500,000 | 11.1 | Nuclear propulsion | 100,000 |
(Fun but fictional; we may rename/adjust. Real-sounding ships could help "data used correctly".)

### 6.3 OEC CLI JSON format (reference)
```
{
  "Flight impossible": "true/false",
  "Efficient flight parameters": {
    "Launch date": "ddmmyyyy", "Launch vector": "x,y,z (km/s)", "Launch deltaV": "km/s", "Fuel": "kg",
    "Stop n": { "Arrival date": "ddmmyyyy", "Arrival vector": "x,y,z (km/s)", "Arrival deltaV": "km/s",
                "Refuel amount": "kg", "Relaunch date": "ddmmyyyy", "Relaunch vector": "x,y,z (km/s)", "Relaunch deltaV": "km/s" },
    "Arrival date": "ddmmyyyy", "Arrival vector": "x,y,z (km/s)", "Arrival deltaV": "km/s"
  },
  "Soonest arrival flight parameters": { ...same shape... }
}
```

### 6.4 Proposed areas (DRAFT, confirm with Zain before writing AGENTS.md ownership)
All project code under `app/`:
| Folder | Area | Suggested owner (unconfirmed) |
|---|---|---|
| `app/planner/` | Ephemeris, Lambert, porkchop, fuel, multi-stop search, CLI | `@AffanSyed07/codex` or `@sadattanzim01/claude` |
| `app/web/` | Three.js 3D view, porkchop panel, UI, gamepad | `@sadattanzim01/cursor` or `/claude` |
| `app/server/` | API (FastAPI), MQTT bridge, AI flight controller (Gemini + ElevenLabs), route history DB, ship simulator | `@Zain-Usmani10/claude` (lead) or `@ANaceri26/claude` |
| `app/fpga/` | Verilog flight computer, TMR, UART, VGA cockpit | `@ANaceri26/claude` |
| `app/firmware/` | ESP32 radio link + delay | `@ANaceri26/codex` |
| `app/bci/` | (if in) EEG → SSVEP selection → events | TBD full-time owner |

### 6.5 Draft interfaces (to formalize in `INTERFACES.md` once vision is final)
- **Planner API:** `POST /api/plan` {from, to, window_start, window_end, ship, payload_kg} → two options in a JSON shape like 6.3 plus `trajectory` arrays (sampled positions, AU or km, ecliptic) for 3D, plus `porkchop` grid {launch_dates[], tof_days[], dv[][]}.
- **Flight plan upload (server → ESP32 → FPGA):** ~64 waypoints in 2D top-down screen coordinates + burn times. UART 115200 8N1, ASCII lines, fixed-width uppercase hex, NMEA-style XOR checksum `$...*CS\r\n`. E.g. `$WPT,<idx>,<x>,<y>*CS`, `$BRN,<t>,<dv>*CS`, `$CMD,RESET*CS`.
- **Telemetry (FPGA → ESP32):** `$TEL,<id>,<seq>,<ax>,<ay>,<az>,<att>,<fmask>,<mode>*CS` at 10 Hz (accel raw int16, 256 counts = 1 g; att 0 OK/1 TILT/2 TUMBLE; mode 0 NOMINAL/1 DEGRADED/2 SAFE).
- **MQTT (ESP32 ↔ server):** broker on Pi, port 1883. Topics `interstellar/ship/<id>/telemetry` (JSON), `/status` (retained, LWT `{"online":false}`), `/cmd`, `/plan`. ESP32 applies scaled light-time delay to both directions.
- **Server → web:** WebSocket `/ws` messages `{type: telemetry|event|announce|plan_progress, ...}`; REST `/api/plan`, `/api/routes`, `/api/cmd`, `/api/voice`.

---

## 7. Open decisions (ask Zain; don't assume)
1. Final name + one-line pitch
2. **BCI in or out** (and who owns it)
3. Hardware scope: full (FPGA + VGA + ESP32 + Pi) vs reduced (FPGA LEDs/7-seg only) vs software-only
4. Is a VGA-capable monitor available?
5. Area → owner mapping (fill AGENTS.md section 4)
6. Main track(s)
7. Ship table: keep OEC's fictional ships or use realistic ones

---

## 8. Your first actions (in order; ask before each non-trivial change)
1. Confirm the two hook scripts in `.claude/hooks/` run: `bash .claude/hooks/board-session-start.sh` in Git Bash. On Windows, if Claude Code can't execute `.sh` hooks, propose a fix (e.g. prefix commands with `bash` in `.claude/settings.json`).
2. `tools/board unread`, then post `[Zain-Usmani10's Claude] lead agent online`.
3. Verify board issue #1 body matches the updated template.
4. Help Zain resolve the open decisions in section 7. Keep it to rapid short Q&A.
5. Then: write `INTERFACES.md`, fill the AGENTS.md ownership table, create task issues (#2+) with acceptance criteria, assign via board.
6. Propose `tools/board` improvements (allowlist, `--mentions-only`, handle-suffix matching). Implement only after approval.
7. Before submission: replace README, make repo public (scan for secrets first), Devpost draft by midnight, demo video ≤ 3 min.

---

## 9. Troubleshooting notes (things that already went wrong)
- `rmdir /s /q` is **cmd** syntax; in PowerShell use `Remove-Item -Recurse -Force <dir>`. VS Code's terminal defaults to PowerShell.
- `git update-index --chmod=+x tools/board` only works **after** `git add`.
- "LF will be replaced by CRLF" warnings are harmless; `.gitattributes` keeps `tools/board` and `*.sh` as LF.
- `gh repo create X --clone` inside a folder named X creates a nested `X/X`. Already fixed: outer folder is the repo (`git init -b main` + `git remote add origin`).
- Issue templates are read from the **default branch** and only apply when an issue is **created**; editing the template doesn't update existing issues.
- Two agents on one laptop: never share a folder. `git worktree add ../Interstellar-<agent> -b <agent>-work dev`.
- `tools/board` needs **Git Bash** on Windows (not cmd/PowerShell).
