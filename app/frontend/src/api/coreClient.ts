import { apiFetch, wsUrl } from "./http";
import type { MissionPlan, MissionSnapshot, PlanSummary } from "./missionTypes";
import type {
  ApiPlanetInfo,
  BodyId,
  InputContext,
  TargetId,
  WsEnvelope,
} from "./types";

export async function getHealth(): Promise<{ status: string; data_mode?: string }> {
  return apiFetch("/api/v1/health");
}

export async function getSession(): Promise<{ operator_token: string }> {
  return apiFetch("/api/v1/session");
}

export async function registerInputSession(source: "mouse" | "keyboard") {
  return apiFetch<{
    input_session_id: string;
    token: string;
    capability: string;
    context: InputContext;
  }>("/api/v1/input/sessions", {
    method: "POST",
    body: JSON.stringify({
      source,
      adapter: { name: "interstellar-frontend", version: "0.1.0", device: "browser" },
    }),
  });
}

export async function postIntent(args: {
  token: string;
  input_session_id: string;
  context_id: string;
  context_revision: number;
  target_id: TargetId;
  source: "mouse" | "keyboard";
}): Promise<{
  event_id: string;
  accepted: boolean;
  reason: string;
  new_context_revision: number;
}> {
  const event_id = crypto.randomUUID();
  return apiFetch("/api/v1/input/intents", {
    method: "POST",
    headers: { "X-Input-Token": args.token },
    body: JSON.stringify({
      schema_version: 1,
      event_id,
      input_session_id: args.input_session_id,
      context_id: args.context_id,
      context_revision: args.context_revision,
      target_id: args.target_id,
      source: args.source,
    }),
  });
}

export async function getPlanetInfo(
  bodyId: BodyId,
  sceneEpochJdTdb?: number | null,
): Promise<ApiPlanetInfo> {
  const query =
    sceneEpochJdTdb === undefined || sceneEpochJdTdb === null
      ? ""
      : `?scene_epoch_jd_tdb=${encodeURIComponent(String(sceneEpochJdTdb))}`;
  return apiFetch(`/api/v1/planets/${bodyId}/info${query}`);
}

export async function listPlans(): Promise<{ plans: PlanSummary[] }> {
  return apiFetch("/api/v1/plans");
}

export async function getPlan(planId: string): Promise<MissionPlan> {
  return apiFetch(`/api/v1/plans/${planId}`);
}

export async function getMission(missionId: string): Promise<MissionSnapshot> {
  return apiFetch(`/api/v1/missions/${missionId}`);
}

export function connectEvents(handlers: {
  onMessage: (msg: WsEnvelope) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: () => void;
}): WebSocket {
  const socket = new WebSocket(wsUrl("/api/v1/events"));
  socket.onopen = () => handlers.onOpen?.();
  socket.onclose = () => handlers.onClose?.();
  socket.onerror = () => handlers.onError?.();
  socket.onmessage = (event) => {
    try {
      handlers.onMessage(JSON.parse(event.data) as WsEnvelope);
    } catch {
      // ignore malformed frames
    }
  };
  return socket;
}
