"""Water-level helpers shared by the MQTT service and REST API.

The distance sensor reports the gap (cm) from the sensor down to the water
surface, so a *larger* distance means a *lower* tank.
"""

import json
import logging
import time

import config
from app.lib.persist import write_json_atomic

logger = logging.getLogger(__name__)


def save_reading(distance_cm, measured_at=None):
    """Record the latest tank reading for the REST API (MQTT service only)."""
    reading = {
        "distance": round(distance_cm, 2),
        "measured_at": measured_at if measured_at is not None else time.time(),
    }
    try:
        write_json_atomic(config.WATER_READING_FILE, reading)
    except OSError as exc:
        logger.error("Failed to save water reading: %s", exc)
    return reading


def load_reading():
    """Return the latest recorded reading, or None if there is none yet."""
    try:
        with open(config.WATER_READING_FILE) as fh:
            data = json.load(fh)
        return {"distance": float(data["distance"]), "measured_at": float(data["measured_at"])}
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        return None


def is_water_low(distance_cm, threshold_cm):
    """Return True if the tank is low.

    ``threshold_cm`` of ``None``/0 means alerting is disabled -> never low.
    A ``distance_cm`` of ``None`` (failed reading) is treated as "not low" so a
    sensor glitch doesn't raise a false alarm.
    """
    if not threshold_cm:
        return False
    if distance_cm is None:
        return False
    return distance_cm > threshold_cm


def gallons_remaining(distance_cm, full_cm, empty_cm, capacity_gal):
    """Estimate gallons left from the sensor distance via a linear full->empty map.

    ``full_cm`` is the distance when the tank is full (small), ``empty_cm`` when
    empty (large). Returns None on a bad reading or invalid calibration; clamps
    to the 0..capacity range otherwise.
    """
    if distance_cm is None or not capacity_gal:
        return None
    span = empty_cm - full_cm
    if span <= 0:
        return None
    fraction = (empty_cm - distance_cm) / span
    fraction = max(0.0, min(1.0, fraction))
    return round(fraction * capacity_gal, 1)
