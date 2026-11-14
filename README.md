# Interstellar

**Hack the Nest 2026.** A NASA-data mission planner whose missions are actually flown by a real FPGA.

The laptop pulls real planet positions from **NASA/JPL Horizons**, searches Earth→Mars transfer orbits (Lambert solver), and offers two routes: least propellant and earliest arrival. The chosen plan is uploaded through a **XIAO ESP32S3** bridge to a **DE10-Lite FPGA**, which runs the mission clock, fires the departure and capture burns, keeps the fuel ledger, and masks injected register faults with triple-redundant voting. The 3D browser view only shows what the board reports: if the FPGA doesn't fire the burn, the ship doesn't arrive.

Optional extension: an EEG headset selects Earth or Mars to open that planet's NASA information card.

> **Status: in development.** Run instructions will be added here as components land.

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
