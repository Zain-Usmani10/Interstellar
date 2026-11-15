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
