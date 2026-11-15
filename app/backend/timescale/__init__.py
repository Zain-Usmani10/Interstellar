"""Shared presentation timing; pure arithmetic, never a mission clock."""

import math

TICK_HZ = 100
COUNTDOWN_TICKS = 500
FLIGHT_TICKS = 3000
TAIL_TICKS = 300


def _integer(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _bounds(departure_tick: int, arrival_tick: int) -> None:
    _integer(departure_tick, "departure_tick", 1)
    _integer(arrival_tick, "arrival_tick", departure_tick + 1)


def tick_map() -> dict[str, int]:
    return {"departure_tick": COUNTDOWN_TICKS,
            "arrival_tick": COUNTDOWN_TICKS + FLIGHT_TICKS,
            "end_tick": COUNTDOWN_TICKS + FLIGHT_TICKS + TAIL_TICKS}


def trip_days(tof_s: float) -> int:
    """Section 18.2: nearest whole day, half up, clamped to display range."""
    if not math.isfinite(tof_s) or tof_s <= 0:
        raise ValueError("tof_s must be finite and positive")
    return max(1, min(9999, math.floor(tof_s / 86400 + 0.5)))


def _days(days: int) -> None:
    _integer(days, "trip_days", 1)
    if days > 9999:
        raise ValueError("trip_days must be <= 9999")


def days_to_arrival(tick: int, departure_tick: int, arrival_tick: int,
                    trip_days: int) -> int:
    """Section 18.4 integer formula, independent of controller state."""
    _integer(tick, "tick")
    _bounds(departure_tick, arrival_tick)
    _days(trip_days)
    elapsed = min(max(tick - departure_tick, 0), arrival_tick - departure_tick)
    return trip_days - elapsed * trip_days // (arrival_tick - departure_tick)


def sim_days_per_second(trip_days: int) -> float:
    _days(trip_days)
    return trip_days / (FLIGHT_TICKS / TICK_HZ)


def epoch_jd_tdb(tick: int, departure_jd_tdb: float, tof_s: float,
                 departure_tick: int = COUNTDOWN_TICKS,
                 arrival_tick: int = COUNTDOWN_TICKS + FLIGHT_TICKS) -> float:
    """Exact physical flight duration, with section 19's real-time countdown.

    Flight and uncaptured tail use section 7's tof_s / flight_ticks mapping.
    Before departure, section 19 supersedes section 7: one tick is 0.01 s.
    The caller supplies confirmed/estimated ticks and stops at its final tick.
    Rounded display days never alter the physical NASA arrival epoch.
    """
    _integer(tick, "tick")
    _bounds(departure_tick, arrival_tick)
    if not math.isfinite(departure_jd_tdb):
        raise ValueError("departure_jd_tdb must be finite")
    trip_days(tof_s)
    offset = tick - departure_tick
    seconds = offset / TICK_HZ if offset < 0 else offset * tof_s / (arrival_tick - departure_tick)
    return departure_jd_tdb + seconds / 86400
