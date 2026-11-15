import { useCallback, useEffect, useRef, useState } from "react";
import {
  connectEvents,
  getHealth,
  getPlan,
  getPlanetInfo,
  getSession,
  listPlans,
  postIntent,
  registerInputSession,
} from "../api/coreClient";
import { cardFromApi, cardFromMock, type PlanetCardModel } from "../api/mapPlanetInfo";
import type { MissionPlan, MissionSnapshot, PlanSummary } from "../api/missionTypes";
import type { BodyId, InputContext, PlanetTargetId, TargetId } from "../api/types";

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

export function useCoreBridge() {
  const [linkMode, setLinkMode] = useState<LinkMode>("connecting");
  const [controllerLabel, setControllerLabel] = useState("unknown");
  const [dataMode, setDataMode] = useState("unknown");
  const [selectedId, setSelectedId] = useState<PlanetTargetId | null>(null);
  const [screen, setScreen] = useState<"planet_choice" | "planet_info" | string>(
    "planet_choice",
  );
  const [card, setCard] = useState<PlanetCardModel | null>(null);
  const [cardStatus, setCardStatus] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [lastError, setLastError] = useState<string | null>(null);
  const [planSummaries, setPlanSummaries] = useState<PlanSummary[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<MissionPlan | null>(null);
  const [snapshot, setSnapshot] = useState<MissionSnapshot | null>(null);

  const sessionRef = useRef<SessionBits | null>(null);
  const serverSeqRef = useRef(0);
  const snapshotSeqRef = useRef(-1);
  const contextRevisionRef = useRef(0);
  const fetchGenRef = useRef(0);
  const socketRef = useRef<WebSocket | null>(null);

  const applySnapshot = useCallback((next: MissionSnapshot) => {
    if (next.server_seq <= snapshotSeqRef.current) return;
    snapshotSeqRef.current = next.server_seq;
    setSnapshot(next);
    if (next.controller_label) setControllerLabel(next.controller_label);
  }, []);

  const loadPreferredPlan = useCallback(async () => {
    const { plans } = await listPlans();
    setPlanSummaries(plans);
    if (plans.length === 0) {
      setSelectedPlan(null);
      return;
    }
    const preferred =
      plans.find((p) => p.objectives_won?.includes("least_fuel")) ?? plans[0];
    const full = await getPlan(preferred.plan_id);
    setSelectedPlan(full);
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
      setScreen(
        nextScreen ?? (bodyId ? "planet_info" : "planet_choice"),
      );

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
      const expectedRevision = contextRevision;
      setCardStatus("loading");
      setLastError(null);

      getPlanetInfo(bodyId)
        .then((info) => {
          // Ignore stale responses after another selection.
          if (
            gen !== fetchGenRef.current ||
            expectedBody !== bodyId ||
            expectedRevision !== contextRevisionRef.current
          ) {
            return;
          }
          setCard(cardFromApi(info));
          setCardStatus("ready");
        })
        .catch((err: unknown) => {
          if (gen !== fetchGenRef.current) return;
          setCardStatus("error");
          setLastError(err instanceof Error ? err.message : "planet_info_failed");
          // Keep highlight; show mock card so UI stays usable.
          setCard(cardFromMock(target));
        });
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;

    async function boot() {
      try {
        const health = await getHealth();
        if (cancelled) return;
        await getSession();
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
        setLinkMode("live");

        try {
          await loadPreferredPlan();
        } catch {
          if (!cancelled) setLastError("plans_unavailable");
        }
        if (cancelled) return;

        socket = connectEvents({
          onOpen: () => {
            if (!cancelled) setLinkMode("live");
          },
          onClose: () => {
            if (!cancelled) setLinkMode("offline_mock");
          },
          onError: () => {
            if (!cancelled) setLinkMode("offline_mock");
          },
          onMessage: (msg) => {
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
                };
              };
              if (data.controller_label) setControllerLabel(data.controller_label);
              if (data.data_mode) setDataMode(data.data_mode);
              if (data.selection && sessionRef.current) {
                const sel = data.selection as {
                  selected_body_id: BodyId | null;
                  context_id?: string;
                  context_revision: number;
                  screen?: string;
                };
                if (sel.context_id) {
                  sessionRef.current.context_id = sel.context_id;
                }
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
              };
              applySelection(
                data.selected_body_id,
                data.context_revision,
                false,
                data.screen,
              );
              // Refresh local context revision for the next intent.
              if (sessionRef.current) {
                sessionRef.current.revision = data.context_revision;
              }
              return;
            }

            if (msg.type === "mission_snapshot") {
              applySnapshot(msg.data as MissionSnapshot);
            }
          },
        });
        socketRef.current = socket;
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
      socket?.close();
      socketRef.current = null;
    };
  }, [applySelection, applySnapshot, loadPreferredPlan]);

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
        // Highlight/card update comes from the WS `selection` event (shared path with EEG).
      } catch (err) {
        setLastError(err instanceof Error ? err.message : "intent_failed");
      }
    },
    [applySelection, linkMode],
  );

  const selectPlanet = useCallback(
    (targetId: PlanetTargetId, source: "mouse" | "keyboard" = "mouse") => {
      // On planet_info only navigation.back / more_details are allowed — avoid action_unavailable noise.
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

  // Keep InputContext revision in sync when hello/selection update context_id.
  useEffect(() => {
    // no-op placeholder for future GET /input/context polling if needed
  }, []);

  const syncContextFromHello = useCallback((ctx: InputContext) => {
    if (!sessionRef.current) return;
    sessionRef.current.context_id = ctx.context_id;
    sessionRef.current.revision = ctx.revision;
  }, []);

  void syncContextFromHello;

  const selectPlanById = useCallback(async (planId: string) => {
    try {
      const full = await getPlan(planId);
      setSelectedPlan(full);
      // Changing the preview plan does not invent mission progression.
      setSnapshot(null);
      snapshotSeqRef.current = -1;
    } catch (err) {
      setLastError(err instanceof Error ? err.message : "plan_fetch_failed");
    }
  }, []);

  return {
    linkMode,
    controllerLabel,
    dataMode,
    selectedId,
    screen,
    planetChoiceEnabled: screen === "planet_choice",
    card,
    cardStatus,
    lastError,
    planSummaries,
    selectedPlan,
    snapshot,
    selectPlanById,
    selectPlanet,
    clearSelection,
  };
}
