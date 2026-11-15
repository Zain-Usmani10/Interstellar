type Props = {
  daysPerSecond: number;
  onChange: (value: number) => void;
  paused: boolean;
  atTrackEnd: boolean;
  visible: boolean;
};

/** Overview speed control — days of simulated calendar per real second. */
export function CalendarSpeedSlider({
  daysPerSecond,
  onChange,
  paused,
  atTrackEnd,
  visible,
}: Props) {
  if (!visible) return null;
  return (
    <div
      className="calendar-speed glass"
      role="group"
      aria-label="Calendar speed"
    >
      <label className="calendar-speed-label" htmlFor="calendar-speed">
        {atTrackEnd
          ? "Track end — calendar stopped"
          : paused
            ? "Calendar paused"
            : `${daysPerSecond} d/s`}
      </label>
      <input
        id="calendar-speed"
        type="range"
        min={1}
        max={60}
        step={1}
        value={daysPerSecond}
        disabled={atTrackEnd}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}
