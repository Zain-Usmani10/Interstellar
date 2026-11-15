# Interstellar FPGA controller (DE10-Lite)

Board: Terasic DE10-Lite, MAX 10 `10M50DAF484C7G`. Tool: Quartus Prime Lite 25.1std.

## Files
| Path | What it is |
|---|---|
| `interstellar.qpf` / `.qsf` | Quartus project and settings (device, pins, source list) |
| `interstellar.sdc` | Timing constraints: one 50 MHz clock, 20 ns period |
| `rtl/interstellar_top.v` | Top level: connects the board pins to the modules |
| `rtl/reset_sync.v` | KEY0 reset: asserts immediately, releases on a clock edge |
| `rtl/tick_gen.v` | 100 Hz mission tick: one pulse per 500,000 clocks |
| `rtl/heartbeat.v` | Blinks LEDR0 once per second from the 100 Hz tick |
| `rtl/uart_rx.v`, `rtl/uart_tx.v` | Serial bytes in and out, 115200 8N1 |
| `rtl/crc16.v` | CRC-16/CCITT-FALSE, one byte per step |
| `rtl/frame_rx.v` | Finds and checks protocol v1 frames in the received bytes |
| `rtl/frame_tx.v` | Sends one protocol v1 frame |
| `rtl/status_gen.v` | Builds the 40-byte STATUS frame: on request, on change, and at 10 Hz |
| `rtl/cmd_handler.v` | Checks each command (session, sequence, state, plan) and answers with an ACK |
| `rtl/sequencer.v` | The mission: active plan, state, tick counter, fuel, the two burns, fault handling |
| `rtl/tmr_lanes.v` | Three stored copies of the control tuple (state, mask, fuel, burn ticks) |
| `rtl/voter.v` | Whole-tuple majority vote over the three copies |
| `rtl/debounce.v` | Cleans up a button or switch |
| `rtl/link_watchdog.v` | Display only: "link lost" when no good frame arrived for 2 s |
| `rtl/trip_clock.v` | Display only: days to arrival from the tick counter and SET_TRIP_DAYS |
| `rtl/cockpit_display.v`, `rtl/seg7.v`, `rtl/bin2bcd.v` | Display only: the six seven-segment digits |
| `docs/SHUTTLE_CCS_EXTENSION.md` | PROPOSAL: shuttle / control-station storyline, what each owner would build, the proposed SET_TRIP_DAYS command |
| `../../tests/fpga/` | Testbenches and `run_sim.sh` (simulation only) |

## Pins
| Signal | Pin | Notes |
|---|---|---|
| `MAX10_CLK1_50` | `PIN_P11` | Onboard 50 MHz oscillator |
| `KEY[0]` | `PIN_B8` | Reset, active low (hold to reset) |
| `KEY[1]` | `PIN_A7` | Local abort |
| `SW[0]` | `PIN_C10` | Flip up: INJECT_SINGLE (corrupt one copy) |
| `SW[1]` | `PIN_C11` | Flip up: INJECT_DIVERGENCE (corrupt two copies differently) |
| `UART_RX` | `PIN_V10` | JP1 pin 1 (GPIO0), from XIAO D6/TX, weak pull-up |
| `UART_TX` | `PIN_W10` | JP1 pin 2 (GPIO1), to XIAO D7/RX, idles high |
| `LEDR[0]`..`LEDR[8]` | `PIN_A8` `A9` `A10` `B10` `D13` `C13` `E14` `D14` `A11` | Status LEDs, see below |
| `LEDR[9]` | `PIN_B11` | On while in reset |
| `HEX0`..`HEX5` | see `interstellar.qsf` | Seven-segment digits, active low, bit 7 = decimal point. Pin numbers typed from memory of the Terasic manual: not confirmed on the board yet |

All I/O is 3.3 V. Unused pins are high-impedance inputs.

Finding JP1 pins 1 and 2 on the board: they are the pair at the end of the 40-pin header next to the `R2`/`R3` labels, not the end next to the `JP1` label (found by the loopback test on Zain's board).

## Simulate (Git Bash)
```
app/tests/fpga/run_sim.sh
```
Needs Icarus Verilog (`iverilog`) on PATH. A pass here is a simulation result, not a board result.

## Build (Git Bash, from this folder)
```
/c/altera_lite/25.1std/quartus/bin64/quartus_sh --flow compile interstellar
```
Or open `interstellar.qpf` in Quartus and press **Start Compilation**. The output is `output_files/interstellar.sof` (not committed).

## Program the board
Plug in the DE10-Lite USB-Blaster cable, then:
```
/c/altera_lite/25.1std/quartus/bin64/quartus_pgm -m jtag -o "p;output_files/interstellar.sof"
```
Or use **Tools > Programmer** in Quartus. A `.sof` is volatile: reprogram after every power cycle.

## What to expect on the board (milestone D)
| LED | Meaning |
|---|---|
| LEDR0 | Heartbeat, blinks once per second |
| LEDR1 | READY: a plan is LOADED or ARMED |
| LEDR2 | RUNNING |
| LEDR3 | COMPLETE |
| LEDR4 | SAFE |
| LEDR5 | ABORTED |
| LEDR6 | A fault was seen since reset (stays on until KEY0) |
| LEDR7 | A session is open |
| LEDR8 | Flips each time a received frame is dropped |
| LEDR9 | On while KEY0 holds the board in reset |

With nothing connected only LEDR0 blinks. The board sends a STATUS frame out of UART_TX ten times a second.

### Seven-segment cockpit readout (extension, display only)
| Digits | Shows |
|---|---|
| HEX5 HEX4 | State: `Id` idle, `Ld` loaded, `Ar` armed, `rn` running, `SF` safe, `Co` complete, `Ab` aborted. Alternates with `nL` (no link) once a second when a link was seen and then no good frame arrived for 2 s |
| HEX3..HEX0 | `----` when idle; trip length in days when loaded/armed (if set); T-minus `SS.cc` while running before the departure burn; days to arrival after it (mission seconds if the trip length was never set) |

With nothing connected it shows `Id----`. None of this feeds back into the mission: the burns, the STATUS frame and the golden-frame behaviour are unchanged.

`SET_TRIP_DAYS` (type `0x16`, payload `mission_id:u32, trip_days:u32`) is a **proposed** command, not in `app/contracts/protocol_v1.json`. A backend that never sends it sees exactly the old behaviour. The control station must send a frame at least once a second (GET_STATUS is enough) or the shuttle shows `nL`.

## Fault tolerance: what is and is not protected
- Triplicated and voted: mission state, executed mask, remaining fuel, the two burn ticks.
- Not triplicated (single points of failure): the plan, the tick counter, the voter, the supervisor logic, UART and I/O.
- Two wrong copies that agree would outvote the correct one. This is a fault-injection demonstration, not radiation hardening.
- Quartus 25.1std Lite kept all three copies: 101 registers each for `reg_a`, `reg_b`, `reg_c` in the fitted netlist, none under "Registers Removed During Synthesis".

## Board test log
Record real-board results here, separately from simulation.

| Date | Build | Test | Result | Tested by |
|---|---|---|---|---|
| 2026-11-14 | heartbeat (uncommitted, branch `8-fpga-heartbeat-uart`) | Heartbeat on LEDR0, KEY0 reset, programmed by `.sof` from Quartus Programmer | Reported working on the DE10-Lite | Zain |
| 2026-11-14 | UART loopback (milestone A) | Jumper JP1 pin 1 to pin 2: LEDR1 on with jumper, off without, LEDR2 stays off, KEY0 clears both | Reported working on the DE10-Lite | Zain |
| 2026-11-14 | frames + STATUS (milestone B) | KEY1 self-test with jumper JP1 pin 1 to pin 2: LEDR1 and LEDR2 flip per press, nothing without the jumper | Reported working on the DE10-Lite | Zain |
