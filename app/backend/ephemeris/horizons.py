"""NASA/JPL Horizons adapter: build the request, fetch it politely, parse and validate the reply.

What NASA gives us: where a planet is (position, km) and how fast it moves (velocity, km/s)
relative to the Sun at the exact times we ask for. Nothing else in the project talks to Horizons.

Rules followed here (docs/plan/MAIN_BACKEND_FPGA_TASKS.md section 5):
- Sun-centred (500@10), ICRF, ecliptic plane, km and km/s, TDB Julian dates, no corrections.
- One request at a time, 30 s timeout, at most three attempts, backoff, honour Retry-After.
- Fail closed: an HTTP 200 that carries an error text, the wrong body, the wrong units or the
  wrong times is rejected. We never guess.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
SOURCE_NAME = "NASA/JPL Horizons API"
SUPPORTED_API_MAJOR = "1"          # signature.version must be 1.x; anything else fails closed
MAX_EPOCHS_PER_REQUEST = 32
REQUEST_TIMEOUT_S = 30.0
MAX_ATTEMPTS = 3
MIN_SECONDS_BETWEEN_REQUESTS = 0.5

SUN_ID = "10"
BODY_NAMES = {"199": "Mercury", "299": "Venus", "399": "Earth", "499": "Mars",
              "599": "Jupiter", "699": "Saturn", "799": "Uranus", "899": "Neptune", SUN_ID: "Sun"}
PLANET_IDS = tuple(body for body in BODY_NAMES if body != SUN_ID)

# The frame every vector in this project lives in. Stored next to every cached row.
FRAME = {"center": "500@10", "ref_system": "ICRF", "ref_plane": "ECLIPTIC", "units": "KM-S", "time_scale": "TDB"}

# Generic by default (no personal contact baked into the repo). Set HORIZONS_USER_AGENT to add one.
DEFAULT_USER_AGENT = "interstellar-mission-planner/0.1 (student hackathon demo; serialized + cached requests)"


class HorizonsError(Exception):
    """Horizons could not be reached, or its reply failed validation. `code` is machine-readable."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class StateRow:
    """One planet state: time (Julian date, TDB), position (km), velocity (km/s), Sun-centred."""
    jd_tdb: float
    r_km: tuple[float, float, float]
    v_km_s: tuple[float, float, float]


@dataclass(frozen=True)
class ParsedVectors:
    api_signature: dict
    rows: list[StateRow]
    gm_km3_s2: float | None        # the body's GM as printed in the Horizons object-data block
    mean_radius_km: float | None


def epoch_key(jd_tdb: float) -> str:
    """Canonical text form of an epoch. Horizons prints 9 decimals (about 86 microseconds)."""
    return f"{jd_tdb:.9f}"


def canonical_epoch(jd_tdb: float) -> float:
    """Round an epoch to what Horizons can echo back, so request, reply and cache key all agree."""
    return float(epoch_key(jd_tdb))


def utc_now_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_vector_request(body_id: str, epochs_jd_tdb: list[float]) -> dict[str, str]:
    """Exact Horizons parameters for planet state vectors at an explicit list of TDB Julian dates."""
    if body_id not in PLANET_IDS:
        raise HorizonsError("UNSUPPORTED_BODY", f"expected a supported planet centre, got {body_id!r}")
    if not 1 <= len(epochs_jd_tdb) <= MAX_EPOCHS_PER_REQUEST:
        raise HorizonsError("BAD_REQUEST", f"need 1..{MAX_EPOCHS_PER_REQUEST} epochs per request, got {len(epochs_jd_tdb)}")
    keys = [epoch_key(e) for e in epochs_jd_tdb]
    if any(not math.isfinite(e) for e in epochs_jd_tdb) or keys != sorted(set(keys), key=float):
        raise HorizonsError("BAD_REQUEST", "epochs must be finite, unique and increasing")
    return {
        "format": "json",
        "COMMAND": f"'{body_id}'",
        "OBJ_DATA": "'YES'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'VECTORS'",
        "CENTER": "'500@10'",
        "REF_SYSTEM": "'ICRF'",
        "REF_PLANE": "'ECLIPTIC'",
        "OUT_UNITS": "'KM-S'",
        "TIME_TYPE": "'TDB'",
        "VEC_CORR": "'NONE'",
        "VEC_TABLE": "'2'",
        "CSV_FORMAT": "'YES'",
        "TLIST_TYPE": "'JD'",
        "TLIST": " ".join(f"'{k}'" for k in keys),
    }


def build_object_data_request(body_id: str) -> dict[str, str]:
    """Object-data page only (no ephemeris). Used once for the Sun to read its GM and radius."""
    return {"format": "json", "COMMAND": f"'{body_id}'", "OBJ_DATA": "'YES'", "MAKE_EPHEM": "'NO'"}


# ----------------------------------------------------------------------------- parsing

_GM_RE = re.compile(r"GM[,\s]*\(?km\^3/s\^2\)?\s*=\s*([0-9]+\.?[0-9]*)")
_RADIUS_RE = re.compile(r"Vol\. [Mm]ean [Rr]adius[,\s]*\(?km\)?\s*=\s*([0-9]+\.?[0-9]*)")


def _unwrap(raw_text: str) -> tuple[dict, str]:
    """Open the JSON envelope. Horizons puts its whole text report in the 'result' string."""
    try:
        payload = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HorizonsError("BAD_RESPONSE", f"reply is not JSON: {exc}") from None
    if not isinstance(payload, dict):
        raise HorizonsError("BAD_RESPONSE", "reply JSON is not an object")
    if "error" in payload:
        raise HorizonsError("API_ERROR", str(payload["error"])[:300])
    signature = payload.get("signature")
    if (not isinstance(signature, dict) or signature.get("source") != SOURCE_NAME
            or not str(signature.get("version", "")).startswith(SUPPORTED_API_MAJOR + ".")):
        raise HorizonsError("BAD_SIGNATURE", f"unexpected API signature {signature!r}")
    result = payload.get("result")
    if not isinstance(result, str):
        raise HorizonsError("BAD_RESPONSE", "reply has no 'result' text")
    return {"source": signature["source"], "version": str(signature["version"])}, result


def _object_constants(result: str) -> tuple[float | None, float | None]:
    header = result.split("Ephemeris /")[0]
    gm = _GM_RE.search(header)
    radius = _RADIUS_RE.search(header)
    return (float(gm.group(1)) if gm else None, float(radius.group(1)) if radius else None)


def parse_vector_response(raw_text: str, body_id: str, epochs_jd_tdb: list[float]) -> ParsedVectors:
    """Turn a raw Horizons reply into validated rows, or raise HorizonsError. Never returns partial data."""
    signature, result = _unwrap(raw_text)
    if "$$SOE" not in result or "$$EOE" not in result:
        # Horizons reports many problems as HTTP 200 plus an explanation and no data table.
        raise HorizonsError("NO_TABLE", "no $$SOE/$$EOE table in reply: " + " ".join(result.split())[:200])

    name = BODY_NAMES[body_id]
    required_lines = {
        "target": rf"Target body name:\s*{name} \({body_id}\)",
        "center": r"Center body name:\s*Sun \(10\)",
        "units": r"Output units\s*:\s*KM-S\b",
        "frame": r"Reference frame\s*:\s*Ecliptic of J2000\.0",
        "axes": r"X-axis\s*:\s*ICRF",
        "geometric": r"Output type\s*:\s*GEOMETRIC cartesian states",
        "columns": r"JDTDB,\s*Calendar Date \(TDB\),\s*X,\s*Y,\s*Z,\s*VX,\s*VY,\s*VZ,",
    }
    for what, pattern in required_lines.items():
        if not re.search(pattern, result):
            raise HorizonsError("WRONG_" + what.upper(), f"reply does not confirm the expected {what}")

    table = result.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    rows: list[StateRow] = []
    for line in table.strip().splitlines():
        cells = [c.strip() for c in line.split(",")]
        if len(cells) < 8:
            raise HorizonsError("BAD_ROW", f"expected 8 columns, got: {line[:80]!r}")
        try:
            numbers = [float(cells[0])] + [float(c) for c in cells[2:8]]
        except ValueError:
            raise HorizonsError("BAD_ROW", f"non-numeric value in row: {line[:80]!r}") from None
        if not all(math.isfinite(n) for n in numbers):
            raise HorizonsError("NONFINITE", f"non-finite value in row: {line[:80]!r}")
        rows.append(StateRow(numbers[0], tuple(numbers[1:4]), tuple(numbers[4:7])))

    wanted = [epoch_key(e) for e in epochs_jd_tdb]
    got = [epoch_key(r.jd_tdb) for r in rows]
    if len(got) != len(wanted):
        raise HorizonsError("ROW_COUNT", f"asked for {len(wanted)} epochs, reply has {len(got)}")
    if got != wanted:
        raise HorizonsError("EPOCH_MISMATCH", "reply epochs differ from the requested epochs")
    if any(float(b) <= float(a) for a, b in zip(got, got[1:])):
        raise HorizonsError("EPOCH_ORDER", "reply epochs are not unique and increasing")

    gm, radius = _object_constants(result)
    return ParsedVectors(signature, rows, gm, radius)


def parse_object_data_response(raw_text: str, body_id: str) -> tuple[dict, float, float]:
    """Read GM and mean radius from an object-data page. Both must be present."""
    signature, result = _unwrap(raw_text)
    if not re.search(rf"\b{BODY_NAMES[body_id]}\s+{body_id}\b", result):
        raise HorizonsError("WRONG_TARGET", f"object-data page is not for body {body_id}")
    gm, radius = _object_constants(result)
    if gm is None or radius is None:
        raise HorizonsError("NO_CONSTANTS", f"GM or mean radius missing from the object-data page of {body_id}")
    return signature, gm, radius


# ----------------------------------------------------------------------------- network

class HorizonsClient:
    """The only place that opens a connection to NASA. One request at a time, application-wide."""

    _lock = threading.Lock()       # shared by every instance: SSD fair use forbids parallel calls
    _last_request_end = 0.0

    def __init__(self, http: httpx.Client | None = None, sleep=time.sleep, user_agent: str | None = None):
        self._http = http or httpx.Client(timeout=REQUEST_TIMEOUT_S)
        self._sleep = sleep
        self._user_agent = user_agent or os.environ.get("HORIZONS_USER_AGENT") or DEFAULT_USER_AGENT
        self.request_count = 0

    def get(self, params: dict[str, str]) -> tuple[str, str]:
        """Send one request (httpx encodes the parameters). Returns (raw reply text, retrieval UTC)."""
        with HorizonsClient._lock:
            last_error = "no attempt made"
            for attempt in range(1, MAX_ATTEMPTS + 1):
                wait = MIN_SECONDS_BETWEEN_REQUESTS - (time.monotonic() - HorizonsClient._last_request_end)
                if wait > 0:
                    self._sleep(wait)
                retry_after = None
                try:
                    self.request_count += 1
                    response = self._http.get(HORIZONS_URL, params=params, timeout=REQUEST_TIMEOUT_S,
                                              headers={"User-Agent": self._user_agent})
                    if response.status_code == 200:
                        return response.text, utc_now_label()
                    last_error = f"HTTP {response.status_code}"
                    if response.status_code not in (429, 500, 502, 503, 504):
                        break                                   # a client error will not fix itself
                    retry_after = response.headers.get("Retry-After")
                except httpx.HTTPError as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                finally:
                    HorizonsClient._last_request_end = time.monotonic()
                if attempt < MAX_ATTEMPTS:
                    backoff = 2.0 ** attempt                    # 2 s, then 4 s
                    if retry_after and retry_after.strip().isdigit():
                        backoff = max(backoff, min(float(retry_after), 60.0))
                    self._sleep(backoff)
            raise HorizonsError("NETWORK", f"Horizons request failed: {last_error}")
