"""INA219 pump power readings: the I2C bus must be passed explicitly."""

import unittest
from unittest.mock import patch

from app.sensors.pump import pump_power


class PumpPowerTestCase(unittest.TestCase):
    @patch("app.sensors.pump.pump_power.time.sleep")
    @patch("app.sensors.pump.pump_power.is_ina219_present", return_value=True)
    @patch("app.sensors.pump.pump_power.INA219")
    def test_reads_on_the_configured_bus(self, mock_ina, _present, _sleep):
        ina = mock_ina.return_value
        ina.voltage.return_value = 12.5
        ina.current.return_value = 0.1
        ina.power.return_value = 4.9
        ina.shunt_voltage.return_value = 0.01
        data = pump_power.fetch_ina219_data()
        mock_ina.assert_called_once_with(
            pump_power.SHUNT_OHMS, busnum=pump_power.I2C_BUS, address=pump_power.INA219_ADDRESS
        )
        self.assertEqual(
            data, {"BusVoltage": 12.5, "BusCurrent": 0.1, "Power": 4.9, "ShuntVoltage": 0.01}
        )

    @patch("app.sensors.pump.pump_power.is_ina219_present", return_value=False)
    def test_missing_chip_reports_an_error(self, _present):
        self.assertIn("not found", pump_power.fetch_ina219_data()["error"])


if __name__ == "__main__":
    unittest.main()
