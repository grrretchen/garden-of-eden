import logging
import time

from flask import Blueprint, jsonify

import config
from app.lib.water import gallons_remaining, load_reading

logger = logging.getLogger(__name__)

distance_blueprint = Blueprint("distance", __name__)

# The MQTT service owns the distance sensor and records each reading; this
# route only reports it. A second DistanceSensor here would pulse the same
# trigger pin and pick up the other process's echoes, so both readings go bad.
# A reading older than three check intervals means the MQTT service has stopped
# measuring, so it is refused rather than shown as current.
MAX_READING_AGE_SECONDS = 3 * config.WATER_CHECK_SECONDS


@distance_blueprint.route("", methods=["GET"])
@distance_blueprint.route("/measure", methods=["GET"])
def get_distance():
    reading = load_reading()
    if reading is None:
        return jsonify(error="No water reading yet (recorded by the MQTT service)"), 503
    age = time.time() - reading["measured_at"]
    if age > MAX_READING_AGE_SECONDS:
        return jsonify(error=f"Water reading is stale ({age:.0f}s old)"), 503
    distance_value = reading["distance"]
    gallons = gallons_remaining(
        distance_value,
        config.WATER_FULL_CM,
        config.WATER_EMPTY_CM,
        config.TANK_CAPACITY_GALLONS,
    )
    return (
        jsonify(
            distance=distance_value,
            gallons=gallons,
            measured_at=reading["measured_at"],
            age_seconds=round(age),
        ),
        200,
    )
