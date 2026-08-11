from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import private


class PrivateSyncTests(unittest.TestCase):
    def test_missing_rclone_reports_code(self) -> None:
        with mock.patch("ai_bridge_kit.private.shutil.which", return_value=None):
            code, lines = private.sync_private("notifier", env={"AI_BRIDGE_PRIVATE_RCLONE_SOURCE": "remote:path"})

        self.assertEqual(code, 1)
        self.assertEqual(lines, ["RCLONE_NOT_CONFIGURED"])

    def test_missing_source_reports_unavailable(self) -> None:
        with mock.patch("ai_bridge_kit.private.shutil.which", return_value="/usr/bin/rclone"):
            code, lines = private.sync_private("notifier", env={})

        self.assertEqual(code, 1)
        self.assertIn("PRIVATE_SOURCE_UNAVAILABLE", lines[0])

    def test_source_unavailable_does_not_print_secret_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch("ai_bridge_kit.private.shutil.which", return_value="/usr/bin/rclone"):
            with mock.patch("ai_bridge_kit.private.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "not found")):
                cwd = os.getcwd()
                os.chdir(tmp)
                try:
                    code, lines = private.sync_private(
                        "notifier",
                        env={"AI_BRIDGE_PRIVATE_RCLONE_SOURCE": "secretremote:Private/GPT_Codex_AI_Bridge_Kit/notifier.env"},
                    )
                finally:
                    os.chdir(cwd)

        self.assertEqual(code, 1)
        text = "\n".join(lines)
        self.assertIn("PRIVATE_SOURCE_UNAVAILABLE", text)
        self.assertNotIn("secretremote", text)

    def test_successful_sync_writes_0600_and_redacts_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch("ai_bridge_kit.private.shutil.which", return_value="/usr/bin/rclone"):
            root = Path(tmp)

            def fake_run(args, text, stdout, stderr, check):
                target = Path(args[-1])
                target.write_text(
                    "AI_BRIDGE_NOTIFY_SMTP_USER=sender@example.org\n"
                    "AI_BRIDGE_NOTIFY_SMTP_PASSWORD=secret\n"
                    "AI_BRIDGE_NOTIFY_FROM=sender@example.org\n"
                    "AI_BRIDGE_NOTIFY_TO=recipient@example.org\n",
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(args, 0, "", "")

            with mock.patch("ai_bridge_kit.private.subprocess.run", side_effect=fake_run):
                cwd = os.getcwd()
                os.chdir(root)
                try:
                    code, lines = private.sync_private("notifier", env={"AI_BRIDGE_PRIVATE_RCLONE_SOURCE": "remote:private/notifier.env"})
                    target = root / ".ai-bridge" / "private" / "notifier.env"
                    target_exists = target.exists()
                    target_mode = target.stat().st_mode & 0o777
                finally:
                    os.chdir(cwd)

        self.assertEqual(code, 0)
        self.assertTrue(target_exists)
        self.assertEqual(target_mode, 0o600)
        output = "\n".join(lines)
        self.assertNotIn("secret", output)
        self.assertIn("Secrets: redacted", output)

    def test_downloaded_private_file_is_gitignored(self) -> None:
        proc = subprocess.run(
            ["git", "check-ignore", ".ai-bridge/private/notifier.env"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_public_example_uses_only_example_org(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "templates" / "private" / "notifier.env.example").read_text(encoding="utf-8")

        self.assertIn("sender@example.org", text)
        self.assertIn("recipient@example.org", text)
        self.assertNotIn("gmail.com", text)


if __name__ == "__main__":
    unittest.main()
