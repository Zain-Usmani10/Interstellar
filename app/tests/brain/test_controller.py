"""Real input API, generated EEG, simulated controller; no live hardware."""
import asyncio

import httpx

from app.backend.api.app import create_app
from app.backend.runtime.stores import Settings
from app.brain.client import CoreClient
from app.brain.controller import PlanetSimulator
from test_selection import Clock


def test_simulator_switches_planet_cards_and_cleans_session():
    async def scenario():
        app = create_app(Settings(brain_enabled=True, db_path=':memory:', plans_dir=''))
        core = CoreClient(transport=httpx.ASGITransport(app=app))
        clock = Clock()

        async def advance(seconds):
            clock.advance(seconds)

        simulator = PlanetSimulator(core, clock, advance)
        try:
            await simulator.start()
            for name, body in [('earth', '399'), ('mars', '499'), ('earth', '399')]:
                result = await simulator.planet(name)
                assert result['accepted']
                context = await core.context()
                assert context['selected_body_id'] == body
                assert context['screen'] == 'planet_info'
            assert app.state.runtime._mission is None
        finally:
            await simulator.close()
        assert core.session is None

    asyncio.run(scenario())
