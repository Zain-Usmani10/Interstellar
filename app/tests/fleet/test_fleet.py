import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.backend.fleet import FleetError, FleetStore


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fleet.json"
        self.fleet = FleetStore(self.path)

    def bind(self, mid="mission-1"):
        self.fleet.bind_mission(mid, "earth-standard", "399", "499", "standard")

    def location(self, fleet=None):
        return next(s["location"] for s in (fleet or self.fleet).snapshot()["shuttles"]
                    if s["id"] == "earth-standard")

    def test_starting_fleet(self):
        counts = [(s["location"]["body_id"], s["class"]) for s in self.fleet.snapshot()["shuttles"]]
        self.assertCountEqual(counts, [("399", "standard"), ("399", "long_range"),
            ("299", "standard"), ("499", "standard"), ("199", "long_range"), ("599", "long_range")])

    def test_reservation_stays_docked_and_excludes_other_missions(self):
        self.bind()
        self.assertEqual(self.location(), {"kind": "docked", "body_id": "399"})
        with self.assertRaisesRegex(FleetError, "MISSION_ACTIVE"):
            self.fleet.bind_mission("other", "mars-standard", "499", "399", "standard")
        restarted = FleetStore(self.path)
        self.assertEqual(restarted.snapshot(), self.fleet.snapshot())

    def test_launch_rule(self):
        for ship, origin, cls in [("missing", "399", "standard"),
                                  ("earth-standard", "299", "standard"),
                                  ("earth-standard", "399", "long_range")]:
            with self.assertRaisesRegex(FleetError, "NO_SHUTTLE_DOCKED"):
                self.fleet.bind_mission("m", ship, origin, "499", cls)

    def test_moves_only_on_evidence_and_capture_docks(self):
        self.bind()
        self.fleet.confirm_status("mission-1", "RUNNING", 0)
        self.assertEqual(self.location()["kind"], "docked")
        self.fleet.confirm_status("mission-1", "RUNNING", 1)
        self.assertEqual(self.location(), {"kind": "in_flight", "mission_id": "mission-1"})
        self.assertEqual(self.location(FleetStore(self.path)), self.location())
        with self.assertRaisesRegex(FleetError, "CAPTURE_NOT_CONFIRMED"):
            self.fleet.confirm_status("mission-1", "COMPLETE", 1)
        self.fleet.confirm_status("mission-1", "COMPLETE", 3)
        self.assertEqual(self.location(), {"kind": "docked", "body_id": "499"})
        self.fleet.bind_mission("return", "earth-standard", "499", "399", "standard")
        # Late previous mission evidence cannot change the new reservation.
        self.fleet.confirm_status("mission-1", "ABORTED", 1)
        self.assertEqual(self.fleet.snapshot()["active_mission_id"], "return")

    def test_first_status_after_blackout_can_be_complete(self):
        self.bind()
        self.fleet.confirm_status("mission-1", "COMPLETE", 3)
        self.assertEqual(self.location(), {"kind": "docked", "body_id": "499"})

    def test_abort_and_clear_before_departure(self):
        self.bind()
        self.fleet.confirm_status("mission-1", "ABORTED", 0)
        self.assertEqual(self.location()["body_id"], "399")
        self.bind("second")
        self.fleet.confirm_clear("second")
        self.assertIsNone(self.fleet.snapshot()["active_mission_id"])
        self.assertEqual(self.location()["body_id"], "399")

    def test_safe_before_departure_requires_explicit_clear(self):
        self.bind()
        self.fleet.confirm_status("mission-1", "SAFE", 0)
        self.assertEqual(self.location()["kind"], "docked")
        self.assertEqual(self.fleet.snapshot()["active_mission_id"], "mission-1")
        self.fleet.confirm_clear("mission-1")
        self.assertIsNone(self.fleet.snapshot()["active_mission_id"])

    def test_safe_abort_clear_after_departure_leave_ship_lost(self):
        for terminal in ("SAFE", "ABORTED", "CLEAR"):
            with self.subTest(terminal=terminal):
                self.fleet.reset()
                self.bind()
                self.fleet.confirm_status("mission-1", "RUNNING", 1)
                if terminal == "CLEAR":
                    self.fleet.confirm_clear("mission-1")
                else:
                    # Even a later zero mask cannot erase the departure evidence.
                    self.fleet.confirm_status("mission-1", terminal, 0)
                self.assertEqual(self.location()["kind"], "lost")
                self.assertEqual(self.location(FleetStore(self.path))["kind"], "lost")
                with self.assertRaisesRegex(FleetError, "NO_SHUTTLE_DOCKED"):
                    self.bind("second")

    def test_unknown_or_invalid_evidence_does_not_mutate(self):
        self.bind()
        before = self.fleet.snapshot()
        for mid, state, mask in [("unknown", "RUNNING", 1), ("mission-1", "ESTIMATE", 3),
                                  ("mission-1", "COMPLETE", 2), ("mission-1", "RUNNING", True)]:
            with self.assertRaises(FleetError):
                self.fleet.confirm_status(mid, state, mask)
        self.assertEqual(self.fleet.snapshot(), before)

    def test_reset_and_defensive_snapshot(self):
        original = self.fleet.snapshot()
        snapshot = self.fleet.snapshot()
        snapshot["shuttles"].clear()
        self.assertEqual(self.fleet.snapshot(), original)
        self.bind()
        self.fleet.confirm_status("mission-1", "SAFE", 1)
        self.fleet.reset()
        self.assertEqual(FleetStore(self.path).snapshot(), original)

    def test_failed_write_preserves_memory_and_disk(self):
        before = self.fleet.snapshot()
        with patch("app.backend.fleet.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.bind()
        self.assertEqual(self.fleet.snapshot(), before)
        self.assertEqual(FleetStore(self.path).snapshot(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_corrupt_storage_is_never_silently_reset(self):
        self.path.write_text('{"version": 99}', encoding="utf-8")
        with self.assertRaises(FleetError):
            FleetStore(self.path)
        self.assertEqual(json.loads(self.path.read_text())["version"], 99)


if __name__ == "__main__":
    unittest.main()
