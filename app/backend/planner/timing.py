"""Shared #45 timing boundary, with the issue-approved pre-merge fallback.

Once PR #51 lands this imports its constants and mapping automatically. Remove
the fallback after integration; it exists only so this PR remains testable on
the current dev branch without copying another owner's module.
"""
try:
    from ..timescale import TICK_HZ, epoch_jd_tdb, tick_map
except ModuleNotFoundError as error:
    if error.name != "app.backend.timescale":
        raise
    TICK_HZ = 100

    def tick_map():
        return {"departure_tick": 500, "arrival_tick": 6500, "end_tick": 6800}

    def epoch_jd_tdb(tick, departure_jd_tdb, tof_s, departure_tick=500, arrival_tick=6500):
        offset = tick - departure_tick
        seconds = offset / TICK_HZ if offset < 0 else offset * tof_s / (arrival_tick - departure_tick)
        return departure_jd_tdb + seconds / 86400

_ticks = tick_map()
DEPARTURE_TICK = _ticks["departure_tick"]
ARRIVAL_TICK = _ticks["arrival_tick"]
END_TICK = _ticks["end_tick"]
