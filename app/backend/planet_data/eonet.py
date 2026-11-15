"""Earth natural hazard events from NASA EONET v3 (severe storms and wildfires, last 30 days).

What this is: a short list of dated, located events that NASA's Earth Observatory tracker lists as open.
What this is NOT: a weather forecast, a complete census, a planet-health score, Mars data, or anything
about the simulated mission date. An empty list is not an all-clear; an error is not zero hazards.

Delivery, most to least fresh:
  1. a copy fetched in this process less than 15 minutes ago (in memory)
  2. a new live fetch, only if INTERSTELLAR_EONET_LIVE=1 (one bounded request, never in parallel)
  3. the checked-in snapshot app/data/eonet/earth_events_snapshot.json, shown with its own retrieval date
  4. otherwise 'unavailable' (never fetched) or 'error' (fetch failed and there is no snapshot)

    python -m app.backend.planet_data.eonet --refresh     # re-download the snapshot
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
EONET_PARAMS = {"category": "severeStorms,wildfires", "status": "open", "days": "30", "limit": "20"}
SOURCE_NAME = "NASA EONET v3 (Earth Observatory Natural Event Tracker)"
CATEGORIES = ("severeStorms", "wildfires")
MAX_ITEMS = 20
TIMEOUT_S = 6.0
FRESH_FOR_S = 15 * 60            # reuse a live reply for 15 minutes
RETRY_AFTER_FAILURE_S = 60       # after a failed fetch, do not hammer the API
LABEL = "Earth natural hazard events"
SNAPSHOT_FILE = Path(__file__).resolve().parents[2] / "data" / "eonet" / "earth_events_snapshot.json"
USER_AGENT = "interstellar-mission-planner/0.1 (student hackathon demo; cached requests)"
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
_FMT = "%Y-%m-%dT%H:%M:%SZ"

_lock = threading.Lock()
_memory: dict = {"reply": None, "fetched_at": None, "failed_at": None}     # monotonic seconds


class EonetError(Exception):
    pass


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime(_FMT)


def live_enabled() -> bool:
    return os.environ.get("INTERSTELLAR_EONET_LIVE") == "1"


def parse_events(raw_text: str) -> list[dict]:
    """Validated card items from a raw EONET reply. A reply of the wrong shape raises; it is never 'no events'."""
    try:
        payload = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise EonetError(f"reply is not JSON: {exc}") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise EonetError("reply has no 'events' list")
    items = []
    for event in payload["events"][:MAX_ITEMS]:
        try:
            category = next(c["id"] for c in event["categories"] if c["id"] in CATEGORIES)
            # An event can have several dated positions (a storm track); show the most recent one.
            latest = max((g for g in event["geometry"] if _UTC_RE.match(str(g.get("date", "")))), key=lambda g: g["date"])
            event_id, title = str(event["id"]), str(event["title"])
        except (KeyError, TypeError, ValueError, StopIteration):
            continue                                     # a malformed or off-topic event is skipped, not guessed
        coords = latest.get("coordinates")
        is_point = (latest.get("type") == "Point" and isinstance(coords, list) and len(coords) == 2
                    and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in coords)
                    and -180 <= coords[0] <= 180 and -90 <= coords[1] <= 90)
        sources = event.get("sources") or []
        items.append({
            "id": event_id, "title": title, "category": category, "date_utc": latest["date"],
            "coordinates": [float(coords[0]), float(coords[1])] if is_point else None,     # [longitude, latitude]
            "source_url": str(sources[0]["url"]) if sources and isinstance(sources[0], dict) and sources[0].get("url")
                          else str(event.get("link") or EONET_URL),
            "eonet_url": str(event.get("link") or EONET_URL),
        })
    return items


def fetch(http: httpx.Client | None = None) -> dict:
    """One bounded request to EONET. Returns a validated reply record or raises EonetError."""
    client = http or httpx.Client(timeout=TIMEOUT_S)
    try:
        response = client.get(EONET_URL, params=EONET_PARAMS, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as exc:
        raise EonetError(f"{type(exc).__name__}: {exc}") from None
    finally:
        if http is None:
            client.close()
    if response.status_code != 200:
        raise EonetError(f"HTTP {response.status_code}")
    parse_events(response.text)                          # validate before anything keeps it
    return {"source_name": SOURCE_NAME, "source_url": str(response.request.url), "request": dict(EONET_PARAMS),
            "retrieved_utc": _now_label(), "raw_sha256": hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
            "raw_response": response.text}


def load_snapshot(path: Path = SNAPSHOT_FILE) -> dict | None:
    """The checked-in reply, if present and intact (SHA-256 must match)."""
    try:
        reply = json.loads(path.read_text(encoding="utf-8"))
        if hashlib.sha256(reply["raw_response"].encode("utf-8")).hexdigest() != reply["raw_sha256"]:
            return None
        parse_events(reply["raw_response"])
        return reply
    except (OSError, KeyError, ValueError, TypeError, EonetError):
        return None


def _section(reply: dict | None, delivery: str | None, availability: str | None, note: str) -> dict:
    items = parse_events(reply["raw_response"]) if reply else []
    if availability is None:
        availability = "available" if items else "empty"
    dates = sorted(i["date_utc"] for i in items)
    age_note = ""
    if reply:
        age_h = (datetime.now(timezone.utc) - datetime.strptime(reply["retrieved_utc"], _FMT).replace(tzinfo=timezone.utc)).total_seconds() / 3600
        age_note = f" Retrieved {reply['retrieved_utc']} ({age_h:.1f} h ago)."
    return {
        "scope": "earth", "kind": "natural_hazard_events", "label": LABEL,
        "availability": availability, "delivery": delivery,
        "observed_from_utc": dates[0] if dates else None, "observed_to_utc": dates[-1] if dates else None,
        "retrieved_utc": reply["retrieved_utc"] if reply else None,
        "items": items,
        "note": note + age_note + " These are dated observations of open severe-storm and wildfire events (at most "
                f"{MAX_ITEMS}, last 30 days), not a forecast, not a complete list, and not a description of the "
                "simulated mission date. An empty list is not an all-clear.",
        "provenance": {
            "mode": None if reply is None else ("nasa_live" if delivery == "live_fetch" else "nasa_cached"),
            "source": None if reply is None else {"name": reply["source_name"], "url": reply["source_url"],
                                                  "retrieved_utc": reply["retrieved_utc"], "sha256": reply["raw_sha256"],
                                                  "api_signature": None},
        },
    }


def earth_conditions(http: httpx.Client | None = None, snapshot_path: Path = SNAPSHOT_FILE, now=time.monotonic) -> dict:
    """The 'conditions' section of Earth's PlanetInfo card. Never raises."""
    with _lock:                                           # one EONET request at a time, process-wide
        fresh = _memory["reply"] is not None and now() - _memory["fetched_at"] < FRESH_FOR_S
        if fresh:
            return _section(_memory["reply"], "cached", None, "NASA EONET reply reused from memory (refreshed every 15 minutes).")
        failure = None
        backing_off = _memory["failed_at"] is not None and now() - _memory["failed_at"] < RETRY_AFTER_FAILURE_S
        if live_enabled() and not backing_off:
            try:
                _memory.update(reply=fetch(http), fetched_at=now(), failed_at=None)
                return _section(_memory["reply"], "live_fetch", None, "Fetched live from NASA EONET.")
            except EonetError as exc:
                _memory["failed_at"] = now()
                failure = str(exc)[:120]
        elif live_enabled():
            failure = "recent fetch failed; waiting before retrying"
        older = _memory["reply"] or load_snapshot(snapshot_path)
        if older is not None:
            why = f"Live NASA EONET fetch failed ({failure}); showing an older saved reply." if failure else \
                  "Live NASA EONET fetch is off; showing the saved snapshot."
            return _section(older, "cached", None, ("STALE DATA. " if failure else "SAVED SNAPSHOT, NOT LIVE. ") + why)
        if failure:
            return _section(None, None, "error", f"NASA EONET could not be reached ({failure}) and no saved reply exists. "
                                                 "An error is not zero hazards.")
        return _section(None, None, "unavailable", "Live NASA EONET fetch is off and no saved snapshot exists.")


def reset_memory() -> None:
    with _lock:
        _memory.update(reply=None, fetched_at=None, failed_at=None)


if __name__ == "__main__":
    import sys
    if "--refresh" not in sys.argv:
        sys.exit(__doc__)
    record = fetch()
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"saved {len(parse_events(record['raw_response']))} events, retrieved {record['retrieved_utc']}")
