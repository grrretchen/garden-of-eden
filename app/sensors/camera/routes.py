import logging
import os
import re

from flask import Blueprint, jsonify, request, send_file

import config

from . import camera

logger = logging.getLogger(__name__)

camera_blueprint = Blueprint("camera", __name__)


# Native MJPEG modes advertised by both Astrid cameras (POTD-394).
MJPEG_RESOLUTIONS = frozenset(
    "2592x1944 2560x1920 1920x1080 1280x960 1280x720 1024x768 "
    "960x540 848x480 800x600 640x480 320x240".split()
)


def _capture_options():
    """Opt-in still parameters; leave no-query capture exactly as before."""
    if not any(key in request.args for key in ("resolution", "skip")):
        return {}
    if any(len(request.args.getlist(key)) > 1 for key in ("resolution", "skip")):
        raise ValueError("resolution and skip must each occur at most once")
    options = {"pixel_format": "MJPEG", "skip": 2}
    if "resolution" in request.args:
        resolution = request.args["resolution"]
        if resolution not in MJPEG_RESOLUTIONS:
            raise ValueError("unsupported MJPEG resolution")
        options["resolution"] = resolution
    if "skip" in request.args:
        skip = request.args["skip"]
        if not re.fullmatch(r"[0-9]+", skip) or not 2 <= int(skip) <= 60:
            raise ValueError("skip must be an integer from 2 to 60")
        options["skip"] = int(skip)
    return options


def _serve(capture_fn, path):
    try:
        options = _capture_options()
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    try:
        capture_fn(**options)
    except FileNotFoundError:
        return jsonify(error="fswebcam not installed on this host"), 503
    except Exception as exc:
        logger.error("Camera capture failed: %s", exc)
        return jsonify(error=f"camera capture failed: {exc}"), 503
    return send_file(path, mimetype="image/jpeg")


@camera_blueprint.route("/upper", methods=["GET"])
def upper():
    return _serve(camera.capture_upper, config.UPPER_IMAGE_PATH)


@camera_blueprint.route("/lower", methods=["GET"])
def lower():
    return _serve(camera.capture_lower, config.LOWER_IMAGE_PATH)


@camera_blueprint.route("/timelapse/<cam>", methods=["GET"])
def get_timelapse(cam):
    if cam not in camera.CAMERAS:
        return jsonify(error="unknown camera"), 400
    path = camera.timelapse_path(cam)
    if not os.path.exists(path):
        return jsonify(error="no timelapse yet — generate one"), 404
    return send_file(path, mimetype="video/mp4")


@camera_blueprint.route("/timelapse/<cam>", methods=["POST"])
def make_timelapse(cam):
    if cam not in camera.CAMERAS:
        return jsonify(error="unknown camera"), 400
    try:
        camera.generate_timelapse(cam)
    except FileNotFoundError as exc:
        return jsonify(error=str(exc)), 404
    except Exception as exc:
        logger.error("Timelapse generation failed: %s", exc)
        return jsonify(error=f"generation failed: {exc}"), 503
    return jsonify(message=f"{cam} timelapse generated"), 200
