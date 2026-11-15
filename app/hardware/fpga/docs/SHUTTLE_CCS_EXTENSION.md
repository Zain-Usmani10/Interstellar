# Shuttle and Central Control Station (CCS): proposed extension

**Status: PROPOSAL from Zain (`@Zain-Usmani10`), written 2026-11-15. Not yet adopted.**
The authoritative spec is still `docs/plan/MAIN_BACKEND_FPGA_TASKS.md`. Nothing here changes
`app/contracts/` until the leader (`@ANaceri26/claude`) adopts it with a version bump. Where
this file and the spec disagree, the spec wins until then.

This file lives in the FPGA folder because that is the folder its author owns. The leader may
move or merge it into `docs/plan/`.

## 1. The idea in one paragraph

The laptop is the **Central Control Station (CCS)**. The DE10-Lite is the **shuttle**. The
XIAO bridge is the **radio link** between them. The CCS waits for the launch window, counts
down, uploads the plan and launches. After launch the link is lost for part of the flight (a
communications blackout). During the blackout the shuttle flies and burns by itself from its
stored plan, both sides show "connection lost", and both keep counting down the days left to
arrival. Before arrival the link comes back and the CCS catches up with what really happened.

## 2. Demo storyline

| Step | CCS (laptop) | Link | Shuttle (FPGA) |
|---|---|---|---|
| 1. Wait | Calendar fast-forwards to the launch window | up | IDLE on the pad |
| 2. Prepare | Uploads plan, arms, sends trip length in days | up | LOADED, then ARMED |
| 3. Countdown | Real-time T-minus | up | RUNNING, counts ticks toward the departure tick |
| 4. Launch | Shows departure burn confirmed | up | Departure burn, fuel deducted |
| 5. Blackout | "Connection lost"; shows an **estimate**, clearly labelled | down | "nL" (no link); keeps flying alone |
| 6. Cruise | Days-to-arrival counts down from its own clock | down | Days-to-arrival counts down from its own ticks |
| 7. Reacquire | Reads STATUS, snaps to the true tick, flags anything that happened during blackout | up | unchanged |
| 8. Arrival | Shows captured, or the truth if not | up | Capture burn and COMPLETE, or SAFE and an uncaptured coast |

Best demo moment: flip the divergence switch (SW1) during the blackout. The CCS estimate
says "arrived". The link returns and the truth is SAFE with no capture.

## 3. What each side must do

### 3.1 CCS backend (`@ANaceri26/claude`)

1. **Keep-alive.** Send `GET_STATUS` at least once per second whenever the link is open. The
   shuttle declares the link lost after 2 seconds without a valid frame.
2. **Trip length.** After `COMMIT_PLAN` (or after `ARM`) and before `START`, send the new
   `SET_TRIP_DAYS` message (section 4). Optional: if it is never sent, the shuttle shows
   mission seconds instead of days.
3. **Real-time countdown.** Use a larger `departure_tick` for demo plans, for example 1000
   (10 seconds). No protocol change: it is just a plan value. Ticks before departure are shown
   as real time, not as compressed mission time.
4. **Blackout.** A way to drop and restore the link: either the human pulls the XIAO cable,
   or a "blackout" control stops sending and ignores telemetry for a set time.
5. **Estimate mode.** With no telemetry, estimate the tick from the laptop clock:
   `tick_est = last_tick + (now - last_rx_time) * 100`, capped at `end_tick`. Everything drawn
   from it carries an **ESTIMATE, NO TELEMETRY** label. This relaxes spec section 7 item 6
   ("no telemetry means last received state") and needs the leader's decision.
6. **Reconcile on reconnect.** First STATUS after the blackout replaces the estimate. Report
   burns whose executed tick falls inside the blackout as "executed while out of contact".
7. **Days to arrival.** Compute with exactly the formula in section 5 so both displays agree.

### 3.2 CCS frontend (`@sadattanzim01/cursor`)

1. Time control before launch: fast-forward the calendar to the launch window, then real time.
2. T-minus countdown during the pre-departure ticks.
3. "Connection lost" banner and the ESTIMATE label during a blackout; clear both on reconnect.
4. Days-to-arrival readout (from the backend's value).
5. Optional: show `link.delay_demo_s` as "signal delay" when it is not null (already exists).

### 3.3 Bridge (`@ANaceri26/codex`)

No change. The bridge stays a transparent byte forwarder.

### 3.4 Shuttle RTL (Zain)

Built on branch `8-fpga-cockpit-link`, additive only: no existing message, ACK or STATUS
byte changes.

| Feature | Module | Notes |
|---|---|---|
| Link watchdog | `rtl/link_watchdog.v` | Link is "lost" if a link was seen and then no valid frame arrives for 2 s |
| Trip length message | `rtl/cmd_handler.v`, `rtl/frame_rx.v` | `SET_TRIP_DAYS` (section 4) |
| Days-to-arrival counter | `rtl/trip_clock.v` | Exact, no division (section 5). Display only; never affects burns |
| Cockpit on the six seven-segment displays | `rtl/cockpit_display.v`, `rtl/bin2bcd.v`, `rtl/seg7.v` | Section 6 |
| VGA cockpit | not built | Still excluded by the spec; Zain decides after this lands |
| Boot from flash (`.pof`) | not built | Lets the shuttle run from a power bank with no laptop |

## 4. Proposed protocol addition: `SET_TRIP_DAYS` (type `0x16`)

Additive. Every existing frame, ACK and STATUS stays byte-for-byte the same, so the current
golden frames remain valid. Needs a contracts minor version bump and new golden frames from
the leader. Until then the board accepts it but nothing in the backend sends it.

| Field | Value |
|---|---|
| Type | `0x16` |
| Direction | host to board |
| Kind | mutation: active session, next sequence number, answered with an ACK |
| Payload | 8 bytes: `mission_id:u32`, `trip_days:u32` (little-endian) |
| Allowed when | a plan is active with the same `mission_id`, state `LOADED` or `ARMED` |
| Meaning | The planned trip from the departure tick to the arrival tick represents `trip_days` days |

ACK results (same 16-byte ACK as every other command, `original_type = 0x16`):

| Case | Detail |
|---|---|
| Accepted | `OK` |
| No active plan, or state not `LOADED`/`ARMED` | `BAD_STATE` |
| `mission_id` differs from the active plan | `BAD_MISSION` |
| `trip_days` is 0 or greater than 9999 | `BAD_PLAN` |
| Session / sequence problems | `BAD_SESSION`, `SEQ_CONFLICT`, `STALE_SEQ` as for any mutation |

The value is forgotten on `CLEAR`, on a new `COMMIT_PLAN`, and on reset. It is not reported in
STATUS; the CCS already knows it.

Example frame (session `0x1A2B3C4D`, sequence 3, mission `0x00C0FFEE`, 300 days):

```
A5 5A 01 16 03 00 4D 3C 2B 1A 08 00 EE FF C0 00 2C 01 00 00 <crc lo> <crc hi>
```

## 5. Days to arrival: the shared formula

Both sides must use integer arithmetic so their displays match exactly.

```text
trip_ticks = arrival_tick - departure_tick
if tick <= departure_tick:   elapsed_days = 0
elif tick >= arrival_tick:   elapsed_days = trip_days
else:                        elapsed_days = floor((tick - departure_tick) * trip_days / trip_ticks)
days_to_arrival = trip_days - elapsed_days
```

The board gets the same result without dividing: on every tick between departure and arrival
it adds `trip_days` to an accumulator, and each time the accumulator reaches `trip_ticks` it
subtracts `trip_ticks` and counts one more elapsed day.

Why the two displays stay in step during a blackout: both count the same 100 Hz ticks from
the same START. The laptop clock and the board's crystal differ by a few parts in 100,000, so
over a two-minute flight the estimate is off by well under one tick.

The countdown does not stop when a capture is missed: a SAFE or ABORTED shuttle still shows
the days until the planned arrival, then 0. The CCS decides what to say about a missed
capture from STATUS, as today.

## 6. Shuttle cockpit on the seven-segment displays

`HEX5 HEX4` show the state. `HEX3..HEX0` show a number.

| State | HEX5 HEX4 |
|---|---|
| IDLE | `Id` |
| LOADED | `Ld` |
| ARMED | `Ar` |
| RUNNING | `rn` |
| SAFE | `SF` |
| COMPLETE | `Co` |
| ABORTED | `Ab` |
| Link lost (any state) | alternates with `nL` once per second |

| Situation | HEX3..HEX0 |
|---|---|
| IDLE | `----` |
| LOADED / ARMED | trip length in days, or `----` if not set |
| RUNNING before the departure burn | T-minus as `SS.cc` (seconds and hundredths) |
| After the departure burn, trip length set | days to arrival |
| After the departure burn, trip length not set | mission seconds elapsed |

## 7. Honesty rules that stay

- The shuttle never fakes anything: the link flag comes from real frames, burns from the real
  tick counter and voted state.
- The CCS may show an estimate only when it is labelled as one, and it must drop it the
  moment telemetry returns.
- A missed capture is never turned into an arrival by the estimate.
- Days to arrival is a display value on both sides. It does not gate any burn.

## 8. Open decisions for the leader and the humans

1. Adopt `SET_TRIP_DAYS` into contracts (type number, golden frames, version bump)?
2. Allow labelled estimates during a blackout (spec section 7 item 6)?
3. Blackout by pulling the cable, by a dashboard control, or both?
4. Keep-alive rate: is one `GET_STATUS` per second acceptable for the Link?
5. VGA cockpit: still excluded, or allowed once the real round trip passes?
