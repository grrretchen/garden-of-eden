"""Plant catalog: bundled plants.json plus the optional custom file."""

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import config
from app import create_app
from app.lib import pods as pods_lib

with open(pods_lib._CATALOG_PATH) as _fh:
    BUNDLED = json.load(_fh)
SHIPPED_CUSTOM = os.path.join(os.path.dirname(pods_lib._CATALOG_PATH), "plants-custom.json")


def plant(name, **changes):
    entry = {
        "name": name,
        "category": "herb",
        "days_to_harvest": "30-40",
        "light_need": "medium",
        "difficulty": "easy",
        "guide": "A test guide.",
    }
    entry.update(changes)
    return entry


class CustomCatalogTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "plants-custom.json")
        patcher = mock.patch.object(config, "PLANTS_CUSTOM_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, data):
        with open(self.path, "w") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))

    def test_missing_custom_file_keeps_bundled_catalog(self):
        catalog, problems = pods_lib.load_catalog_with_problems()
        self.assertEqual(catalog, BUNDLED)
        self.assertEqual(problems, [])
        self.assertEqual(pods_lib.load_catalog(), BUNDLED)

    def test_valid_custom_entries_follow_bundled_in_file_order(self):
        self.write([plant("Zeta Test Herb"), plant("Alpha Test Herb")])
        catalog, problems = pods_lib.load_catalog_with_problems()
        self.assertEqual(problems, [])
        self.assertEqual(catalog[: len(BUNDLED)], BUNDLED)
        self.assertEqual(
            [p["name"] for p in catalog[len(BUNDLED) :]], ["Zeta Test Herb", "Alpha Test Herb"]
        )

    def test_malformed_json_keeps_bundled_and_reports(self):
        self.write("[{not json")
        catalog, problems = pods_lib.load_catalog_with_problems()
        self.assertEqual(catalog, BUNDLED)
        self.assertEqual(len(problems), 1)
        self.assertIsNone(problems[0]["index"])

    def test_non_list_file_keeps_bundled_and_reports(self):
        self.write({"name": "Not A List"})
        catalog, problems = pods_lib.load_catalog_with_problems()
        self.assertEqual(catalog, BUNDLED)
        self.assertIn("JSON list", problems[0]["problem"])

    def test_bundled_wins_name_conflicts(self):
        bundled_name = BUNDLED[0]["name"]
        # Differs only in case and spacing: still the same plant.
        variant = "  " + bundled_name.upper().replace(" ", "   ") + " "
        self.write([plant(variant, guide="Custom guide that must not replace canon.")])
        catalog, problems = pods_lib.load_catalog_with_problems()
        self.assertEqual(catalog, BUNDLED)
        self.assertEqual(problems[0]["index"], 0)
        self.assertIn("bundled", problems[0]["problem"])

    def test_duplicate_custom_names_keep_the_first(self):
        self.write([plant("Test Basil", guide="First."), plant("test basil", guide="Second.")])
        catalog, problems = pods_lib.load_catalog_with_problems()
        added = catalog[len(BUNDLED) :]
        self.assertEqual([p["guide"] for p in added], ["First."])
        self.assertEqual(problems[0]["index"], 1)
        self.assertIn("earlier custom", problems[0]["problem"])

    def test_invalid_entries_are_skipped_individually(self):
        too_long_name = "N" * (pods_lib.MAX_NAME + 1)
        reordered = {k: plant("Reordered")[k] for k in reversed(pods_lib.CATALOG_FIELDS)}
        extra = dict(plant("Extra Field"), sku="1346.5")
        self.write(
            [
                plant("Good One"),
                reordered,
                extra,
                plant("Bad Category", category="vegetable"),
                plant("Bad Light", light_need="bright"),
                plant("Bad Difficulty", difficulty="trivial"),
                plant(too_long_name),
                plant("Long Guide", guide="g" * (pods_lib.MAX_GUIDE + 1)),
                plant("Number Days", days_to_harvest=40),
                plant("Blank Guide", guide="  "),
                "not an object",
                plant("Good Two"),
            ]
        )
        catalog, problems = pods_lib.load_catalog_with_problems()
        self.assertEqual([p["name"] for p in catalog[len(BUNDLED) :]], ["Good One", "Good Two"])
        self.assertEqual([p["index"] for p in problems], list(range(1, 11)))

    def test_entries_at_the_limits_are_accepted(self):
        self.write([plant("N" * pods_lib.MAX_NAME, guide="g" * pods_lib.MAX_GUIDE)])
        catalog, problems = pods_lib.load_catalog_with_problems()
        self.assertEqual(problems, [])
        self.assertEqual(len(catalog), len(BUNDLED) + 1)


class ShippedCatalogTestCase(unittest.TestCase):
    """The curated app/lib/plants-custom.json must load without problems."""

    def test_shipped_custom_file_is_clean(self):
        with mock.patch.object(config, "PLANTS_CUSTOM_FILE", SHIPPED_CUSTOM):
            catalog, problems = pods_lib.load_catalog_with_problems()
        with open(SHIPPED_CUSTOM) as fh:
            custom = json.load(fh)
        self.assertEqual(problems, [])
        self.assertEqual(catalog, BUNDLED + custom)
        names = [pods_lib._normalized_name(p["name"]) for p in catalog]
        self.assertEqual(len(names), len(set(names)))

    def test_bundled_catalog_fits_the_same_schema(self):
        # The custom-entry rules are taken from the bundled catalog; keep them in step.
        self.assertEqual([p["name"] for p in BUNDLED if pods_lib._entry_problem(p)], [])


class PodsRouteCatalogTestCase(unittest.TestCase):
    def setUp(self):
        self.client = create_app("default").test_client()

    def test_get_pods_serves_merged_catalog_and_problems(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "plants-custom.json")
            with open(path, "w") as fh:
                json.dump([plant("Route Test Herb"), plant(BUNDLED[0]["name"])], fh)
            with mock.patch.object(config, "PLANTS_CUSTOM_FILE", path):
                body = self.client.get("/pods").get_json()
        self.assertEqual(len(body["catalog"]), len(BUNDLED) + 1)
        self.assertEqual(body["catalog"][-1]["name"], "Route Test Herb")
        self.assertEqual(len(body["catalog_problems"]), 1)
        self.assertEqual(len(body["pods"]), config.POD_COUNT)

    def test_get_pods_without_custom_file(self):
        with mock.patch.object(config, "PLANTS_CUSTOM_FILE", "/nonexistent/plants-custom.json"):
            body = self.client.get("/pods").get_json()
        self.assertEqual(body["catalog"], BUNDLED)
        self.assertEqual(body["catalog_problems"], [])


if __name__ == "__main__":
    unittest.main()
