# coding=utf-8
import os
import sys
import time

import smbus
from ina219 import INA219, DeviceRangeError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
import config

SHUNT_OHMS = 0.08
INA219_ADDRESS = config.INA219_ADDRESS
# The Pi's I2C bus. Passed to INA219 explicitly: its own bus detection
# (Adafruit_GPIO) does not recognise the Zero 2 W and raises
# "Could not determine default I2C bus for platform".
I2C_BUS = 1


def is_ina219_present(address):
    try:
        bus = smbus.SMBus(I2C_BUS)
        bus.read_byte_data(address, 0)  # Try to read a byte from the specified address
        return True  # If no exception is raised, the device is present
    except Exception:
        return False


def fetch_ina219_data():
    data = {}
    if is_ina219_present(INA219_ADDRESS):  # Check if the INA219 is present
        try:
            ina = INA219(SHUNT_OHMS, busnum=I2C_BUS, address=INA219_ADDRESS)
            ina.configure()
            time.sleep(1)
            data = {
                "BusVoltage": ina.voltage(),
                "BusCurrent": None,
                "Power": None,
                "ShuntVoltage": ina.shunt_voltage(),
            }
            data["BusCurrent"] = ina.current()
            data["Power"] = ina.power()
        except DeviceRangeError as e:
            data["error"] = str(e)
    else:
        data["error"] = f"INA219 not found at address {hex(INA219_ADDRESS)}"

    return data


if __name__ == "__main__":
    """
    If the module is executed as a standalone script, it will return the temperature in a telegraf friendly format.
    """
    try:
        sensor_data = fetch_ina219_data()
        print("INA219 Sensor Data:")
        for key, value in sensor_data.items():
            print(f"{key}, value={value}")
    except Exception as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("Script interrupted.")
