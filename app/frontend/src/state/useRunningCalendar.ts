import { useCallback, useEffect, useRef, useState } from "react";
import { getPlanetPositions } from "../api/coreClient";
import { jdTdbToUtcIso, utcIsoToJdTdb } from "../api/jd";
import { getPlanetTrack, type PlanetTrackResponse } from "../api/planetTrack";
import { interpolateTrack } from "../api/planetTrackMath";
import type { SceneBodyId, ScenePlanetPosition } from "../scene/types";

const BODY_IDS: SceneBodyId[] = [
  "199",
  "299",
  "399",
  "499",
  "599",
  "699",
  "799",
  "899",
];

const DEFAULT_DAYS_PER_SECOND = 7;
const BLOCK_DAYS = 400;
const STEP_DAYS = 1;
const PREFETCH_LEAD_DAYS = 80;

type Args = {
  live: boolean;
  /** Overview with no planet focus — calendar may run. */
  overviewRunning: boolean;
  /** Mission snapshot date drives the clock when set. */
  missionDateUtc: string | null;
};

function clampJd(jd: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, jd));
}

function toScenePositions(
  samples: Array<{ body_id: string; r_km: [number, number, number] }>,
): ScenePlanetPosition[] {
  return samples
    .filter((p) => (BODY_IDS as string[]).includes(p.body_id))
    .map((p) => ({
      body_id: p.body_id as SceneBodyId,
      r_km: p.r_km,
    }));
}

/**
 * Free-running overview calendar (§19.3) backed by GET /planets/track.
 * Mission dates take over when a snapshot date is present; never extrapolates past the track.
 */
export function useRunningCalendar({
  live,
  overviewRunning,
  missionDateUtc,
}: Args) {
  const [daysPerSecond, setDaysPerSecond] = useState(DEFAULT_DAYS_PER_SECOND);
  const [calendarJd, setCalendarJd] = useState<number | null>(null);
  const [trackLo, setTrackLo] = useState<number | null>(null);
  const [trackHi, setTrackHi] = useState<number | null>(null);
  const [atTrackEnd, setAtTrackEnd] = useState(false);
  const [positions, setPositions] = useState<ScenePlanetPosition[]>([]);
  const [ready, setReady] = useState(false);
  const [blockTick, setBlockTick] = useState(0);

  const blockRef = useRef<PlanetTrackResponse | null>(null);
  const fetchingRef = useRef(false);
  const daysPerSecondRef = useRef(daysPerSecond);
  daysPerSecondRef.current = daysPerSecond;
  const calendarJdRef = useRef(calendarJd);
  calendarJdRef.current = calendarJd;
  const trackHiRef = useRef(trackHi);
  trackHiRef.current = trackHi;
  const trackLoRef = useRef(trackLo);
  trackLoRef.current = trackLo;

  const ensureBlock = useCallback(async (jd: number, lo: number, hi: number) => {
    const block = blockRef.current;
    if (block?.epochs_jd_tdb.length) {
      const first = block.epochs_jd_tdb[0];
      const last = block.epochs_jd_tdb[block.epochs_jd_tdb.length - 1];
      if (jd >= first && jd <= last) {
        if (jd <= last - PREFETCH_LEAD_DAYS || last >= hi) return block;
      }
    }
    if (fetchingRef.current) return blockRef.current;
    fetchingRef.current = true;
    try {
      const start = clampJd(Math.floor(jd), lo, hi);
      const end = clampJd(start + BLOCK_DAYS, lo, hi);
      try {
        const next = await getPlanetTrack({
          start_jd_tdb: start,
          end_jd_tdb: Math.max(start, end),
          step_days: STEP_DAYS,
        });
        blockRef.current = next;
        setBlockTick((n) => n + 1);
        return next;
      } catch {
        // Older backends without /track: one positions sample, still no extrapolation.
        const res = await getPlanetPositions({ jd_tdb: clampJd(jd, lo, hi) });
        const synthetic: PlanetTrackResponse = {
          start_jd_tdb: lo,
          end_jd_tdb: hi,
          step_days: STEP_DAYS,
          epochs_jd_tdb: [res.epoch_jd_tdb],
          planets: (res.planets ?? []).map((p) => ({
            body_id: p.body_id,
            r_km: [p.r_km],
          })),
        };
        blockRef.current = synthetic;
        setBlockTick((n) => n + 1);
        return synthetic;
      }
    } catch {
      return blockRef.current;
    } finally {
      fetchingRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!live) {
      setReady(false);
      setPositions([]);
      blockRef.current = null;
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const res = await getPlanetPositions({ date_utc: "2026-11-17T00:00:00Z" });
        if (cancelled) return;
        const lo = res.start_jd_tdb;
        const hi = res.end_jd_tdb;
        if (lo == null || hi == null) return;
        setTrackLo(lo);
        setTrackHi(hi);
        const seed =
          (missionDateUtc ? utcIsoToJdTdb(missionDateUtc) : null) ??
          res.epoch_jd_tdb;
        const jd = clampJd(seed, lo, hi);
        setCalendarJd(jd);
        setAtTrackEnd(jd >= hi);
        await ensureBlock(jd, lo, hi);
        if (!cancelled) setReady(true);
      } catch {
        if (!cancelled) setReady(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, ensureBlock]);

  useEffect(() => {
    if (!missionDateUtc || trackLo == null || trackHi == null) return;
    const jd = utcIsoToJdTdb(missionDateUtc);
    if (jd == null) return;
    const clamped = clampJd(jd, trackLo, trackHi);
    setCalendarJd(clamped);
    setAtTrackEnd(clamped >= trackHi);
  }, [missionDateUtc, trackLo, trackHi]);

  useEffect(() => {
    if (!ready || !live || !overviewRunning || missionDateUtc) return;
    let raf = 0;
    let last = performance.now();
    let publishAt = 0;
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const lo = trackLoRef.current;
      const hi = trackHiRef.current;
      const cur = calendarJdRef.current;
      if (lo == null || hi == null || cur == null) {
        raf = requestAnimationFrame(tick);
        return;
      }
      if (cur >= hi) {
        setAtTrackEnd(true);
        raf = requestAnimationFrame(tick);
        return;
      }
      const next = clampJd(cur + daysPerSecondRef.current * dt, lo, hi);
      calendarJdRef.current = next;
      if (now >= publishAt) {
        publishAt = now + 50; // ~20 Hz React updates
        setCalendarJd(next);
        if (next >= hi) setAtTrackEnd(true);
        else void ensureBlock(next, lo, hi);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [ready, live, overviewRunning, missionDateUtc, ensureBlock]);

  useEffect(() => {
    if (calendarJd == null || trackLo == null || trackHi == null) return;
    const apply = (block: PlanetTrackResponse | null) => {
      if (!block) return;
      const samples = interpolateTrack(
        block.epochs_jd_tdb,
        block.planets,
        calendarJd,
      );
      if (samples) setPositions(toScenePositions(samples));
    };
    const current = blockRef.current;
    const first = current?.epochs_jd_tdb[0];
    const last = current?.epochs_jd_tdb[current.epochs_jd_tdb.length - 1];
    if (
      current &&
      first != null &&
      last != null &&
      calendarJd >= first &&
      calendarJd <= last
    ) {
      apply(current);
      return;
    }
    void ensureBlock(calendarJd, trackLo, trackHi).then(apply);
  }, [calendarJd, trackLo, trackHi, ensureBlock, blockTick]);

  const jumpToUtc = useCallback(
    (iso: string | null | undefined) => {
      if (!iso || trackLo == null || trackHi == null) return;
      const jd = utcIsoToJdTdb(iso);
      if (jd == null) return;
      const clamped = clampJd(jd, trackLo, trackHi);
      setCalendarJd(clamped);
      setAtTrackEnd(clamped >= trackHi);
      void ensureBlock(clamped, trackLo, trackHi);
    },
    [trackLo, trackHi, ensureBlock],
  );

  const calendarDateUtc =
    calendarJd != null ? jdTdbToUtcIso(calendarJd) : null;

  return {
    daysPerSecond,
    setDaysPerSecond,
    calendarJd,
    calendarDateUtc,
    positions,
    atTrackEnd,
    trackReady: ready,
    jumpToUtc,
  };
}
