import unittest
from unittest.mock import patch

import config
from app import create_app
from app.sensors.camera import camera


class CameraRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app("default")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    @patch("app.sensors.camera.routes.camera.capture_upper")
    def test_capture_failure_returns_503(self, mock_capture):
        mock_capture.side_effect = FileNotFoundError("fswebcam missing")
        resp = self.client.get("/camera/upper")
        self.assertEqual(resp.status_code, 503)

    @patch("app.sensors.camera.routes.send_file")
    @patch("app.sensors.camera.routes.camera.capture_lower")
    def test_capture_success_serves_file(self, mock_capture, mock_send_file):
        mock_send_file.return_value = "IMG"
        resp = self.client.get("/camera/lower")
        mock_capture.assert_called_once()
        self.assertEqual(resp.status_code, 200)

    @patch("app.sensors.camera.routes.send_file", return_value="IMG")
    def test_options_and_defaults(self, _send):
        for cam in ("upper", "lower"):
            with patch("app.sensors.camera.routes.camera.capture_" + cam) as capture:
                self.assertEqual(self.client.get("/camera/" + cam).status_code, 200)
                capture.assert_called_once_with()
            for (
                resolution
            ) in "2592x1944 2560x1920 1920x1080 1280x960 1280x720 1024x768 960x540 848x480 800x600 640x480 320x240".split():
                with (
                    self.subTest(cam=cam, resolution=resolution),
                    patch("app.sensors.camera.routes.camera.capture_" + cam) as capture,
                ):
                    self.assertEqual(
                        self.client.get("/camera/" + cam + "?resolution=" + resolution).status_code,
                        200,
                    )
                    capture.assert_called_once_with(
                        resolution=resolution, skip=2, pixel_format="MJPEG"
                    )
            for skip in (2, 30, 60):
                with patch("app.sensors.camera.routes.camera.capture_" + cam) as capture:
                    self.assertEqual(
                        self.client.get("/camera/" + cam + "?skip=" + str(skip)).status_code, 200
                    )
                    capture.assert_called_once_with(skip=skip, pixel_format="MJPEG")
            with patch("app.sensors.camera.routes.camera.capture_" + cam) as capture:
                self.assertEqual(
                    self.client.get("/camera/" + cam + "?resolution=2592x1944&skip=30").status_code,
                    200,
                )
                capture.assert_called_once_with(
                    resolution="2592x1944", skip=30, pixel_format="MJPEG"
                )

    def test_invalid_options_never_capture(self):
        for cam in ("upper", "lower"):
            for query in (
                "resolution=",
                "resolution=1600x1200",
                "resolution=2592X1944",
                "resolution=640x480;id",
                "skip=",
                "skip=1",
                "skip=61",
                "skip=-2",
                "skip=2.5",
                "skip=abc",
                "skip=2&skip=30",
                "resolution=640x480&resolution=2592x1944",
            ):
                with (
                    self.subTest(cam=cam, query=query),
                    patch("app.sensors.camera.routes.camera.capture_" + cam) as capture,
                ):
                    self.assertEqual(
                        self.client.get("/camera/" + cam + "?" + query).status_code, 400
                    )
                    capture.assert_not_called()

    @patch("app.sensors.camera.camera.subprocess.run")
    def test_capture_command_legacy_and_opt_in(self, run):
        camera.capture("/dev/test", "/tmp/test.jpg")
        run.assert_called_once_with(
            [
                "fswebcam",
                "-d",
                "/dev/test",
                "--no-banner",
                "-r",
                config.CAMERA_RESOLUTION,
                "-S",
                "2",
                "/tmp/test.jpg",
            ],
            capture_output=True,
            check=True,
        )
        run.reset_mock()
        camera.capture(
            "/dev/test", "/tmp/test.jpg", resolution="2592x1944", skip=30, pixel_format="MJPEG"
        )
        run.assert_called_once_with(
            [
                "fswebcam",
                "-p",
                "MJPEG",
                "-d",
                "/dev/test",
                "--no-banner",
                "-r",
                "2592x1944",
                "-S",
                "30",
                "/tmp/test.jpg",
            ],
            capture_output=True,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
