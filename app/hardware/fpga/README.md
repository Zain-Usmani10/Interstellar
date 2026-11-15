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
| `../../tests/fpga/` | Testbenches and `run_sim.sh` (simulation only) |

## Pins
| Signal | Pin | Notes |
|---|---|---|
| `MAX10_CLK1_50` | `PIN_P11` | Onboard 50 MHz oscillator |
| `KEY[0]` | `PIN_B8` | Reset, active low (hold to reset) |
| `KEY[1]` | `PIN_A7` | Not used yet |
| `UART_RX` | `PIN_V10` | JP1 pin 1 (GPIO0), from XIAO D6/TX, weak pull-up |
| `UART_TX` | `PIN_W10` | JP1 pin 2 (GPIO1), to XIAO D7/RX, idles high |
| `LEDR[0]` | `PIN_A8` | Heartbeat |
| `LEDR[9]` | `PIN_B11` | On while in reset |

All I/O is 3.3 V. Unused pins are high-impedance inputs.

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

## What to expect on the board (bring-up stage)
- LEDR0 blinks once per second (0.5 s on, 0.5 s off).
- Holding KEY0 turns LEDR9 on and LEDR0 off; releasing it restarts the blink.
- All other red LEDs are off.

## Board test log
Record real-board results here, separately from simulation.

| Date | Build | Test | Result | Tested by |
|---|---|---|---|---|
| 2026-11-14 | heartbeat (uncommitted, branch `8-fpga-heartbeat-uart`) | Heartbeat on LEDR0, KEY0 reset, programmed by `.sof` from Quartus Programmer | Reported working on the DE10-Lite | Zain |
