import {
  linkLightLabel,
  type LinkIndicator,
} from "../api/linkIndicator";

type Props = {
  indicator: LinkIndicator | null;
  controllerSource: "fpga" | "simulator" | "unknown";
};

/** Always-visible corner chip; state comes only from the backend. */
export function LinkLight({ indicator, controllerSource }: Props) {
  if (!indicator) return null;
  const label = linkLightLabel(indicator, controllerSource);
  return (
    <div
      className={`link-light link-light-${indicator}`}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <span className="link-light-dot" aria-hidden />
      <span className="link-light-text">{label}</span>
    </div>
  );
}
