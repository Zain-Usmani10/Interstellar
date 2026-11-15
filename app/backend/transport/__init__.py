"""Real serial and optional host-delay transports (contracts v1)."""
import os

from .delay import DelayTransport
from .reconnect import ReconnectingSerialTransport
from .serial_transport import SerialTransport


def create_transport(port: str, baud: int = 115200) -> SerialTransport | ReconnectingSerialTransport:
    """Construct a closed transport; the runtime owns opening and reconciliation."""
    transport = SerialTransport(port, baud)
    if os.environ.get("SERIAL_AUTO_RECONNECT", "").strip().lower() == "true":
        return ReconnectingSerialTransport(transport)
    return transport
