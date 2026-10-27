"""Build the garden-of-eden Postman collection (v2.1) and environment."""

import json
import os
import sys
import uuid

RESP, OUT = sys.argv[1], sys.argv[2]
NS = uuid.UUID("6f1c2a3e-0000-4000-8000-000000000001")


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(parts)))


def example(name):
    p = os.path.join(RESP, name + ".json")
    if not os.path.exists(p):
        return None
    body = json.load(open(p))
    if name == "pods":
        body["catalog"] = body["catalog"][:2]  # 108 entries; trimmed for the example
    return int(open(p + ".status").read()), json.dumps(body, indent=2)


def req(name, method, path, desc="", body=None, headers=(), auth=True, ex=None, test=200):
    url_path = path.strip("/").split("/") if path != "/" else [""]
    item = {
        "id": uid(method, path, name),
        "name": name,
        "request": {
            "method": method,
            "header": [{"key": k, "value": v} for k, v in headers],
            "url": {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"], "path": url_path},
            "description": desc,
        },
    }
    if not auth:
        item["request"]["auth"] = {"type": "noauth"}
    if body is not None:
        item["request"]["header"].append({"key": "Content-Type", "value": "application/json"})
        item["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {"raw": {"language": "json"}},
        }
    if test:
        item["event"] = [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        f'pm.test("status {test}", () => pm.response.to.have.status({test}));'
                    ],
                },
            }
        ]
    if ex and (e := example(ex)):
        code, text = e
        item["response"] = [
            {
                "name": f"gardyn_home3 2026-10-27 ({code})",
                "originalRequest": item["request"],
                "status": "OK" if code == 200 else "Error",
                "code": code,
                "_postman_previewlanguage": "json",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": text,
            }
        ]
    return item


def folder(name, desc, items):
    return {"id": uid("folder", name), "name": name, "description": desc, "item": items}


PUMP = "⚠ Runs the real pump. Only with water in the tank."
schedule_now = json.load(open(os.path.join(RESP, "schedule.json")))

current = [
    folder(
        "Health and system",
        "No hardware access.",
        [
            req(
                "Health", "GET", "/health", "Liveness. Never needs a key.", auth=False, ex="health"
            ),
            req(
                "System info",
                "GET",
                "/system",
                "Identity, model profile, sensor type, water-low threshold, pump cap, default pump speed (fork).",
                ex="system",
            ),
            req(
                "Dashboard page",
                "GET",
                "/",
                "The on-device web page (HTML). Never needs a key.",
                auth=False,
            ),
        ],
    ),
    folder(
        "Sensors",
        "Read-only.",
        [
            req("Air temperature", "GET", "/temperature", "DHT20, °C.", ex="temperature"),
            req("Humidity", "GET", "/humidity", "DHT20, % RH.", ex="humidity"),
            req("PCB temperature", "GET", "/pcb-temp", "PCT2075, °C.", ex="pcb-temp"),
            req(
                "Water level",
                "GET",
                "/distance",
                "Fork: the latest reading recorded by the MQTT service (cm from the sensor to the water, gallons, age). 503 if missing or older than 3 × WATER_CHECK_SECONDS. `/distance/measure` is an alias.",
                ex="distance",
            ),
        ],
    ),
    folder(
        "Light",
        "Grow lights, GPIO18 PWM. Levels are 0–100.",
        [
            req(
                "Get brightness",
                "GET",
                "/light/brightness",
                "Read from the pin (true even after cron changes).",
                ex="light_brightness",
            ),
            req(
                "Set brightness",
                "POST",
                "/light/brightness",
                "`value` 0–100; 400 if out of range. Saves state.",
                body={"value": 30},
            ),
            req(
                "Light on",
                "POST",
                "/light/on",
                "Full brightness (100) if currently off; no change if already on.",
            ),
            req(
                "Light off",
                "POST",
                "/light/off",
                "Off now. The next scheduled ramp turns it back on.",
            ),
        ],
    ),
    folder(
        "Pump",
        PUMP + " Levels are 0–100.",
        [
            req(
                "Get speed", "GET", "/pump/speed", "Current duty; 0 when stopped.", ex="pump_speed"
            ),
            req(
                "Set speed",
                "POST",
                "/pump/speed",
                PUMP
                + " Starts the pump at `value` % (0 stops it) and arms the MAX_PUMP_RUN_SECONDS safety cut-off.",
                body={"value": 60},
            ),
            req(
                "Pump on",
                "POST",
                "/pump/on",
                PUMP
                + " Runs at DEFAULT_PUMP_SPEED (upstream: 100 %), with the MAX_PUMP_RUN_SECONDS safety cut-off.",
            ),
            req("Pump off", "POST", "/pump/off", "Stops the pump."),
            req(
                "Run for seconds",
                "POST",
                "/pump/run",
                PUMP
                + " Runs at DEFAULT_PUMP_SPEED (upstream: 100 %) for `seconds` (1–MAX_PUMP_RUN_SECONDS; default is the cap, 900). Returns at once.",
                body={"seconds": 10},
            ),
            req(
                "Pump power stats",
                "GET",
                "/pump/stats",
                "INA219 readings (bus V, mA, mW, shunt mV), read on I2C bus 1. Takes about 1 s.",
                ex="pump_stats",
            ),
        ],
    ),
    folder(
        "Schedule",
        "Stored as JSON (~/.garden_schedule.json) and compiled into the crontab. HA's sync automation overwrites changes made here (see the proposal).",
        [
            req("Get schedule", "GET", "/schedule", "Normalized per-day schedule.", ex="schedule"),
            req(
                "Set schedule",
                "POST",
                "/schedule",
                "Replaces the whole schedule and rewrites the crontab. ⚠ HA will push its own copy back within seconds. Body below is the current schedule.",
                body=schedule_now,
            ),
        ],
    ),
    folder(
        "Grow cycle",
        "Grow-cycle reminders are disabled on this device (*_REMINDER_DAYS=0); CropOps owns reminders.",
        [
            req(
                "Get grow state",
                "GET",
                "/grow",
                "Stage, start time, due and acknowledged reminders.",
                ex="grow",
            ),
            req(
                "Start cycle",
                "POST",
                "/grow/start",
                "Resets the cycle start to now. The page's Germinate preset calls this.",
            ),
            req(
                "Set stage",
                "POST",
                "/grow/stage",
                "One of germination, thinning, root_check, harvest.",
                body={"stage": "germination"},
            ),
            req(
                "Acknowledge reminder",
                "POST",
                "/grow/acknowledge",
                "Key: thinning, root_check, harvest, nutrient.",
                body={"key": "nutrient"},
            ),
        ],
    ),
    folder(
        "Pods",
        "Per-pod name and shape code, plus the plant catalog: bundled app/lib/plants.json, then valid entries from the optional custom file (PLANTS_CUSTOM_FILE, default app/lib/plants-custom.json).",
        [
            req(
                "Get pods and catalog",
                "GET",
                "/pods",
                "`pods` (30), `shapes`, `catalog` (108 bundled entries, then valid custom ones; example trimmed to 2), `catalog_problems` (skipped custom entries and why; [] when clean).",
                ex="pods",
            ),
            req(
                "Set one pod",
                "POST",
                "/pods/25",
                "Name and/or symbols for one pod; returns all pods. A pod id outside 1–POD_COUNT is silently ignored (no 404).",
                body={"name": "Cecelia Lettuce", "symbols": ["circle", "square"]},
            ),
            req(
                "Replace all pods",
                "POST",
                "/pods",
                "Whole list. ⚠ Overwrites every pod; missing ids become empty.",
                body=[{"id": 1, "name": "Thyme", "symbols": []}],
            ),
        ],
    ),
    folder(
        "Cameras",
        "Captures take about 1 s each. Responses are JPEG/MP4.",
        [
            req("Upper camera", "GET", "/camera/upper", "Fresh JPEG from /dev/gardyn-upper."),
            req("Lower camera", "GET", "/camera/lower", "Fresh JPEG from /dev/gardyn-lower."),
            req(
                "Get timelapse",
                "GET",
                "/camera/timelapse/upper",
                "MP4; 404 until one is built.",
                test=None,
            ),
            req(
                "Build timelapse",
                "POST",
                "/camera/timelapse/upper",
                "Assembles archived frames into MP4 (can take a minute).",
                test=None,
            ),
        ],
    ),
]

P = "**v2, not implemented yet.** See code.gardyn docs/proposal-schedules-presets-plants.md. "
preset = {
    "name": "Early Germinate",
    "description": "Germinate an hour earlier; off by 20:00",
    "stage": "germinate",
    "every_day": True,
    "lights": {
        "days": {
            "mon": [{"onTime": "05:00", "offTime": "20:00", "brightness": 30, "rampMinutes": 15}]
        }
    },
    "pump": {
        "days": {
            "mon": [
                {"time": "05:00", "duration": 3},
                {"time": "12:00", "duration": 3},
                {"time": "19:00", "duration": 3},
            ]
        }
    },
}
proposed = [
    folder(
        "1. Schedule revisions (two editors)",
        P
        + "Adds `meta` {revision, updated_at, updated_by, preset_id, modified} to GET /schedule; MQTT retained `gardyn/schedule/state`.",
        [
            req(
                "⚠ Set schedule (If-Match), applies on v1",
                "POST",
                "/schedule",
                P
                + "**⚠ On v1 firmware this is the v1 `POST /schedule`: the headers are ignored and the body is applied (200).** "
                "Same body as today plus headers. A stale `If-Match` revision returns 409 with the current schedule. `X-Client` is recorded as `meta.updated_by`.",
                body=schedule_now,
                headers=[("If-Match", "42"), ("X-Client", "ha")],
                test=None,
            ),
            req(
                "Patch lights only",
                "PATCH",
                "/schedule/lights",
                P + "Change one section without resending the rest.",
                body={
                    "days": {
                        "mon": [
                            {
                                "onTime": "05:00",
                                "offTime": "20:00",
                                "brightness": 30,
                                "rampMinutes": 15,
                            }
                        ]
                    }
                },
                headers=[("If-Match", "42")],
                test=None,
            ),
        ],
    ),
    folder(
        "2. Presets",
        P
        + "Built-ins move from the page's JS into app/lib/presets.json (read-only); custom presets in ~/.garden_presets.json. Responses include photoperiod_h, boost_equivalent_h, dark_h, pump_min_per_day.",
        [
            req("List presets", "GET", "/schedule/presets", P, test=None),
            req(
                "Save custom preset",
                "POST",
                "/schedule/presets",
                P + 'Or `{"from_current": true, "name": ...}` to save the active schedule.',
                body=preset,
                test=None,
            ),
            req(
                "Edit custom preset",
                "PUT",
                "/schedule/presets/custom-early-germinate",
                P + "403 for built-ins.",
                body=preset,
                test=None,
            ),
            req(
                "Delete custom preset",
                "DELETE",
                "/schedule/presets/custom-early-germinate",
                P + "403 for built-ins.",
                test=None,
            ),
            req(
                "Apply preset",
                "POST",
                "/schedule/presets/custom-early-germinate/apply",
                P + "Sets meta.preset_id and modified=false.",
                headers=[("X-Client", "ha")],
                test=None,
            ),
            req(
                "Calendar feed (ICS)",
                "GET",
                "/schedule.ics",
                P
                + "Read-only: next 14 days of light windows and pump runs as VEVENTs, for calendar display.",
                test=None,
            ),
        ],
    ),
    folder(
        "3. Plants and pods",
        P
        + "plants.json entries gain optional plant_code, source, source_url, scientific_name, family, harvest_style, light_zone, weeks{}, needs_review. A local overlay (~/.garden_plants.json) from the CropOps PlantAttributes export is merged over the bundled catalog.",
        [
            req(
                "Get merged catalog",
                "GET",
                "/plants",
                P + "Each entry tagged origin: bundled | local.",
                test=None,
            ),
            req(
                "Replace local overlay",
                "PUT",
                "/plants/local",
                P + "Written by the CropOps export (the Sheet is the master).",
                body=[
                    {
                        "plant_code": "cecelia_lettuce",
                        "name": "Cecelia Lettuce",
                        "category": "lettuce",
                        "source": "johnnys",
                        "scientific_name": "Lactuca sativa",
                        "family": "Asteraceae",
                        "harvest_style": "cut_and_come_again",
                        "light_zone": "medium",
                        "weeks": {
                            "germinate": 1,
                            "thin": 2,
                            "maturity": 6,
                            "harvest": 6,
                            "replace": 9,
                            "retire": 12,
                        },
                        "needs_review": True,
                    }
                ],
                test=None,
            ),
            req(
                "Patch one pod",
                "PATCH",
                "/pods/25",
                P
                + "Partial update; new optional fields. On v1 firmware: 405 (only POST exists on this path).",
                body={
                    "plant_code": "cecelia_lettuce",
                    "sown_on": "2026-10-26",
                    "slot_code": "C3.4",
                },
                test=None,
            ),
        ],
    ),
]

collection = {
    "info": {
        "_postman_id": uid("collection"),
        "name": "garden-of-eden API (gardyn-home3)",
        "description": (
            "REST API of the garden-of-eden firmware on the Gardyn Home 3.0, fork `grrretchen/garden-of-eden` "
            "branch `gardyn-home3`, generated against commit b0413fa (2026-10-27).\n\n"
            "**Auth:** with GARDEN_API_KEY set, every request except `/`, `/health` and `/static` needs the "
            "`X-API-Key` header (collection auth uses `{{apiKey}}`). Requests from the Pi itself skip the check.\n\n"
            "**Folders:** `v1` is the API the device serves today. `v2` holds the planned changes "
            '(on v1 firmware: 404, except `PATCH /pods/{id}` 405, and "Set schedule (If-Match)", which v1 '
            "accepts and applies).\n\n"
            "⚠ Requests in Pump and some in Light change real hardware."
        ),
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "auth": {
        "type": "apikey",
        "apikey": [
            {"key": "key", "value": "X-API-Key", "type": "string"},
            {"key": "value", "value": "{{apiKey}}", "type": "string"},
            {"key": "in", "value": "header", "type": "string"},
        ],
    },
    "variable": [{"key": "baseUrl", "value": "http://gardyn.lan:5000"}],
    "item": [
        folder("v1", "The API the device serves today (fork commit b0413fa).", current),
        folder(
            "v2",
            P
            + 'On v1 firmware these return 404, except `PATCH /pods/{id}` (405) and "Set schedule (If-Match)", which v1 accepts and applies.',
            proposed,
        ),
    ],
}
environment = {
    "id": uid("env"),
    "name": "gardyn.lan",
    "_postman_variable_scope": "environment",
    "values": [
        {"key": "baseUrl", "value": "http://gardyn.lan:5000", "type": "default", "enabled": True},
        {"key": "apiKey", "value": "", "type": "secret", "enabled": True},
    ],
}
os.makedirs(OUT, exist_ok=True)
json.dump(
    collection,
    open(os.path.join(OUT, "garden-of-eden.postman_collection.json"), "w"),
    indent=2,
    ensure_ascii=False,
)
json.dump(
    environment, open(os.path.join(OUT, "gardyn-lan.postman_environment.json"), "w"), indent=2
)


def n(items):
    return sum(n(i["item"]) if "item" in i else 1 for i in items)


print("requests:", n(collection["item"][0]["item"]), "v1,", n(collection["item"][1]["item"]), "v2")
