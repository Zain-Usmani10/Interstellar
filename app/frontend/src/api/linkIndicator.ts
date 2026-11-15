export type LinkIndicator = "active" | "inactive" | "reconnecting";

export function isLinkIndicator(value: unknown): value is LinkIndicator {
  return value === "active" || value === "inactive" || value === "reconnecting";
}

export function linkLightLabel(
  indicator: LinkIndicator,
  controllerSource: "fpga" | "simulator" | "unknown",
): string {
  const prefix = controllerSource === "fpga" ? "FPGA" : "Simulator";
  const state =
    indicator === "active"
      ? "Link Active"
      : indicator === "inactive"
        ? "Link Inactive"
        : "Reconnecting";
  return `${prefix} · ${state}`;
}
