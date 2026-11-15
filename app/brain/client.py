"""Input-only client: no operator token, mission route or serial access."""
from urllib.parse import urlsplit
import json
import httpx
from websockets.asyncio.client import connect


class CoreClient:
    def __init__(self, base_url="http://127.0.0.1:8000", transport=None):
        url = urlsplit(base_url)
        if (url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost")
                or url.username or url.password or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError("core must be a loopback HTTP origin")
        self.http = httpx.AsyncClient(base_url=base_url, transport=transport, timeout=0.45,
                                      follow_redirects=False, trust_env=False)
        self.events_url = base_url.rstrip('/').replace('http://', 'ws://', 1) + '/api/v1/events'
        self.session = None

    async def _request(self, method, path, body=None):
        if not path.startswith("/api/v1/input/"):
            raise ValueError("brain client is limited to input routes")
        headers = {"X-Input-Token": self.session["token"]} if self.session else {}
        response = await self.http.request(method, path, json=body, headers=headers)
        response.raise_for_status()
        return response.json() if response.status_code != 204 else None

    async def register(self, info):
        self.session = await self._request("POST", "/api/v1/input/sessions",
                                          {"source": info.source, "adapter": {
                                              "name": info.name, "version": info.version, "device": info.device}})
        return self.session["context"]

    async def heartbeat(self, body):
        return await self._request("POST", f"/api/v1/input/sessions/{self.session['input_session_id']}/heartbeat", body)

    async def context(self):
        return await self._request("GET", "/api/v1/input/context")

    async def submit(self, intent):
        # No automatic retry/new event ID after a timeout: outcome may be unknown.
        result = await self._request("POST", "/api/v1/input/intents", intent)
        if result.get("event_id") != intent["event_id"] or not isinstance(result.get("accepted"), bool):
            raise ValueError("invalid core acknowledgment")
        return result

    async def events(self):
        async with connect(self.events_url, additional_headers={"X-Input-Token": self.session["token"]},
                           max_size=2**20, max_queue=8, open_timeout=2, proxy=None) as ws:
            async for message in ws:
                yield json.loads(message)

    async def close(self):
        try:
            if self.session:
                await self._request("DELETE", f"/api/v1/input/sessions/{self.session['input_session_id']}")
        finally:
            self.session = None
            await self.http.aclose()
