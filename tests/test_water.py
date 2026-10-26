import os
import tempfile
import unittest
from unittest.mock import patch

import config
from app.lib.water import gallons_remaining, is_water_low, load_reading, save_reading


class WaterLowTestCase(unittest.TestCase):
    def test_low_when_distance_exceeds_threshold(self):
        # 15cm gap to the surface, alert above 11cm -> low.
        self.assertTrue(is_water_low(15.0, 11.0))

    def test_not_low_when_distance_within_threshold(self):
        self.assertFalse(is_water_low(8.0, 11.0))

    def test_equal_is_not_low(self):
        self.assertFalse(is_water_low(11.0, 11.0))

    def test_disabled_threshold_never_low(self):
        self.assertFalse(is_water_low(99.0, 0))
        self.assertFalse(is_water_low(99.0, None))

    def test_failed_reading_not_low(self):
        self.assertFalse(is_water_low(None, 11.0))


class GallonsRemainingTestCase(unittest.TestCase):
    def test_linear_map(self):
        # full=5cm -> capacity, empty=20cm -> 0, midpoint -> half.
        self.assertEqual(gallons_remaining(5, 5, 20, 5), 5.0)
        self.assertEqual(gallons_remaining(20, 5, 20, 5), 0.0)
        self.assertEqual(gallons_remaining(12.5, 5, 20, 5), 2.5)

    def test_clamps_out_of_range(self):
        self.assertEqual(gallons_remaining(2, 5, 20, 5), 5.0)  # over-full
        self.assertEqual(gallons_remaining(99, 5, 20, 5), 0.0)  # past empty

    def test_guards(self):
        self.assertIsNone(gallons_remaining(None, 5, 20, 5))  # bad reading
        self.assertIsNone(gallons_remaining(10, 5, 20, 0))  # no capacity
        self.assertIsNone(gallons_remaining(10, 20, 20, 5))  # zero span


class WaterReadingTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.path)  # start absent
        self._patch = patch.object(config, "WATER_READING_FILE", self.path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_none_when_absent(self):
        self.assertIsNone(load_reading())

    def test_save_and_load_roundtrip(self):
        save_reading(13.126, measured_at=1000.0)
        self.assertEqual(load_reading(), {"distance": 13.13, "measured_at": 1000.0})

    def test_none_when_corrupt(self):
        with open(self.path, "w") as fh:
            fh.write("{not json")
        self.assertIsNone(load_reading())


if __name__ == "__main__":
    unittest.main()
