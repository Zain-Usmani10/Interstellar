# Serial and delayed transport

Issue #4, owner `@ANaceri26/codex`. Requires contracts v1 from PR #9 and
`pyserial==3.5` (already requested in the leader's core requirements).

`create_transport(port, baud=115200)` returns a **closed** `SerialTransport`.
The runtime's single worker calls `open`, `send`, `receive`, and `close`.
`send` confirms only a complete serial write, never controller acknowledgment.
A short/failed write closes the port: execution is unknown until reconciliation.
All reads enforce version, CRC, known type and exact payload length. Parser
storage is bounded to 142 bytes and reads to 1024 bytes. The incomplete-frame
deadline is 100 ms. Flow control is disabled; serial settings are 115200 8N1.

The shared contract explicitly assigns stop-and-wait, ACK matching, retries,
session/sequence persistence and reconnect reconciliation to the leader's
`app/backend/runtime/link.py`, above `Transport`. There is no second command link
here. Runtime must match ACK type, sequence, session and mission; resume the
existing session after status reconciliation; and require a fresh IDLE session
before sequence wrap. These runtime requirements were reported on the board.

Optional delay:

```python
transport = DelayTransport(create_transport("COM7", 115200), delay_s=1.0)
# Runtime Link must use transport.retry_timeout_s, not the default 0.5 seconds.
```

`delay_s` can be a callable returning the latest selected one-way demo delay.
The runtime computes `min(3.0, max(0.1, distance_km / 299792.458 / 300))` and
labels the compressed delay and estimate age. The callback must return a finite
value within `max_delay_s`; the default maximum is 3 seconds. Each frame receives
its release time once. FIFO is preserved when the delay decreases. All frame
types are delayed, including administrative queries; there is no hidden bypass.
Both queues hold at most 128 frames. Full telemetry queues coalesce an old STATUS
with a newly timed STATUS; commands/ACKs are never silently discarded.

The single runtime worker must keep calling `receive` to pump the delayed link,
including while waiting for ACKs. Use three total attempts of identical command
bytes with timeout `0.5 + 2 * max_delay_s` (6.5 seconds by default). Queue overflow
or underlying transport failure closes the wrapper and discards unsent traffic.
`close` and reopening discard all queued STARTs; runtime must read and reconcile
STATUS before allowing new mutations. Neither implementation auto-reconnects.

## Verification

Run from the repository root after contracts PR #9 is available:

```text
python -m unittest discover -s app/tests/transport -v
```

18 software tests passed on Python 3.10.11 on 2026-11-14: every golden valid and
invalid frame, every split of the four stream fixtures, bytewise reads, timeout
recovery, large garbage, exact/short serial writes, reconnect clearing, FIFO,
bidirectional delay, queue overflow and newly timed telemetry coalescing.
The final run used the merged contracts and backend on dev. The additional
runtime boundary tests exercise a delayed simulated upload/commit/arm/start and
a lost START ACK with an identical retry. No shared contract files were changed.

Serial I/O is fake in these tests. Python 3.12, Arduino compilation, USB loopback,
FPGA exchange and runtime reconciliation after real link loss remain unverified.
