import { ApiError } from "./http";

/** Prefer the backend's `detail` / `message` text over a bare status code. */
export function formatApiError(err: unknown, fallback = "request_failed"): string {
  if (err instanceof ApiError) {
    const body = err.body;
    if (typeof body === "string" && body.trim()) return body;
    if (body && typeof body === "object") {
      const record = body as Record<string, unknown>;
      if (typeof record.detail === "string") return record.detail;
      if (typeof record.message === "string") return record.message;
      if (Array.isArray(record.detail)) {
        return record.detail
          .map((item) =>
            typeof item === "string"
              ? item
              : item && typeof item === "object" && "msg" in item
                ? String((item as { msg: unknown }).msg)
                : JSON.stringify(item),
          )
          .join("; ");
      }
    }
    return `API ${err.status}`;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
