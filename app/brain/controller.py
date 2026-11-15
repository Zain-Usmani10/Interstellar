"""Keyboard-controlled synthetic EEG demo: Earth/Mars cards, never missions."""
from __future__ import annotations

import argparse
import asyncio
import os
import time

from .acquisition import SyntheticAdapter
from .client import CoreClient
from .selection import LABELS, SelectionGate


class PlanetSimulator:
    def __init__(self, core, clock=time.monotonic, sleep=asyncio.sleep):
        self.core, self.clock, self.sleep = core, clock, sleep
        self.adapter = SyntheticAdapter(clock)
        self.gate = SelectionGate(clock=clock)

    async def start(self):
        info = self.adapter.start({'frequency_hz': 10})
        self.gate.context_update(await self.core.register(info))

    async def heartbeat(self):
        self.gate.context_update(await self.core.heartbeat(self.gate.heartbeat()))

    async def select(self, target):
        """Generate evidence, submit once, return the authoritative acknowledgment."""
        context = await self.core.context()
        targets = context['allowed_targets']
        if not context['enabled'] or target not in targets or len(targets) != 2:
            raise RuntimeError(f'{target} is unavailable in the current app context')
        self.adapter.stop()
        self.adapter.start({'frequency_hz': (10, 15)[targets.index(target)]})
        self.gate.configure(context, targets, (10, 15))
        next_beat = self.clock()
        for sequence in range(80):
            before = self.clock()
            await self.sleep(0.1)
            if self.clock() - before > 0.35:
                self.gate.stop('acquisition_stall')
                raise RuntimeError('Simulator paused too long; rearm explicitly')
            if self.clock() >= next_beat:
                await self.heartbeat()
                next_beat = self.clock() + 0.5
            # Simulation timing only: there is deliberately no flashing stimulus.
            self.gate.stimulus(dict(context_id=context['context_id'], context_revision=context['revision'],
                                    sequence=sequence, active=True, visible=True, focused=True,
                                    frame_count=sequence+1, dropped_frames=0, largest_frame_gap_ms=17,
                                    effective_frequencies_hz=[10, 15]))
            intent = self.gate.feed(self.adapter.read_batch())
            if intent is not None:
                result = await self.core.submit(intent)
                self.gate.context_update(await self.core.context())
                if not result['accepted']:
                    raise RuntimeError(f"Core rejected selection: {result['reason']}")
                return result
            if self.gate.state != 'ARMED':
                raise RuntimeError(f'Selection stopped: {self.gate.reason}')
        self.gate.stop('no_decision')
        raise RuntimeError('No stable decision within eight seconds')

    async def planet(self, name):
        target = {'earth': 'planet.399', 'mars': 'planet.499'}[name]
        context = await self.core.context()
        if target not in context['allowed_targets']:
            # Back is itself decoded synthetic input, not an operator bypass.
            await self.select('navigation.back')
        return await self.select(target)

    async def close(self):
        self.gate.stop()
        self.adapter.stop()
        await self.core.close()


async def read_command(simulator):
    print('[E] Earth  [M] Mars  [B] Back  [Q] Quit', flush=True)
    if os.name == 'nt':
        import msvcrt
        while True:
            await simulator.heartbeat()
            if msvcrt.kbhit():
                key = msvcrt.getwch().lower()
                if key in ('e', 'm', 'b', 'q'):
                    return key
                if key == '\x03':
                    return 'q'
            await asyncio.sleep(0.25)
    pending = asyncio.create_task(asyncio.to_thread(input, '> '))
    while not pending.done():
        await simulator.heartbeat()
        await asyncio.sleep(0.25)
    return pending.result().strip().lower()


async def run(args):
    simulator = PlanetSimulator(CoreClient(args.core))
    print(LABELS['synthetic'], flush=True)
    print('Open the app in your browser. Each decoded selection takes about four seconds.', flush=True)
    try:
        await simulator.start()
        if args.demo or args.planet:
            for name in (('earth', 'mars', 'earth') if args.demo else (args.planet,)):
                print(f'Simulating {name} selection…', flush=True)
                await simulator.planet(name)
                print(f'Core accepted {name} planet card.', flush=True)
            return
        while True:
            command = await read_command(simulator)
            if command == 'q':
                return
            if command not in ('e', 'm', 'b'):
                continue
            try:
                print('Generating synthetic EEG evidence…', flush=True)
                if command == 'b':
                    await simulator.select('navigation.back')
                else:
                    await simulator.planet('earth' if command == 'e' else 'mars')
                print('Core accepted selection.', flush=True)
            except RuntimeError as error:
                print(str(error), flush=True)
    finally:
        await simulator.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', default='http://127.0.0.1:8000')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--demo', action='store_true', help='Earth -> Mars -> Earth, then exit')
    modes.add_argument('--planet', choices=['earth', 'mars'], help='one planet selection, then exit')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
    except Exception as error:
        # Third-party HTTP errors may contain details we do not need to print.
        raise SystemExit(f'Controller stopped ({type(error).__name__}). Check the core is running '
                         'with BRAIN_ENABLED=true and the app is in planet exploration.') from None


if __name__ == '__main__':
    main()
