# CONTEXT: Hack the Nest 2026 (read this first)

> **Note:** event facts and deadlines below are still valid. The project vision and hardware scope are **superseded** by `docs/plan/` (no VGA, accelerometer, MQTT, Raspberry Pi, PS controller, Gemini, ElevenLabs or MongoDB). Roles/owners: see `AGENTS.md`.

> Status: **vision draft, not final.** Items marked **[DECIDE]** are open.
> Source of truth for event facts: the official Hacker Packet (Nov 2026) + hackthenest.tech.

---

## 1. The event (facts)
- **Hack the Nest 2026**, Eastern Michigan University (Ypsilanti, MI). MLH event. 600+ hackers, teams of 1–4.
- **Hacking:** Sat Nov 14 **12:00 PM** → Sun Nov 15 **12:00 PM** (Halle Library, badge required overnight).
- **Draft submission:** Sun **12:00 AM** (midnight) on Devpost + event app. Keep improving after.
- **Final submission:** Sun **12:00 PM** on Devpost. **No late entries.**
- **Demos:** Sun 1:15–2:15 PM, Student Center Ballroom, science-fair style. ~**2 min live demo** then questions. Judges visit more than once.
- **Judges may ask ANY teammate to explain ANY part of the code.** Everyone must understand what the agents wrote.

### Submission must include (Devpost)
- Name, short description, the problem it solves
- **Public GitHub repo** (our repo is private now → make public before submitting; **no keys in history**)
- **Demo video ≤ 3 min** (MLH requirement)
- Every teammate added; track(s) + partner/MLH prizes entered
- **Which AI tools we used** (Claude Code, Codex, Cursor, Gemini, etc.)

### Rules that affect us
- **All project code is written during the 24 hours.** Ideas/planning beforehand are fine. Old projects (e.g. Interstellar Highway V2) = inspiration only, no copied code.
- Partner keys/codes never committed to GitHub, never posted publicly.
- Borrowed hardware goes back; g.tec gear needs a signed waiver.
- Public, synthetic or our own data only. No medical advice.

### Prizes (relevant)
- **Overall:** 1st PS5 each · 2nd Switch 2 each · 3rd 43" 4K TV each
- **Beyond the Horizon** (space & Earth data, NASA/Michigan Space Grant): Celestron telescope each. Quality bar: *data must be used correctly; a judge who knows the science will check.*
- **Mind and Machine** (BCI, g.tec + PiEEG): 1st g.tec Unicorn headset · 2nd two PiEEG Octopus boards · 3rd Logitech MX Keys S each. Quality bar: *a real brain signal driving a real outcome live; not a plot of a CSV.*
- **Best Use of ElevenLabs:** judged on whether **voice is the product**, not a bolted-on feature. (Weak fit for us unless voice is central.)
- **MLH (easy add-ons):** Gemini API (swag) · MongoDB Atlas (M5Stack IoT kit each) · GoDaddy domain · SpaceXSI raffle (Cursor as core agent + a Grok bot in workflow).

### Useful schedule items (Sat)
- 3:00–3:45 PM g.tec BCI workshop (Rm 300) · 4:00–5:00 PM PiEEG workshop (Rm 300)
- 3:00–4:00 PM MLH Gemini workshop (Rm 320) · 4:00–5:00 PM MLH SpaceX Cursor workshop (Rm 320)
- 6:30–8:30 PM Robotics & hardware with g.tec (Rm 310AB) · 9:00 PM "how to submit on Devpost"
- Sun 10:00 AM "how to make a demo video"

---

## 2. Current idea: INTERSTELLAR **[DECIDE: final name]**
**One line:** a 3D interplanetary mission planner that computes real transfer orbits from NASA data, then hands the flight plan to a real hardware "spacecraft" that flies it, survives radiation faults, and works through deep-space communication delay.

**Core split (why every part exists):** ground computers plan, the onboard flight computer executes. Real missions work this way.

### 2.1 Software (finalized direction)
- **Mission planner** (inspired by our OEC "Interstellar Highway", rewritten from scratch):
  - Input: departure, destination, launch window, ship type, payload mass.
  - Real planet positions from **NASA JPL ephemeris** (Horizons API, or offline JPL approximate elements as fallback).
  - **Lambert solver** over launch date × flight time → **porkchop plot** (Δv heatmap).
  - Two answers: **most fuel-efficient** and **soonest arrival**, with dates, vectors, Δv, fuel (rocket equation), refuel stops if one tank can't make it.
  - Δv measured from a circular parking orbit (12 h period) at each body.
  - Route history saved + comparable (candidate: **MongoDB Atlas** → MLH prize).
- **3D visual**: solar system with real orbits, animated transfer trajectories, ship progress. Browser (Three.js).
- **AI flight controller**: Gemini (reasoning/commands) + ElevenLabs (voice). Explains routes, announces faults, takes voice commands.
- Optional extra NASA data: near-Earth asteroid API as destinations ("asteroid mining runs").

### 2.2 Hardware (the "spacecraft") **[DECIDE: scope]**
| Part | Role | Why it makes sense |
|---|---|---|
| **DE10-Lite FPGA** | Ship flight computer: stores the uploaded flight plan (waypoints), runs mission clock + burn sequence, **TMR fault protection** (3 redundant copies + voter; DIP switches inject "radiation bit flips"; 2 faults → SAFE MODE in hardware) | Real spacecraft use FPGAs for deterministic, radiation-tolerant control |
| **FPGA VGA output** | Onboard cockpit display: top-down orbit view, ship dot moving along the uploaded path, fuel/Δv bars, turns red in SAFE MODE | Shows the FPGA *visibly* flying the plan. Needs a VGA monitor |
| **ADXL345 accelerometer (on FPGA board)** | Attitude check: tilt the "ship" to match the launch vector before the burn is armed | Physical link between hardware and the 3D route |
| **ESP32** | Deep-space radio: carries plan up and telemetry down over WiFi, **adds scaled light-time delay** | The delay is *why* the ship must act autonomously |
| **Raspberry Pi 5** (Pi 3 backup) | Ground station server (backend, MQTT broker) | Cheap always-on host |
| **PS controller** | Pilot input: fly the 3D camera, confirm burn (X), abort (O) | Natural "flying" input |

Honest framing for judges: the FPGA **executes and displays** the uploaded plan; it does not solve orbits.

### 2.3 Optional: brain control (Mind and Machine) **[DECIDE]**
- Borrow a **g.tec Unicorn** headset (g.tec booth, Sat afternoon, waiver) or **PiEEG Octopus 16** (PiEEG Cloud has simulated signals for development).
- Most reliable paradigm in 24 h: **SSVEP**: planets/route options flicker at different frequencies; looking at one selects it. Possible second input: **P300**-style selection. Avoid motor imagery (unreliable without long training).
- Use in demo: pick destination / confirm burn **with your brain**.
- Must be a **live signal driving the app**, per the track rules. Teams using g.tec hardware must also submit to g.tec's GitHub by **Nov 30**.
- Risk: adds a whole new subsystem. Only if someone owns it full-time.

### 2.4 Demo flow (target ~2 min live)
1. Pick Earth → Mars, ship, payload → porkchop + 3D routes (efficient vs soonest). *(Optional: choose destination by brain.)*
2. "Upload to ship" → arrives after a delay → FPGA cockpit shows the plan.
3. Tilt the ship to align with the launch vector → FPGA arms → press X → burn → ship flies (time sped up) on laptop 3D + FPGA VGA.
4. Flip 1 switch: TMR survives. Flip 2: SAFE MODE, red alert, AI voice announces, planner re-plans a fallback.
5. Arrival burn → mission complete.

---

## 3. Track strategy **[DECIDE]**
- **Main:** Overall + **Beyond the Horizon** (NASA/JPL data used correctly is the core).
- **If BCI is in:** also **Mind and Machine**.
- **Add-ons (cheap):** MLH Gemini API, MongoDB Atlas, GoDaddy domain, SpaceXSI raffle (if Cursor is the core agent for one teammate + Grok bot).
- ElevenLabs only if voice becomes central.

---

## 4. Team and agents
| Human | GitHub | Agents |
|---|---|---|
| Zain (lead) | Zain-Usmani10 | Claude |
| Abderrahmene | ANaceri26 | Claude, Codex |
| Affan | AffanSyed07 | Codex |
| Sadat | sadattanzim01 | Claude, Cursor |

Coordination: pinned GitHub issue board + `tools/board` (see `AGENTS.md`). Work on `dev`, PRs into `dev`, lead merges to `main`.
**[DECIDE]** area → owner mapping (planner math, 3D web, server/AI, FPGA, ESP32, BCI).

## 5. Hardware on hand
2× DE10-Lite (MAX 10), 2× ESP32, Raspberry Pi 5 (8 GB), Raspberry Pi 3, PS controller, OKdo C100 Nano (spare), Arduino Uno + Nano Every (spare, **5 V: never wire to FPGA**), XIAO ESP32S3 Sense boards. Borrowable at event: g.tec Unicorn, PiEEG Octopus 16.

## 6. Open decisions
1. Final name and one-line pitch
2. BCI in or out
3. Hardware scope: full (FPGA + VGA + ESP32) vs reduced (FPGA LEDs/7-seg only)
4. VGA monitor available?
5. Area → owner mapping
6. Main track(s) to submit to
