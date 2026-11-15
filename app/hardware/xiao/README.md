# XIAO ESP32S3 USB/UART bridge

`bridge/bridge.ino` forwards binary bytes between native USB CDC (`Serial`) and
`Serial1.begin(115200, SERIAL_8N1, 44, 43)`. It emits no text, adds no delay, and
does not interpret or acknowledge protocol frames. Each direction retains
partial writes in a 256-byte buffer. UART RX has a 2048-byte buffer. With USB
absent, downlink data is drained/discarded; the host must reconcile retained FPGA
STATUS on reconnect. Sustained backpressure can overrun finite hardware buffers;
the protocol's CRC/retry/status mechanisms detect or recover lost traffic.

## Build and wiring

Use the Espressif Arduino ESP32 board package with board **XIAO_ESP32S3**,
native USB CDC enabled on boot, and hardware CDC/JTAG USB mode. Open
`bridge/bridge.ino` in Arduino IDE, select the XIAO's actual port, compile, then
upload. Record the installed IDE/CLI version, ESP32 core version, board options,
port before/after upload and compiler output in the test record below. The tested versions are recorded below.

Power off before wiring. Verify physical pin 1/orientation on the actual boards.
Use 3.3 V signals, crossed TX/RX and common ground:

| XIAO | DE10-Lite JP1 | FPGA pin |
|---|---|---|
| D6 / GPIO43 / TX | physical pin 1 / GPIO0 / RX | V10 |
| D7 / GPIO44 / RX | physical pin 2 / GPIO1 / TX | W10 |
| GND | physical pin 12 or 30 / GND | ground |

Power each board using its own USB connection. Do not connect their power rails.
Do not remove one board's power while the other drives its UART pins.

## Physical acceptance record

On 2026-11-14 (America/Toronto), compiled and flashed the actual XIAO ESP32S3 on
COM10. Arduino CLI 1.5.1, Espressif core 3.3.12, esptool 5.3.1.
FQBN: `esp32:esp32:XIAO_ESP32S3:USBMode=hwcdc,CDCOnBoot=default`.
Compiler: 281477 bytes flash, 22360 bytes RAM. Upload hashes verified; COM10 remained COM10.

User confirmed D6/TX jumpered to D7/RX with no FPGA attached. Actual test:

```text
python -m app.hardware.xiao.loopback --port COM10 --confirm-loopback-only
```

PASS: 30 valid golden frames, 10 repetitions per open cycle, 2 open cycles:
**600/600 exact echoes**, 115200 8N1, 6.016 seconds. Uses production SerialTransport,
Python 3.10.11 and pyserial 3.5. Both open cycles used the powered XIAO; no power removal.
Never run this script with the FPGA attached: it sends both command and reply fixtures.

Still pending: physical FPGA wiring, DISCOVER/STATUS and command/ACK exchanges,
FPGA idempotency and retained execution/reconciliation during serial reconnect.
Loopback proves the USB/UART bridge path, not FPGA execution.

## FPGA bring-up probe (issue #24)

Zain confirmed FPGA RX = JP1 physical pin 1 / PIN_V10 and TX = physical pin 2 /
PIN_W10, 3.3 V. His board places pins 1–2 at the header end beside R2/R3;
verify the board drawing/pin-1 mark rather than relying only on viewing orientation.
UART contract is 115200 8N1; confirmation of the currently programmed baud was
requested on the board. The wiring table above crosses XIAO D6/TX to FPGA RX
and FPGA TX to XIAO D7/RX. Remove the D6–D7 loopback jumper before FPGA wiring.

Before connecting:
1. With power off, check intended GND points for continuity, and check that
   signal/power rails are not accidentally shorted. Never use resistance mode powered.
2. With boards separate and powered, measure each TX's idle voltage relative to
   its own GND: approximately 3.3 V, never 5 V. A multimeter cannot verify baud,
   pulse shape or short spikes; a scope/logic analyzer is needed for those.
3. Turn both boards off, wire signals plus common ground, inspect, then power both.
   Do not connect the boards' 5 V/3.3 V rails. Do not remove one board's power
   while the other drives its UART; USB unplug testing below is loopback-only.

Close Arduino Serial Monitor and stop the backend serial owner before probing:

```text
python -m app.hardware.xiao.probe --port COM10 --seconds 5
```

The probe prints timestamped JSON frames with type, sequence, session, CRC validity,
STATUS fields and ACK fields. Corrupt bytes are discarded by production parsing;
only error reason/count is reported for them (untrusted header fields are not decoded).
DISCOVER is read-only. On a reset IDLE board with session/mission zero, the probe
opens a random nonzero session using three identical attempts, 500 ms each.
Existing sessions or non-IDLE state are inspected without takeover. The probe
never LOADs, COMMITs, ARMs, STARTs, ABORTs or CLEARs. It is a standalone diagnostic,
not a way to restore the runtime's persisted sequence state.

Exit codes: 0 success; 2 missing port (or argparse usage); 3 busy/access denied;
4 no matching reply; 5 CRC errors with no matching reply; 6 wrong version with
no matching reply; 7 other serial I/O failure. Inspect JSON error counters even
when a valid reply ultimately succeeds. Any received matching STATUS is a board
observation; telemetry is not correlated to a query sequence.

Only with FPGA disconnected and D6–D7 jumpered:

```text
python -m app.hardware.xiao.probe --port COM10 --loopback
python -m app.hardware.xiao.reconnect_probe --port COM10 --confirm-loopback-only
```

The reconnect script prompts READY_UNPLUG then READY_REPLUG and waits up to
180 seconds at each step. Do not unplug until prompted. If Windows assigns a new
COM number, stop and rerun using that port; the script never guesses another device.

### Observed issue #24 results (2026-11-14 America/Toronto)

- Real COM10 second open rejected with readable PORT_BUSY; first owner retained.
- Human physically unplugged USB: TransportError raised, port closed.
- Human replugged: the SAME SerialTransport object reopened COM10; no unsolicited
  frame before a new send; new golden frame echoed correctly. No backend restart
  was involved (standalone harness). This is not an integrated backend recovery test.
- New probe --loopback: 600/600 exact echoes, two open cycles, 5.265 seconds.
- 23 software tests passed on Python 3.10.11, pyserial 3.5, including parser error
  categories, session preservation, fake device removal, and unsent START clearing.
- FPGA was NOT attached. Physical FPGA protocol round trip remains pending.

After production TransportError, runtime must reopen and reconcile STATUS with its
persisted session/mission/sequence before new mutations. Transport never replays
traffic or reconnects itself; this keeps a queued START from being silently sent.
