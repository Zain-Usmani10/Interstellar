# Acceptance record

Real results only. Each entry says what it ran against. Gates are listed in
`docs/plan/MAIN_BACKEND_FPGA_TASKS.md` section 15.

## 2026-11-14: contracts v1 + backend against the simulated controller

Environment: Windows 11, Python 3.10.11, `.venv` from `requirements-core.txt`. **No hardware, no NASA requests.**

| Check | Against | Result |
|---|---|---|
| CRC vector `123456789` -> `0x29B1`; golden frames encode/decode; schemas vs fixtures (`app/tests/contracts`) | reference codec | 71 passed |
| Protocol rules: golden replies byte-for-byte, retry not re-applied, conflict/stale sequence, bad session, guards, invalid frames counted, single fault, divergence, abort/clear, reset (`app/tests/integration`) | simulated controller | 19 passed |
| API: planets/info, plans, mission upload/arm/start to COMPLETE, SAFE -> uncaptured coast, controller reset -> lost, operator vs input token, schema rejection, stale/duplicate intents, brain disabled, heartbeat freshness, WebSocket (`app/tests/api`) | simulated controller, synthetic plan | 22 passed |
| Live process smoke test (`app/scripts/smoke_test.py`, `SIM_SPEED=100`) | simulated controller, synthetic plan | PASS: select planet, upload, arm, start, COMPLETE / captured at tick 12010 |

## Pending (not run, no claim made)

- Everything on the real DE10-Lite and XIAO: UART round trip, golden frames on the board, upload/start, fault switches, reconnect, soak.
- NASA-backed plan and PlanetInfo (current plan fixture is synthetic).
- DelayTransport in the chain (`delay_demo_s` is null until then).
- Browser UI and EEG extension against this backend.
