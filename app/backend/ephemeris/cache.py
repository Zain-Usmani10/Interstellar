"""On-disk cache of NASA/JPL Horizons replies (app/data/ephemeris/) and the offline-safe data source.

Every cache file keeps the raw NASA reply, the exact request, when it was retrieved, the API
signature, the source URL and a SHA-256 of the raw reply. The normalized rows used by the planner
are re-derived from the raw reply every time a file is loaded, so an edited file cannot slip through.

Offline rule: if an epoch is not in the cache and there is no network client, we raise
EPHEMERIS_UNAVAILABLE. We never substitute made-up orbits.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import horizons
from .horizons import HorizonsError, StateRow, epoch_key

CACHE_SCHEMA_VERSION = 1
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "ephemeris"


class EphemerisUnavailable(Exception):
    """Requested planet states are not in the cache and cannot be fetched."""
    code = "EPHEMERIS_UNAVAILABLE"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class EphemerisCache:
    """Reads and writes cache files; answers 'state of body X at epoch T' from verified rows only."""

    def __init__(self, directory: Path | str = DEFAULT_CACHE_DIR, *, fallback_directory: Path | str | None = None):
        self.directory = Path(directory)
        self._rows: dict[tuple[str, str], tuple[StateRow, str]] = {}   # (body, epoch key) -> (row, file name)
        self._entries: dict[str, dict] = {}                            # file name -> provenance (no raw text)
        self._constants: dict[str, dict] = {}                          # body -> {gm, radius, file}
        if fallback_directory is not None:
            for path in sorted(Path(fallback_directory).glob("horizons_*.json")):
                self._load(path)
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("horizons_*.json")):
                self._load(path)

    # -- loading and integrity ------------------------------------------------------------

    def _load(self, path: Path) -> None:
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("cache_schema_version") != CACHE_SCHEMA_VERSION:
            raise HorizonsError("CACHE_CORRUPT", f"{path.name}: unknown cache schema version")
        if sha256_text(entry["raw_response"]) != entry["raw_sha256"]:
            raise HorizonsError("CACHE_CORRUPT", f"{path.name}: raw reply does not match its SHA-256")
        if sha256_text(_canonical_json(entry["request"])) != entry["request_sha256"]:
            raise HorizonsError("CACHE_CORRUPT", f"{path.name}: request does not match its SHA-256")
        self._index(path.name, entry)

    def _index(self, file_name: str, entry: dict) -> None:
        body = entry["body_id"]
        if entry["kind"] == "vectors":
            epochs = [float(r["jd_tdb"]) for r in entry["rows"]]
            parsed = horizons.parse_vector_response(entry["raw_response"], body, epochs)
            stored = [StateRow(r["jd_tdb"], tuple(r["r_km"]), tuple(r["v_km_s"])) for r in entry["rows"]]
            if parsed.rows != stored:
                raise HorizonsError("CACHE_CORRUPT", f"{file_name}: stored rows differ from the raw NASA reply")
            for row in parsed.rows:
                self._rows[(body, epoch_key(row.jd_tdb))] = (row, file_name)
            gm, radius = parsed.gm_km3_s2, parsed.mean_radius_km
        else:
            _, gm, radius = horizons.parse_object_data_response(entry["raw_response"], body)
        if gm is not None and radius is not None:
            self._constants.setdefault(body, {"gm_km3_s2": gm, "mean_radius_km": radius, "file": file_name})
        self._entries[file_name] = {k: entry[k] for k in
                                    ("source_name", "source_url", "retrieved_utc", "raw_sha256", "api_signature")}

    # -- writing --------------------------------------------------------------------------

    def store(self, body_id: str, kind: str, request: dict, raw_text: str, retrieved_utc: str,
              epochs_jd_tdb: list[float] | None = None) -> str:
        """Validate a raw reply and save it with its provenance. Invalid replies are never written."""
        if kind == "vectors":
            parsed = horizons.parse_vector_response(raw_text, body_id, epochs_jd_tdb)
            signature = parsed.api_signature
            rows = [{"jd_tdb": r.jd_tdb, "r_km": list(r.r_km), "v_km_s": list(r.v_km_s)} for r in parsed.rows]
        else:
            signature, _, _ = horizons.parse_object_data_response(raw_text, body_id)
            rows = []
        request_sha = sha256_text(_canonical_json(request))
        entry = {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "kind": kind,
            "body_id": body_id,
            "body_name": horizons.BODY_NAMES[body_id],
            "source_name": horizons.SOURCE_NAME,
            "source_url": horizons.HORIZONS_URL,
            "request": request,
            "request_sha256": request_sha,
            "retrieved_utc": retrieved_utc,
            "api_signature": signature,
            "frame": horizons.FRAME if kind == "vectors" else None,
            "raw_sha256": sha256_text(raw_text),
            "rows": rows,
            "raw_response": raw_text,
        }
        file_name = f"horizons_{body_id}_{kind}_{request_sha[:16]}.json"
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / file_name).write_text(json.dumps(entry, indent=1) + "\n", encoding="utf-8")
        self._index(file_name, entry)
        return file_name

    # -- reading --------------------------------------------------------------------------

    def get(self, body_id: str, jd_tdb: float) -> tuple[StateRow, str] | None:
        return self._rows.get((body_id, epoch_key(jd_tdb)))

    def constants(self, body_id: str) -> dict | None:
        return self._constants.get(body_id)

    def provenance(self, file_name: str) -> dict:
        return self._entries[file_name]

    def neighbours(self, body_id: str, jd_tdb: float) -> tuple[tuple[StateRow, str], tuple[StateRow, str]] | None:
        """The cached rows just before and just after jd_tdb (for interpolation), or None if not bracketed."""
        import bisect
        rows = sorted((v for (body, _), v in self._rows.items() if body == body_id), key=lambda v: v[0].jd_tdb)
        times = [row.jd_tdb for row, _ in rows]
        i = bisect.bisect_right(times, jd_tdb)
        if i == 0 or i == len(times):
            return None
        return rows[i - 1], rows[i]

    def epoch_bounds(self, body_id: str) -> tuple[float, float] | None:
        """Earliest and latest cached epoch for a body (the date bounds an offline demo is locked to)."""
        epochs = [float(key) for (body, key) in self._rows if body == body_id]
        return (min(epochs), max(epochs)) if epochs else None


class EphemerisSource:
    """What the planner uses. Serves from the cache; fetches missing epochs only if given a client.

    client=None means offline: missing data raises EphemerisUnavailable.
    `data_mode` says honestly whether anything in this run came over the network.
    """

    def __init__(self, cache: EphemerisCache, client: horizons.HorizonsClient | None = None):
        self.cache = cache
        self.client = client
        self.fetched_live = False
        self.files_used: set[str] = set()

    @property
    def data_mode(self) -> str:
        return "nasa_live" if self.fetched_live else "nasa_cached"

    def states(self, body_id: str, epochs_jd_tdb: list[float]) -> list[StateRow]:
        """States at exactly these epochs, in the given order. All of them or an exception."""
        epochs = [horizons.canonical_epoch(e) for e in epochs_jd_tdb]
        missing = sorted({e for e in epochs if self.cache.get(body_id, e) is None})
        if missing and self.client is None:
            raise EphemerisUnavailable(
                f"EPHEMERIS_UNAVAILABLE: {len(missing)} epoch(s) for body {body_id} are not in the NASA cache "
                f"(first missing JD TDB {epoch_key(missing[0])}) and offline mode cannot fetch them")
        for start in range(0, len(missing), horizons.MAX_EPOCHS_PER_REQUEST):
            batch = missing[start:start + horizons.MAX_EPOCHS_PER_REQUEST]
            request = horizons.build_vector_request(body_id, batch)
            raw_text, retrieved_utc = self.client.get(request)
            self.cache.store(body_id, "vectors", request, raw_text, retrieved_utc, batch)
            self.fetched_live = True
        rows = []
        for e in epochs:
            row, file_name = self.cache.get(body_id, e)
            self.files_used.add(file_name)
            rows.append(row)
        return rows

    def body_constants(self, body_id: str) -> dict:
        """GM (km^3/s^2) and mean radius (km) exactly as printed by Horizons for this body."""
        found = self.cache.constants(body_id)
        if found is None:
            if self.client is None:
                raise EphemerisUnavailable(f"EPHEMERIS_UNAVAILABLE: no cached Horizons constants for body {body_id}")
            request = horizons.build_object_data_request(body_id)
            raw_text, retrieved_utc = self.client.get(request)
            self.cache.store(body_id, "object_data", request, raw_text, retrieved_utc)
            self.fetched_live = True
            found = self.cache.constants(body_id)
        self.files_used.add(found["file"])
        return found

    def sources(self) -> list[dict]:
        """Provenance list for a MissionPlan: one item per NASA reply that was actually used."""
        out = []
        for file_name in sorted(self.files_used):
            p = self.cache.provenance(file_name)
            out.append({
                "name": f"{p['source_name']} ({file_name})",
                "url": p["source_url"],
                "retrieved_utc": p["retrieved_utc"],
                "sha256": p["raw_sha256"],
                "api_signature": f"{p['api_signature']['source']} v{p['api_signature']['version']}",
            })
        return out
