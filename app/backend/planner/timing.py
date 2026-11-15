"""Planner timing imports the single shared presentation mapping."""
from ..timescale import TICK_HZ, epoch_jd_tdb, tick_map

_ticks = tick_map()
DEPARTURE_TICK = _ticks['departure_tick']
ARRIVAL_TICK = _ticks['arrival_tick']
END_TICK = _ticks['end_tick']
