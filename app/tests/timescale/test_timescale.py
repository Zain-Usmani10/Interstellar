import unittest

from app.backend import timescale as t


class TimescaleTests(unittest.TestCase):
    def test_map_and_rate(self):
        self.assertEqual(t.tick_map(), dict(departure_tick=500, arrival_tick=6500, end_tick=6800))
        self.assertEqual(t.sim_days_per_second(300), 5)
        mapping = t.tick_map()
        mapping["departure_tick"] = 1
        self.assertEqual(t.tick_map()["departure_tick"], 500)

    def test_rounding_and_limits(self):
        for seconds, expected in [(1, 1), (1.49 * 86400, 1), (1.5 * 86400, 2),
                                  (9999 * 86400, 9999), (20000 * 86400, 9999)]:
            self.assertEqual(t.trip_days(seconds), expected)
        for bad in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                t.trip_days(bad)

    def test_every_tick_against_integer_accumulator(self):
        # Independent hardware-style remainder accumulator; >6000 days may
        # advance multiple days per tick, so a single subtraction is insufficient.
        for days in (1, 300, 9999):
            elapsed_days = remainder = 0
            for tick in range(6801):
                if 500 < tick <= 6500:
                    remainder += days
                    while remainder >= 6000:
                        remainder -= 6000
                        elapsed_days += 1
                self.assertEqual(t.days_to_arrival(tick, 500, 6500, days), days - elapsed_days,
                                 (days, tick))

    def test_epochs_countdown_flight_tail_and_custom_ticks(self):
        jd, tof = 2460000.5, 300.25 * 86400
        self.assertAlmostEqual(t.epoch_jd_tdb(0, jd, tof), jd - 5 / 86400)
        self.assertEqual(t.epoch_jd_tdb(500, jd, tof), jd)
        self.assertEqual(t.epoch_jd_tdb(3500, jd, tof), jd + 150.125)
        self.assertEqual(t.epoch_jd_tdb(6500, jd, tof), jd + 300.25)
        self.assertAlmostEqual(t.epoch_jd_tdb(6800, jd, tof), jd + 315.2625)
        self.assertEqual(t.epoch_jd_tdb(12010, jd, tof, 10, 12010), jd + 300.25)

    def test_invalid_ticks_days_and_epochs(self):
        for args in [(-1, 500, 6500, 1), (0, 500, 500, 1), (0, 500, 6500, 0),
                     (0, 500, 6500, 10000), (1.5, 500, 6500, 1), (True, 500, 6500, 1)]:
            with self.assertRaises(ValueError):
                t.days_to_arrival(*args)
        with self.assertRaises(ValueError):
            t.epoch_jd_tdb(0, float("nan"), 86400)


if __name__ == "__main__":
    unittest.main()
