# Interstellar

**Hack the Nest 2026.** A NASA-data mission planner whose missions are actually flown by a real FPGA.

The laptop pulls real planet positions from **NASA/JPL Horizons**, searches Earth→Mars transfer orbits (Lambert solver), and offers two routes: least propellant and earliest arrival. The chosen plan is uploaded through a **XIAO ESP32S3** bridge to a **DE10-Lite FPGA**, which runs the mission clock, fires the departure and capture burns, keeps the fuel ledger, and masks injected register faults with triple-redundant voting. The 3D browser view only shows what the board reports: if the FPGA doesn't fire the burn, the ship doesn't arrive.

Optional extension: an EEG headset selects Earth or Mars to open that planet's NASA information card.

> **Status: in development.** The backend runs today against a **simulated controller** with a **synthetic** route. Real FPGA, NASA data and the browser UI are still landing; see `app/artifacts/acceptance.md` for what has actually been tested.

## Run the backend (no hardware needed)

Needs Python 3.10+ on Windows. From the repo root:

```
app\scripts\start-backend.ps1 simulator      # PowerShell
app/scripts/start-backend.sh simulator        # Git Bash
```

The first run creates `.venv` from `requirements-core.txt`. The backend listens on `http://127.0.0.1:8000` and prints an operator token. Routes are listed in `app/contracts/api_v1.md`.

```
.venv\Scripts\python -m pytest app/tests                        # all tests
.venv\Scripts\python app/scripts/smoke_test.py <operator-token>  # full mission against the running backend
```

Settings live in `.env` (copy `.env.example`). `TRANSPORT_MODE=fpga` needs the serial transport and a wired board; it refuses to start otherwise.

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
