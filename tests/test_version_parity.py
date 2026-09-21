from __future__ import annotations

import unittest
from pathlib import Path

import ai_bridge_kit


REPO_ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    for line in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError("pyproject.toml project version not found")


class VersionParityTests(unittest.TestCase):
    def test_runtime_version_matches_project_metadata_version(self) -> None:
        self.assertEqual(ai_bridge_kit.__version__, _project_version())


if __name__ == "__main__":
    unittest.main()
