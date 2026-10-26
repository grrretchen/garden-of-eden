import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import config

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.sensors.light.light import Light


class TestLight(unittest.TestCase):
    @patch("app.sensors.light.light.PWMLED")
    @patch("app.sensors.light.light.PiGPIOFactory")
    @patch("app.sensors.light.light.pigpio.pi")
    def setUp(self, MockPi, MockFactory, MockPWMLED):
        self.mock_led = MockPWMLED.return_value
        self.mock_led.value = 0
        self.mock_pi = MockPi.return_value
        self.light = Light(18)

    def test_turn_on_from_0(self):
        self.mock_led.value = 0
        self.light.on()
        self.assertEqual(self.mock_led.value, 1)
        self.assertLogs("Turning light on")

    def test_turn_on_from_nonzero(self):
        self.mock_led.value = 0.5
        self.light.on()
        self.assertEqual(self.mock_led.value, 0.5)
        self.assertLogs("Light already on, skipping")

    def test_off(self):
        self.mock_led.value = 1
        self.light.off()
        self.assertEqual(self.mock_led.value, 0)
        self.assertLogs("Turning light off")

    def test_set_brightness_valid(self):
        valid_brightness = 70
        self.light.set_brightness(valid_brightness)
        self.assertEqual(self.mock_led.value * 100, valid_brightness)

    def test_set_brightness_invalid(self):
        with self.assertRaises(ValueError):
            self.light.set_brightness(110)

    def test_set_frequency(self):
        freq = 10000  # 10kHz
        self.light.set_frequency(freq)
        self.mock_pi.set_PWM_frequency.assert_called_with(18, freq)

    def test_close(self):
        self.light.close()
        self.mock_led.close.assert_called_once()


class TestLightKeepsLevel(unittest.TestCase):
    """Opening the pin must not change the light (PWMLED defaults to 0)."""

    @patch("app.sensors.light.light.PWMLED")
    @patch("app.sensors.light.light.PiGPIOFactory")
    @patch("app.sensors.light.light.pigpio.pi")
    def test_opens_at_current_level(self, MockPi, MockFactory, MockPWMLED):
        MockPi.return_value.get_PWM_dutycycle.return_value = 51
        MockPi.return_value.get_PWM_range.return_value = 255
        Light(18)
        self.assertAlmostEqual(MockPWMLED.call_args.kwargs["initial_value"], 0.2)

    @patch("app.sensors.light.light.PWMLED")
    @patch("app.sensors.light.light.PiGPIOFactory")
    @patch("app.sensors.light.light.pigpio.pi")
    def test_pin_not_in_pwm_mode_opens_off(self, MockPi, MockFactory, MockPWMLED):
        MockPi.return_value.get_PWM_dutycycle.side_effect = Exception("not a PWM GPIO")
        Light(18)
        self.assertEqual(MockPWMLED.call_args.kwargs["initial_value"], 0)


class TestLightCliRecordsState(unittest.TestCase):
    """The `light` CLI (cron) saves its result, as the REST API does."""

    SCRIPT = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app/sensors/light/light.py"
    )

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.path)
        self._patch = patch.object(config, "STATE_FILE", self.path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if os.path.exists(self.path):
            os.unlink(self.path)

    def _run(self, *args):
        with patch.object(sys, "argv", ["light.py", *args]), patch("pigpio.pi") as MockPi:
            MockPi.return_value.get_PWM_dutycycle.return_value = 0
            MockPi.return_value.get_PWM_range.return_value = 255
            runpy.run_path(self.SCRIPT, run_name="__main__")
        with open(self.path) as fh:
            return json.load(fh)

    def test_brightness_is_recorded(self):
        state = self._run("--on", "--brightness", "30")
        self.assertTrue(state["light_on"])
        self.assertEqual(state["brightness"], 30)

    def test_off_keeps_last_brightness(self):
        self._run("--on", "--brightness", "30")
        state = self._run("--off")
        self.assertFalse(state["light_on"])
        self.assertEqual(state["brightness"], 30)


class TestAppPackageImport(unittest.TestCase):
    def test_app_lib_does_not_open_devices(self):
        # The light CLI imports app.lib.state; that must not import the route
        # modules, which open every GPIO/I2C device (and the pump at 0).
        code = (
            "import sys, app.lib.state; "
            "print(any(m.startswith('app.sensors') for m in sys.modules))"
        )
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=root, capture_output=True, text=True, check=True
        )
        self.assertEqual(out.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
