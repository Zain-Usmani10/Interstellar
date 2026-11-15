"""EONET Earth hazard events. Offline: a fake HTTP transport replays the checked-in real NASA reply."""
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.backend.planet_data import eonet, get_planet_info

SNAPSHOT = json.loads(eonet.SNAPSHOT_FILE.read_text(encoding="utf-8"))
RAW = SNAPSHOT["raw_response"]
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "contracts" / "schemas"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakeEonet:
    def __init__(self, text=RAW, status=200, error=None):
        self.text, self.status, self.error, self.calls = text, status, error, []

    def __call__(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return httpx.Response(self.status, text=self.text)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    eonet.reset_memory()
    monkeypatch.delenv("INTERSTELLAR_EONET_LIVE", raising=False)
    yield
    eonet.reset_memory()


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("INTERSTELLAR_EONET_LIVE", "1")


NO_SNAPSHOT = Path("/nonexistent/eonet_snapshot.json")


# ------------------------------------------------------------------ parsing

def test_real_reply_keeps_ids_dates_locations_and_links():
    items = eonet.parse_events(RAW)
    assert 0 < len(items) <= 20
    raw_ids = [e["id"] for e in json.loads(RAW)["events"]]
    assert [i["id"] for i in items] == raw_ids[:len(items)]
    for item in items:
        assert item["category"] in ("wildfires", "severeStorms")
        assert item["date_utc"].endswith("Z") and item["source_url"].startswith("http")
        assert item["eonet_url"].startswith("https://eonet.gsfc.nasa.gov/")
        if item["coordinates"] is not None:
            lon, lat = item["coordinates"]
            assert -180 <= lon <= 180 and -90 <= lat <= 90


def test_latest_position_of_a_storm_track_is_used_and_polygons_have_no_point():
    reply = {"events": [
        {"id": "E1", "title": "Storm", "link": "https://eonet.gsfc.nasa.gov/api/v3/events/E1",
         "categories": [{"id": "severeStorms"}], "sources": [],
         "geometry": [{"date": "2026-11-01T00:00:00Z", "type": "Point", "coordinates": [10.0, 5.0]},
                      {"date": "2026-11-03T00:00:00Z", "type": "Point", "coordinates": [12.0, 7.0]}]},
        {"id": "E2", "title": "Fire area", "categories": [{"id": "wildfires"}],
         "geometry": [{"date": "2026-11-02T00:00:00Z", "type": "Polygon", "coordinates": [[[1, 2], [3, 4], [5, 6], [1, 2]]]}]},
    ]}
    storm, fire = eonet.parse_events(json.dumps(reply))
    assert storm["date_utc"] == "2026-11-03T00:00:00Z" and storm["coordinates"] == [12.0, 7.0]
    assert storm["source_url"] == "https://eonet.gsfc.nasa.gov/api/v3/events/E1"        # no source: fall back to EONET link
    assert fire["coordinates"] is None


def test_malformed_and_off_topic_events_are_skipped_not_guessed():
    reply = {"events": [
        {"id": "V1", "title": "Volcano", "categories": [{"id": "volcanoes"}],
         "geometry": [{"date": "2026-11-01T00:00:00Z", "type": "Point", "coordinates": [1, 2]}]},
        {"id": "X1", "title": "No geometry", "categories": [{"id": "wildfires"}], "geometry": []},
        {"id": "X2", "title": "Bad date", "categories": [{"id": "wildfires"}],
         "geometry": [{"date": "yesterday", "type": "Point", "coordinates": [1, 2]}]},
        {"title": "No id", "categories": [{"id": "wildfires"}],
         "geometry": [{"date": "2026-11-01T00:00:00Z", "type": "Point", "coordinates": [1, 2]}]},
        {"id": "OK", "title": "Fire", "categories": [{"id": "wildfires"}],
         "geometry": [{"date": "2026-11-01T00:00:00Z", "type": "Point", "coordinates": [500, 2]}]},
    ]}
    items = eonet.parse_events(json.dumps(reply))
    assert [i["id"] for i in items] == ["OK"] and items[0]["coordinates"] is None       # impossible longitude dropped


@pytest.mark.parametrize("bad", ["<html>Service Unavailable</html>", "[]", '{"title": "EONET Events"}', '{"events": "none"}'])
def test_a_reply_of_the_wrong_shape_is_an_error_not_an_empty_list(bad):
    with pytest.raises(eonet.EonetError):
        eonet.parse_events(bad)


def test_no_more_than_twenty_items():
    event = {"id": "E", "title": "Fire", "categories": [{"id": "wildfires"}],
             "geometry": [{"date": "2026-11-01T00:00:00Z", "type": "Point", "coordinates": [1, 2]}]}
    assert len(eonet.parse_events(json.dumps({"events": [dict(event, id=f"E{i}") for i in range(50)]}))) == 20


# ------------------------------------------------------------------ delivery modes

def test_offline_default_serves_the_dated_snapshot_and_makes_no_request():
    fake = FakeEonet()
    section = eonet.earth_conditions(fake.client())
    assert fake.calls == []                                                   # live is off unless enabled
    assert section["availability"] == "available" and section["delivery"] == "cached"
    assert section["retrieved_utc"] == SNAPSHOT["retrieved_utc"]
    assert section["provenance"]["mode"] == "nasa_cached"
    assert section["provenance"]["source"]["sha256"] == hashlib.sha256(RAW.encode()).hexdigest()
    assert "NOT LIVE" in section["note"] and SNAPSHOT["retrieved_utc"] in section["note"]
    dates = [i["date_utc"] for i in section["items"]]
    assert section["observed_from_utc"] == min(dates) and section["observed_to_utc"] == max(dates)


def test_live_fetch_uses_the_bounded_request_then_reuses_it_for_15_minutes(live):
    fake, clock = FakeEonet(), Clock()
    first = eonet.earth_conditions(fake.client(), NO_SNAPSHOT, clock)
    assert first["delivery"] == "live_fetch" and first["provenance"]["mode"] == "nasa_live"
    assert first["availability"] == "available" and len(first["items"]) <= 20
    assert dict(fake.calls[0].url.params) == {"category": "severeStorms,wildfires", "status": "open", "days": "30", "limit": "20"}
    assert str(fake.calls[0].url).startswith("https://eonet.gsfc.nasa.gov/api/v3/events?")

    clock.t += 14 * 60
    again = eonet.earth_conditions(fake.client(), NO_SNAPSHOT, clock)
    assert len(fake.calls) == 1 and again["delivery"] == "cached" and again["provenance"]["mode"] == "nasa_cached"
    assert again["retrieved_utc"] == first["retrieved_utc"]                   # the timestamp does not pretend to be new

    clock.t += 2 * 60                                                         # now 16 minutes old
    assert eonet.earth_conditions(fake.client(), NO_SNAPSHOT, clock)["delivery"] == "live_fetch"
    assert len(fake.calls) == 2


def test_empty_result_is_labelled_empty_and_not_an_all_clear(live):
    section = eonet.earth_conditions(FakeEonet(text='{"events": []}').client(), NO_SNAPSHOT, Clock())
    assert section["availability"] == "empty" and section["items"] == []
    assert section["observed_from_utc"] is None and section["retrieved_utc"] is not None
    assert "not an all-clear" in section["note"]


@pytest.mark.parametrize("fake", [FakeEonet(status=503), FakeEonet(text="<html>oops</html>"),
                                  FakeEonet(error=httpx.ConnectTimeout("timed out"))])
def test_failure_without_any_saved_reply_is_an_error_not_zero_hazards(live, fake):
    section = eonet.earth_conditions(fake.client(), NO_SNAPSHOT, Clock())
    assert section["availability"] == "error" and section["items"] == [] and section["delivery"] is None
    assert section["retrieved_utc"] is None and section["provenance"] == {"mode": None, "source": None}
    assert "not zero hazards" in section["note"]


def test_failure_falls_back_to_the_snapshot_marked_stale_and_backs_off(live):
    fake, clock = FakeEonet(status=500), Clock()
    section = eonet.earth_conditions(fake.client(), eonet.SNAPSHOT_FILE, clock)
    assert section["availability"] == "available" and section["delivery"] == "cached"
    assert "STALE DATA" in section["note"] and "HTTP 500" in section["note"]
    assert section["retrieved_utc"] == SNAPSHOT["retrieved_utc"]              # the old timestamp stays visible
    clock.t += 30
    eonet.earth_conditions(fake.client(), eonet.SNAPSHOT_FILE, clock)
    assert len(fake.calls) == 1                                               # within 60 s: no second attempt
    clock.t += 31
    eonet.earth_conditions(fake.client(), eonet.SNAPSHOT_FILE, clock)
    assert len(fake.calls) == 2


def test_after_a_good_fetch_a_later_failure_shows_the_last_good_reply_as_stale(live):
    clock = Clock()
    good = eonet.earth_conditions(FakeEonet().client(), NO_SNAPSHOT, clock)
    clock.t += 20 * 60
    later = eonet.earth_conditions(FakeEonet(status=502).client(), NO_SNAPSHOT, clock)
    assert later["availability"] == "available" and later["delivery"] == "cached" and "STALE DATA" in later["note"]
    assert later["retrieved_utc"] == good["retrieved_utc"] and later["items"] == good["items"]


def test_no_snapshot_and_live_off_is_unavailable():
    section = eonet.earth_conditions(FakeEonet().client(), NO_SNAPSHOT, Clock())
    assert section["availability"] == "unavailable" and section["items"] == []


def test_a_tampered_snapshot_is_ignored(tmp_path):
    edited = dict(SNAPSHOT, raw_response=RAW.replace("Wildfire", "Picnic", 1))
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(edited), encoding="utf-8")
    assert eonet.load_snapshot(path) is None
    assert eonet.earth_conditions(None, path, Clock())["availability"] == "unavailable"


# ------------------------------------------------------------------ on the card

def test_hazards_appear_only_on_earth_and_the_card_matches_the_schema():
    earth, mars = get_planet_info("399"), get_planet_info("499")
    assert earth["conditions"]["kind"] == "natural_hazard_events" and earth["conditions"]["items"]
    assert mars["conditions"]["kind"] == "current_weather" and mars["conditions"]["items"] == []
    assert earth["conditions"]["retrieved_utc"] != earth["scene_epoch_jd_tdb"]          # observation time is its own field
    if not SCHEMA_DIR.is_dir():
        pytest.skip("app/contracts/schemas not on this branch yet (lands with contracts v1, PR #9)")
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    schemas = [json.loads(f.read_text(encoding="utf-8")) for f in SCHEMA_DIR.glob("*.json")]
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
    validator = Draft202012Validator(next(s for s in schemas if s.get("title") == "PlanetInfo"), registry=registry)
    assert [e.message for e in validator.iter_errors(earth)] == []
