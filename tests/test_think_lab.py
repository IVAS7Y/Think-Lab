import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "src" / "think_lab.py"
SPEC = importlib.util.spec_from_file_location("think_lab", MODULE_PATH)
think_lab = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(think_lab)


class ConfigurationTests(unittest.TestCase):
    def test_repository_configuration_loads(self):
        path = Path(__file__).parents[1] / "config" / "instruments.toml"
        config = think_lab.load_config(path)
        enabled = [item["id"] for item in think_lab.enabled_instruments(config)]
        self.assertEqual(enabled, ["mvd", "fiji1", "fiji2", "savannah"])
        think_lab.validate_clock(
            config["settings"],
            dt.datetime(2026, 8, 15, tzinfo=dt.timezone.utc),
        )

    def test_duplicate_instrument_is_rejected(self):
        content = b"""
[settings]
staging_root = "/tmp"
[[instruments]]
id = "same"
display_name = "One"
mount = "/mnt/one"
oak_directory = "One"
[[instruments]]
id = "same"
display_name = "Two"
mount = "/mnt/two"
oak_directory = "Two"
"""
        with tempfile.NamedTemporaryFile(delete=False) as stream:
            stream.write(content)
            path = Path(stream.name)
        try:
            with self.assertRaises(think_lab.WorkflowError):
                think_lab.load_config(path)
        finally:
            path.unlink()


class SelectionTests(unittest.TestCase):
    def test_recent_file_selection_uses_modification_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_file = root / "old.txt"
            new_file = root / "new.txt"
            old_file.write_text("old", encoding="utf-8")
            new_file.write_text("new", encoding="utf-8")
            old_time = time.time() - 60 * 24 * 60 * 60
            old_file.touch()
            import os
            os.utime(old_file, (old_time, old_time))
            cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=30)
            selected = list(think_lab.recent_relative_files(root, cutoff))
            self.assertEqual(selected, ["new.txt"])

    def test_invalid_clock_is_rejected(self):
        settings = {"minimum_valid_time": "2026-08-14T00:00:00+00:00"}
        now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
        with self.assertRaises(think_lab.WorkflowError):
            think_lab.validate_clock(settings, now)


class CleanupTests(unittest.TestCase):
    def make_config(self, staging_root: str) -> dict:
        return {
            "settings": {
                "staging_root": staging_root,
                "retention_days": 30,
                "minimum_valid_time": "2026-08-14T00:00:00+00:00",
            },
            "instruments": [],
        }

    def test_cleanup_report_does_not_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            staged_file = Path(directory) / "sample.txt"
            staged_file.write_text("data", encoding="utf-8")
            config = self.make_config(directory)
            with (
                mock.patch.object(think_lab, "birth_epoch", return_value=1),
                mock.patch.object(think_lab, "process_lock", return_value=mock.MagicMock()),
            ):
                result = think_lab.cleanup(config, delete=False)
            self.assertEqual(result, 0)
            self.assertTrue(staged_file.exists())

    def test_cleanup_delete_removes_only_eligible_file(self):
        with tempfile.TemporaryDirectory() as directory:
            staged_file = Path(directory) / "sample.txt"
            staged_file.write_text("data", encoding="utf-8")
            config = self.make_config(directory)
            with (
                mock.patch.object(think_lab, "birth_epoch", return_value=1),
                mock.patch.object(think_lab, "process_lock", return_value=mock.MagicMock()),
            ):
                result = think_lab.cleanup(config, delete=True)
            self.assertEqual(result, 0)
            self.assertFalse(staged_file.exists())


if __name__ == "__main__":
    unittest.main()
