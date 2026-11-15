# Runtime integration

`FleetStore(path)` loads persisted state or initializes it from the packaged
`initial_fleet.json`. Pass a writable runtime-data path, not the packaged file.
Use one store instance in the single backend process. Its methods serialize
threads; separate processes must not share the file. Writes atomically replace
the file. Invalid persisted data raises an error rather than resetting ships.

1. At mission creation, call `bind_mission(mission_id, shuttle_id,
   origin_body_id, destination_body_id, vehicle_class)`. Body IDs are strings,
   and classes are `standard` or `long_range`. The caller obtains the class
   from the validated plan's vehicle (450 s / 900 s), never a UI assertion.
   Binding reserves the single mission slot but keeps the shuttle docked.
2. After validating STATUS session and mission correlation, call
   `confirm_status(mission_id, state_name, executed_mask)`. State names are
   uppercase protocol names; masks use departure bit 0 and capture bit 1.
   Do not pass estimated, stale-session or uncorrelated board data. A first
   post-blackout COMPLETE with both burns can dock the shuttle directly.
3. After a confirmed CLEAR, call `confirm_clear(mission_id)`; reconcile the
   board's executed mask before clearing it. Clearing after departure never
   restores a shuttle. SAFE before departure retains the reservation until
   abort/clear. Duplicate evidence for finished missions has no effect.
4. `snapshot()` returns a detached JSON-compatible dictionary: `version`,
   `shuttles`, `missions`, `active_mission_id`. Each shuttle has `id`, `name`,
   `class`, and `location`. A docked location has `kind` and `body_id`; an
   in-flight/lost location has `kind` and `mission_id`.
5. Operator `reset()` restores the starting fleet and clears mission history.
   First stop/clear the controller and serialize mission actions in the runtime.
   There are no implicit resets or wall-clock-driven arrivals.

`FleetError.code` exposes errors such as `NO_SHUTTLE_DOCKED`, `MISSION_ACTIVE`,
`UNKNOWN_MISSION`, and `CAPTURE_NOT_CONFIRMED`. The API owner maps these to HTTP.
The API/runtime must coordinate its own mission persistence with reservation
creation, retaining/reconciling reservations if an upload or restart fails.

These are bookkeeping tests, not physical FPGA qualification.
