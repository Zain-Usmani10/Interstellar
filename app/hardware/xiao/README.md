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
port before/after upload and compiler output in the test record below. No tool
or core version has been claimed tested yet.

Power off before wiring. Verify physical pin 1/orientation on the actual boards.
Use 3.3 V signals, crossed TX/RX and common ground:

| XIAO | DE10-Lite JP1 | FPGA pin |
|---|---|---|
| D6 / GPIO43 / TX | physical pin 1 / GPIO0 / RX | V10 |
| D7 / GPIO44 / RX | physical pin 2 / GPIO1 / TX | W10 |
| GND | physical pin 12 or 30 / GND | ground |

Power each board using its own USB connection. Do not connect their power rails.
Do not remove one board's power while the other drives its UART pins.

## Physical acceptance record — pending

As of 2026-11-14 the user confirmed the XIAO is **not connected or wired**.
Arduino tooling is not on this shell's PATH. Firmware has not been compiled,
uploaded or tested on hardware. These are the remaining checks:

1. Record tool/core versions and successful compiler output.
2. With FPGA disconnected, power off, connect XIAO TX to RX for loopback, then
   power on and verify exact binary bytes (including 00/A5/5A/FF) both ways.
3. Power off, remove loopback, wire the FPGA as above, power both boards and
   exchange DISCOVER/STATUS and golden command/ACK frames with Zain.
4. Verify LOAD/COMMIT retries do not double-apply; verify malformed CRC recovery.
5. Close/reopen only the host serial port while both boards remain powered.
   Check retained tick/events/session and that no queued START is replayed.

A software fake-serial test is not evidence of any of these physical checks.
