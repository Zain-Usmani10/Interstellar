"""Transport interface v1: the boundary between the backend runtime and whatever carries frames.

The runtime (leader) talks only to this interface. Implementations:

  SerialTransport      app/backend/transport/   real XIAO USB serial port      (@ANaceri26/codex)
  DelayTransport       app/backend/transport/   wraps any Transport, adds the  (@ANaceri26/codex)
                                                one host-side demo delay
  SimulatorTransport   app/backend/runtime/     simulated controller, labelled (leader)
                                                SIMULATED CONTROLLER

Rules for every implementation:
  * A frame is one complete encoded protocol-v1 frame (magic .. CRC), as bytes.
  * ``send`` hands over exactly one frame. It never means the board acknowledged anything.
  * ``receive`` returns the next complete CRC-valid frame from the board, or None on timeout.
    Corrupt bytes are dropped and counted, never returned.
  * Calls come from one thread only (the runtime's single transport worker). No other code
    opens the serial port.
  * Stop-and-wait, retries, ACK correlation and session/sequence bookkeeping sit above this
    interface (the link layer), so they work the same over serial, delay and simulator.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable


class TransportError(Exception):
    """The transport cannot send or receive (port closed, device gone, queue overflow)."""


@runtime_checkable
class Transport(Protocol):
    # "fpga" for anything that reaches the real board, "simulator" otherwise.
    controller_source: Literal["fpga", "simulator"]

    def open(self) -> None:
        """Acquire the port/resources. Raises TransportError if that fails."""

    def close(self) -> None:
        """Release everything. Safe to call twice. Drops frames that were queued but not sent."""

    def is_open(self) -> bool: ...

    def send(self, frame: bytes) -> None:
        """Queue/write one complete frame. Raises TransportError if closed or the queue is full."""

    def receive(self, timeout_s: float) -> bytes | None:
        """Block up to ``timeout_s`` for the next complete valid frame; None if none arrived."""

    def stats(self) -> dict:
        """Counters for the health endpoint, e.g. frames_sent, frames_received, rx_errors."""
