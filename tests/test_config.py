import importlib
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigParsingTestCase(unittest.TestCase):
    """config.py uses helpers to parse env vars; verify hex/bool/int parsing."""

    def _reload(self, **env):
        for k, v in env.items():
            os.environ[k] = v
        try:
            import config

            return importlib.reload(config)
        finally:
            for k in env:
                os.environ.pop(k, None)

    def test_hex_address_parsing(self):
        cfg = self._reload(PCB_TEMP_ADDRESS="0x48", INA219_ADDRESS="0x40")
        self.assertEqual(cfg.PCB_TEMP_ADDRESS, 0x48)
        self.assertEqual(cfg.INA219_ADDRESS, 0x40)

    def test_decimal_pin_parsing(self):
        cfg = self._reload(LIGHT_PIN="18", PUMP_PIN="24")
        self.assertEqual(cfg.LIGHT_PIN, 18)
        self.assertEqual(cfg.PUMP_PIN, 24)

    def test_bool_parsing(self):
        cfg = self._reload(TELEGRAF_ENABLED="true", ALEXA_ENABLED="0")
        self.assertTrue(cfg.TELEGRAF_ENABLED)
        self.assertFalse(cfg.ALEXA_ENABLED)

    def test_water_low_zero_disables(self):
        cfg = self._reload(WATER_LOW_CM="0")
        self.assertIsNone(cfg.WATER_LOW_CM)


class EnvFileLocationTestCase(unittest.TestCase):
    """cron runs `python -c 'import config'` from $HOME; the repo .env must
    still be the one loaded, not whatever .env sits in the working directory."""

    def _config_from(self, cwd, expr):
        env = {k: v for k, v in os.environ.items() if k != "DEFAULT_PUMP_SPEED"}
        env["PYTHONPATH"] = REPO_ROOT
        out = subprocess.run(
            [sys.executable, "-c", f"import config; print({expr})"],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()

    def test_env_file_is_next_to_config(self):
        with tempfile.TemporaryDirectory() as cwd:
            self.assertEqual(
                self._config_from(cwd, "config.ENV_FILE"), os.path.join(REPO_ROOT, ".env")
            )

    def test_working_directory_env_is_ignored(self):
        with tempfile.TemporaryDirectory() as cwd:
            with open(os.path.join(cwd, ".env"), "w") as fh:
                fh.write("DEFAULT_PUMP_SPEED=7\n")
            self.assertNotEqual(self._config_from(cwd, "config.DEFAULT_PUMP_SPEED"), "7")


if __name__ == "__main__":
    unittest.main()
