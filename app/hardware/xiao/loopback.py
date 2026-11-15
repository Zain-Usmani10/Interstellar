"""Physical D6-D7 loopback only: NEVER run with an FPGA connected."""
import argparse
import json
import time
from pathlib import Path

from app.backend.transport import create_transport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--confirm-loopback-only', action='store_true', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2] / 'contracts/fixtures/frames'
    entries = json.loads((root / 'manifest.json').read_text())['frames']
    frames = [bytes.fromhex(f['hex']) for f in entries if f.get('valid') is True]
    transport = create_transport(args.port)
    passed = 0
    started = time.monotonic()
    try:
        for cycle in range(2):
            transport.open()
            time.sleep(1)
            for repeat in range(10):
                for frame in frames:
                    transport.send(frame)
                    received = transport.receive(2)
                    if received != frame:
                        raise RuntimeError(f'echo mismatch at cycle={cycle} repeat={repeat} frame={frame.hex()} received={received}')
                    passed += 1
            transport.close()
        print(json.dumps({'mode': 'real_xiao_uart_loopback_no_fpga', 'port': args.port,
                          'baud': 115200, 'golden_frames': len(frames), 'echoes_passed': passed,
                          'open_cycles': 2, 'elapsed_s': round(time.monotonic()-started, 3)}))
    finally:
        transport.close()


if __name__ == '__main__':
    main()
