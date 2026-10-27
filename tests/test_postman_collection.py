"""The Postman collection's v1 folder must match the app's real routes.

Every v1 request has to hit a registered route with the same method, and every
API route needs a v1 request (except the ones listed in NOT_IN_COLLECTION), so
the collection can't drift from the firmware.
"""

import json
import os
import re
import unittest

from app import create_app

COLLECTION = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "postman",
    "garden-of-eden.postman_collection.json",
)

# Routes deliberately left out: Flask's static files, and an alias that the
# /distance request's description mentions.
NOT_IN_COLLECTION = {("GET", "/static/<path:filename>"), ("GET", "/distance/measure")}


def _requests(items, folder=""):
    for item in items:
        if "item" in item:
            yield from _requests(item["item"], folder + "/" + item["name"])
        else:
            url = item["request"]["url"]["raw"].replace("{{baseUrl}}", "")
            yield folder, item["request"]["method"], url


class PostmanCollectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app("default")
        cls.routes = {
            (method, rule.rule): re.compile(
                "^"
                + re.sub(
                    r"<(?:\w+:)?\w+>",
                    "[^/]+",
                    re.escape(rule.rule).replace("\\<", "<").replace("\\>", ">"),
                )
                + "$"
            )
            for rule in app.url_map.iter_rules()
            for method in rule.methods - {"HEAD", "OPTIONS"}
        }
        with open(COLLECTION) as fh:
            collection = json.load(fh)
        cls.v1 = [r for r in _requests(collection["item"]) if r[0].startswith("/v1")]

    def _route_for(self, method, url):
        for (m, rule), pattern in self.routes.items():
            if m == method and pattern.match(url):
                return rule
        return None

    def test_every_v1_request_hits_a_route(self):
        for folder, method, url in self.v1:
            with self.subTest(request=f"{method} {url}", folder=folder):
                self.assertIsNotNone(self._route_for(method, url))

    def test_every_route_has_a_v1_request(self):
        covered = {(m, self._route_for(m, url)) for _, m, url in self.v1}
        missing = set(self.routes) - covered - NOT_IN_COLLECTION
        self.assertEqual(missing, set(), "routes without a v1 request in the Postman collection")


if __name__ == "__main__":
    unittest.main()
