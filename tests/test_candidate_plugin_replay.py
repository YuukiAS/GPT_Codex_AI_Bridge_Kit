from __future__ import annotations

import contextlib
import io
import json
import multiprocessing
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import candidate_plugin_replay


class CandidatePluginReplayTests(unittest.TestCase):
    @staticmethod
    def init_git_repo(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
        return path

    def make_candidate_repo(
        self,
        base: Path,
        *,
        manifest_plugins: list[dict] | None = None,
    ) -> tuple[Path, str, Path, Path]:
        repo = self.init_git_repo(base / "repo")
        plugin_dir = repo / "plugins" / "visualize"
        skill_dir = plugin_dir / "skills" / "visualize"
        skill_dir.mkdir(parents=True)
        (plugin_dir / ".codex-plugin").mkdir()
        (plugin_dir / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"id": "visualize", "version": "0.8.0-test"}) + "\n",
            encoding="utf-8",
        )
        (skill_dir / "SKILL.md").write_text("candidate marker v1\n", encoding="utf-8")
        task = repo / "TASK.md"
        task.write_text("Use the visualize plugin.\n", encoding="utf-8")
        input_file = repo / "INPUT.txt"
        input_file.write_text("input\n", encoding="utf-8")
        plugins = manifest_plugins
        if plugins is None:
            plugins = [
                {
                    "name": "visualize",
                    "source": {"source": "local", "path": "./plugins/visualize"},
                    "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                }
            ]
        manifest_path = repo / ".agents" / "plugins" / "marketplace.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(json.dumps({"name": "test", "plugins": plugins}) + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "candidate"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        return repo, commit, task, input_file

    def test_invalid_candidate_commit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, _, _ = self.make_candidate_repo(Path(tmp))
            with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_COMMIT_INVALID):
                candidate_plugin_replay.resolve_candidate_source(repo, "visualize", "does-not-exist")

    def test_missing_committed_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.init_git_repo(Path(tmp) / "repo")
            (repo / "README.md").write_text("no manifest\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "no manifest"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_MARKETPLACE_MANIFEST_INVALID):
                candidate_plugin_replay.resolve_candidate_source(repo, "visualize", commit)

    def test_zero_and_multiple_manifest_matches_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit, _, _ = self.make_candidate_repo(Path(tmp) / "zero")
            with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_PLUGIN_NOT_FOUND):
                candidate_plugin_replay.resolve_candidate_source(repo, "missing", commit)

        with tempfile.TemporaryDirectory() as tmp:
            entries = [
                {"name": "visualize", "source": {"source": "local", "path": "./plugins/visualize"}},
                {"name": "visualize", "source": {"source": "local", "path": "./plugins/visualize"}},
            ]
            repo, commit, _, _ = self.make_candidate_repo(Path(tmp) / "multi", manifest_plugins=entries)
            with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_MARKETPLACE_MANIFEST_INVALID):
                candidate_plugin_replay.resolve_candidate_source(repo, "visualize", commit)

    def test_non_local_and_path_escape_sources_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit, _, _ = self.make_candidate_repo(
                Path(tmp) / "nonlocal",
                manifest_plugins=[{"name": "visualize", "source": {"source": "github", "path": "./plugins/visualize"}}],
            )
            with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_PLUGIN_SOURCE_INVALID):
                candidate_plugin_replay.resolve_candidate_source(repo, "visualize", commit)

        with tempfile.TemporaryDirectory() as tmp:
            repo, commit, _, _ = self.make_candidate_repo(
                Path(tmp) / "escape",
                manifest_plugins=[{"name": "visualize", "source": {"source": "local", "path": "../outside"}}],
            )
            with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_PLUGIN_SOURCE_INVALID):
                candidate_plugin_replay.resolve_candidate_source(repo, "visualize", commit)

    def test_dirty_worktree_does_not_affect_staged_candidate_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit, _, _ = self.make_candidate_repo(Path(tmp))
            dirty_skill = repo / "plugins" / "visualize" / "skills" / "visualize" / "SKILL.md"
            dirty_skill.write_text("dirty marker should not stage\n", encoding="utf-8")
            candidate = candidate_plugin_replay.resolve_candidate_source(repo, "visualize", commit)
            run_dir = Path(tmp) / "run"
            _, staged_plugin_path, _ = candidate_plugin_replay.stage_candidate_marketplace(
                target_repo=repo,
                candidate=candidate,
                plugin="visualize",
                run_dir=run_dir,
                marketplace_name="ai-bridge-candidate-test",
            )

            staged_text = (staged_plugin_path / "skills" / "visualize" / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(staged_text, "candidate marker v1\n")

    def test_b0_child_argv_uses_ignore_user_config_and_no_persistent_marketplace_command(self) -> None:
        argv = candidate_plugin_replay._build_candidate_child_argv(
            workspace=Path("/tmp/workspace"),
            outputs_dir=Path("/tmp/outputs"),
            codex_executable="/trusted/bin/codex",
            marketplace_name="ai-bridge-candidate-run",
            marketplace_root=Path("/tmp/marketplace"),
            plugin_id="visualize@ai-bridge-candidate-run",
            json_events=True,
        )

        self.assertEqual(argv[:3], ["/trusted/bin/codex", "exec", "--ignore-user-config"])
        self.assertIn("--json", argv)
        self.assertIn('marketplaces.ai-bridge-candidate-run.source_type="local"', argv)
        self.assertIn("plugins.visualize@ai-bridge-candidate-run.enabled=true", argv)
        self.assertNotIn("marketplace", " ".join(argv[:3]))
        self.assertNotIn('plugins."visualize@ai-bridge-candidate-run".enabled=true', argv)

    def test_active_json_is_written_before_plugin_add_and_success_cleans_owned_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state"), "CODEX_HOME": str(Path(tmp) / "codex-home")}):
            codex_home = Path(tmp) / "codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text("model = \"gpt-5\"\n", encoding="utf-8")
            repo, commit, task, input_file = self.make_candidate_repo(Path(tmp))
            installed_root = Path(tmp) / "installed"
            remove_calls: list[str] = []

            def fake_run_codex(args, *, codex_home=None):
                if args[0] == "plugin" and args[-2:] == ["list", "--json"]:
                    marketplace_args = [item for item in args if item.startswith("marketplaces.")]
                    if marketplace_args:
                        marketplace = marketplace_args[0].split(".", 2)[1]
                        plugin_id = f"visualize@{marketplace}"
                        enabled = any(item == f"plugins.{plugin_id}.enabled=true" for item in args)
                        return subprocess.CompletedProcess(
                            args=args,
                            returncode=0,
                            stdout=json.dumps({"installed": [{"pluginId": plugin_id, "name": "visualize", "marketplaceName": marketplace, "installed": enabled, "enabled": enabled}], "available": [] if enabled else [{"pluginId": plugin_id, "name": "visualize", "marketplaceName": marketplace, "installed": False, "enabled": False}]}),
                            stderr="",
                        )
                    return subprocess.CompletedProcess(
                        args=args,
                        returncode=0,
                        stdout=json.dumps({"installed": [{"pluginId": "visualize@openai-bundled", "name": "visualize", "installed": True, "enabled": True}], "available": []}),
                        stderr="",
                    )
                if args[0] == "plugin" and "add" in args:
                    active = candidate_plugin_replay._candidate_state(codex_home).active_path
                    self.assertTrue(active.exists())
                    selector = args[-1]
                    plugin_name, marketplace = selector.split("@", 1)
                    source_arg = next(item for item in args if item.startswith(f'marketplaces.{marketplace}.source="'))
                    marketplace_root = Path(source_arg.split("=", 1)[1].strip('"'))
                    installed_path = installed_root / marketplace / plugin_name / "0.8.0-test"
                    shutil.copytree(marketplace_root / "plugins" / plugin_name, installed_path)
                    return subprocess.CompletedProcess(
                        args=args,
                        returncode=0,
                        stdout=json.dumps({"pluginId": selector, "installedPath": str(installed_path)}),
                        stderr="",
                    )
                if args[0:3] == ["plugin", "remove", "--json"]:
                    remove_calls.append(args[3])
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")
                raise AssertionError(args)

            def fake_child(command, **kwargs):
                installed_path = next(installed_root.rglob("0.8.0-test"))
                self.assertIn("--ignore-user-config", command)
                self.assertIn("--json", command)
                return subprocess.CompletedProcess(args=command, returncode=0, stdout=f"event read {installed_path}/skills/visualize/SKILL.md\n")

            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=fake_run_codex), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.probe_child_filesystem_read_scope",
                return_value={"probe_result": "READABLE", "strict_read_isolation": False, "contract_errors": []},
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.verify_child_write_isolation",
                return_value={"status": "passed", "error_code": None, "contract_errors": [], "canary_changed": False},
            ), mock.patch("ai_bridge_kit.plugin_replay.run_child_command", side_effect=fake_child):
                summary, code = candidate_plugin_replay.run_candidate_plugin_replay(
                    target=repo,
                    plugin="visualize",
                    candidate_commit=commit,
                    task_file=task,
                    input_files=[input_file],
                    caller_cwd=repo,
                )

            self.assertEqual(code, 0)
            self.assertEqual(summary["status"], "completed")
            self.assertTrue(summary["actual_consumption"]["proven"])
            self.assertEqual(summary["child_config_hash_before"], summary["child_config_hash_after"])
            self.assertFalse(candidate_plugin_replay._candidate_state(codex_home).active_path.exists())
            self.assertEqual(len(remove_calls), 1)

    def test_missing_actual_consumption_proof_fails_and_still_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state"), "CODEX_HOME": str(Path(tmp) / "codex-home")}):
            repo, commit, task, input_file = self.make_candidate_repo(Path(tmp))
            codex_home = Path(tmp) / "codex-home"
            codex_home.mkdir()
            installed_path = Path(tmp) / "installed" / "visualize"
            installed_path.mkdir(parents=True)
            shutil.copytree(repo / "plugins" / "visualize", installed_path / "0.8.0-test")
            removed: list[str] = []

            def fake_run_codex(args, *, codex_home=None):
                if args[0] == "plugin" and args[-2:] == ["list", "--json"]:
                    marketplace_args = [item for item in args if item.startswith("marketplaces.")]
                    if marketplace_args:
                        marketplace = marketplace_args[0].split(".", 2)[1]
                        plugin_id = f"visualize@{marketplace}"
                        enabled = any(item == f"plugins.{plugin_id}.enabled=true" for item in args)
                        return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps({"installed": [{"pluginId": plugin_id, "name": "visualize", "marketplaceName": marketplace, "installed": enabled, "enabled": enabled}], "available": [] if enabled else [{"pluginId": plugin_id, "name": "visualize", "marketplaceName": marketplace}]}), stderr="")
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps({"installed": [{"pluginId": "visualize@openai-bundled", "name": "visualize", "installed": True, "enabled": True}], "available": []}), stderr="")
                if args[0] == "plugin" and "add" in args:
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps({"pluginId": args[-1], "installedPath": str(installed_path / "0.8.0-test")}), stderr="")
                if args[0:3] == ["plugin", "remove", "--json"]:
                    removed.append(args[3])
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")
                raise AssertionError(args)

            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=fake_run_codex), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.probe_child_filesystem_read_scope",
                return_value={"probe_result": "READABLE", "strict_read_isolation": False, "contract_errors": []},
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.verify_child_write_isolation",
                return_value={"status": "passed", "error_code": None, "contract_errors": [], "canary_changed": False},
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.run_child_command",
                return_value=subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="no installed path here\n"),
            ):
                with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_EFFECTIVE_PLUGIN_NOT_PROVEN):
                    candidate_plugin_replay.run_candidate_plugin_replay(
                        target=repo,
                        plugin="visualize",
                        candidate_commit=commit,
                        task_file=task,
                        input_files=[input_file],
                        caller_cwd=repo,
                    )

            self.assertEqual(len(removed), 1)
            self.assertFalse(candidate_plugin_replay._candidate_state(codex_home).active_path.exists())

    def test_config_hash_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state"), "CODEX_HOME": str(Path(tmp) / "codex-home")}):
            repo, commit, task, input_file = self.make_candidate_repo(Path(tmp))
            codex_home = Path(tmp) / "codex-home"
            codex_home.mkdir()
            config = codex_home / "config.toml"
            config.write_text("model = \"gpt-5\"\n", encoding="utf-8")
            installed_path = Path(tmp) / "installed" / "visualize" / "0.8.0-test"
            shutil.copytree(repo / "plugins" / "visualize", installed_path)

            def fake_run_codex(args, *, codex_home=None):
                if args[0] == "plugin" and args[-2:] == ["list", "--json"]:
                    marketplace_args = [item for item in args if item.startswith("marketplaces.")]
                    if marketplace_args:
                        marketplace = marketplace_args[0].split(".", 2)[1]
                        plugin_id = f"visualize@{marketplace}"
                        enabled = any(item == f"plugins.{plugin_id}.enabled=true" for item in args)
                        return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps({"installed": [{"pluginId": plugin_id, "name": "visualize", "marketplaceName": marketplace, "installed": enabled, "enabled": enabled}], "available": [] if enabled else [{"pluginId": plugin_id, "name": "visualize", "marketplaceName": marketplace}]}), stderr="")
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps({"installed": [{"pluginId": "visualize@openai-bundled", "name": "visualize", "installed": True, "enabled": True}], "available": []}), stderr="")
                if args[0] == "plugin" and "add" in args:
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps({"pluginId": args[-1], "installedPath": str(installed_path)}), stderr="")
                if args[0:3] == ["plugin", "remove", "--json"]:
                    return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")
                raise AssertionError(args)

            def fake_child(command, **kwargs):
                config.write_text("model = \"changed\"\n", encoding="utf-8")
                return subprocess.CompletedProcess(args=command, returncode=0, stdout=f"{installed_path}\n")

            with mock.patch("ai_bridge_kit.plugin_replay._run_codex", side_effect=fake_run_codex), mock.patch(
                "ai_bridge_kit.plugin_replay.resolved_executable",
                side_effect=lambda name: f"/trusted/bin/{name}",
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.probe_child_filesystem_read_scope",
                return_value={"probe_result": "READABLE", "strict_read_isolation": False, "contract_errors": []},
            ), mock.patch(
                "ai_bridge_kit.plugin_replay.verify_child_write_isolation",
                return_value={"status": "passed", "error_code": None, "contract_errors": [], "canary_changed": False},
            ), mock.patch("ai_bridge_kit.plugin_replay.run_child_command", side_effect=fake_child):
                with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_CHILD_CONFIG_CHANGED):
                    candidate_plugin_replay.run_candidate_plugin_replay(
                        target=repo,
                        plugin="visualize",
                        candidate_commit=commit,
                        task_file=task,
                        input_files=[input_file],
                        caller_cwd=repo,
                    )

    def test_stale_recovery_removes_only_bridge_owned_journal_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            state = candidate_plugin_replay._candidate_state(Path(tmp) / "codex-home")
            staging = state.identity_root / "old-run" / "marketplace"
            staging.mkdir(parents=True)
            active = {
                "candidate_plugin_id": "visualize@ai-bridge-candidate-old",
                "candidate_marketplace_name": "ai-bridge-candidate-old",
                "staging_path": str(staging),
            }
            candidate_plugin_replay._atomic_write_json(state.active_path, active)
            with mock.patch(
                "ai_bridge_kit.candidate_plugin_replay._plugin_remove",
                return_value=subprocess.CompletedProcess(args=["codex"], returncode=0, stdout="{}", stderr=""),
            ) as remove:
                recovered = candidate_plugin_replay.recover_stale_journal(state)

            self.assertEqual(recovered["recovered_plugin_id"], "visualize@ai-bridge-candidate-old")
            remove.assert_called_once()
            self.assertFalse(state.active_path.exists())
            self.assertFalse(staging.exists())

    def test_stale_recovery_rejects_unowned_plugin_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            state = candidate_plugin_replay._candidate_state(Path(tmp) / "codex-home")
            staging = state.identity_root / "old-run" / "marketplace"
            staging.mkdir(parents=True)
            candidate_plugin_replay._atomic_write_json(
                state.active_path,
                {
                    "candidate_plugin_id": "visualize@openai-bundled",
                    "candidate_marketplace_name": "openai-bundled",
                    "staging_path": str(staging),
                },
            )
            with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_REPLAY_CLEANUP_FAILED):
                candidate_plugin_replay.recover_stale_journal(state)

    def test_same_identity_lock_rejects_concurrent_replay_but_different_identity_has_distinct_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            state_a = candidate_plugin_replay._candidate_state(Path(tmp) / "codex-a")
            state_b = candidate_plugin_replay._candidate_state(Path(tmp) / "codex-b")
            self.assertNotEqual(state_a.lock_path, state_b.lock_path)
            with candidate_plugin_replay.acquire_identity_lock(state_a):
                with self.assertRaisesRegex(candidate_plugin_replay.CandidateReplayError, candidate_plugin_replay.CANDIDATE_REPLAY_LOCKED):
                    with candidate_plugin_replay.acquire_identity_lock(state_a):
                        pass
                with candidate_plugin_replay.acquire_identity_lock(state_b):
                    pass

    def test_dead_process_releases_os_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"AI_BRIDGE_STATE_HOME": str(Path(tmp) / "state")}):
            state = candidate_plugin_replay._candidate_state(Path(tmp) / "codex-home")

            def child(lock_path: str) -> None:
                import fcntl
                import os

                Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
                handle = open(lock_path, "a+")
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                os._exit(0)

            process = multiprocessing.Process(target=child, args=(str(state.lock_path),))
            process.start()
            process.join(5)
            self.assertEqual(process.exitcode, 0)
            with candidate_plugin_replay.acquire_identity_lock(state):
                pass

    def test_bridge_cli_routes_candidate_plugin_replay(self) -> None:
        with mock.patch(
            "ai_bridge_kit.candidate_plugin_replay.run_candidate_plugin_replay",
            return_value=({"status": "completed", "candidate_plugin_id": "visualize@ai-bridge-candidate-run"}, 0),
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            code = bridge_cli.main(
                [
                    "candidate-plugin-replay",
                    "--target",
                    "/tmp/repo",
                    "--plugin",
                    "visualize",
                    "--candidate-commit",
                    "HEAD",
                    "--task",
                    "/tmp/TASK.md",
                    "--input",
                    "/tmp/INPUT.txt",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["candidate_plugin_id"], "visualize@ai-bridge-candidate-run")

    def test_cli_rejects_plugin_path_escape_hatch(self) -> None:
        with self.assertRaises(SystemExit):
            candidate_plugin_replay.build_parser().parse_args(
                [
                    "--target",
                    "/tmp/repo",
                    "--plugin",
                    "visualize",
                    "--candidate-commit",
                    "HEAD",
                    "--task",
                    "/tmp/TASK.md",
                    "--input",
                    "/tmp/INPUT.txt",
                    "--plugin-path",
                    "/tmp/plugin",
                ]
            )


if __name__ == "__main__":
    unittest.main()
