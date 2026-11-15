# Interstellar

**Hack the Nest 2026.** A NASA-data mission planner whose missions are actually flown by a real FPGA.

The laptop (the **Central Control Station**) takes real planet positions from **NASA/JPL Horizons**, solves transfer orbits between planets, and offers two routes per trip: one that saves the most fuel and one that gets there fastest. The chosen plan is uploaded through a **XIAO ESP32S3** bridge to a **DE10-Lite FPGA** (the **shuttle**), which runs the mission clock, fires the departure and capture burns, keeps the fuel ledger, and masks injected register faults with triple-redundant voting. The 3D browser view only shows what the board reports: if the FPGA does not fire the burn, the shuttle does not arrive.

During every flight the laptop goes silent for a while (a **blackout**). The shuttle keeps flying and counting down the days by itself; the laptop shows only a labelled estimate, then syncs to what really happened when contact returns.

Optional extension: a two-choice brain input selects a planet and opens its information card (synthetic signals today).

## What is real and what is not

| Part | State |
|---|---|
| Planet positions, route maths, fuel | Real NASA/JPL data, stored in the repo so the demo runs offline. 13 routes between Mercury, Venus, Earth, Mars and Jupiter, each checked by an independent re-flight of the trajectory. |
| Shuttles | Two model ships ("Standard" and "Long-range"). They are not real spacecraft. |
| Simulated controller | A software stand-in for the FPGA. The screen says "Simulator" when it is in use. |
| Real FPGA | Reported by the FPGA owner on the real board through the XIAO: a full mission to capture and a blackout run. The fault-switch runs and the seven-segment readout are not confirmed on the board yet. See the board log in `app/hardware/fpga/README.md`. |
| Brain input | Synthetic signals and a keyboard simulator only. No live EEG result is claimed. |

Model limits: only the Sun's gravity during the coast, instant burns, no gravity assists, no launch from the surface, and "best" means best within the searched grid of dates. Trips of months or years are compressed to a 5 second countdown plus a 60 second flight.

## Run it (no hardware needed)

Needs Python 3.10+ and Node.js on Windows. Use two Git Bash windows in the repo folder.

```
app/scripts/start-backend.sh simulator          # window 1: backend on http://127.0.0.1:8000
cd app/frontend && npm ci && npm run dev         # window 2: GUI
```

Open **http://localhost:5173** (not 127.0.0.1). The first backend run creates `.venv` from `requirements-core.txt`.

```
.venv/Scripts/python -m pytest app/tests        # all tests, offline
```

## Run it with the real FPGA

1. Program the DE10-Lite (see `app/hardware/fpga/README.md`). Wire the XIAO to header JP1 as in `app/hardware/xiao/README.md` (3.3 V only).
2. Check the link: `python -m app.hardware.xiao.probe --port COM10 --seconds 5` should print about ten STATUS frames a second with no CRC errors.
3. In `.env` (copy `.env.example`): `TRANSPORT_MODE=fpga` and `SERIAL_PORT=COM10`. Start the backend and the GUI as above. The screen should say the controller is the FPGA.

Useful settings in `.env`: `AUTO_BLACKOUT=true` (one blackout per flight, from 25 % to 85 % of the flight), `LINK_DELAY_DEMO=false` (keep off for the blackout demo).

## Two-minute demo

1. **Plan (about a minute).** Open the overview, click a planet, open **From → To**, pick a destination and a shuttle, and compare "Saves the most fuel" with "Gets there fastest". Say: positions are NASA data, the route is solved on the laptop.
2. **Launch.** Prepare, arm, launch. Five-second countdown on the screen and on the board, then the shuttle leaves.
3. **Blackout.** About 15 seconds after departure the laptop loses contact by itself and shows an estimate. The board shows `nL` and keeps counting down the days. Optional: pull the two data wires between the XIAO and the FPGA (leave the XIAO on USB) and put them back before the last ten seconds.
4. **Fault.** Flip switch SW0: the fault is outvoted and the flight continues. For the second run flip SW1 instead: the board goes to safe mode and the shuttle misses the planet.
5. **Sync.** Contact returns shortly before arrival; the screen shows what happened while out of contact.

Between runs: clear the mission, and use **Reset fleet** if a shuttle has moved or was lost (a route can only launch from a planet where a shuttle of the right class is docked).

## Repository map

| Path | What |
|---|---|
| `app/` | All project code (backend, frontend, FPGA, XIAO, brain, contracts). See `app/README.md`. |
| `docs/plan/` | The design specs. Start with `MAIN_BACKEND_FPGA_TASKS.md`. |
| `docs/TEAM_SETUP.md` | How a teammate gets set up. |
| `AGENTS.md` | Rules for the team's AI coding agents (ownership, git, board). |
| `tools/board` | Team message board on GitHub issue #1. |

## Team

Abderrahmene (`ANaceri26`) · Sadat (`sadattanzim01`) · Affan (`AffanSyed07`) · Zain (`Zain-Usmani10`)

## AI tools used

Claude Code, OpenAI Codex, Cursor.
