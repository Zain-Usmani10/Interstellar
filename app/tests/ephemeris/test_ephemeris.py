"""NASA adapter tests. All offline: they use the checked-in NASA cache or a fake HTTP transport."""
import json
import shutil

import httpx
import numpy as np
import pytest

from app.backend.ephemeris import horizons
from app.backend.ephemeris.cache import DEFAULT_CACHE_DIR, EphemerisCache, EphemerisSource, EphemerisUnavailable
from app.backend.ephemeris.horizons import HorizonsClient, HorizonsError
from app.backend.ephemeris.interp import hermite_state
from app.backend.ephemeris.timeconv import jd_tdb_to_utc, utc_to_jd_tdb


def cached_entry(body_id: str) -> dict:
    """A real NASA reply from the checked-in cache."""
    path = sorted(DEFAULT_CACHE_DIR.glob(f"horizons_{body_id}_vectors_*.json"))[0]
    return json.loads(path.read_text(encoding="utf-8"))


def reply_with(entry: dict, old: str, new: str) -> str:
    """The same NASA reply with one piece of its text report changed."""
    payload = json.loads(entry["raw_response"])
    assert old in payload["result"]
    payload["result"] = payload["result"].replace(old, new, 1)
    return json.dumps(payload)


def epochs_of(entry: dict) -> list[float]:
    return [r["jd_tdb"] for r in entry["rows"]]


# ------------------------------------------------------------------ request contract

def test_request_uses_the_exact_horizons_contract():
    request = horizons.build_vector_request("499", [2461359.5, 2461360.5])
    assert request == {
        "format": "json", "COMMAND": "'499'", "OBJ_DATA": "'YES'", "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'VECTORS'",
        "CENTER": "'500@10'", "REF_SYSTEM": "'ICRF'", "REF_PLANE": "'ECLIPTIC'", "OUT_UNITS": "'KM-S'",
        "TIME_TYPE": "'TDB'", "VEC_CORR": "'NONE'", "VEC_TABLE": "'2'", "CSV_FORMAT": "'YES'", "TLIST_TYPE": "'JD'",
        "TLIST": "'2461359.500000000' '2461360.500000000'",
    }


@pytest.mark.parametrize("body, epochs", [
    ("999", [2461359.5]),                              # Pluto is outside the eight-planet scope
    ("399", []),                                       # nothing asked
    ("399", [2461359.5 + i for i in range(33)]),       # more than 32 per request
    ("399", [2461360.5, 2461359.5]),                   # not increasing
    ("399", [2461359.5, 2461359.5]),                   # duplicate
    ("399", [float("nan")]),
])
def test_bad_requests_are_refused(body, epochs):
    with pytest.raises(HorizonsError):
        horizons.build_vector_request(body, epochs)


# ------------------------------------------------------------------ reply validation

def test_real_reply_parses_with_units_and_constants():
    entry = cached_entry("399")
    parsed = horizons.parse_vector_response(entry["raw_response"], "399", epochs_of(entry))
    assert len(parsed.rows) == len(entry["rows"])
    distance_au = np.linalg.norm(parsed.rows[0].r_km) / 149597870.7
    speed = np.linalg.norm(parsed.rows[0].v_km_s)
    assert 0.98 < distance_au < 1.02 and 29.0 < speed < 30.5       # Earth: about 1 au, about 30 km/s
    assert parsed.gm_km3_s2 == pytest.approx(398600.435, abs=0.01)
    assert parsed.api_signature["source"] == "NASA/JPL Horizons API"


@pytest.mark.parametrize("old, new, code", [
    ("$$SOE", "", "NO_TABLE"),
    ("$$EOE", "", "NO_TABLE"),
    ("Target body name: Earth (399)", "Target body name: Venus (299)", "WRONG_TARGET"),
    ("Center body name: Sun (10)", "Center body name: Earth (399)", "WRONG_CENTER"),
    ("KM-S", "AU-D", "WRONG_UNITS"),
    ("Ecliptic of J2000.0", "ICRF", "WRONG_FRAME"),
    ("JDTDB,", "JDUT,", "WRONG_COLUMNS"),
    ("E+07", "E+07x", "BAD_ROW"),
])
def test_wrong_or_damaged_replies_are_rejected(old, new, code):
    entry = cached_entry("399")
    with pytest.raises(HorizonsError) as err:
        horizons.parse_vector_response(reply_with(entry, old, new), "399", epochs_of(entry))
    assert err.value.code == code


def test_nonfinite_numbers_are_rejected():
    entry = cached_entry("399")
    first_x = json.loads(entry["raw_response"])["result"].split("$$SOE")[1].split(",")[2].strip()
    with pytest.raises(HorizonsError) as err:
        horizons.parse_vector_response(reply_with(entry, first_x, "NaN"), "399", epochs_of(entry))
    assert err.value.code == "NONFINITE"


def test_http_200_error_text_is_rejected():
    error_page = json.dumps({"signature": {"source": "NASA/JPL Horizons API", "version": "1.2"},
                             "result": "No ephemeris for target \"Earth\" prior to A.D. 1900 ... no matches found"})
    with pytest.raises(HorizonsError) as err:
        horizons.parse_vector_response(error_page, "399", [2461359.5])
    assert err.value.code == "NO_TABLE"
    with pytest.raises(HorizonsError) as err:
        horizons.parse_vector_response(json.dumps({"error": "bad parameter"}), "399", [2461359.5])
    assert err.value.code == "API_ERROR"
    with pytest.raises(HorizonsError):
        horizons.parse_vector_response("<html>503</html>", "399", [2461359.5])


def test_unexpected_api_signature_fails_closed():
    entry = cached_entry("399")
    payload = json.loads(entry["raw_response"])
    payload["signature"]["version"] = "2.0"
    with pytest.raises(HorizonsError) as err:
        horizons.parse_vector_response(json.dumps(payload), "399", epochs_of(entry))
    assert err.value.code == "BAD_SIGNATURE"


def test_reply_epochs_must_match_the_request_exactly():
    entry = cached_entry("399")
    epochs = epochs_of(entry)
    with pytest.raises(HorizonsError) as err:
        horizons.parse_vector_response(entry["raw_response"], "399", epochs[:-1])
    assert err.value.code == "ROW_COUNT"
    with pytest.raises(HorizonsError) as err:
        horizons.parse_vector_response(entry["raw_response"], "399", epochs[:-1] + [epochs[-1] + 1.0])
    assert err.value.code == "EPOCH_MISMATCH"


def test_mars_reply_is_not_accepted_as_earth():
    entry = cached_entry("499")
    with pytest.raises(HorizonsError):
        horizons.parse_vector_response(entry["raw_response"], "399", epochs_of(entry))


# ------------------------------------------------------------------ cache and offline behaviour

def test_every_checked_in_cache_file_is_intact_and_has_provenance():
    cache = EphemerisCache(DEFAULT_CACHE_DIR)          # loading re-parses every raw reply and checks SHA-256
    files = sorted(DEFAULT_CACHE_DIR.glob("horizons_*.json"))
    assert files
    for path in files:
        entry = json.loads(path.read_text(encoding="utf-8"))
        for field in ("request", "request_sha256", "retrieved_utc", "api_signature", "source_url", "raw_sha256", "raw_response"):
            assert entry[field], f"{path.name} lacks {field}"
        assert entry["source_url"] == "https://ssd.jpl.nasa.gov/api/horizons.api"
    for body in ("10", "399", "499"):
        assert cache.constants(body)["gm_km3_s2"] > 0
    assert cache.constants("10")["gm_km3_s2"] == pytest.approx(1.3271244004e11, rel=1e-9)


def test_tampered_cache_file_is_refused(tmp_path):
    source_file = sorted(DEFAULT_CACHE_DIR.glob("horizons_399_vectors_*.json"))[0]
    entry = json.loads(source_file.read_text(encoding="utf-8"))
    entry["rows"][0]["r_km"][0] += 1000.0                        # move Earth by 1000 km
    (tmp_path / source_file.name).write_text(json.dumps(entry), encoding="utf-8")
    with pytest.raises(HorizonsError) as err:
        EphemerisCache(tmp_path)
    assert err.value.code == "CACHE_CORRUPT"

    entry = json.loads(source_file.read_text(encoding="utf-8"))
    entry["raw_response"] = entry["raw_response"].replace("E+07", "E+08", 1)
    (tmp_path / source_file.name).write_text(json.dumps(entry), encoding="utf-8")
    with pytest.raises(HorizonsError) as err:
        EphemerisCache(tmp_path)
    assert err.value.code == "CACHE_CORRUPT"


def test_offline_serves_cached_epochs_and_refuses_missing_ones():
    source = EphemerisSource(EphemerisCache(DEFAULT_CACHE_DIR))          # no client = offline
    entry = cached_entry("399")
    rows = source.states("399", epochs_of(entry)[:3])
    assert [r.jd_tdb for r in rows] == epochs_of(entry)[:3]
    assert source.data_mode == "nasa_cached"
    assert all(s["sha256"] and s["retrieved_utc"] and s["url"].startswith("https://ssd.jpl.nasa.gov") for s in source.sources())
    with pytest.raises(EphemerisUnavailable) as err:
        source.states("399", [2440000.5])                               # 1968: not in the cache
    assert "EPHEMERIS_UNAVAILABLE" in str(err.value)


class FakeHorizons:
    """Stands in for NASA: replays a real cached reply and records how it was called."""

    def __init__(self, entry, failures=()):
        self.entry, self.failures, self.calls, self.active, self.max_active = entry, list(failures), [], 0, 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.calls.append(request)
        try:
            if self.failures:
                status, headers = self.failures.pop(0)
                return httpx.Response(status, headers=headers, text="busy")
            return httpx.Response(200, text=self.entry["raw_response"])
        finally:
            self.active -= 1


def client_for(fake) -> tuple[HorizonsClient, list[float]]:
    sleeps = []
    return HorizonsClient(http=httpx.Client(transport=httpx.MockTransport(fake)), sleep=sleeps.append), sleeps


def test_live_fetch_is_validated_cached_and_then_reused(tmp_path):
    entry = cached_entry("499")
    fake = FakeHorizons(entry)
    client, _ = client_for(fake)
    source = EphemerisSource(EphemerisCache(tmp_path), client)
    rows = source.states("499", epochs_of(entry))
    assert source.data_mode == "nasa_live" and len(fake.calls) == 1
    sent = dict(fake.calls[0].url.params)
    assert sent == horizons.build_vector_request("499", epochs_of(entry))        # properly URL-encoded round trip
    assert "interstellar" in fake.calls[0].headers["user-agent"]

    source.states("499", epochs_of(entry))                                       # second time: no network
    assert len(fake.calls) == 1
    offline = EphemerisSource(EphemerisCache(tmp_path))                          # fresh process, cache only
    assert offline.states("499", epochs_of(entry)) == rows
    assert offline.data_mode == "nasa_cached"


def test_retries_are_bounded_and_honour_retry_after():
    fake = FakeHorizons(cached_entry("399"), failures=[(503, {"Retry-After": "7"}), (503, {})])
    client, sleeps = client_for(fake)
    text, retrieved = client.get({"format": "json"})
    assert len(fake.calls) == 3 and retrieved.endswith("Z")
    assert 7.0 in sleeps and 4.0 in sleeps                                       # Retry-After, then backoff

    fake = FakeHorizons(cached_entry("399"), failures=[(503, {})] * 5)
    client, _ = client_for(fake)
    with pytest.raises(HorizonsError) as err:
        client.get({"format": "json"})
    assert err.value.code == "NETWORK" and len(fake.calls) == 3                  # never more than three attempts

    fake = FakeHorizons(cached_entry("399"), failures=[(400, {})])
    client, _ = client_for(fake)
    with pytest.raises(HorizonsError):
        client.get({"format": "json"})
    assert len(fake.calls) == 1                                                  # a client error is not retried


def test_requests_are_never_sent_in_parallel():
    import threading
    fake = FakeHorizons(cached_entry("399"))
    clients = [client_for(fake)[0] for _ in range(4)]
    threads = [threading.Thread(target=c.get, args=({"format": "json"},)) for c in clients]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(fake.calls) == 4 and fake.max_active == 1


def test_a_bad_live_reply_is_never_written_to_the_cache(tmp_path):
    entry = cached_entry("399")
    bad = dict(entry, raw_response=reply_with(entry, "KM-S", "AU-D"))
    client, _ = client_for(FakeHorizons(bad))
    with pytest.raises(HorizonsError):
        EphemerisSource(EphemerisCache(tmp_path), client).states("399", epochs_of(entry))
    assert list(tmp_path.glob("*.json")) == []


# ------------------------------------------------------------------ time and interpolation

@pytest.mark.parametrize("utc", ["2026-11-15T00:00:00Z", "2027-02-15T12:34:56Z", "2027-09-11T23:59:59Z"])
def test_utc_tdb_round_trip(utc):
    jd = utc_to_jd_tdb(utc)
    assert jd_tdb_to_utc(jd) == utc
    assert jd_tdb_to_utc(horizons.canonical_epoch(jd)) == utc


def test_tdb_is_not_utc_relabelled():
    # 2026-11-15T00:00:00 UTC is JD 2461359.5 in UTC; TDB is ahead by 69.184 s (37 leap seconds + 32.184 s).
    offset_s = (utc_to_jd_tdb("2026-11-15T00:00:00Z") - 2461359.5) * 86400
    assert offset_s == pytest.approx(69.184, abs=0.01)


def test_hermite_interpolation_matches_nodes_and_refuses_extrapolation():
    entry = cached_entry("399")
    states = entry["rows"]
    r, v = hermite_state(states, states[1]["jd_tdb"])
    assert np.allclose(r, states[1]["r_km"], atol=1e-3) and np.allclose(v, states[1]["v_km_s"], atol=1e-9)
    with pytest.raises(ValueError):
        hermite_state(states, states[0]["jd_tdb"] - 0.01)
    with pytest.raises(ValueError):
        hermite_state(states, states[-1]["jd_tdb"] + 0.01)
