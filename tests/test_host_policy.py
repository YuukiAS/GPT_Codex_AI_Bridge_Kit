from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import host as host_module
from ai_bridge_kit import bridge_cli
from ai_bridge_kit import reviewed_runner
from ai_bridge_kit.host import (
    EXTERNAL_WAIT_POLICY_MARKERS,
    HOST_BEGIN_MARKER,
    HOST_END_MARKER,
    HostPublishError,
    NARRATIVE_POLICY_MARKERS,
    RULES_RELATIVE_PATH,
    _effective_execpolicy_decision,
    _execpolicy_decision,
    _canonical_repo_identity,
    config_values,
    desired_agents_block,
    desired_rules_text,
    format_status,
    inspect_host_policy,
    install_host_policy,
    install_managed_block,
    patch_config_text,
    publish_current_branch,
    resolve_ai_bridge_executable,
    resolve_codex_home,
    validate_host_policy,
)


class HostPolicyTests(unittest.TestCase):
    def make_publish_repo(self, tmp: str) -> tuple[Path, str]:
        root = Path(tmp)
        remote = root / "remote.git"
        repo = root / "repo"
        subprocess.check_call(["git", "init", "--bare", "--initial-branch", "main", str(remote)], stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "init", "--initial-branch", "main", str(repo)], stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=repo)
        subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=repo)
        (repo / "README.md").write_text("initial\n", encoding="utf-8")
        subprocess.check_call(["git", "add", "README.md"], cwd=repo)
        subprocess.check_call(["git", "commit", "-m", "initial"], cwd=repo, stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "remote", "add", "origin", str(remote)], cwd=repo)
        subprocess.check_call(["git", "push", "-u", "origin", "main"], cwd=repo, stdout=subprocess.DEVNULL)
        (repo / "README.md").write_text("initial\nchange\n", encoding="utf-8")
        subprocess.check_call(["git", "add", "README.md"], cwd=repo)
        subprocess.check_call(["git", "commit", "-m", "change"], cwd=repo, stdout=subprocess.DEVNULL)
        return repo, "local:" + remote.resolve().as_posix()

    def make_github_https_publish_repo(self, tmp: str) -> tuple[Path, str]:
        repo, _identity = self.make_publish_repo(tmp)
        subprocess.check_call(
            ["git", "remote", "set-url", "origin", "https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git"],
            cwd=repo,
        )
        return repo, "YuukiAS/GPT_Codex_AI_Bridge_Kit"

    def make_canary(self, tmp: str, name: str = "canary") -> tuple[Path, Path]:
        marker = Path(tmp) / f"{name}.marker"
        script = Path(tmp) / name
        script.write_text(f"#!/bin/sh\nprintf invoked > {marker}\nexit 1\n", encoding="utf-8")
        script.chmod(0o700)
        return script, marker

    def remote_main_head(self, tmp: str) -> str:
        return subprocess.check_output(
            ["git", "rev-parse", "refs/heads/main"],
            cwd=Path(tmp) / "remote.git",
            text=True,
        ).strip()

    def assert_publish_rejects_without_canary_or_remote_change(
        self,
        repo: Path,
        identity: str,
        tmp: str,
        *,
        env: dict[str, str],
        message: str,
        marker: Path,
    ) -> None:
        before = self.remote_main_head(tmp)
        with self.assertRaisesRegex(HostPublishError, message):
            publish_current_branch(repo, expected_repo=identity, expected_branch="main", env=env)
        self.assertFalse(marker.exists())
        self.assertEqual(self.remote_main_head(tmp), before)

    def run_with_fake_github_network(self, repo: Path, callback, *, remote_oid: str | None = None):
        real_git = host_module._git
        remote_oid = remote_oid or subprocess.check_output(["git", "rev-parse", "HEAD^"], cwd=repo, text=True).strip()
        network_calls: list[list[str]] = []

        def fake_git(cwd, args, *, env=None, check=True):
            if args[:2] == ["ls-remote", "--heads"]:
                network_calls.append(list(args))
                return subprocess.CompletedProcess(
                    ["git", *args],
                    0,
                    stdout=f"{remote_oid}\trefs/heads/main\n",
                    stderr="",
                )
            if "push" in args and "--porcelain" in args:
                network_calls.append(list(args))
                return subprocess.CompletedProcess(["git", *args], 0, stdout="", stderr="")
            return real_git(cwd, args, env=env, check=check)

        with mock.patch("ai_bridge_kit.host._git", side_effect=fake_git):
            result = callback()
        return result, network_calls

    def assert_publish_rejects_before_network(self, repo: Path, identity: str, *, message: str) -> None:
        real_git = host_module._git
        network_calls: list[list[str]] = []

        def fake_git(cwd, args, *, env=None, check=True):
            if args[:2] == ["ls-remote", "--heads"] or ("push" in args and "--porcelain" in args):
                network_calls.append(list(args))
                return subprocess.CompletedProcess(["git", *args], 1, stdout="", stderr="network should not run")
            return real_git(cwd, args, env=env, check=check)

        with mock.patch("ai_bridge_kit.host._git", side_effect=fake_git):
            with self.assertRaisesRegex(HostPublishError, message):
                publish_current_branch(repo, expected_repo=identity, expected_branch="main", env={"PATH": os.environ["PATH"]})
        self.assertEqual(network_calls, [])

    def test_codex_home_resolution_priority(self) -> None:
        explicit = Path("/tmp/explicit-codex-home")
        env = {"CODEX_HOME": "/tmp/env-codex-home"}

        self.assertEqual(resolve_codex_home(explicit, env), explicit.resolve())
        self.assertEqual(resolve_codex_home(None, env), Path("/tmp/env-codex-home").resolve())

    def test_new_config_install_values(self) -> None:
        values = config_values(patch_config_text(""))

        self.assertEqual(values[("", "approval_policy")], '"on-request"')
        self.assertEqual(values[("", "sandbox_mode")], '"workspace-write"')
        self.assertEqual(values[("", "approvals_reviewer")], '"auto_review"')
        self.assertEqual(values[("sandbox_workspace_write", "network_access")], "true")
        self.assertEqual(values[("features", "default_mode_request_user_input")], "false")
        self.assertEqual(values[("features", "memories")], "true")

    def test_config_merge_preserves_unrelated_fields(self) -> None:
        source = """model = "gpt-5"
reasoning_effort = "high"

[mcp_servers.example]
command = "example"

[features]
apps = true
memories = false
"""
        patched = patch_config_text(source)

        self.assertIn('model = "gpt-5"', patched)
        self.assertIn('reasoning_effort = "high"', patched)
        self.assertIn("[mcp_servers.example]", patched)
        self.assertIn('command = "example"', patched)
        self.assertIn("apps = true", patched)
        self.assertLess(patched.index('approval_policy = "on-request"'), patched.index("[mcp_servers.example]"))
        values = config_values(patched)
        self.assertEqual(values[("features", "memories")], "true")
        self.assertEqual(values[("features", "default_mode_request_user_input")], "false")

    def test_existing_features_section_updates_only_target_keys(self) -> None:
        patched = patch_config_text("[features]\nmemories = false\nplugins = true\n")
        values = config_values(patched)

        self.assertEqual(patched.count("[features]"), 1)
        self.assertEqual(values[("features", "memories")], "true")
        self.assertEqual(values[("features", "default_mode_request_user_input")], "false")
        self.assertEqual(values[("features", "plugins")], "true")

    def test_existing_sandbox_section_updates_network_access(self) -> None:
        patched = patch_config_text("[sandbox_workspace_write]\nnetwork_access = false\n")
        values = config_values(patched)

        self.assertEqual(patched.count("[sandbox_workspace_write]"), 1)
        self.assertEqual(values[("sandbox_workspace_write", "network_access")], "true")

    def test_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            first_status, first_actions = install_host_policy(codex_home)
            second_status, second_actions = install_host_policy(codex_home)

            self.assertEqual(first_status.overall_state, "configured")
            self.assertEqual(second_status.overall_state, "configured")
            self.assertTrue(any(action.startswith("Backup:") for action in first_actions))
            self.assertEqual(second_actions, ["No changes needed; host policy is already configured."])

    def test_agents_block_create_append_update_preserves_user_content(self) -> None:
        block = desired_agents_block()

        self.assertEqual(install_managed_block(None, block), block)
        appended = install_managed_block("User rule\n", block)
        self.assertIn("User rule", appended)
        self.assertIn(block, appended)

        old = (
            "Header\n\n"
            f"{HOST_BEGIN_MARKER}\nold managed text\n{HOST_END_MARKER}\n\n"
            "Footer\n"
        )
        updated = install_managed_block(old, block)
        self.assertIn("Header", updated)
        self.assertIn("Footer", updated)
        self.assertIn(block, updated)
        self.assertNotIn("old managed text", updated)

    def test_new_install_agents_block_contains_narrative_language_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            agents_text = (codex_home / "AGENTS.md").read_text(encoding="utf-8")

            for marker in NARRATIVE_POLICY_MARKERS:
                self.assertIn(marker, agents_text)
            for marker in EXTERNAL_WAIT_POLICY_MARKERS:
                self.assertIn(marker, agents_text)
            self.assertIn(
                "narrative_language: zh-CN",
                format_status(inspect_host_policy(codex_home)),
            )

    def test_rules_install_and_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            rules_path = codex_home / "rules" / "ai-bridge-global.rules"

            self.assertEqual(rules_path.read_text(encoding="utf-8"), desired_rules_text())
            self.assertIn("host_executable(", rules_path.read_text(encoding="utf-8"))
            self.assertIn('pattern = ["ai-bridge", "plugin-replay"]', rules_path.read_text(encoding="utf-8"))
            self.assertIn('pattern = ["ai-bridge", "host", "publish-current-branch"]', rules_path.read_text(encoding="utf-8"))
            self.assertIn('pattern = ["ai-bridge", "reviewed-handoff", "materialize-worktree"]', rules_path.read_text(encoding="utf-8"))
            self.assertIn('pattern = ["gh", "pr", "list", "--"]', rules_path.read_text(encoding="utf-8"))
            self.assertIn('pattern = ["ps"]', rules_path.read_text(encoding="utf-8"))
            self.assertIn('pattern = ["git", "fetch", "--all", "--prune"]', rules_path.read_text(encoding="utf-8"))
            self.assertIn('pattern = ["tmux", ["ls", "list-sessions", "has-session"]]', rules_path.read_text(encoding="utf-8"))
            _, actions = install_host_policy(codex_home)
            self.assertEqual(actions, ["No changes needed; host policy is already configured."])

    def test_existing_managed_block_updates_narrative_policy_and_preserves_user_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            agents_path = codex_home / "AGENTS.md"
            agents_path.write_text(
                "User header\n\n"
                f"{HOST_BEGIN_MARKER}\n"
                "# AI Bridge Kit Host Policy\n\n"
                "## Old Policy\n\n"
                "old\n"
                f"{HOST_END_MARKER}\n\n"
                "User footer\n",
                encoding="utf-8",
            )

            install_host_policy(codex_home)
            agents_text = agents_path.read_text(encoding="utf-8")

            self.assertIn("User header", agents_text)
            self.assertIn("User footer", agents_text)
            for marker in NARRATIVE_POLICY_MARKERS:
                self.assertIn(marker, agents_text)
            self.assertEqual(inspect_host_policy(codex_home).narrative_language_state, "configured")

    def test_status_missing_configured_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            self.assertEqual(inspect_host_policy(codex_home).overall_state, "missing")

            install_host_policy(codex_home)
            self.assertEqual(inspect_host_policy(codex_home).overall_state, "configured")
            self.assertEqual(inspect_host_policy(codex_home).narrative_language_state, "configured")

            (codex_home / "rules" / "ai-bridge-global.rules").write_text("drift\n", encoding="utf-8")
            self.assertEqual(inspect_host_policy(codex_home).overall_state, "drifted")

    def test_status_reports_narrative_language_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            status_text = format_status(inspect_host_policy(codex_home))

            self.assertIn("narrative_language: zh-CN (configured)", status_text)
            self.assertIn("artifact_language_policy: repository/task controlled", status_text)

    def test_validate_reports_drift_when_narrative_policy_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            agents_path = codex_home / "AGENTS.md"
            agents_path.write_text(
                agents_path.read_text(encoding="utf-8").replace(
                    "## User-Facing Narrative Language",
                    "## User-Facing Language Removed",
                ),
                encoding="utf-8",
            )

            status, lines, exit_code = validate_host_policy(codex_home)

            self.assertEqual(status.narrative_language_state, "drifted")
            self.assertEqual(status.overall_state, "drifted")
            self.assertEqual(exit_code, 1)
            self.assertTrue(any("Host policy files are drifted" in line for line in lines))

    def test_validate_with_real_codex_cli_when_available(self) -> None:
        if shutil.which("codex") is None:
            self.skipTest("codex CLI is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            status, lines, exit_code = validate_host_policy(codex_home)

            self.assertEqual(status.overall_state, "configured")
            self.assertEqual(status.trusted_ai_bridge_executable, resolve_ai_bridge_executable())
            self.assertEqual(exit_code, 0, "\n".join(lines))
            self.assertTrue(any("Trusted ai-bridge executable:" in line for line in lines))
            self.assertTrue(
                any(
                    "Feature availability: default_mode_request_user_input supported/" in line
                    and "memories available/enabled" in line
                    for line in lines
                )
            )
            self.assertTrue(any("ai-bridge plugin-replay" in line and "=> allow" in line for line in lines))
            self.assertTrue(any("ai-bridge host publish-current-branch" in line and "=> allow" in line for line in lines))
            self.assertTrue(any("ai-bridge reviewed-handoff materialize-worktree" in line and "=> allow" in line for line in lines))
            self.assertTrue(any("gh auth status -- => allow" in line for line in lines))
            self.assertTrue(any("gh pr list -- => allow" in line for line in lines))
            self.assertTrue(any("gh pr status -- => allow" in line for line in lines))
            self.assertTrue(any("gh issue list -- => allow" in line for line in lines))
            self.assertTrue(any("gh issue status -- => allow" in line for line in lines))
            self.assertTrue(any("gh run list -- => allow" in line for line in lines))
            self.assertTrue(any("gh auth status --show-token => prompt" in line for line in lines))
            self.assertTrue(any("gh pr view 1 => prompt" in line for line in lines))
            self.assertTrue(any("gh pr list --repo private/repo => prompt" in line for line in lines))
            self.assertTrue(any("gh api /user => prompt" in line for line in lines))
            self.assertTrue(any("squeue -j 156911 -o %.18i %.9P %.30j %.8u %.2t %.12M %.12l %.20R %.30b => allow" in line for line in lines))
            self.assertTrue(any("squeue -u testuser -h => allow" in line for line in lines))
            self.assertTrue(any("sinfo -h => allow" in line for line in lines))
            self.assertTrue(any("sacct -j 156911 => allow" in line for line in lines))
            self.assertTrue(any("sstat -j 156911.batch => allow" in line for line in lines))
            self.assertTrue(any("sprio -j 156911 => allow" in line for line in lines))
            self.assertTrue(any("scontrol show job 156911 => allow" in line for line in lines))
            self.assertTrue(any("scontrol show partition => allow" in line for line in lines))
            self.assertTrue(any("scontrol ping => allow" in line for line in lines))
            self.assertTrue(any("sbatch job.sh => prompt" in line for line in lines))
            self.assertTrue(any("srun --pty bash => prompt" in line for line in lines))
            self.assertTrue(any("salloc -t 00:10:00 => prompt" in line for line in lines))
            self.assertTrue(any("scancel 156911 => prompt" in line for line in lines))
            self.assertTrue(any("scontrol update JobId=156911 TimeLimit=30 => prompt" in line for line in lines))
            self.assertTrue(any("scontrol hold 156911 => prompt" in line for line in lines))
            self.assertTrue(any("scontrol release 156911 => prompt" in line for line in lines))
            self.assertTrue(any("scontrol requeue 156911 => prompt" in line for line in lines))
            self.assertTrue(any("scontrol suspend 156911 => prompt" in line for line in lines))
            self.assertTrue(any("scontrol resume 156911 => prompt" in line for line in lines))
            self.assertTrue(any("sacctmgr modify user name=test set Fairshare=2 => prompt" in line for line in lines))
            self.assertTrue(any("bash -lc squeue -h | xargs scancel => prompt" in line for line in lines))
            self.assertTrue(any("ps -u testuser -o pid,ppid,stat,etime,cmd => allow" in line for line in lines))
            self.assertTrue(any("ps -ef => allow" in line for line in lines))
            self.assertTrue(any("kill 123 => prompt" in line for line in lines))
            self.assertTrue(any("pkill python => prompt" in line for line in lines))
            self.assertTrue(any("renice 10 -p 123 => prompt" in line for line in lines))
            self.assertTrue(any("setsid bash => prompt" in line for line in lines))
            self.assertTrue(any("python script.py => prompt" in line for line in lines))
            self.assertTrue(any("bash -lc ps -ef => prompt" in line for line in lines))
            self.assertTrue(any("sh -c ps -ef => prompt" in line for line in lines))
            self.assertTrue(any("zsh -c ps -ef => prompt" in line for line in lines))
            self.assertTrue(any("tmux ls => allow" in line for line in lines))
            self.assertTrue(any("tmux list-sessions => allow" in line for line in lines))
            self.assertTrue(any("tmux has-session -t example => allow" in line for line in lines))
            self.assertTrue(any("tmux new-session -d -s example => prompt" in line for line in lines))
            self.assertTrue(any("tmux kill-session -t example => prompt" in line for line in lines))
            self.assertTrue(any("tmux kill-server => prompt" in line for line in lines))
            self.assertTrue(any("tmux send-keys -t example ls Enter => prompt" in line for line in lines))
            self.assertTrue(any("tmux attach-session -t example => prompt" in line for line in lines))
            self.assertTrue(any("tmux detach-client -s example => prompt" in line for line in lines))
            self.assertTrue(any("codex exec -C /tmp - => prompt" in line for line in lines))
            self.assertTrue(any("git fetch origin main => allow" in line for line in lines))
            self.assertTrue(any("git fetch --all --prune => allow" in line for line in lines))
            self.assertTrue(any("git fetch https://example.invalid/repo.git main => prompt" in line for line in lines))
            self.assertTrue(any("git fetch origin feature:feature => prompt" in line for line in lines))
            self.assertTrue(any("git pull --ff-only origin main => allow" in line for line in lines))
            self.assertTrue(any("git pull --rebase origin main => prompt" in line for line in lines))
            self.assertTrue(any("git pull --ff-only --autostash origin main => prompt" in line for line in lines))
            self.assertTrue(any("git pull --ff-only origin main --autostash => prompt" in line for line in lines))
            self.assertTrue(any("git add README.md => allow" in line for line in lines))
            self.assertTrue(any("git commit -m test => allow" in line for line in lines))
            self.assertTrue(any("git commit --amend --no-edit => allow" in line for line in lines))
            self.assertTrue(any("git push origin main => prompt" in line for line in lines))
            self.assertTrue(any("git push origin test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git push upstream main => no_match" in line for line in lines))
            self.assertTrue(any("git switch main => prompt" in line for line in lines))
            self.assertTrue(any("git switch -c test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git checkout -b test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git branch test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git reset --hard => prompt" in line for line in lines))
            self.assertTrue(any("git clean -fd => prompt" in line for line in lines))
            self.assertTrue(any("git restore README.md => prompt" in line for line in lines))
            self.assertTrue(any("git remote add mirror https://example.invalid/repo.git => prompt" in line for line in lines))
            self.assertTrue(any("git remote remove origin => prompt" in line for line in lines))
            self.assertTrue(any("git remote set-url origin https://example.invalid/repo.git => prompt" in line for line in lines))
            self.assertTrue(any("git branch -d test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git branch -m old-branch new-branch => prompt" in line for line in lines))
            self.assertTrue(any("git worktree add ../wt -b test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git push -u origin test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git push --set-upstream origin test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git push origin --delete test-branch => prompt" in line for line in lines))
            self.assertTrue(any("git push origin --force main => prompt" in line for line in lines))
            self.assertTrue(any("git push origin main --force => prompt" in line for line in lines))
            self.assertTrue(any("git push origin main --force-with-lease => prompt" in line for line in lines))
            self.assertTrue(any("git push origin main -f => prompt" in line for line in lines))

    def test_execpolicy_git_authorization_semantics_with_real_codex_cli_when_available(self) -> None:
        if shutil.which("codex") is None:
            self.skipTest("codex CLI is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            rules_path = codex_home / RULES_RELATIVE_PATH
            expectations = {
                ("ai-bridge", "plugin-replay", "--target", str(Path.cwd()), "--plugin", "sites", "--task", "TASK.md", "--input", "INPUT.txt", "--dry-run"): "allow",
                ("ai-bridge", "host", "publish-current-branch", "--expected-repo", "YuukiAS/GPT_Codex_AI_Bridge_Kit", "--expected-branch", "main"): "allow",
                ("ai-bridge", "reviewed-handoff", "materialize-worktree", "--target", str(Path.cwd()), "--task-key", "repo--feature", "--expected-repo", "YuukiAS/GPT_Codex_AI_Bridge_Kit", "--expected-worktree", "/tmp/repo--feature", "--expected-base-ref", "origin/main", "--mode", "bootstrap"): "allow",
                ("gh", "auth", "status", "--"): "allow",
                ("gh", "pr", "list", "--"): "allow",
                ("gh", "pr", "status", "--"): "allow",
                ("gh", "issue", "list", "--"): "allow",
                ("gh", "issue", "status", "--"): "allow",
                ("gh", "run", "list", "--"): "allow",
                ("gh", "auth", "status", "--show-token"): "prompt",
                ("gh", "pr", "view", "1"): "prompt",
                ("gh", "pr", "list", "--repo", "private/repo"): "prompt",
                ("gh", "api", "/user"): "prompt",
                ("squeue", "-j", "156911", "-o", "%.18i %.9P %.30j %.8u %.2t %.12M %.12l %.20R %.30b"): "allow",
                ("squeue", "-u", "testuser", "-h"): "allow",
                ("sinfo", "-h"): "allow",
                ("sacct", "-j", "156911"): "allow",
                ("sstat", "-j", "156911.batch"): "allow",
                ("sprio", "-j", "156911"): "allow",
                ("scontrol", "show", "job", "156911"): "allow",
                ("scontrol", "show", "partition"): "allow",
                ("scontrol", "ping"): "allow",
                ("sbatch", "job.sh"): "prompt",
                ("srun", "--pty", "bash"): "prompt",
                ("salloc", "-t", "00:10:00"): "prompt",
                ("scancel", "156911"): "prompt",
                ("scontrol", "update", "JobId=156911", "TimeLimit=30"): "prompt",
                ("scontrol", "hold", "156911"): "prompt",
                ("scontrol", "release", "156911"): "prompt",
                ("scontrol", "requeue", "156911"): "prompt",
                ("scontrol", "suspend", "156911"): "prompt",
                ("scontrol", "resume", "156911"): "prompt",
                ("sacctmgr", "modify", "user", "name=test", "set", "Fairshare=2"): "prompt",
                ("bash", "-lc", "squeue -h | xargs scancel"): "prompt",
                ("ps", "-u", "testuser", "-o", "pid,ppid,stat,etime,cmd"): "allow",
                ("ps", "-ef"): "allow",
                ("kill", "123"): "prompt",
                ("pkill", "python"): "prompt",
                ("renice", "10", "-p", "123"): "prompt",
                ("setsid", "bash"): "prompt",
                ("python", "script.py"): "prompt",
                ("bash", "-lc", "ps -ef"): "prompt",
                ("sh", "-c", "ps -ef"): "prompt",
                ("zsh", "-c", "ps -ef"): "prompt",
                ("tmux", "ls"): "allow",
                ("tmux", "list-sessions"): "allow",
                ("tmux", "has-session", "-t", "example"): "allow",
                ("tmux", "new-session", "-d", "-s", "example"): "prompt",
                ("tmux", "kill-session", "-t", "example"): "prompt",
                ("tmux", "kill-server"): "prompt",
                ("tmux", "send-keys", "-t", "example", "ls", "Enter"): "prompt",
                ("tmux", "attach-session", "-t", "example"): "prompt",
                ("tmux", "detach-client", "-s", "example"): "prompt",
                ("codex", "exec", "-C", "/tmp", "-"): "prompt",
                ("git", "fetch", "origin", "main"): "allow",
                ("git", "fetch", "--all", "--prune"): "allow",
                ("git", "fetch", "https://example.invalid/repo.git", "main"): "prompt",
                ("git", "fetch", "origin", "feature:feature"): "prompt",
                ("git", "pull", "--ff-only", "origin", "main"): "allow",
                ("git", "pull", "--rebase", "origin", "main"): "prompt",
                ("git", "pull", "--ff-only", "--autostash", "origin", "main"): "prompt",
                ("git", "pull", "--ff-only", "origin", "main", "--autostash"): "prompt",
                ("git", "add", "README.md"): "allow",
                ("git", "commit", "-m", "test"): "allow",
                ("git", "commit", "--amend", "--no-edit"): "allow",
                ("git", "push", "origin", "main"): "prompt",
                ("git", "push", "origin", "test-branch"): "prompt",
                ("git", "push", "upstream", "main"): "no_match",
                ("git", "switch", "main"): "prompt",
                ("git", "switch", "-c", "test-branch"): "prompt",
                ("git", "checkout", "-b", "test-branch"): "prompt",
                ("git", "branch", "test-branch"): "prompt",
                ("git", "reset", "--hard"): "prompt",
                ("git", "clean", "-fd"): "prompt",
                ("git", "restore", "README.md"): "prompt",
                ("git", "remote", "add", "mirror", "https://example.invalid/repo.git"): "prompt",
                ("git", "remote", "remove", "origin"): "prompt",
                ("git", "remote", "set-url", "origin", "https://example.invalid/repo.git"): "prompt",
                ("git", "branch", "-d", "test-branch"): "prompt",
                ("git", "branch", "-D", "test-branch"): "prompt",
                ("git", "branch", "-m", "old-branch", "new-branch"): "prompt",
                ("git", "worktree", "add", "../wt", "-b", "test-branch"): "prompt",
                ("git", "push", "-u", "origin", "test-branch"): "prompt",
                ("git", "push", "--set-upstream", "origin", "test-branch"): "prompt",
                ("git", "push", "origin", "--delete", "test-branch"): "prompt",
                ("git", "push", "origin", "--force", "main"): "prompt",
                ("git", "push", "origin", "main", "--force"): "prompt",
                ("git", "push", "origin", "main", "--force-with-lease"): "prompt",
                ("git", "push", "origin", "main", "-f"): "prompt",
            }

            for command, expected in expectations.items():
                with self.subTest(command=" ".join(command)):
                    decision, raw = _execpolicy_decision(
                        rules_path,
                        list(command),
                        resolve_host_executables=command[0] == "ai-bridge",
                    )
                    observed = decision if expected == "no_match" else _effective_execpolicy_decision(decision)
                    self.assertEqual(observed, expected, raw)

    def test_execpolicy_does_not_trust_repo_local_fake_ai_bridge(self) -> None:
        if shutil.which("codex") is None:
            self.skipTest("codex CLI is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / "codex-home"
            repo = Path(tmp) / "repo"
            repo.mkdir()
            fake = repo / "ai-bridge"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake.chmod(0o700)
            install_host_policy(codex_home)
            rules_path = codex_home / RULES_RELATIVE_PATH

            decision, raw = _execpolicy_decision(
                rules_path,
                ["./ai-bridge", "plugin-replay", "--plugin", "sites"],
                resolve_host_executables=True,
            )

            self.assertEqual(_effective_execpolicy_decision(decision), "prompt", raw)

    def test_shared_repo_identity_still_supports_reviewed_and_local_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "repo.git"
            local.mkdir()

            self.assertEqual(_canonical_repo_identity("https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git"), "YuukiAS/GPT_Codex_AI_Bridge_Kit")
            self.assertEqual(_canonical_repo_identity("git@github.com:YuukiAS/GPT_Codex_AI_Bridge_Kit.git"), "YuukiAS/GPT_Codex_AI_Bridge_Kit")
            self.assertEqual(_canonical_repo_identity("ssh://git@github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git"), "YuukiAS/GPT_Codex_AI_Bridge_Kit")
            self.assertEqual(_canonical_repo_identity(str(local)), "local:" + local.resolve().as_posix())

    def test_publish_current_branch_pushes_existing_same_name_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_github_https_publish_repo(tmp)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

            result, network_calls = self.run_with_fake_github_network(
                repo,
                lambda: publish_current_branch(
                    repo,
                    expected_repo=identity,
                    expected_branch="main",
                    env={"PATH": os.environ["PATH"]},
                ),
            )

            self.assertEqual(result.status, "published")
            self.assertEqual(result.pushed_oid, head)
            self.assertEqual([call[0] for call in network_calls], ["ls-remote", "ls-remote", "-c"])

    def test_publish_current_branch_cli_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_github_https_publish_repo(tmp)
            old_cwd = Path.cwd()
            try:
                os.chdir(repo)
                code, network_calls = self.run_with_fake_github_network(
                    repo,
                    lambda: bridge_cli.main(
                        [
                            "host",
                            "publish-current-branch",
                            "--expected-repo",
                            identity,
                            "--expected-branch",
                            "main",
                        ]
                    ),
                )
            finally:
                os.chdir(old_cwd)

            self.assertEqual(code, 0)
            self.assertEqual([call[0] for call in network_calls], ["ls-remote", "ls-remote", "-c"])

    def test_publish_current_branch_rejects_wrong_repo_branch_and_remote_ahead(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_github_https_publish_repo(tmp)
            with self.assertRaisesRegex(HostPublishError, "REMOTE_IDENTITY_MISMATCH"):
                publish_current_branch(repo, expected_repo="YuukiAS/Other_Repo", expected_branch="main", env={"PATH": os.environ["PATH"]})
            with self.assertRaisesRegex(HostPublishError, "BRANCH_ASSERTION_FAILED"):
                publish_current_branch(repo, expected_repo=identity, expected_branch="develop", env={"PATH": os.environ["PATH"]})

            with self.assertRaisesRegex(HostPublishError, "REMOTE_AHEAD_REQUIRES_PULL"):
                self.run_with_fake_github_network(
                    repo,
                    lambda: publish_current_branch(repo, expected_repo=identity, expected_branch="main", env={"PATH": os.environ["PATH"]}),
                    remote_oid="0" * 40,
                )

    def test_publish_current_branch_rejects_non_https_effective_transports_before_network(self) -> None:
        cases = [
            ("git@github.com:YuukiAS/GPT_Codex_AI_Bridge_Kit.git", None),
            ("ssh://git@github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git", None),
            ("foo::YuukiAS/GPT_Codex_AI_Bridge_Kit", None),
            ("https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git", ("url.git@github.com:.insteadOf", "https://github.com/")),
        ]
        for remote_url, rewrite in cases:
            with self.subTest(remote_url=remote_url, rewrite=rewrite):
                with tempfile.TemporaryDirectory() as tmp:
                    repo, identity = self.make_github_https_publish_repo(tmp)
                    subprocess.check_call(["git", "remote", "set-url", "origin", remote_url], cwd=repo)
                    if rewrite:
                        subprocess.check_call(["git", "config", "--local", rewrite[0], rewrite[1]], cwd=repo)

                    self.assert_publish_rejects_before_network(
                        repo,
                        identity,
                        message="UNSUPPORTED_TRANSPORT_REQUIRES_ORDINARY_APPROVAL",
                    )

    def test_publish_current_branch_rejects_https_fetch_ssh_push_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_github_https_publish_repo(tmp)
            subprocess.check_call(
                ["git", "remote", "set-url", "--push", "origin", "git@github.com:YuukiAS/GPT_Codex_AI_Bridge_Kit.git"],
                cwd=repo,
            )

            self.assert_publish_rejects_before_network(
                repo,
                identity,
                message="UNSUPPORTED_TRANSPORT_REQUIRES_ORDINARY_APPROVAL",
            )

    def test_publish_current_branch_transport_fence_negatives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_publish_repo(tmp)
            ssh, ssh_marker = self.make_canary(tmp, "ssh-canary")
            askpass, askpass_marker = self.make_canary(tmp, "askpass-canary")
            cases = [
                ({"GIT_SSH_COMMAND": str(ssh)}, "CUSTOM_SSH_TRANSPORT_REQUIRES_APPROVAL", ssh_marker),
                ({"GIT_SSH": str(ssh)}, "CUSTOM_SSH_TRANSPORT_REQUIRES_APPROVAL", ssh_marker),
                ({"GIT_ASKPASS": str(askpass)}, "ASKPASS_REQUIRES_APPROVAL", askpass_marker),
                ({"SSH_ASKPASS": str(askpass)}, "ASKPASS_REQUIRES_APPROVAL", askpass_marker),
                ({"GIT_CONFIG_GLOBAL": str(Path(tmp) / "gitconfig")}, "CUSTOM_GIT_CONFIG_REQUIRES_APPROVAL", ssh_marker),
                ({"GIT_CONFIG_SYSTEM": str(Path(tmp) / "gitconfig")}, "CUSTOM_GIT_CONFIG_REQUIRES_APPROVAL", ssh_marker),
                ({"GIT_CONFIG_NOSYSTEM": "1"}, "CUSTOM_GIT_CONFIG_REQUIRES_APPROVAL", ssh_marker),
                (
                    {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "credential.helper", "GIT_CONFIG_VALUE_0": f"!{ssh}"},
                    "CUSTOM_GIT_CONFIG_REQUIRES_APPROVAL",
                    ssh_marker,
                ),
            ]
            for extra_env, message, marker in cases:
                with self.subTest(extra_env=extra_env):
                    marker.unlink(missing_ok=True)
                    env = {"PATH": os.environ["PATH"], **extra_env}
                    self.assert_publish_rejects_without_canary_or_remote_change(
                        repo,
                        identity,
                        tmp,
                        env=env,
                        message=message,
                        marker=marker,
                    )

    def test_publish_current_branch_rejects_repo_config_injection_and_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ssh, ssh_marker = self.make_canary(tmp, "ssh-config-canary")
            askpass, askpass_marker = self.make_canary(tmp, "askpass-config-canary")
            cred, cred_marker = self.make_canary(tmp, "credential-canary")
            config_cases = [
                ("core.sshCommand", str(ssh), "CUSTOM_SSH_TRANSPORT_REQUIRES_APPROVAL", ssh_marker),
                ("credential.helper", f"!{cred}", "REPO_CREDENTIAL_HELPER_REQUIRES_APPROVAL", cred_marker),
                ("core.askPass", str(askpass), "ASKPASS_REQUIRES_APPROVAL", askpass_marker),
                ("push.followTags", "true", "FOLLOW_TAGS_REQUIRES_APPROVAL", ssh_marker),
                ("push.recurseSubmodules", "on-demand", "RECURSIVE_SUBMODULE_PUSH_REQUIRES_APPROVAL", ssh_marker),
                ("push.pushOption", "ci.skip", "PUSH_OPTIONS_REQUIRE_APPROVAL", ssh_marker),
                ("push.gpgSign", "true", "SIGNED_PUSH_REQUIRES_APPROVAL", ssh_marker),
            ]
            for key, value, message, marker in config_cases:
                with self.subTest(key=key):
                    case_root = Path(tmp) / key.replace(".", "-")
                    case_root.mkdir()
                    repo, identity = self.make_publish_repo(str(case_root))
                    marker.unlink(missing_ok=True)
                    subprocess.check_call(["git", "config", "--local", key, value], cwd=repo)
                    self.assert_publish_rejects_without_canary_or_remote_change(
                        repo,
                        identity,
                        str(case_root),
                        env={"PATH": os.environ["PATH"]},
                        message=message,
                        marker=marker,
                    )

    def test_publish_current_branch_rejects_worktree_config_canaries_before_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_publish_repo(tmp)
            ssh, ssh_marker = self.make_canary(tmp, "worktree-ssh-canary")
            cred, cred_marker = self.make_canary(tmp, "worktree-credential-canary")
            subprocess.check_call(["git", "config", "extensions.worktreeConfig", "true"], cwd=repo)
            cases = [
                ("core.sshCommand", str(ssh), "CUSTOM_SSH_TRANSPORT_REQUIRES_APPROVAL", ssh_marker),
                ("credential.helper", f"!{cred}", "REPO_CREDENTIAL_HELPER_REQUIRES_APPROVAL", cred_marker),
            ]
            for key, value, message, marker in cases:
                with self.subTest(key=key):
                    marker.unlink(missing_ok=True)
                    subprocess.check_call(["git", "config", "--worktree", key, value], cwd=repo)
                    self.assert_publish_rejects_without_canary_or_remote_change(
                        repo,
                        identity,
                        tmp,
                        env={"PATH": os.environ["PATH"]},
                        message=message,
                        marker=marker,
                    )
                    subprocess.check_call(["git", "config", "--worktree", "--unset-all", key], cwd=repo)

        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_publish_repo(tmp)
            hook = repo / ".git" / "hooks" / "pre-push"
            hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            hook.chmod(0o700)
            with self.assertRaisesRegex(HostPublishError, "PRE_PUSH_HOOK_REQUIRES_APPROVAL"):
                publish_current_branch(repo, expected_repo=identity, expected_branch="main", env={"PATH": os.environ["PATH"]})

    def test_publish_current_branch_rejects_review_executor_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_publish_repo(tmp)
            with self.assertRaisesRegex(HostPublishError, "REVIEW_EXECUTOR_GUARD"):
                publish_current_branch(
                    repo,
                    expected_repo=identity,
                    expected_branch="main",
                    env={"PATH": os.environ["PATH"], "AI_BRIDGE_REVIEWED_RUNNER_PUSH_GUARD": "1"},
                )

    def test_publish_current_branch_rejects_real_reviewed_runner_guard_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, identity = self.make_publish_repo(tmp)
            old_state_home = os.environ.get("AI_BRIDGE_STATE_HOME")
            os.environ["AI_BRIDGE_STATE_HOME"] = str(Path(tmp) / "state")
            try:
                guard_env = reviewed_runner.push_guard_environment(repo)
            finally:
                if old_state_home is None:
                    os.environ.pop("AI_BRIDGE_STATE_HOME", None)
                else:
                    os.environ["AI_BRIDGE_STATE_HOME"] = old_state_home

            with self.assertRaisesRegex(HostPublishError, "CUSTOM_GIT_CONFIG_REQUIRES_APPROVAL"):
                publish_current_branch(repo, expected_repo=identity, expected_branch="main", env=guard_env)


if __name__ == "__main__":
    unittest.main()
