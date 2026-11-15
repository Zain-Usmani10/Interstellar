import { useCallback, useEffect, useRef, useState } from "react";
import {
  connectEvents,
  createMission,
  getHealth,
  getMission,
  getPlan,
  getPlanetInfo,
  getSession,
  injectSimFault,
  listPlans,
  postIntent,
  postMissionCommand,
  registerInputSession,
} from "../api/coreClient";
import { formatApiError } from "../api/errors";
import { cardFromApi, cardFromMock, type PlanetCardModel } from "../api/mapPlanetInfo";
import type {
  FaultHistoryEntry,
  MissionCommand,
  MissionPlan,
  MissionSnapshot,
  PlanSummary,
  SimFaultKind,
} from "../api/missionTypes";
import type { BodyId, PlanetTargetId, TargetId } from "../api/types";
import { missionActionGates } from "./missionGates";
import { pickRoutePair } from "./pickRoutePair";

export type LinkMode = "connecting" | "live" | "offline_mock";

type SessionBits = {
  input_session_id: string;
  token: string;
  context_id: string;
  revision: number;
  source: "mouse";
};

function bodyToTarget(bodyId: BodyId | null): PlanetTargetId | null {
  return bodyId ? `planet.${bodyId}` : null;
}

function pushFaultHistory(
  prev: FaultHistoryEntry[],
  next: MissionSnapshot,
  prevSnap: MissionSnapshot | null,
): FaultHistoryEntry[] {
  const entries: FaultHistoryEntry[] = [];
  const prevFaults = prevSnap?.faults;
  const faults = next.faults;
  if (faults) {
    const maskedDelta =
      faults.masked_fault_count - (prevFaults?.masked_fault_count ?? 0);
    if (maskedDelta > 0) {
      entries.push({
        id: `${next.server_seq}-masked`,
        at_seq: next.server_seq,
        kind: "masked_fault",
        detail: `masked_fault_count=${faults.masked_fault_count}`,
      });
    }
    const nomajDelta =
      faults.no_majority_count - (prevFaults?.no_majority_count ?? 0);
    if (nomajDelta > 0) {
      entries.push({
        id: `${next.server_seq}-nomaj`,
        at_seq: next.server_seq,
        kind: "no_majority",
        detail: `no_majority_count=${faults.no_majority_count}`,
      });
    }
  }
  if (next.state === "SAFE" && prevSnap?.state !== "SAFE") {
    entries.push({
      id: `${next.server_seq}-safe`,
      at_seq: next.server_seq,
      kind: "SAFE",
      detail: next.safe_reason ?? "SAFE",
    });
  }
  if (next.state === "ABORTED" && prevSnap?.state !== "ABORTED") {
    entries.push({
      id: `${next.server_seq}-abort`,
      at_seq: next.server_seq,
      kind: "ABORTED",
      detail: next.failure?.message ?? "ABORTED",
    });
  }
  if (
    next.outcome === "uncaptured" &&
    prevSnap?.outcome !== "uncaptured"
  ) {
    entries.push({
      id: `${next.server_seq}-uncaptured`,
      at_seq: next.server_seq,
      kind: "uncaptured",
      detail: "outcome=uncaptured",
    });
  }
  if (!entries.length) return prev;
  const merged = [...entries, ...prev];
  const seen = new Set<string>();
  return merged.filter((e) => {
    if (seen.has(e.id)) return false;
    seen.add(e.id);
    return true;
  }).slice(0, 40);
}

export function useCoreBridge() {
  const [linkMode, setLinkMode] = useState<LinkMode>("connecting");
  const [controllerLabel, setControllerLabel] = useState("unknown");
  const [controllerSource, setControllerSource] = useState<
    "fpga" | "simulator" | "unknown"
  >("unknown");
  const [dataMode, setDataMode] = useState("unknown");
  const [inputSourceLabel, setInputSourceLabel] = useState("mouse");
  const [selectedId, setSelectedId] = useState<PlanetTargetId | null>(null);
  const [screen, setScreen] = useState<"planet_choice" | "planet_info" | string>(
    "planet_choice",
  );
  const [card, setCard] = useState<PlanetCardModel | null>(null);
  const [cardStatus, setCardStatus] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [lastError, setLastError] = useState<string | null>(null);
  const [commandBusy, setCommandBusy] = useState(false);
  const [planSummaries, setPlanSummaries] = useState<PlanSummary[]>([]);
  const [routePlans, setRoutePlans] = useState<{
    least_fuel: MissionPlan | null;
    earliest_arrival: MissionPlan | null;
  }>({ least_fuel: null, earliest_arrival: null });
  const [selectedPlan, setSelectedPlan] = useState<MissionPlan | null>(null);
  const [snapshot, setSnapshot] = useState<MissionSnapshot | null>(null);
  const [faultHistory, setFaultHistory] = useState<FaultHistoryEntry[]>([]);

  const sessionRef = useRef<SessionBits | null>(null);
  const operatorTokenRef = useRef<string | null>(null);
  const serverSeqRef = useRef(0);
  const snapshotSeqRef = useRef(-1);
  const snapshotRef = useRef<MissionSnapshot | null>(null);
  const missionIdRef = useRef<string | null>(null);
  const contextRevisionRef = useRef(0);
  const fetchGenRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);
  const acceptSnapshotsRef = useRef(false);
  const bootReadyRef = useRef(false);

  const applySnapshot = useCallback((next: MissionSnapshot) => {
    if (next.server_seq <= snapshotSeqRef.current) return;
    snapshotSeqRef.current = next.server_seq;
    setFaultHistory((prev) =>
      pushFaultHistory(prev, next, snapshotRef.current),
    );
    snapshotRef.current = next;
    missionIdRef.current = next.mission_id;
    setSnapshot(next);
    if (next.controller_label) setControllerLabel(next.controller_label);
    if (next.controller_source) setControllerSource(next.controller_source);
  }, []);

  const loadPlans = useCallback(async () => {
    const { plans } = await listPlans();
    setPlanSummaries(plans);
    const pair = pickRoutePair(plans);

    const [least, fast] = await Promise.all([
      pair.least_fuel ? getPlan(pair.least_fuel.plan_id) : Promise.resolve(null),
      pair.earliest_arrival
        ? getPlan(pair.earliest_arrival.plan_id)
        : Promise.resolve(null),
    ]);
    setRoutePlans({ least_fuel: least, earliest_arrival: fast });
    setSelectedPlan((current) => {
      if (current) {
        const still =
          (least && least.plan_id === current.plan_id && least) ||
          (fast && fast.plan_id === current.plan_id && fast);
        if (still) return still;
      }
      return least ?? fast ?? null;
    });
  }, []);

  const applySelection = useCallback(
    (
      bodyId: BodyId | null,
      contextRevision: number,
      offline: boolean,
      nextScreen?: string,
    ) => {
      contextRevisionRef.current = contextRevision;
      const target = bodyToTarget(bodyId);
      setSelectedId(target);
      setScreen(nextScreen ?? (bodyId ? "planet_info" : "planet_choice"));

      if (!bodyId || !target) {
        fetchGenRef.current += 1;
        setCard(null);
        setCardStatus("idle");
        return;
      }

      if (offline) {
        setCard(cardFromMock(target));
        setCardStatus("ready");
        return;
      }

      const gen = ++fetchGenRef.current;
      const expectedBody = bodyId;
      setCardStatus("loading");
      setLastError(null);

      getPlanetInfo(bodyId)
        .then((info) => {
          if (
            gen !== fetchGenRef.current ||
            expectedBody !== bodyId ||
            expectedRevisionMismatch(contextRevision)
          ) {
            return;
          }
          setCard(cardFromApi(info));
          setCardStatus("ready");
        })
        .catch((err: unknown) => {
          if (gen !== fetchGenRef.current) return;
          setCardStatus("error");
          setLastError(formatApiError(err, "planet_info_failed"));
          setCard(cardFromMock(target));
        });

      function expectedRevisionMismatch(expected: number) {
        return expected !== contextRevisionRef.current;
      }
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let intentionalClose = false;

    async function refreshMissionSnapshot() {
      const id = missionIdRef.current;
      if (!id) {
        acceptSnapshotsRef.current = true;
        return;
      }
      try {
        const snap = await getMission(id);
        if (!cancelled) applySnapshot(snap);
      } catch {
        // Mission may have been cleared; keep waiting for WS.
      } finally {
        if (!cancelled) acceptSnapshotsRef.current = true;
      }
    }

    function handleMessage(msg: {
      type: string;
      server_seq?: number;
      data: unknown;
    }) {
      if (cancelled) return;
      if (
        typeof msg.server_seq === "number" &&
        msg.server_seq <= serverSeqRef.current &&
        msg.type !== "hello"
      ) {
        return;
      }
      if (typeof msg.server_seq === "number") {
        serverSeqRef.current = Math.max(serverSeqRef.current, msg.server_seq);
      }

      if (msg.type === "hello") {
        const data = msg.data as {
          controller_label?: string;
          data_mode?: string;
          selection?: {
            selected_body_id: BodyId | null;
            context_id?: string;
            context_revision: number;
            screen?: string;
          };
        };
        if (data.controller_label) setControllerLabel(data.controller_label);
        if (data.data_mode) setDataMode(data.data_mode);
        if (data.selection && sessionRef.current) {
          const sel = data.selection;
          if (sel.context_id) sessionRef.current.context_id = sel.context_id;
          sessionRef.current.revision = sel.context_revision;
          applySelection(
            sel.selected_body_id,
            sel.context_revision,
            false,
            sel.screen,
          );
        }
        return;
      }

      if (msg.type === "selection") {
        const data = msg.data as {
          selected_body_id: BodyId | null;
          context_revision: number;
          screen?: string;
          source?: string;
        };
        if (data.source) setInputSourceLabel(data.source);
        applySelection(
          data.selected_body_id,
          data.context_revision,
          false,
          data.screen,
        );
        if (sessionRef.current) {
          sessionRef.current.revision = data.context_revision;
        }
        return;
      }

      if (msg.type === "mission_snapshot") {
        if (!acceptSnapshotsRef.current) return;
        applySnapshot(msg.data as MissionSnapshot);
        return;
      }

      if (msg.type === "transport") {
        const data = msg.data as { transport_state?: string; detail?: string };
        if (data.detail) setLastError(data.detail);
      }
    }

    function openSocket() {
      if (cancelled || !bootReadyRef.current) return;
      acceptSnapshotsRef.current = false;
      const socket = connectEvents({
        onOpen: () => {
          if (cancelled) return;
          setLinkMode("live");
          void refreshMissionSnapshot();
        },
        onClose: () => {
          if (cancelled || intentionalClose) return;
          setLinkMode("offline_mock");
          acceptSnapshotsRef.current = false;
          reconnectTimer = setTimeout(openSocket, 1500);
        },
        onError: () => {
          if (!cancelled) setLinkMode("offline_mock");
        },
        onMessage: handleMessage,
      });
      socketRef.current = socket;
    }

    async function boot() {
      try {
        const health = await getHealth();
        if (cancelled) return;
        const session = await getSession();
        operatorTokenRef.current = session.operator_token;
        const registered = await registerInputSession("mouse");
        if (cancelled) return;

        sessionRef.current = {
          input_session_id: registered.input_session_id,
          token: registered.token,
          context_id: registered.context.context_id,
          revision: registered.context.revision,
          source: "mouse",
        };
        contextRevisionRef.current = registered.context.revision;
        setDataMode(health.data_mode ?? "unknown");
        if (health.transport?.controller_label) {
          setControllerLabel(health.transport.controller_label);
        }
        if (health.transport?.mode === "fpga" || health.transport?.mode === "simulator") {
          setControllerSource(health.transport.mode);
        }
        setLinkMode("live");
        bootReadyRef.current = true;

        try {
          await loadPlans();
        } catch {
          if (!cancelled) setLastError("plans_unavailable");
        }
        if (cancelled) return;
        openSocket();
      } catch {
        if (cancelled) return;
        setLinkMode("offline_mock");
        setControllerLabel("OFFLINE — local mock");
        setDataMode("mock");
        setLastError("backend_unreachable");
        setSelectedPlan(null);
        setSnapshot(null);
      }
    }

    void boot();
    return () => {
      cancelled = true;
      intentionalClose = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [applySelection, applySnapshot, loadPlans]);

  const proposeTarget = useCallback(
    async (targetId: TargetId, source: "mouse" | "keyboard") => {
      const offline = linkMode !== "live" || !sessionRef.current;

      if (offline) {
        if (targetId === "navigation.back") {
          applySelection(null, contextRevisionRef.current + 1, true, "planet_choice");
          return;
        }
        if (targetId === "planet.399" || targetId === "planet.499") {
          applySelection(
            targetId.slice("planet.".length) as BodyId,
            contextRevisionRef.current + 1,
            true,
            "planet_info",
          );
        }
        return;
      }

      const session = sessionRef.current!;
      try {
        setInputSourceLabel(source);
        const result = await postIntent({
          token: session.token,
          input_session_id: session.input_session_id,
          context_id: session.context_id,
          context_revision: session.revision,
          target_id: targetId,
          source,
        });
        session.revision = result.new_context_revision;
        if (!result.accepted) {
          setLastError(`intent_${result.reason}`);
        }
      } catch (err) {
        setLastError(formatApiError(err, "intent_failed"));
      }
    },
    [applySelection, linkMode],
  );

  const selectPlanet = useCallback(
    (targetId: PlanetTargetId, source: "mouse" | "keyboard" = "mouse") => {
      if (screen === "planet_info") {
        setLastError("select_unavailable_on_info_screen");
        return;
      }
      void proposeTarget(targetId, source);
    },
    [proposeTarget, screen],
  );

  const clearSelection = useCallback(
    (source: "mouse" | "keyboard" = "mouse") => {
      void proposeTarget("navigation.back", source);
    },
    [proposeTarget],
  );

  const selectPlanById = useCallback(async (planId: string) => {
    try {
      const fromRoutes =
        (routePlans.least_fuel?.plan_id === planId && routePlans.least_fuel) ||
        (routePlans.earliest_arrival?.plan_id === planId &&
          routePlans.earliest_arrival);
      const full = fromRoutes || (await getPlan(planId));
      setSelectedPlan(full);
      setLastError(null);
    } catch (err) {
      setLastError(formatApiError(err, "plan_fetch_failed"));
    }
  }, [routePlans]);

  const createMissionFromSelected = useCallback(async () => {
    const token = operatorTokenRef.current;
    const plan = selectedPlan;
    if (!token || !plan || linkMode !== "live") {
      setLastError("operator_or_plan_unavailable");
      return;
    }
    setCommandBusy(true);
    setLastError(null);
    try {
      const snap = await createMission(token, plan.plan_id);
      applySnapshot(snap);
    } catch (err) {
      setLastError(formatApiError(err, "create_mission_failed"));
    } finally {
      setCommandBusy(false);
    }
  }, [applySnapshot, linkMode, selectedPlan]);

  const sendCommand = useCallback(
    async (command: MissionCommand) => {
      const token = operatorTokenRef.current;
      const missionId = missionIdRef.current;
      if (!token || !missionId || linkMode !== "live") {
        setLastError("mission_unavailable");
        return;
      }
      setCommandBusy(true);
      setLastError(null);
      try {
        const result = await postMissionCommand(token, missionId, command);
        if (result.snapshot) applySnapshot(result.snapshot);
        if (!result.applied) {
          setLastError(`${command}: ${result.detail || "not_applied"}`);
        }
        return result;
      } catch (err) {
        setLastError(formatApiError(err, `${command}_failed`));
        return null;
      } finally {
        setCommandBusy(false);
      }
    },
    [applySnapshot, linkMode],
  );

  /** Guided "Prepare": create mission if needed, then upload (LOAD+COMMIT). */
  const prepareMission = useCallback(async () => {
    const token = operatorTokenRef.current;
    const plan = selectedPlan;
    if (!token || !plan || linkMode !== "live") {
      setLastError("operator_or_plan_unavailable");
      return;
    }
    setCommandBusy(true);
    setLastError(null);
    try {
      let missionId = missionIdRef.current;
      const state = snapshotRef.current?.state;
      if (!missionId || state === "IDLE" || state === "UNKNOWN" || !state) {
        const snap = await createMission(token, plan.plan_id);
        applySnapshot(snap);
        missionId = snap.mission_id;
      }
      if (!missionId) return;
      const result = await postMissionCommand(token, missionId, "upload");
      if (result.snapshot) applySnapshot(result.snapshot);
      if (!result.applied) {
        setLastError(`upload: ${result.detail || "not_applied"}`);
      }
    } catch (err) {
      setLastError(formatApiError(err, "prepare_failed"));
    } finally {
      setCommandBusy(false);
    }
  }, [applySnapshot, linkMode, selectedPlan]);

  const injectFault = useCallback(
    async (kind: SimFaultKind) => {
      const token = operatorTokenRef.current;
      if (!token || linkMode !== "live") {
        setLastError("operator_unavailable");
        return;
      }
      if (controllerSource !== "simulator") {
        setLastError("sim_faults_fpga_only_on_board");
        return;
      }
      setCommandBusy(true);
      setLastError(null);
      try {
        await injectSimFault(token, kind);
      } catch (err) {
        setLastError(formatApiError(err, "sim_fault_failed"));
      } finally {
        setCommandBusy(false);
      }
    },
    [controllerSource, linkMode],
  );

  /** Clear controller mission so Prepare works again after abort/complete. */
  const resetMission = useCallback(async () => {
    const token = operatorTokenRef.current;
    const missionId = missionIdRef.current;
    setLastError(null);
    let cleared = false;
    if (token && missionId && linkMode === "live") {
      setCommandBusy(true);
      try {
        const result = await postMissionCommand(token, missionId, "clear");
        if (result.snapshot) {
          applySnapshot(result.snapshot);
          cleared =
            result.snapshot.state === "IDLE" ||
            result.snapshot.state === "UNKNOWN";
        }
        if (!result.applied && !cleared) {
          setLastError(`clear: ${result.detail || "not_applied"}`);
        }
      } catch (err) {
        setLastError(formatApiError(err, "clear_failed"));
      } finally {
        setCommandBusy(false);
      }
    }
    if (!cleared) {
      // Drop local mission without resetting seq — otherwise WS re-applies ABORTED.
      missionIdRef.current = null;
      snapshotRef.current = null;
      setSnapshot(null);
    }
    void proposeTarget("navigation.back", "mouse");
  }, [applySnapshot, linkMode, proposeTarget]);

  const gates = missionActionGates(snapshot);
  const simFaultsEnabled =
    linkMode === "live" && controllerSource === "simulator";

  return {
    linkMode,
    controllerLabel,
    controllerSource,
    dataMode,
    inputSourceLabel,
    selectedId,
    screen,
    planetChoiceEnabled: screen === "planet_choice",
    card,
    cardStatus,
    lastError,
    commandBusy,
    planSummaries,
    routePlans,
    selectedPlan,
    snapshot,
    faultHistory,
    gates,
    simFaultsEnabled,
    selectPlanById,
    createMissionFromSelected,
    prepareMission,
    resetMission,
    sendCommand,
    injectFault,
    selectPlanet,
    clearSelection,
  };
}
