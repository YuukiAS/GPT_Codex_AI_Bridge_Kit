from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import persistent_run


def git_call(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class FakeTmux:
    def __init__(self) -> None:
        self.sessions: set[str] = set()
        self.calls: list[list[str]] = []
        self.fail_create = False

    def __call__(self, command, **_kwargs):
        self.calls.append(list(command))
        if command[:2] == ["tmux", "has-session"]:
            name = command[command.index("-t") + 1].removeprefix("=")
            return SimpleNamespace(returncode=0 if name in self.sessions else 1, stdout="", stderr="")
        if command[:2] == ["tmux", "new-session"]:
            if self.fail_create:
                return SimpleNamespace(returncode=1, stdout="", stderr="create failed")
            self.sessions.add(command[command.index("-s") + 1])
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(command)


class PersistentRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous_codex_home = os.environ.get("CODEX_HOME")
        self.previous_state_home = os.environ.get("AI_BRIDGE_STATE_HOME")
        os.environ["CODEX_HOME"] = str(self.root / "codex-home")
        os.environ["AI_BRIDGE_STATE_HOME"] = str(self.root / "bridge-state")

    def tearDown(self) -> None:
        if self.previous_codex_home is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = self.previous_codex_home
        if self.previous_state_home is None:
            os.environ.pop("AI_BRIDGE_STATE_HOME", None)
        else:
            os.environ["AI_BRIDGE_STATE_HOME"] = self.previous_state_home
        self.tmp.cleanup()

    def make_repo(self) -> Path:
        target = self.root / f"project-{len(list(self.root.glob('project-*')))}"
        target.mkdir()
        git_call(target, "init")
        return target

    def write_goal(self, target: Path, rel: str = "prompts/tasks/001_goal.md") -> Path:
        goal = target / rel
        goal.parent.mkdir(parents=True, exist_ok=True)
        goal.write_text(
            "# Goal\n\n"
            "Persistent execution: REQUIRED\n"
            "Backend: tmux\n"
            f"Goal source: {rel}\n"
            "Run/session key: test-run\n"
            "Working directory: .\n"
            f"Launch argv: {json.dumps([sys.executable, '-c', 'raise SystemExit(7)'])}\n"
            "Progress mode: none\n"
            "Progress mode reason: exit-code fixture has no domain work counter\n"
            "Progress owner: none\n"
            "Progress source locator: NONE\n"
            "Expected progress update seconds: UNKNOWN\n"
            "Notify: OFF\n"
            "Recipient override: NONE\n"
            "Notification cadence minutes: 60\n",
            encoding="utf-8",
        )
        return goal

    def test_install_into_real_git_repo_without_lite(self) -> None:
        target = self.make_repo()

        actions = persistent_run.install_persistent_run(target)

        self.assertTrue(any("persistent_run/README.md" in item for item in actions))
        self.assertTrue((target / "automation" / "persistent_run" / "README.md").is_file())
        self.assertTrue((target / "automation" / "persistent_run" / "CONTRACT_TEMPLATE.md").is_file())
        self.assertTrue((target / "automation" / "persistent_run" / "KICKOFF_TEMPLATE.md").is_file())
        self.assertFalse((target / "prompts" / "AGENT_RULES.md").exists())
        self.assertFalse((target / ".agents" / "skills" / "agent-task-executor" / "SKILL.md").exists())

    def test_persistent_notifications_are_runtime_only_and_failure_is_nonfatal(self) -> None:
        binding = {
            "notify": "ON",
            "repo_realpath": str(self.root / "project"),
            "run_key": "test-run",
            "launch_id": "a" * 64,
            "recipient_override": "",
            "child_started_at": "2026-10-19T12:00:00+00:00",
        }
        captured: list[dict[str, object]] = []

        def fail_delivery(request, **_kwargs):
            captured.append(request)
            raise RuntimeError("synthetic transport failure")

        with mock.patch("ai_bridge_kit.notifier.deliver_notification", side_effect=fail_delivery):
            persistent_run._persistent_notification(
                binding,
                fact_class="runtime_start",
                status="STARTED",
                summary="Persistent child started.",
                next_action="Observe runtime progress.",
            )
        self.assertEqual(captured[0]["consumer"], "persistent")
        self.assertEqual(captured[0]["decision_authority"], "Runtime")
        self.assertEqual(binding["last_notification"]["status"], "FAILED")

    def test_install_preserves_user_agents_content_and_updates_managed_block(self) -> None:
        target = self.make_repo()
        agents = target / "AGENTS.md"
        agents.write_text("# User Rules\n\nKeep this.\n", encoding="utf-8")

        persistent_run.install_persistent_run(target)
        first = agents.read_text(encoding="utf-8")

        self.assertIn("# User Rules", first)
        self.assertIn("Keep this.", first)
        self.assertIn(persistent_run.PERSISTENT_RUN_BEGIN_MARKER, first)
        self.assertEqual(first.count(persistent_run.PERSISTENT_RUN_BEGIN_MARKER), 1)

        agents.write_text(
            first.replace("full-launch-id exact tmux session", "stale managed text"),
            encoding="utf-8",
        )
        persistent_run.install_persistent_run(target)
        updated = agents.read_text(encoding="utf-8")

        self.assertIn("# User Rules", updated)
        self.assertNotIn("stale managed text", updated)
        self.assertIn("full-launch-id exact tmux session", updated)
        self.assertEqual(updated.count(persistent_run.PERSISTENT_RUN_BEGIN_MARKER), 1)

    def test_managed_block_update_preserves_all_marker_external_bytes(self) -> None:
        target = self.make_repo()
        agents = target / "AGENTS.md"
        begin = persistent_run.PERSISTENT_RUN_BEGIN_MARKER.encode("utf-8")
        end = persistent_run.PERSISTENT_RUN_END_MARKER.encode("utf-8")
        prefix = "# 用户规则  \r\n\r\n保留连续空行\n尾随空白 \t \r\n".encode("utf-8")
        suffix = "\r\n\r\n后置中文\n\n末尾空白  \t".encode("utf-8")
        agents.write_bytes(prefix + begin + b"\r\nstale managed bytes\r\n" + end + suffix)

        persistent_run.install_persistent_run(target)

        updated = agents.read_bytes()
        start = updated.index(begin)
        marker_end = updated.index(end, start) + len(end)
        self.assertEqual(updated[:start], prefix)
        self.assertEqual(updated[marker_end:], suffix)
        self.assertNotIn(b"stale managed bytes", updated)

    def test_repeated_install_is_stable_and_does_not_write_codex_home_or_rules(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)
        first_files = {
            path.relative_to(target).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted((target / "automation" / "persistent_run").glob("*.md"))
        }
        first_agents = (target / "AGENTS.md").read_text(encoding="utf-8")

        persistent_run.install_persistent_run(target)

        second_files = {
            path.relative_to(target).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted((target / "automation" / "persistent_run").glob("*.md"))
        }
        self.assertEqual(first_files, second_files)
        self.assertEqual(first_agents, (target / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertFalse(Path(os.environ["CODEX_HOME"]).exists())
        self.assertFalse((target / ".codex" / "rules").exists())

    def test_validate_pass_and_failures(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)

        lines, code = persistent_run.validate_persistent_run(target)
        self.assertEqual(code, 0)
        self.assertTrue(any("Persistent Run validation passed" in line for line in lines))

        (target / "automation" / "persistent_run" / "README.md").unlink()
        lines, code = persistent_run.validate_persistent_run(target)
        self.assertEqual(code, 1)
        self.assertTrue(any("missing automation/persistent_run/README.md" in line for line in lines))

        persistent_run.install_persistent_run(target)
        agents = target / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace(persistent_run.PERSISTENT_RUN_END_MARKER, ""),
            encoding="utf-8",
        )
        lines, code = persistent_run.validate_persistent_run(target)
        self.assertEqual(code, 1)
        self.assertTrue(any("markers" in line for line in lines))

    def test_kickoff_requires_existing_repo_relative_goal_and_rejects_escape(self) -> None:
        target = self.make_repo()
        self.write_goal(target)
        outside = self.root / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")

        prompt = persistent_run.render_kickoff_prompt(target, "prompts/tasks/001_goal.md")

        self.assertIn("Goal: `prompts/tasks/001_goal.md`", prompt)
        self.assertIn("persistent tmux session", prompt)
        self.assertIn("Do not ask again", prompt)
        self.assertIn("does not permit scope expansion", prompt)

        with self.assertRaisesRegex(persistent_run.PersistentRunError, "repo-relative"):
            persistent_run.render_kickoff_prompt(target, "../outside.md")
        with self.assertRaisesRegex(persistent_run.PersistentRunError, "repo-relative"):
            persistent_run.render_kickoff_prompt(target, str(outside))
        with self.assertRaisesRegex(persistent_run.PersistentRunError, "does not exist"):
            persistent_run.render_kickoff_prompt(target, "prompts/tasks/missing.md")

    def test_validate_rejects_codex_rules_created_by_target(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)
        (target / ".codex" / "rules").mkdir(parents=True)

        lines, code = persistent_run.validate_persistent_run(target)

        self.assertEqual(code, 1)
        self.assertTrue(any(".codex/rules" in line for line in lines))

    def test_installed_guidance_separates_duration_scheduler_and_tmux_topology(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)

        readme = (target / "automation" / "persistent_run" / "README.md").read_text(encoding="utf-8")
        agents = (target / "AGENTS.md").read_text(encoding="utf-8")
        contract = (target / "automation" / "persistent_run" / "CONTRACT_TEMPLATE.md").read_text(encoding="utf-8")
        kickoff = (target / "automation" / "persistent_run" / "KICKOFF_TEMPLATE.md").read_text(encoding="utf-8")

        combined = "\n".join([readme, agents, contract, kickoff])
        self.assertIn("upfront authorization readiness", combined)
        self.assertIn("process persistence topology", combined)
        self.assertIn("project-native progress reporting", combined)
        self.assertIn("不自动选择 tmux", readme)
        self.assertIn("scheduler-owned batch", combined)
        self.assertIn("sbatch", combined)
        self.assertIn("already-detached", combined)
        self.assertIn("terminal-owned", combined)
        self.assertIn("survive Codex/SSH/terminal disconnect", combined)
        self.assertIn("not a universal unattended approval", kickoff)

    def test_report_latest_guidance_is_independent_of_tmux_session(self) -> None:
        target = self.make_repo()
        persistent_run.install_persistent_run(target)

        readme = (target / "automation" / "persistent_run" / "README.md").read_text(encoding="utf-8")
        agents = (target / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("独立于 tmux", readme)
        self.assertIn("scheduler-native", readme)
        self.assertIn("不需要对应的 tmux session", agents)
        self.assertIn("不要从 tmux/PID 存在推断", agents)

    def test_bridge_cli_dispatches_install_validate_and_kickoff(self) -> None:
        target = self.make_repo()
        self.write_goal(target)

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bridge_cli.main(["persistent-run", "install", "--target", str(target)]), 0)
        self.assertIn("persistent_run/README.md", out.getvalue())

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(bridge_cli.main(["persistent-run", "validate", "--target", str(target)]), 0)
        self.assertIn("Persistent Run validation passed", out.getvalue())

        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(
                bridge_cli.main(
                    [
                        "persistent-run",
                        "prompt",
                        "kickoff",
                        "--target",
                        str(target),
                        "--goal",
                        "prompts/tasks/001_goal.md",
                    ]
                ),
                0,
            )
        self.assertIn("Goal: `prompts/tasks/001_goal.md`", out.getvalue())

    def test_install_projected_overflow_has_zero_project_mutation(self) -> None:
        target = self.make_repo()
        agents = target / "AGENTS.md"
        agents.write_bytes(b"user bytes\n")
        codex_home = Path(os.environ["CODEX_HOME"])
        codex_home.mkdir()
        (codex_home / "config.toml").write_text("project_doc_max_bytes = 32\n", encoding="utf-8")
        before = agents.read_bytes()

        with self.assertRaisesRegex(persistent_run.PersistentRunError, "PROJECTED_OVERFLOW"):
            persistent_run.install_persistent_run(target)

        self.assertEqual(agents.read_bytes(), before)
        self.assertFalse((target / "automation").exists())

    def test_start_status_existing_and_real_wait_observation(self) -> None:
        target = self.make_repo()
        goal = self.write_goal(target)
        digest = hashlib.sha256(goal.read_bytes()).hexdigest()
        state = self.root / "state-lifecycle"
        tmux = FakeTmux()

        started = persistent_run.start_persistent_run(
            target,
            goal.relative_to(target).as_posix(),
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(started["status"], "NEW_START")
        self.assertRegex(started["session_name"], r"^ai-bridge-pr-[0-9a-f]{64}$")
        self.assertEqual(sum(call[:2] == ["tmux", "new-session"] for call in tmux.calls), 1)

        status = persistent_run.status_persistent_run(
            target,
            goal.relative_to(target).as_posix(),
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(status["status"], "STARTING")
        self.assertEqual(status["progress"]["state"], "UNKNOWN")

        existing = persistent_run.start_persistent_run(
            target,
            goal.relative_to(target).as_posix(),
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(existing["status"], "RETURN_EXISTING")
        self.assertEqual(sum(call[:2] == ["tmux", "new-session"] for call in tmux.calls), 1)

        class Child:
            pid = 12345

            @staticmethod
            def wait() -> int:
                return 7

        with mock.patch.object(persistent_run.subprocess, "Popen", return_value=Child()):
            self.assertEqual(
                persistent_run.supervise_binding(
                    Path(started["binding_path"]),
                    started["launch_id"],
                ),
                0,
            )
        tmux.sessions.remove(started["session_name"])
        terminal = persistent_run.status_persistent_run(
            target,
            goal.relative_to(target).as_posix(),
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(terminal["status"], "TERMINAL")
        self.assertEqual(terminal["exit_code"], 7)
        self.assertIn("child_exit_observed_at", terminal["binding"])

    def test_progress_update_atomic_and_eta_warmup_reset(self) -> None:
        progress = self.root / "progress.json"
        env = {
            "AI_BRIDGE_PROGRESS_PATH": str(progress),
            "AI_BRIDGE_PROGRESS_MODE": "count",
            "AI_BRIDGE_PROGRESS_OWNER": "bridge-child",
            "AI_BRIDGE_RUN_KEY": "run-a",
            "AI_BRIDGE_RUNTIME_ID": "a" * 64,
        }
        payload = persistent_run.update_run_progress(stage="fit", completed=2, total=10, env=env)
        self.assertEqual(payload["completed"], 2)
        self.assertEqual(json.loads(progress.read_text(encoding="utf-8"))["runtime_id"], "a" * 64)
        self.assertEqual(list(progress.parent.glob(".progress.json.tmp-*")), [])

        history = [
            {"observed_at": "2026-10-19T00:00:00+00:00", "stage": "fit", "completed": 1, "total": 10},
            {"observed_at": "2026-10-19T00:05:00+00:00", "stage": "fit", "completed": 3, "total": 10},
            {"observed_at": "2026-10-19T00:10:00+00:00", "stage": "fit", "completed": 5, "total": 10},
        ]
        eta = persistent_run.estimate_progress_eta(history, mode="count", expected_update_seconds=300)
        self.assertNotEqual(eta["eta"], "UNKNOWN")
        reset = persistent_run.estimate_progress_eta(
            [*history, {"observed_at": "2026-10-19T00:15:00+00:00", "stage": "evaluate", "completed": 6, "total": 10}],
            mode="count",
            expected_update_seconds=300,
        )
        self.assertEqual(reset["eta"], "UNKNOWN")

    def test_malformed_progress_is_nonfatal_and_last_good_recovers(self) -> None:
        progress = self.root / "project-progress.json"
        binding = {
            "progress_source_path": str(progress),
            "progress_mode": "fraction",
            "expected_progress_update_seconds": 300,
            "launch_id": "a" * 64,
            "run_key": "run-a",
        }
        frozen_clock = mock.patch.object(persistent_run, "_utc_now", return_value="2026-10-19T00:05:00+00:00")
        frozen_clock.start()
        self.addCleanup(frozen_clock.stop)
        progress.write_text(
            json.dumps({"runtime_id": "a" * 64, "run_key": "run-a", "observed_at": "2026-10-19T00:00:00+00:00", "stage": "fit", "fraction": 0.2}),
            encoding="utf-8",
        )
        persistent_run.observe_binding_progress(binding)
        last_good = dict(binding["last_good_progress"])
        progress.write_text('{"half":', encoding="utf-8")
        persistent_run.observe_binding_progress(binding)
        self.assertEqual(binding["progress_observation"]["state"], "UNAVAILABLE")
        self.assertEqual(binding["last_good_progress"], last_good)
        progress.write_text(
            json.dumps({"runtime_id": "a" * 64, "run_key": "run-a", "observed_at": "2026-10-19T00:05:00+00:00", "stage": "fit", "fraction": 0.4}),
            encoding="utf-8",
        )
        persistent_run.observe_binding_progress(binding)
        self.assertEqual(binding["progress_observation"]["state"], "AVAILABLE")
        self.assertEqual(binding["last_good_progress"]["fraction"], 0.4)

    def test_recover_and_resolve_require_proven_dead_child(self) -> None:
        target = self.make_repo()
        goal = self.write_goal(target)
        rel_goal = goal.relative_to(target).as_posix()
        digest = hashlib.sha256(goal.read_bytes()).hexdigest()
        state = self.root / "state-recover"
        tmux = FakeTmux()
        started = persistent_run.start_persistent_run(
            target,
            rel_goal,
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        tmux.sessions.clear()
        binding_path = Path(started["binding_path"])
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        binding["host_boot_id"] = "boot-a"
        binding["child_process_identity"] = {
            "pid": 123,
            "boot_id": "boot-a",
            "start_ticks": "7",
            "argv_digest": "digest",
        }
        binding_path.write_text(json.dumps(binding), encoding="utf-8")
        with mock.patch.object(persistent_run, "_boot_identity", return_value="boot-a"), mock.patch.object(
            persistent_run,
            "_process_identity",
            return_value={"pid": 123, "boot_id": "boot-a", "start_ticks": "7", "argv_digest": "digest"},
        ):
            active = persistent_run.recover_persistent_run(
                target, rel_goal, expected_goal_sha256=digest, state_root=state, runner=tmux
            )
        self.assertEqual(active["classification"], "ORPHAN_CHILD_ALIVE")
        with self.assertRaisesRegex(persistent_run.PersistentRunError, "ORPHAN_CHILD_ALIVE"):
            with mock.patch.object(persistent_run, "_boot_identity", return_value="boot-a"), mock.patch.object(
                persistent_run, "_process_identity", return_value=active["binding"]["child_process_identity"]
            ):
                persistent_run.resolve_persistent_run(
                    target,
                    rel_goal,
                    expected_goal_sha256=digest,
                    expected_launch_id=started["launch_id"],
                    close_stale=True,
                    state_root=state,
                    runner=tmux,
                )
        with mock.patch.object(persistent_run, "_boot_identity", return_value="boot-a"), mock.patch.object(
            persistent_run, "_process_identity", return_value=None
        ):
            safe = persistent_run.recover_persistent_run(
                target, rel_goal, expected_goal_sha256=digest, state_root=state, runner=tmux
            )
            closed = persistent_run.resolve_persistent_run(
                target,
                rel_goal,
                expected_goal_sha256=digest,
                expected_launch_id=started["launch_id"],
                close_stale=True,
                state_root=state,
                runner=tmux,
            )
        self.assertEqual(safe["classification"], "SAFE_TO_CLOSE_STALE")
        self.assertEqual(closed["status"], "STALE_CLOSED_WITHOUT_COMPLETION")
        self.assertFalse(closed["semantic_completion_claim"])
        self.assertNotIn("exit_code", json.loads(binding_path.read_text(encoding="utf-8")))

    def test_stale_mismatch_partial_and_supervisor_loss_never_relaunch(self) -> None:
        target = self.make_repo()
        goal = self.write_goal(target)
        rel_goal = goal.relative_to(target).as_posix()
        digest = hashlib.sha256(goal.read_bytes()).hexdigest()
        state = self.root / "state-negatives"
        tmux = FakeTmux()
        started = persistent_run.start_persistent_run(
            target,
            rel_goal,
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        tmux.sessions.clear()
        calls_before = sum(call[:2] == ["tmux", "new-session"] for call in tmux.calls)
        stale = persistent_run.start_persistent_run(
            target,
            rel_goal,
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(stale["status"], "NO_RELAUNCH")
        self.assertEqual(stale["lifecycle_state"], "UNKNOWN/UNAVAILABLE")
        self.assertEqual(sum(call[:2] == ["tmux", "new-session"] for call in tmux.calls), calls_before)
        observed = persistent_run.status_persistent_run(
            target,
            rel_goal,
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(observed["status"], "UNKNOWN/UNAVAILABLE")
        self.assertNotIn("exit_code", observed["binding"])

        binding_path = Path(started["binding_path"])
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        binding["launch_id"] = "0" * 64
        binding_path.write_text(json.dumps(binding), encoding="utf-8")
        mismatch = persistent_run.status_persistent_run(
            target,
            rel_goal,
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(mismatch["status"], "CONFLICT")

    def test_create_failure_is_recorded_and_same_run_is_not_retried(self) -> None:
        target = self.make_repo()
        goal = self.write_goal(target)
        rel_goal = goal.relative_to(target).as_posix()
        digest = hashlib.sha256(goal.read_bytes()).hexdigest()
        state = self.root / "state-create-failure"
        tmux = FakeTmux()
        tmux.fail_create = True
        failed = persistent_run.start_persistent_run(
            target,
            rel_goal,
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(failed["status"], "CREATE_FAILED")
        create_calls = sum(call[:2] == ["tmux", "new-session"] for call in tmux.calls)
        again = persistent_run.start_persistent_run(
            target,
            rel_goal,
            expected_goal_sha256=digest,
            state_root=state,
            runner=tmux,
        )
        self.assertEqual(again["status"], "ALREADY_TERMINAL")
        self.assertEqual(sum(call[:2] == ["tmux", "new-session"] for call in tmux.calls), create_calls)

    def test_normalize_progress_uses_real_fraction_and_unknown_eta(self) -> None:
        normalized = persistent_run.normalize_progress_evidence(
            {
                "stage": "fit-model",
                "completed": 3,
                "total": 10,
                "events": [{"timestamp": "2026-09-23T01:00:00+00:00", "message": "checkpoint"}],
            }
        )

        self.assertEqual(normalized["stage"], "fit-model")
        self.assertEqual(normalized["fraction"], 0.3)
        self.assertEqual(normalized["eta"], "UNKNOWN")
        self.assertFalse(normalized["semantic_completion_claim"])

    def test_normalize_progress_marks_stalled_from_real_no_progress_threshold(self) -> None:
        normalized = persistent_run.normalize_progress_evidence(
            {
                "stage": "collect",
                "seconds_since_progress": 7200,
                "last_progress_at": "2026-09-23T01:00:00+00:00",
            },
            stalled_after_seconds=3600,
        )

        self.assertEqual(normalized["status"], "stalled")
        self.assertEqual(normalized["last_progress_at"], "2026-09-23T01:00:00+00:00")

    def test_progress_cli_outputs_normalized_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "progress.json"
            evidence.write_text('{"stage":"stage-a","eta":"2026-09-23T03:00:00+00:00","eta_basis":"recent checkpoints","eta_uncertainty":"plus/minus 20 minutes"}', encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(persistent_run.main(["progress", "--evidence", str(evidence)]), 0)

            self.assertIn('"stage": "stage-a"', out.getvalue())
            self.assertIn('"eta_basis": "recent checkpoints"', out.getvalue())

    def test_report_records_latest_bounded_history_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            state = Path(tmp) / "state"
            events = [
                {
                    "run_locator": "repo/run-a",
                    "stage": "prepare",
                    "observed_at": "2026-09-23T01:00:00+00:00",
                    "last_progress_at": "2026-09-23T01:00:00+00:00",
                    "message": "started",
                    "events": [{"timestamp": "2026-09-23T01:00:00+00:00", "message": "started"}],
                    "report_interval_seconds": 1,
                    "allow_short_test_interval": True,
                },
                {
                    "run_locator": "repo/run-a",
                    "stage": "prepare",
                    "observed_at": "2026-09-23T01:00:01+00:00",
                    "last_progress_at": "2026-09-23T01:00:00+00:00",
                    "message": "started",
                    "events": [{"timestamp": "2026-09-23T01:00:00+00:00", "message": "started"}],
                    "report_interval_seconds": 3600,
                },
                {
                    "run_locator": "repo/run-a",
                    "stage": "fit",
                    "observed_at": "2026-09-23T01:05:00+00:00",
                    "last_progress_at": "2026-09-23T01:05:00+00:00",
                    "completed": 5,
                    "total": 10,
                    "unit": "epochs",
                    "eta": "2026-09-23T01:20:00+00:00",
                    "eta_basis": "checkpoint throughput",
                    "eta_uncertainty": "plus/minus 5 minutes",
                    "message": "halfway",
                    "events": [{"timestamp": "2026-09-23T01:05:00+00:00", "message": "halfway"}],
                    "report_interval_seconds": 3600,
                },
            ]
            reports = []
            for event in events:
                progress.write_text(json.dumps(event), encoding="utf-8")
                reports.append(persistent_run.report_progress_file(progress, state_root=state, history_limit=2))

            self.assertEqual(reports[0]["delivery_decision"], "deliver")
            self.assertEqual(reports[1]["delivery_decision"], "suppress")
            self.assertEqual(reports[2]["delivery_reason"], "stage_transition")
            self.assertEqual(reports[2]["normalized"]["fraction"], 0.5)
            history_lines = Path(reports[2]["history_path"]).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(history_lines), 2)

            latest = persistent_run.latest_report_for_progress(progress, state_root=state)
            self.assertEqual(latest["normalized"]["stage"], "fit")

    def test_report_notifications_require_explicit_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            state = Path(tmp) / "state"
            progress.write_text(
                json.dumps(
                    {
                        "run_locator": "repo/run",
                        "task_key": "repo--run",
                        "stage": "stage-a",
                        "observed_at": "2026-09-23T01:00:00+00:00",
                        "progress_since_previous": "one step",
                        "delivery_mode": "notifications",
                    }
                ),
                encoding="utf-8",
            )

            report = persistent_run.report_progress_file(progress, state_root=state)
            self.assertEqual(report["notification_projection"], "unavailable_existing_configuration_not_verified")
            self.assertIsNone(report["notification_result"])

            payload = json.loads(progress.read_text(encoding="utf-8"))
            payload["notification_authorized"] = True
            payload["notification_dry_run"] = True
            payload["observed_at"] = "2026-09-23T01:20:00+00:00"
            payload["stage"] = "stage-b"
            payload["progress_since_previous"] = "two steps"
            progress.write_text(json.dumps(payload), encoding="utf-8")

            authorized = persistent_run.report_progress_file(progress, state_root=state)
            self.assertEqual(authorized["notification_projection"], "unavailable_existing_configuration_not_verified")

            self.assertIsNone(authorized["notification_result"])

    def test_report_unknown_eta_and_stall_without_intervention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            progress.write_text(
                json.dumps(
                    {
                        "run_locator": "repo/run-stall",
                        "stage": "collect",
                        "observed_at": "2026-09-23T02:00:00+00:00",
                        "last_progress_at": "2026-09-23T01:00:00+00:00",
                        "seconds_since_progress": 7200,
                        "stall_threshold_seconds": 60,
                    }
                ),
                encoding="utf-8",
            )

            report = persistent_run.report_progress_file(progress, state_root=Path(tmp) / "state")

            self.assertEqual(report["normalized"]["eta"], "UNKNOWN")
            self.assertEqual(report["normalized"]["status"], "stalled")
            self.assertEqual(report["delivery_reason"], "start_or_resume")
            self.assertNotIn("restart", json.dumps(report).lower())

    def test_report_cli_and_latest_cli_are_normal_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "progress.json"
            state = Path(tmp) / "state"
            progress.write_text('{"run_locator":"repo/run-cli","stage":"stage-a","observed_at":"2026-09-23T01:00:00+00:00"}', encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(
                    persistent_run.main(["report", "--progress", str(progress), "--state-home", str(state)]),
                    0,
                )
            self.assertIn('"schema": "ai-bridge.persistent_run.report.v1"', out.getvalue())

            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(
                    persistent_run.main(["latest", "--progress", str(progress), "--state-home", str(state)]),
                    0,
                )
            self.assertIn('"stage": "stage-a"', out.getvalue())


if __name__ == "__main__":
    unittest.main()
