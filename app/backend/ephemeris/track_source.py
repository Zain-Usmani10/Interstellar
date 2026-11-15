"""Offline search source: verified NASA rows, then the validated all-planet track."""
import bisect

from .cache import EphemerisCache, EphemerisSource, EphemerisUnavailable, DEFAULT_CACHE_DIR
from .horizons import StateRow, canonical_epoch
from .interp import hermite_state
from .planet_tracks import load_tracks, TRACK_CACHE_DIR


class TrackSource(EphemerisSource):
    def __init__(self):
        super().__init__(EphemerisCache(TRACK_CACHE_DIR, fallback_directory=DEFAULT_CACHE_DIR))
        self.track = load_tracks()
        self.bodies = {b['body_id']: b for b in self.track['bodies']}
        self.times = {k: [s['jd_tdb'] for s in b['states']] for k, b in self.bodies.items()}
        self.interpolated = set()

    def states(self, body_id, epochs_jd_tdb):
        result = []
        for epoch in epochs_jd_tdb:
            epoch = canonical_epoch(epoch)
            cached = self.cache.get(body_id, epoch)
            if cached is not None:
                row, name = cached
                self.files_used.add(name)
            else:
                times = self.times[body_id]
                if not times[0] <= epoch <= times[-1]:
                    raise EphemerisUnavailable('outside validated NASA track; no extrapolation')
                body = self.bodies[body_id]
                if body['validation']['max_error_km'] >= 10:
                    raise EphemerisUnavailable('NASA track interpolation gate failed')
                i = min(max(bisect.bisect_right(times, epoch) - 1, 0), len(times) - 2)
                r, v = hermite_state(body['states'][i:i+2], epoch)
                row = StateRow(epoch, tuple(r), tuple(v))
                self.interpolated.add(body_id)
            result.append(row)
        return result

    def validation_states(self, body_id, epochs):
        # NEVER validate an interpolant against itself: raw NASA held-out rows only.
        return super().states(body_id, epochs)

    def sources(self):
        sources = super().sources()
        if self.interpolated:
            sources.append(dict(name='NASA/JPL Horizons interpolated planet_tracks.json',
                                url='https://github.com/Zain-Usmani10/Interstellar/blob/dev/app/data/planet_tracks.json',
                                sha256=self.track['sha256'],
                                retrieved_utc=max(p['retrieved_utc'] for p in self.track['provenance']),
                                api_signature='validated cubic Hermite track; semantic SHA-256'))
        return sources
