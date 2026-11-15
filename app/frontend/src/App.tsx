import { useEffect, useMemo, useState } from "react";
import { getPlanetPositions } from "./api/coreClient";
import { toScenePlan, toSceneSnapshot } from "./api/mapToSceneViews";
import { BlackoutBanner } from "./components/BlackoutBanner";
import { BrandBlock } from "./components/BrandBlock";
import { DateTimeCorner } from "./components/DateTimeCorner";
import { DetailsTray } from "./components/DetailsTray";
import { LinkLight } from "./components/LinkLight";
import {
  PlanetFocusPanel,
  type FocusTab,
} from "./components/PlanetFocusPanel";
import { PlanetBar } from "./components/PlanetBar";
import { ReconciliationCard } from "./components/ReconciliationCard";
import { TripReadout } from "./components/TripReadout";
import { BciSlot } from "./integrations/bciSlot";
import { OrbitScene } from "./scene/OrbitScene";
import type { SceneBodyId, ScenePlanetPosition } from "./scene/types";
import {
  dockedAt,
  toSceneFleet,
  type FleetShuttle,
} from "./state/fleetMock";
import {
  PLANET_BODIES,
  type PlanetBodyId,
  planetName,
} from "./state/planetBodies";
import { unavailableMessage } from "./state/selectPresentationRoutes";
import { useCoreBridge } from "./state/useCoreBridge";

function bodyIdFromName(name: string | null): PlanetBodyId | null {
  if (!name) return null;
  return PLANET_BODIES.find((p) => p.name === name)?.bodyId ?? null;
}

/** Format T-minus from confirmed tick vs plan departure_tick (100 Hz). */
function formatTMinus(
  tick: number | null | undefined,
  departureTick: number | null | undefined,
): string | null {
  if (
    tick == null ||
    departureTick == null ||
    !Number.isFinite(tick) ||
    !Number.isFinite(departureTick) ||
    tick >= departureTick
  ) {
    return null;
  }
  const seconds = (departureTick - tick) / 100;
  const whole = Math.floor(seconds);
  const centi = Math.floor((seconds - whole) * 100);
  return `T−${String(whole).padStart(2, "0")}.${String(centi).padStart(2, "0")}`;
}

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

function isoUtcMinute(d: Date): string {
  return d.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export default function App() {
  const {
    linkMode,
    controllerSource,
    linkIndicator,
    dataMode,
    selectedId,
    planetChoiceEnabled,
    card,
    cardStatus,
    lastError,
    commandBusy,
    routePlans,
    selectedPlan,
    originBodyId,
    destinationBodyId,
    shuttleClass,
    selectedShuttleId,
    fleet,
    routeUnavailable,
    snapshot,
    faultHistory,
    gates,
    simFaultsEnabled,
    selectPlanById,
    setTrip,
    setSelectedShuttleId,
    prepareMission,
    resetMission,
    resetFleet,
    sendCommand,
    injectFault,
    selectPlanet,
    clearSelection,
  } = useCoreBridge();

  const [focusName, setFocusName] = useState<string | null>(null);
  const [overview, setOverview] = useState(true);
  const [focusTab, setFocusTab] = useState<FocusTab>("about");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [clockIso, setClockIso] = useState(() => isoUtcMinute(new Date()));
  const [planetPositions, setPlanetPositions] = useState<
    ScenePlanetPosition[]
  >([]);

  const scenePlan = useMemo(() => toScenePlan(selectedPlan), [selectedPlan]);
  const sceneSnapshot = useMemo(() => toSceneSnapshot(snapshot), [snapshot]);
  const sceneFleet = useMemo(() => toSceneFleet(fleet), [fleet]);
  const live = linkMode === "live";
  const originLabel = planetName(originBodyId);
  const destinationLabel = planetName(destinationBodyId);
  const routeLabel = `${originLabel} → ${destinationLabel}`;

  const dockedShuttles = dockedAt(fleet, originBodyId);
  const blackout = Boolean(snapshot?.link?.blackout);
  const tripLocked =
    commandBusy ||
    blackout ||
    Boolean(
      snapshot &&
        snapshot.state !== "IDLE" &&
        snapshot.state !== "UNKNOWN" &&
        snapshot.state !== "ABORTED" &&
        snapshot.state !== "COMPLETE",
    );

  const daysToArrival = blackout
    ? (snapshot?.estimate?.days_to_arrival ?? null)
    : (snapshot?.trip?.days_to_arrival ?? null);
  /** Selected route length before / without a live trip field — never a stale prior trip. */
  const planTripDays =
    selectedPlan?.tof_s != null && Number.isFinite(selectedPlan.tof_s)
      ? Math.round(selectedPlan.tof_s / 86400)
      : null;
  const tripDays =
    snapshot?.state === "RUNNING" ||
    snapshot?.state === "COMPLETE" ||
    blackout
      ? (snapshot?.trip?.trip_days ?? planTripDays)
      : planTripDays;
  const tMinus = formatTMinus(
    snapshot?.tick,
    selectedPlan?.ticks?.departure_tick,
  );

  const missionActive = Boolean(
    snapshot &&
      snapshot.state !== "IDLE" &&
      snapshot.state !== "UNKNOWN" &&
      snapshot.mission_id,
  );
  const missionDateUtc = missionActive
    ? blackout
      ? (snapshot?.estimate?.date_utc ?? snapshot?.date_utc ?? null)
      : (snapshot?.date_utc ?? null)
    : null;
  const dateEstimated = Boolean(
    missionActive && blackout && snapshot?.estimate?.date_utc,
  );

  /** Same date used for positions: mission clock, else live UTC (minute). */
  const positionsDateUtc = missionDateUtc ?? clockIso;

  const routeMsg = unavailableMessage(
    routeUnavailable,
    dockedShuttles.length > 0,
  );

  const reconciliation =
    snapshot?.reconciliation &&
    snapshot.state !== "IDLE" &&
    snapshot.state !== "UNKNOWN"
      ? {
          blackoutStartTick: snapshot.reconciliation.blackout_start_tick,
          blackoutEndTick: snapshot.reconciliation.blackout_end_tick,
          eventsDuringBlackout:
            snapshot.reconciliation.events_during_blackout.map((e) =>
              typeof e === "string" ? e : e.event,
            ),
          estimateMatched: snapshot.reconciliation.estimate_matched,
          differences: snapshot.reconciliation.differences,
        }
      : null;

  const inFlight = Boolean(
    snapshot &&
      (snapshot.state === "RUNNING" ||
        snapshot.state === "ARMED" ||
        snapshot.state === "LOADED"),
  );
  const followFlight = Boolean(
    snapshot &&
      snapshot.state !== "COMPLETE" &&
      snapshot.state !== "ABORTED" &&
      snapshot.state !== "IDLE" &&
      snapshot.state !== "UNKNOWN" &&
      ((snapshot.executed_mask & 1) !== 0 || snapshot.state === "RUNNING"),
  );
  const showPlanetPanel =
    !overview && !followFlight && focusName != null && focusName !== "Black Hole";
  const showMiniSystem = showPlanetPanel;

  useEffect(() => {
    if (missionDateUtc) return;
    const id = window.setInterval(
      () => setClockIso(isoUtcMinute(new Date())),
      30_000,
    );
    return () => window.clearInterval(id);
  }, [missionDateUtc]);

  useEffect(() => {
    if (linkMode !== "live" || !positionsDateUtc) {
      setPlanetPositions([]);
      return;
    }
    let cancelled = false;
    void getPlanetPositions({ date_utc: positionsDateUtc })
      .then((res) => {
        if (cancelled) return;
        setPlanetPositions(
          (res.planets ?? [])
            .filter((p) => (BODY_IDS as string[]).includes(p.body_id))
            .map((p) => ({
              body_id: p.body_id as SceneBodyId,
              r_km: p.r_km,
            })),
        );
      })
      .catch(() => {
        if (!cancelled) setPlanetPositions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [positionsDateUtc, linkMode]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        clearSelection("keyboard");
        goOverview();
        return;
      }
      if (planetChoiceEnabled) {
        if (event.key === "1") {
          visitPlanet("Earth");
          selectPlanet("planet.399", "keyboard");
        }
        if (event.key === "2") {
          visitPlanet("Mars");
          selectPlanet("planet.499", "keyboard");
        }
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === "o") {
        event.preventDefault();
        void resetMission();
      } else if (key === "p" && live && selectedPlan && !commandBusy && !blackout) {
        event.preventDefault();
        void prepareMission();
      } else if (key === "r" && live && gates.canArm && !commandBusy && !blackout) {
        event.preventDefault();
        void sendCommand("arm");
      } else if (key === "g" && live && gates.canStart && !commandBusy && !blackout) {
        event.preventDefault();
        void sendCommand("start");
      } else if (key === "x" && live && gates.canAbort && !commandBusy && !blackout) {
        event.preventDefault();
        void sendCommand("abort");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function goOverview() {
    setOverview(true);
    setFocusName(null);
    clearSelection("mouse");
  }

  function visitPlanet(name: string) {
    setOverview(false);
    setFocusName(name);
    setFocusTab("about");
    if (name === "Earth") {
      selectPlanet("planet.399");
    } else if (name === "Mars") {
      selectPlanet("planet.499");
    } else {
      // Clear a leftover Earth/Mars info card so About does not show Earth on Jupiter.
      clearSelection("mouse");
    }
    const bodyId = bodyIdFromName(name);
    if (!bodyId) return;
    const docked = dockedAt(fleet, bodyId);
    const first = docked[0] ?? null;
    setSelectedShuttleId(first?.id ?? null);
    setTrip({
      origin: bodyId,
      shuttleClass: first?.class ?? "standard",
      shuttleId: first?.id ?? null,
    });
  }

  function pickShuttle(shuttle: FleetShuttle) {
    setSelectedShuttleId(shuttle.id);
    setTrip({ shuttleClass: shuttle.class, shuttleId: shuttle.id });
  }

  function handleLaunch() {
    void sendCommand("start").then(() => {
      setOverview(false);
      setFocusName(null);
    });
  }

  return (
    <div className="app-shell sci-fi">
      <div className="scene-layer">
        <OrbitScene
          selectedId={selectedId}
          selectionEnabled={planetChoiceEnabled && !blackout}
          onSelect={(id) => {
            const name = id === "planet.399" ? "Earth" : "Mars";
            visitPlanet(name);
            if (planetChoiceEnabled && !blackout) selectPlanet(id);
          }}
          onFocusName={(name) => visitPlanet(name)}
          focusName={overview ? null : focusName}
          overview={overview && !followFlight}
          plan={scenePlan}
          snapshot={sceneSnapshot}
          fleet={sceneFleet}
          mockFleet={false}
          planetPositions={planetPositions}
          dateUtc={positionsDateUtc}
          fetchPositions={false}
        />
      </div>

      <BrandBlock />

      <DateTimeCorner
        missionDateUtc={missionDateUtc}
        estimated={dateEstimated}
      />

      <LinkLight
        indicator={linkIndicator}
        controllerSource={controllerSource}
      />

      {showMiniSystem ? (
        <button
          type="button"
          className="mini-system glass"
          aria-label="Overview — whole solar system"
          title="Overview"
          onClick={goOverview}
        >
          <OrbitScene
            selectedId={null}
            selectionEnabled={false}
            onSelect={() => undefined}
            focusName={null}
            overview
            compact
            plan={scenePlan}
            snapshot={sceneSnapshot}
            fleet={sceneFleet}
            mockFleet={false}
            planetPositions={planetPositions}
            dateUtc={positionsDateUtc}
            fetchPositions={false}
          />
        </button>
      ) : null}

      <BlackoutBanner visible={blackout} />

      {showPlanetPanel ? (
        <PlanetFocusPanel
          planetNameLabel={focusName!}
          tab={focusTab}
          onTab={(tab) => {
            setFocusTab(tab);
            const bodyId = bodyIdFromName(focusName);
            if (!bodyId) return;
            if (tab === "from-to") {
              const dest =
                destinationBodyId !== bodyId
                  ? destinationBodyId
                  : originBodyId !== bodyId
                    ? originBodyId
                    : ((bodyId === "399" ? "499" : "399") as typeof bodyId);
              setTrip({ origin: bodyId, destination: dest });
            } else if (tab === "to-from") {
              const from =
                originBodyId !== bodyId
                  ? originBodyId
                  : destinationBodyId !== bodyId
                    ? destinationBodyId
                    : ((bodyId === "399" ? "499" : "399") as typeof bodyId);
              setTrip({ origin: from, destination: bodyId });
            }
          }}
          card={card && focusName && card.name === focusName ? card : null}
          cardStatus={
            card && focusName && card.name === focusName ? cardStatus : "idle"
          }
          originBodyId={originBodyId}
          destinationBodyId={destinationBodyId}
          dockedShuttles={dockedShuttles}
          shuttleId={selectedShuttleId}
          shuttleClass={shuttleClass}
          leastFuel={routePlans.least_fuel}
          earliestArrival={routePlans.earliest_arrival}
          selectedPlanId={selectedPlan?.plan_id ?? null}
          unavailableMessage={routeMsg}
          tripLocked={tripLocked}
          onShuttle={pickShuttle}
          onDestination={(id) => {
            setTrip({ destination: id });
          }}
          onOrigin={(id) => {
            const docked = dockedAt(fleet, id);
            const first = docked[0] ?? null;
            setSelectedShuttleId(first?.id ?? null);
            setTrip({
              origin: id,
              destination: bodyIdFromName(focusName) ?? destinationBodyId,
              shuttleClass: first?.class ?? "standard",
              shuttleId: first?.id ?? null,
            });
          }}
          onSelectPlan={(id) => void selectPlanById(id)}
          daysToArrival={daysToArrival}
          tripDays={tripDays}
          tMinusLabel={tMinus}
          blackout={blackout}
          live={live}
          commandBusy={commandBusy}
          hasPlan={Boolean(selectedPlan)}
          snapshot={snapshot}
          gates={gates}
          simFaultsEnabled={simFaultsEnabled}
          routeLabel={routeLabel}
          onPrepare={() => void prepareMission()}
          onArm={() => void sendCommand("arm")}
          onLaunch={handleLaunch}
          onAbort={() => {
            void sendCommand("abort");
            clearSelection("mouse");
          }}
          onReset={() => void resetMission()}
          onBlackoutStart={() => void sendCommand("blackout_start")}
          onBlackoutEnd={() => void sendCommand("blackout_end")}
          onResetFleet={() => void resetFleet()}
          onFaultSingle={() => void injectFault("single")}
          onFaultDivergence={() => void injectFault("divergence")}
        />
      ) : null}

      {inFlight || followFlight ? (
        <div className="flight-hud glass" aria-label="Flight readout">
          <TripReadout
            daysToArrival={daysToArrival}
            tripDays={tripDays}
            tMinusLabel={tMinus}
            estimated={blackout}
          />
          <button
            type="button"
            className="abort-btn"
            disabled={commandBusy || blackout || !(live && gates.canAbort)}
            onClick={() => {
              void sendCommand("abort");
              clearSelection("mouse");
            }}
          >
            Abort
          </button>
          {blackout ? (
            <button
              type="button"
              className="blackout-btn end"
              disabled={commandBusy}
              onClick={() => void sendCommand("blackout_end")}
            >
              End blackout
            </button>
          ) : null}
          <button
            type="button"
            disabled={commandBusy || (blackout && snapshot?.state === "RUNNING")}
            onClick={() => void resetMission()}
          >
            Start over
          </button>
        </div>
      ) : null}

      <ReconciliationCard data={reconciliation} />

      <DetailsTray
        open={detailsOpen}
        onToggle={() => setDetailsOpen((v) => !v)}
        snapshot={snapshot}
        lastError={lastError}
        destinationName={destinationLabel}
        plan={selectedPlan}
        faultHistory={faultHistory}
        dataMode={dataMode}
        live={live}
        busy={commandBusy}
        blackout={blackout}
        simFaultsEnabled={simFaultsEnabled}
        onBlackoutStart={() => void sendCommand("blackout_start")}
        onBlackoutEnd={() => void sendCommand("blackout_end")}
        onResetFleet={() => void resetFleet()}
        onFaultSingle={() => void injectFault("single")}
        onFaultDivergence={() => void injectFault("divergence")}
      />

      <div className="bci-float" aria-label="Optional brain widget">
        <BciSlot />
      </div>

      <PlanetBar
        focusName={focusName}
        overview={overview && !followFlight}
        selectedId={selectedId}
        selectionEnabled={planetChoiceEnabled && !blackout}
        onOverview={goOverview}
        onVisit={visitPlanet}
        onSelectEarthMars={selectPlanet}
      />
    </div>
  );
}
