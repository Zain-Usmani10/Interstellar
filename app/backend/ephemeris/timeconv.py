"""Time conversion. Numbers inside the project are Julian dates in TDB; people see UTC labels.

UTC and TDB differ by about 69 seconds, so a UTC number is never relabelled as TDB: astropy converts.
"""
from __future__ import annotations

from astropy.time import Time


def utc_to_jd_tdb(utc_iso: str) -> float:
    """'2026-11-15T00:00:00Z' -> Julian date in the TDB time scale."""
    if not utc_iso.endswith("Z"):
        raise ValueError(f"UTC timestamps must end with Z, got {utc_iso!r}")
    t = Time(utc_iso[:-1], format="isot", scale="utc").tdb
    return float(t.jd1 + t.jd2)


def jd_tdb_to_utc(jd_tdb: float) -> str:
    """Julian date (TDB) -> UTC display label, rounded to the nearest second."""
    t = Time(jd_tdb, format="jd", scale="tdb").utc
    t.precision = 0
    return t.isot + "Z"
