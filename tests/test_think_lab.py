import tempfile
import unittest
from pathlib import Path

from think_lab import collect


class ThinkLabTests(unittest.TestCase):
    def test_collects_and_skips_the_same_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "instrument"
            source.mkdir()
            (source / "run.log").write_text("pressure=1.25\n", encoding="utf-8")
            config = root / "machines.toml"
            config.write_text(
                f"""
archive = "{(root / "archive").as_posix()}"
[[machines]]
name = "test-tool"
sources = [{{ path = "{source.as_posix()}", dataset = "pressure" }}]
""",
                encoding="utf-8",
            )

            self.assertEqual(collect(config), (1, 0))
            self.assertEqual(collect(config), (0, 1))
            self.assertEqual(len(list((root / "archive").rglob("run.log"))), 1)

    def test_disabled_machine_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "machines.toml"
            config.write_text(
                """
archive = "archive"
[[machines]]
name = "disabled"
enabled = false
sources = [{ path = "missing", dataset = "raw" }]
""",
                encoding="utf-8",
            )
            self.assertEqual(collect(config), (0, 0))


if __name__ == "__main__":
    unittest.main()
