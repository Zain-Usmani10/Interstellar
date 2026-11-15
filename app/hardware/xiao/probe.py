"""Diagnostic UART probe. Does not upload, arm, start or clear missions."""
import argparse
import json
import secrets
import time
from dataclasses import asdict
from datetime import datetime, timezone

from app.backend.transport import create_transport
from app.contracts import protocol_v1 as p
from app.contracts.transport import TransportError


class ProbeError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def emit(event, **fields):
    print(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(),
                      'event': event, **fields}), flush=True)


def receive(transport, timeout, log=emit):
    before = transport.stats().get('parser_errors', {})
    raw = transport.receive(timeout)
    after = transport.stats().get('parser_errors', {})
    for reason, count in after.items():
        if count > before.get(reason, 0):
            log('discarded_bytes', reason=reason, count=count-before.get(reason, 0),
                crc='bad' if reason == 'crc' else 'not_validated')
    if raw is None:
        return None
    frame = p.decode_frame(raw)
    fields = {}
    if frame.msg_type == p.MsgType.STATUS:
        fields = asdict(p.Status.unpack(frame.payload))
    elif frame.msg_type == p.MsgType.ACK:
        fields = asdict(p.Ack.unpack(frame.payload))
    log('frame', type=p.MsgType(frame.msg_type).name, sequence=frame.sequence,
        session=frame.session_id, crc='ok', **fields)
    return frame


def wait_for(transport, predicate, timeout, log):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = receive(transport, min(.1, max(0, deadline-time.monotonic())), log)
        if frame is not None and predicate(frame):
            return frame
    errors = transport.stats().get('parser_errors', {})
    if errors.get('version'):
        raise ProbeError(6, 'Wrong protocol version received; protocol v1 required.')
    if errors.get('crc'):
        raise ProbeError(5, 'Bad CRC received; no matching valid reply.')
    raise ProbeError(4, 'No matching reply. Check crossed UART, common ground, firmware and baud.')


def handshake(transport, timeout=2, log=emit):
    transport.send(p.encode_frame(p.MsgType.DISCOVER, 0, 0))
    status_frame = wait_for(transport, lambda f: f.msg_type == p.MsgType.STATUS, timeout, log)
    status = p.Status.unpack(status_frame.payload)
    # Never take over a running/loaded controller, or silently replace a known session.
    if status_frame.session_id or status.state != p.State.IDLE or status.mission_id:
        log('existing_controller', session=status_frame.session_id, state=status.state,
            message='Read-only inspection; no replacement session opened.')
        return status_frame.session_id
    session = secrets.randbelow(0xffffffff) + 1
    request = p.encode_frame(p.MsgType.OPEN_SESSION, 0, 0, p.pack_u32(session))
    def accepted(f):
        if f.msg_type != p.MsgType.ACK or f.sequence != 0 or f.session_id != session:
            return False
        ack = p.Ack.unpack(f.payload)
        return (ack.original_type == p.MsgType.OPEN_SESSION and ack.result == p.Result.APPLIED
                and ack.detail == p.Detail.OK and ack.mission_id == 0)
    for attempt in range(3):
        transport.send(request)
        try:
            wait_for(transport, accepted, .5, log)
            log('session_opened', session=session)
            return session
        except ProbeError:
            if attempt == 2:
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--seconds', type=float, default=3)
    parser.add_argument('--loopback', action='store_true', help='D6-D7 jumper ONLY, no FPGA')
    args = parser.parse_args()
    if not 0 <= args.seconds <= 300:
        parser.error('--seconds must be between 0 and 300')
    if args.loopback:
        from app.hardware.xiao.loopback import main as loopback
        import sys
        sys.argv = [sys.argv[0], '--port', args.port, '--confirm-loopback-only']
        try:
            loopback()
            return 0
        except TransportError as exc:
            code = 2 if 'PORT_MISSING' in str(exc) else 3 if 'PORT_BUSY' in str(exc) else 7
            emit('error', exit_code=code, message=str(exc))
            return code
        except RuntimeError as exc:
            emit('error', message=str(exc))
            return 4
    transport = create_transport(args.port)
    try:
        transport.open()
        time.sleep(.3)
        handshake(transport)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            receive(transport, min(.1, deadline-time.monotonic()))
        return 0
    except ProbeError as exc:
        emit('error', exit_code=exc.code, message=str(exc))
        return exc.code
    except TransportError as exc:
        code = 2 if 'PORT_MISSING' in str(exc) else 3 if 'PORT_BUSY' in str(exc) else 7
        emit('error', exit_code=code, message=str(exc))
        return code
    finally:
        transport.close()


if __name__ == '__main__':
    raise SystemExit(main())
