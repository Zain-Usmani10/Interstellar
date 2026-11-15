"""Real serial and optional host-delay transports (contracts v1)."""
from .delay import DelayTransport
from .serial_transport import SerialTransport


def create_transport(port: str, baud: int = 115200) -> SerialTransport:
    """Construct a closed transport; the runtime owns opening and reconciliation."""
    return SerialTransport(port, baud)
