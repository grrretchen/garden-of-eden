import re
import unittest

from app import create_app


class WebUITestCase(unittest.TestCase):
    def setUp(self):
        self.client = create_app("default").test_client()

    def test_root_serves_html(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.content_type)
        self.assertIn(b"Garden of Eden", resp.data)

    def test_media_is_fetched_with_the_api_key(self):
        # <img>/<video> src requests can't send X-API-Key, so with a key set
        # they get 401. Camera and timelapse media must go through loadMedia.
        html = self.client.get("/").get_data(as_text=True)
        self.assertIsNone(re.search(r"\.src\s*=\s*[\"']/camera", html))
        self.assertIn('loadMedia($("cam-upper"), "/camera/upper")', html)
        self.assertIn('loadMedia($("tl-" + c), "/camera/timelapse/" + c', html)

    def test_sliders_are_synced_from_the_device(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('setSlider("brightness"', html)
        self.assertIn('setSlider("speed"', html)


if __name__ == "__main__":
    unittest.main()
