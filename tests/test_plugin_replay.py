from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import plugin_replay


class PluginReplayTests(unittest.TestCase):
    @staticmethod
    def init_git_repo(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return path

    def make_files(self, base: Path) -> tuple[Path, Path, Path, Path]:
        target = base / "consumer"
        self.init_git_repo(target)
        task = target / "TASK.md"
        task.write_text("Summarize the explicit input without printing full content.\n", encoding="utf-8")
        input_file = target / "INPUT.txt"
        input_file.write_text("generic private-like smoke text\n", encoding="utf-8")
        secret = target / "secret.txt"
        secret.write_text("do not stage me\n", encoding="utf-8")
        return target, task, input_file, secret

    @staticmethod
    def fake_plugin_check(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["codex", "plugin", "list"],
            returncode=0,
            stdout="PLUGIN STATUS VERSION PATH\nsites@openai-bundled installed, enabled 0.1 /tmp/sites\n",
            stderr="",
        )

    def test_dry_run_builds_fixed_child_argv_without_launching_codex(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), mock.patch("ai_bridge_kit.plugin_replay.run_child_command") as child_run:
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    dry_run=True,
                )

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "dry_run")
            child_run.assert_not_called()
            argv = summary["child_argv"]
            self.assertEqual(argv[1], "exec")
            self.assertEqual(argv[argv.index("-c") + 1], 'approval_policy="never"')
            self.assertEqual(argv[argv.index("-s") + 1], "workspace-write")
            self.assertIn("sandbox_workspace_write.network_access=false", argv)
            self.assertIn("--disable", argv)
            self.assertEqual(argv[argv.index("--disable") + 1], "memories")
            self.assertIn("--skip-git-repo-check", argv)
            self.assertIn("--ephemeral", argv)
            self.assertNotIn("danger-full-access", argv)
            self.assertNotIn(str(target), argv)
            self.assertFalse((Path(summary["run_dir"]) / "inputs").exists())

    def test_run_stages_only_explicit_files_and_saves_local_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, input_file, secret = self.make_files(Path(tmp))

            def fake_child(command, **kwargs):
                self.assertEqual(Path(kwargs["workspace"]), Path(command[command.index("-C") + 1]))
                self.assertNotIn(str(target), command)
                self.assertIn("--add-dir", command)
                self.assertEqual(Path(command[command.index("--add-dir") + 1]).name, "outputs")
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout="approval: never\nsandbox: workspace-write [workdir, /tmp, $TMPDIR]\nchild summary\n",
                )

            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.verify_child_read_isolation",
                return_value={"status": "passed", "error_code": None, "contract_errors": []},
            ), mock.patch("ai_bridge_kit.plugin_replay.run_child_command", side_effect=fake_child):
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites@openai-bundled",
                    task_file=task,
                    input_files=[input_file],
                )

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "completed")
            staged_names = sorted(path.name for path in (Path(summary["run_dir"]) / "inputs").iterdir())
            self.assertEqual(len(staged_names), 2)
            self.assertTrue(any(name.endswith("_task_TASK.md") for name in staged_names))
            self.assertTrue(any(name.endswith("_input_INPUT.txt") for name in staged_names))
            self.assertFalse(any(secret.name == name for name in staged_names))
            self.assertIn("child summary", Path(summary["child_output_path"]).read_text(encoding="utf-8"))
            run_json = json.loads((Path(summary["run_dir"]) / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_json["exit_code"], 0)
            self.assertEqual(run_json["contract_errors"], [])
            self.assertNotIn("generic private-like smoke text", json.dumps(run_json))
            self.assertNotIn("do not stage me", json.dumps(run_json))

    def test_child_contract_drift_marks_replay_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.verify_child_read_isolation",
                return_value={"status": "passed", "error_code": None, "contract_errors": []},
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.run_child_command",
                return_value=subprocess.CompletedProcess(
                    args=["codex"],
                    returncode=0,
                    stdout="approval: on-request\nsandbox: workspace-write [workdir, /tmp, $TMPDIR] (network access enabled)\n",
                ),
            ):
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                )

            self.assertEqual(code, 70)
            self.assertEqual(summary["status"], "failed")
            run_json = json.loads((Path(summary["run_dir"]) / "run.json").read_text(encoding="utf-8"))
            self.assertIn("approval: never", " ".join(run_json["contract_errors"]))
            self.assertIn("network access enabled", " ".join(run_json["contract_errors"]))

    def test_directory_inputs_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check):
                with self.assertRaisesRegex(ValueError, "must be an explicit file"):
                    plugin_replay.run_plugin_replay(
                        target=target,
                        plugin="sites",
                        task_file=task,
                        input_files=[input_file.parent],
                    )

    def test_target_must_be_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "not-a-repo"
            target.mkdir()
            task = target / "TASK.md"
            task.write_text("task\n", encoding="utf-8")
            input_file = target / "INPUT.txt"
            input_file.write_text("input\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "target must be a real Git repository"):
                plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    dry_run=True,
                )

    def test_tilde_target_is_rejected_when_home_is_not_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"HOME": str(Path(tmp) / "home")}):
            home = Path(tmp) / "home"
            home.mkdir()
            task = home / "TASK.md"
            task.write_text("task\n", encoding="utf-8")
            input_file = home / "INPUT.txt"
            input_file.write_text("input\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "target must be a real Git repository"):
                plugin_replay.run_plugin_replay(
                    target=Path("~"),
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    dry_run=True,
                )

    def test_input_in_target_repo_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ):
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    dry_run=True,
                )

            self.assertEqual(code, 0)
            self.assertEqual(summary["inputs"][1]["source_path"], str(input_file.resolve()))

    def test_input_outside_target_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target, task, _, _ = self.make_files(Path(tmp))
            outside = Path(tmp) / "private" / "INPUT.txt"
            outside.parent.mkdir()
            outside.write_text("outside\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input is outside authorized plugin replay roots"):
                plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[outside],
                    dry_run=True,
                )

    def test_fake_ssh_secret_outside_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target, task, _, _ = self.make_files(Path(tmp))
            fake_secret = Path(tmp) / "home" / ".ssh" / "id_rsa"
            fake_secret.parent.mkdir(parents=True)
            fake_secret.write_text("fake secret\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input is outside authorized plugin replay roots"):
                plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[fake_secret],
                    dry_run=True,
                )

    def test_symlink_escape_from_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target, task, _, _ = self.make_files(Path(tmp))
            outside = Path(tmp) / "outside"
            outside.mkdir()
            secret = outside / "id_rsa"
            secret.write_text("fake secret\n", encoding="utf-8")
            link = target / "link"
            link.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "input is outside authorized plugin replay roots"):
                plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[link / "id_rsa"],
                    dry_run=True,
                )

    def test_trusted_plugin_replay_inbox_input_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, _, _ = self.make_files(Path(tmp))
            inbox_input = plugin_replay.trusted_inbox() / "INBOX.txt"
            inbox_input.parent.mkdir(parents=True)
            inbox_input.write_text("trusted inbox input\n", encoding="utf-8")
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ):
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[inbox_input],
                    dry_run=True,
                )

            self.assertEqual(code, 0)
            self.assertEqual(summary["inputs"][1]["source_path"], str(inbox_input.resolve()))

    def test_task_in_caller_repo_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, _, input_file, _ = self.make_files(Path(tmp))
            caller = self.init_git_repo(Path(tmp) / "caller")
            task = caller / "TASK.md"
            task.write_text("caller repo task\n", encoding="utf-8")
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ):
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    caller_cwd=caller,
                    dry_run=True,
                )

            self.assertEqual(code, 0)
            self.assertEqual(summary["inputs"][0]["source_path"], str(task.resolve()))

    def test_task_in_arbitrary_private_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target, _, input_file, _ = self.make_files(Path(tmp))
            task = Path(tmp) / "private" / "TASK.md"
            task.parent.mkdir()
            task.write_text("private task\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "task file is outside authorized plugin replay roots"):
                plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    caller_cwd=Path(tmp),
                    dry_run=True,
                )

    def test_cli_has_no_public_codex_home_option(self) -> None:
        with self.assertRaises(SystemExit):
            plugin_replay.build_parser().parse_args(
                [
                    "--target",
                    "/tmp",
                    "--plugin",
                    "sites",
                    "--task",
                    "/tmp/TASK.md",
                    "--input",
                    "/tmp/INPUT.txt",
                    "--codex-home",
                    "/tmp/other-codex-home",
                    "--dry-run",
                ]
            )

    def test_internal_codex_home_cannot_cross_current_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"CODEX_HOME": str(Path(tmp) / "current")}):
            target, task, input_file, _ = self.make_files(Path(tmp))
            with self.assertRaisesRegex(ValueError, "cannot select another Codex identity"):
                plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    codex_home=Path(tmp) / "other",
                    dry_run=True,
                )

    def test_read_isolation_failure_fails_closed_without_copying_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.verify_child_read_isolation",
                return_value={
                    "status": "failed",
                    "error_code": plugin_replay.READ_ISOLATION_ERROR,
                    "exit_code": 0,
                    "result_marker": "READABLE",
                    "contract_errors": [],
                },
            ), mock.patch("ai_bridge_kit.plugin_replay.run_child_command") as child_run:
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                )

            self.assertEqual(code, 71)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["error_code"], plugin_replay.READ_ISOLATION_ERROR)
            child_run.assert_not_called()
            self.assertFalse((Path(summary["run_dir"]) / "inputs").exists())

    def test_uninstalled_plugin_is_rejected_when_cli_can_inspect_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch(
                "ai_bridge_kit.plugin_replay._run_codex",
                return_value=subprocess.CompletedProcess(
                    args=["codex", "plugin", "list"],
                    returncode=0,
                    stdout="PLUGIN STATUS VERSION PATH\nsites@openai-bundled not installed /tmp/sites\n",
                    stderr="",
                ),
            ):
                with self.assertRaisesRegex(ValueError, "not installed"):
                    plugin_replay.run_plugin_replay(
                        target=target,
                        plugin="sites",
                        task_file=task,
                        input_files=[input_file],
                    )

    def test_plugin_check_unavailable_is_recorded_not_fabricated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch(
                "ai_bridge_kit.plugin_replay._run_codex",
                return_value=subprocess.CompletedProcess(args=["codex"], returncode=2, stdout="", stderr="no plugin command"),
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ):
                summary, code = plugin_replay.run_plugin_replay(
                    target=target,
                    plugin="sites",
                    task_file=task,
                    input_files=[input_file],
                    dry_run=True,
                )

            self.assertEqual(code, 0)
            run_json = json.loads((Path(summary["run_dir"]) / "run.json").read_text(encoding="utf-8"))
            self.assertFalse(run_json["plugin_check"]["checked"])
            self.assertIn("no plugin command", run_json["plugin_check"]["reason"])

    def test_cli_rejects_arbitrary_codex_flag_passthrough(self) -> None:
        with self.assertRaises(SystemExit):
            plugin_replay.main(
                [
                    "--target",
                    "/tmp",
                    "--plugin",
                    "sites",
                    "--task",
                    "/tmp/TASK.md",
                    "--input",
                    "/tmp/INPUT.txt",
                    "--extra-codex-args",
                    "--dangerously-bypass-approvals-and-sandbox",
                ]
            )

    def test_cli_rejects_danger_full_access_argument(self) -> None:
        with self.assertRaises(SystemExit):
            plugin_replay.main(
                [
                    "--target",
                    "/tmp",
                    "--plugin",
                    "sites",
                    "--task",
                    "/tmp/TASK.md",
                    "--input",
                    "/tmp/INPUT.txt",
                    "--sandbox",
                    "danger-full-access",
                ]
            )

    def test_bridge_cli_routes_plugin_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            target, task, input_file, _ = self.make_files(Path(tmp))
            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=self.fake_plugin_check), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), contextlib.redirect_stdout(io.StringIO()) as output:
                code = bridge_cli.main(
                    [
                        "plugin-replay",
                        "--target",
                        str(target),
                        "--plugin",
                        "sites",
                        "--task",
                        str(task),
                        "--input",
                        str(input_file),
                        "--dry-run",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["plugin"], "sites")
            self.assertEqual(payload["status"], "dry_run")


if __name__ == "__main__":
    unittest.main()
