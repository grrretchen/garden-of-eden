import os
import tempfile
import time
import unittest
from unittest.mock import patch

from parameterized import parameterized

import config
from app import create_app
from app.lib.water import save_reading


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        super().setUp()  # This will call the setUp method of the BaseTestCase
        self.app = create_app("default")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()


class PumpBlueprintTestCase(BaseTestCase):

    BASE_ROUTE = "/pump"

    # Parameterized test for /on and /off routes
    @parameterized.expand([("/on", "on", "Pump turned on!"), ("/off", "off", "Pump turned off!")])
    def test_pump_actions(self, route, mock_method, expected_message):
        with patch(f"app.sensors.pump.routes.pump_control.{mock_method}") as mock_action:
            response = self.client.post(f"{self.BASE_ROUTE}{route}")
            self.assertEqual(response.status_code, 200)
            mock_action.assert_called_once()
            self.assertEqual(response.get_json(), {"message": expected_message})

    @patch("app.sensors.pump.routes.pump_control.on")
    def test_pump_turn_on(self, mock_on):
        response = self.client.post(f"{self.BASE_ROUTE}/on")
        self.assertEqual(response.status_code, 200)
        mock_on.assert_called_once()
        self.assertEqual(response.get_json(), {"message": "Pump turned on!"})

    @patch("app.sensors.pump.routes.pump_control.off")
    def test_pump_turn_off(self, mock_off):
        response = self.client.post(f"{self.BASE_ROUTE}/off")
        self.assertEqual(response.status_code, 200)
        mock_off.assert_called_once()
        self.assertEqual(response.get_json(), {"message": "Pump turned off!"})

    @patch("app.sensors.pump.routes.pump_control.set_speed")
    def test_pump_adjust_speed(self, mock_set_speed):
        response = self.client.post(f"{self.BASE_ROUTE}/speed", json={"value": 50})
        self.assertEqual(response.status_code, 200)
        mock_set_speed.assert_called_once_with(50)
        self.assertEqual(response.get_json(), {"message": "Pump adjusted to 50% speed!"})

    @patch("app.sensors.pump.routes.PumpControl.get_speed")
    def test_pump_get_speed(self, mock_get_speed):
        mock_get_speed.return_value = 75
        response = self.client.get(f"{self.BASE_ROUTE}/speed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"value": 75})

    @patch("app.sensors.pump.routes.fetch_ina219_data")
    def test_pump_get_power_data(self, mock_fetch_data):
        mock_data = {"current": 5.2, "voltage": 12.5}
        mock_fetch_data.return_value = mock_data
        response = self.client.get(f"{self.BASE_ROUTE}/stats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), mock_data)

    def test_pump_adjust_speed_invalid(self):
        # Out-of-range values are rejected with 400 before reaching hardware.
        response = self.client.post(f"{self.BASE_ROUTE}/speed", json={"value": 150})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())


class LightBlueprintTestCase(BaseTestCase):

    BASE_ROUTE = "/light"

    def setUp(self):
        self.app = create_app("default")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    @patch("app.sensors.light.routes.light_control.on")
    def test_light_turn_on(self, mock_on):
        response = self.client.post(f"{self.BASE_ROUTE}/on")
        self.assertEqual(response.status_code, 200)
        mock_on.assert_called_once()
        self.assertEqual(response.get_json(), {"message": "Light turned on!"})

    @patch("app.sensors.light.routes.light_control.off")
    def test_light_turn_off(self, mock_off):
        response = self.client.post(f"{self.BASE_ROUTE}/off")
        self.assertEqual(response.status_code, 200)
        mock_off.assert_called_once()
        self.assertEqual(response.get_json(), {"message": "Light turned off!"})

    @patch("app.sensors.light.routes.light_control.set_brightness")
    def test_light_set_brightness(self, mock_set_brightness):
        response = self.client.post(f"{self.BASE_ROUTE}/brightness", json={"value": 75})
        self.assertEqual(response.status_code, 200)
        mock_set_brightness.assert_called_once_with(75)
        self.assertEqual(response.get_json(), {"message": "Light adjusted to 75%"})

    @patch("app.sensors.light.routes.light_control.get_brightness")
    def test_light_get_brightness(self, mock_get_brightness):
        mock_get_brightness.return_value = 60
        response = self.client.get(f"{self.BASE_ROUTE}/brightness")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"value": 60})

    def test_light_set_brightness_invalid(self):
        # Out-of-range values are rejected with 400 before reaching hardware.
        response = self.client.post(f"{self.BASE_ROUTE}/brightness", json={"value": 150})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())


class DistanceBlueprintTestCase(BaseTestCase):

    BASE_ROUTE = "/distance"

    def setUp(self):
        super().setUp()
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.path)  # start with no reading
        self._patch = patch.object(config, "WATER_READING_FILE", self.path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_get_distance_reports_recorded_reading(self):
        # The MQTT service records readings; the route only reports them.
        save_reading(55.5, measured_at=time.time() - 10)

        response = self.client.get(f"{self.BASE_ROUTE}/measure")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        # 55.5cm is past empty -> 0 gallons.
        self.assertEqual(body["distance"], 55.5)
        self.assertEqual(body["gallons"], 0.0)
        self.assertAlmostEqual(body["age_seconds"], 10, delta=2)

    def test_get_distance_without_reading_is_503(self):
        response = self.client.get(self.BASE_ROUTE)
        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.get_json())

    def test_get_distance_refuses_stale_reading(self):
        # Older than three check intervals: the MQTT service has stopped
        # measuring, so the old value must not be shown as current.
        stale = time.time() - 3 * config.WATER_CHECK_SECONDS - 5
        save_reading(12.0, measured_at=stale)

        response = self.client.get(self.BASE_ROUTE)

        self.assertEqual(response.status_code, 503)
        self.assertIn("stale", response.get_json()["error"])

    def test_route_module_does_not_own_the_sensor(self):
        # A second DistanceSensor in the API process corrupts the MQTT
        # service's echoes; the route module must not create one.
        from app.sensors.distance import routes

        self.assertFalse(hasattr(routes, "distance_control"))


class PCBTempBlueprintTestCase(BaseTestCase):

    BASE_ROUTE = "/pcb-temp"

    @patch("app.sensors.pcb_temp.routes.get_pcb_temperature")
    def test_get_pcb_temperature(self, mock_get_pcb_temperature):
        # Mocking the return value of get_pcb_temperature function to simulate a temperature value of 55.7
        mock_get_pcb_temperature.return_value = 55.7

        # Making a GET request to the pcb_temp endpoint
        response = self.client.get(f"{self.BASE_ROUTE}")

        # Asserting that the status code is 200 OK
        self.assertEqual(response.status_code, 200)

        # Asserting that the response JSON contains the mocked temperature value
        self.assertEqual(response.get_json(), {"pcb-temp": 55.7})


class TemperatureBlueprintTestCase(BaseTestCase):

    BASE_ROUTE = "/temperature"

    @patch("app.sensors.temperature.routes.temperature_sensor.read")
    def test_get_temperature(self, mock_get_value):
        # Mocking the return value of read() to simulate a temperature value of 45.6
        mock_get_value.return_value = 45.6

        # Making a GET request to the temperature endpoint
        response = self.client.get(f"{self.BASE_ROUTE}")

        # Asserting that the status code is 200 OK
        self.assertEqual(response.status_code, 200)

        # Asserting that the response JSON contains the mocked temperature value
        self.assertEqual(response.get_json(), {"temperature": 45.6})


class HumidityBlueprintTestCase(BaseTestCase):

    BASE_ROUTE = "/humidity"

    @patch("app.sensors.humidity.routes.humidity_sensor.read")
    def test_get_humidity(self, mock_get_value):
        # Mocking the return value of read() to simulate a humidity value of 45.6
        mock_get_value.return_value = 45.6

        # Making a GET request to the humidity endpoint
        response = self.client.get(f"{self.BASE_ROUTE}")

        # Asserting that the status code is 200 OK
        self.assertEqual(response.status_code, 200)

        # Asserting that the response JSON contains the mocked humidity value
        self.assertEqual(response.get_json(), {"humidity": 45.6})


if __name__ == "__main__":
    unittest.main()
