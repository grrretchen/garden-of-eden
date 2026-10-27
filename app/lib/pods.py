"""Per-pod plant tracking: each pod has a name and a short 'shape code' (a
sequence of geometric symbols) that mirrors the glyphs printed on the physical
Gardyn pod, so you can match a row in the UI to a pod in the tower.

State is a list of POD_COUNT pods persisted as JSON. Unknown shapes and overlong
names/codes are dropped on normalize so the file can't drift out of spec.

The plant catalog is the bundled plants.json plus an optional custom file
(config.PLANTS_CUSTOM_FILE) in the same six-field format. Bundled entries are
canon: a custom entry that repeats a bundled name, or an earlier custom name, is
skipped and reported, as is any custom entry that doesn't fit the schema.
"""

import json
import logging
import os

import config
from app.lib.persist import write_json_atomic

logger = logging.getLogger(__name__)

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "plants.json")

# Every catalog entry has exactly these fields, in this order, as in plants.json.
CATALOG_FIELDS = ("name", "category", "days_to_harvest", "light_need", "difficulty", "guide")
# The values the bundled catalog uses; custom entries must use them too.
CATEGORIES = ("brassica/kale", "flower", "fruiting", "herb", "leafy-green/lettuce")
LIGHT_NEEDS = ("low", "medium", "high")
DIFFICULTIES = ("easy", "medium", "hard")
MAX_GUIDE = 190  # the longest bundled guide

# Allowed symbol keys; the UI renders each as a geometric glyph.
SHAPES = ["circle", "square", "triangle", "diamond", "star", "hexagon", "heart", "plus"]
MAX_SYMBOLS = 5
MAX_NAME = 40


def default_pods():
    return [{"id": i + 1, "name": "", "symbols": []} for i in range(config.POD_COUNT)]


def _load_bundled():
    try:
        with open(_CATALOG_PATH) as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return []


def _normalized_name(name):
    """Case- and whitespace-insensitive key for comparing plant names."""
    return " ".join(str(name).casefold().split())


def _entry_problem(entry):
    """Why a custom catalog entry can't be used, or None if it fits the schema."""
    if not isinstance(entry, dict) or tuple(entry) != CATALOG_FIELDS:
        return "fields must be exactly " + ", ".join(CATALOG_FIELDS) + ", in that order"
    if not all(isinstance(entry[f], str) and entry[f].strip() for f in CATALOG_FIELDS):
        return "every field must be a non-empty string"
    if entry["category"] not in CATEGORIES:
        return f"unknown category {entry['category']!r}"
    if entry["light_need"] not in LIGHT_NEEDS:
        return f"unknown light_need {entry['light_need']!r}"
    if entry["difficulty"] not in DIFFICULTIES:
        return f"unknown difficulty {entry['difficulty']!r}"
    if len(entry["name"]) > MAX_NAME:
        return f"name longer than {MAX_NAME} characters"
    if len(entry["guide"]) > MAX_GUIDE:
        return f"guide longer than {MAX_GUIDE} characters"
    return None


def load_catalog_with_problems():
    """The bundled catalog followed by the valid custom entries, plus a list of
    problems ({"index", "name", "problem"}) for custom entries that were skipped.
    A missing custom file is not a problem; an unreadable one is (index None)."""
    catalog = _load_bundled()
    problems = []
    path = config.PLANTS_CUSTOM_FILE
    try:
        with open(path) as fh:
            custom = json.load(fh)
    except FileNotFoundError:
        return catalog, problems
    except (OSError, ValueError) as exc:
        custom = exc
    if not isinstance(custom, list):
        reason = custom if isinstance(custom, Exception) else "top level must be a JSON list"
        problems.append({"index": None, "name": None, "problem": f"{path}: {reason}"})
        logger.error("Custom plant catalog ignored: %s: %s", path, reason)
        return catalog, problems

    bundled = {_normalized_name(p.get("name", "")) for p in catalog if isinstance(p, dict)}
    seen = set()
    for index, entry in enumerate(custom):
        name = entry.get("name") if isinstance(entry, dict) else None
        problem = _entry_problem(entry)
        if problem is None:
            key = _normalized_name(name)
            if key in bundled:
                problem = "duplicates a bundled entry (bundled kept)"
            elif key in seen:
                problem = "duplicates an earlier custom entry (first kept)"
            seen.add(key)
        if problem:
            problems.append({"index": index, "name": name, "problem": problem})
            logger.warning("Custom plant #%s %r skipped: %s", index, name, problem)
        else:
            catalog.append(entry)
    return catalog, problems


def load_catalog():
    """The plant variety catalog (name/category/light/difficulty/guide) used to
    populate the UI's variety picker: bundled plants.json, then any valid custom
    entries. Returns [] if the bundled data file is missing."""
    return load_catalog_with_problems()[0]


def _clean(pod):
    name = str(pod.get("name", ""))[:MAX_NAME]
    symbols = [s for s in (pod.get("symbols") or []) if s in SHAPES][:MAX_SYMBOLS]
    return name, symbols


def normalize(data):
    """Return exactly POD_COUNT pods (id 1..N), merging any saved entries by id."""
    by_id = {}
    if isinstance(data, list):
        for pod in data:
            try:
                by_id[int(pod.get("id"))] = pod
            except (TypeError, ValueError):
                continue
    pods = []
    for i in range(config.POD_COUNT):
        pid = i + 1
        name, symbols = _clean(by_id.get(pid, {}))
        pods.append({"id": pid, "name": name, "symbols": symbols})
    return pods


def load_pods():
    try:
        with open(config.PODS_FILE) as fh:
            return normalize(json.load(fh))
    except (FileNotFoundError, ValueError):
        return default_pods()


def save_pods(pods):
    normalized = normalize(pods)
    write_json_atomic(config.PODS_FILE, normalized)
    return normalized


def set_pod(pod_id, name=None, symbols=None):
    """Update a single pod's name and/or symbols; returns the full pod list."""
    pod_id = int(pod_id)
    pods = load_pods()
    for pod in pods:
        if pod["id"] == pod_id:
            if name is not None:
                pod["name"] = str(name)[:MAX_NAME]
            if symbols is not None:
                pod["symbols"] = [s for s in symbols if s in SHAPES][:MAX_SYMBOLS]
            break
    return save_pods(pods)
