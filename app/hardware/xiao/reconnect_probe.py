"""Human-assisted physical USB removal test; D6-D7 loopback ONLY, no FPGA."""
import argparse
import time
from app.backend.transport import create_transport
from app.contracts import protocol_v1 as p
from app.contracts.transport import TransportError
from app.hardware.xiao.probe import emit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--confirm-loopback-only', action='store_true', required=True)
    args = parser.parse_args()
    transport = create_transport(args.port)
    other = create_transport(args.port)
    frame = p.encode_frame(p.MsgType.GET_STATUS, 0, 0)
    try:
        transport.open()
        transport.send(frame)
        if transport.receive(2) != frame:
            raise RuntimeError('Initial physical loopback failed')
        try:
            other.open()
        except TransportError as exc:
            emit('second_owner_rejected', message=str(exc))
        else:
            raise RuntimeError('Second serial owner unexpectedly opened the port')
        emit('READY_UNPLUG', message='Unplug XIAO USB now. No FPGA may be attached.')
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                transport.receive(.1)
            except TransportError as exc:
                emit('disconnect_detected', message=str(exc), is_open=transport.is_open())
                break
        else:
            raise RuntimeError('Timed out waiting for unplug')
        emit('READY_REPLUG', message='Reconnect the XIAO USB to the same port now.')
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                transport.open()
                break
            except TransportError:
                time.sleep(.5)
        else:
            raise RuntimeError('COM port did not return; inspect new enumeration')
        time.sleep(1)
        if transport.receive(.2) is not None:
            raise RuntimeError('Unexpected stale traffic before new send')
        transport.send(frame)
        if transport.receive(2) != frame:
            raise RuntimeError('Reopened physical loopback failed')
        emit('PASS', mode='real_xiao_loopback_no_fpga', same_transport_instance=True,
             no_unsolicited_frame_after_reopen=True)
    finally:
        other.close()
        transport.close()


if __name__ == '__main__':
    main()
