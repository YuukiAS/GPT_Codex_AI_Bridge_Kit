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

from ai_bridge_kit import bridge_cli, host
from tests import test_host_policy


class HostNormalEntryTests(unittest.TestCase):
    def fixture(self, directory):
        repo, identity = test_host_policy.HostPolicyTests().make_github_https_publish_repo(directory)
        remote = Path(directory) / "remote.git"
        head = self.git(repo, "rev-parse", "HEAD")
        self.git(repo, "push", str(remote), "HEAD:refs/heads/feature")
        self.git(repo, "checkout", "-b", "feature", "HEAD^")
        self.git(repo, "config", "branch.feature.remote", "origin")
        self.git(repo, "config", "branch.feature.merge", "refs/heads/feature")
        return repo, remote, identity, head

    def git(self, cwd, *args):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()

    def invoke(self, repo, identity, *, env=None):
        previous = Path.cwd()
        try:
            os.chdir(repo)
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err, \
                 mock.patch.dict(os.environ, env or {"PATH": os.environ["PATH"]}, clear=True):
                code = bridge_cli.main(["host", "sync-current-branch", "--expected-repo", identity,
                                        "--expected-branch", "feature"])
            return code, out.getvalue(), err.getvalue()
        finally:
            os.chdir(previous)

    def test_cli_https_fast_forward_uses_real_git_objects_with_controlled_fetch_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, remote, identity, expected = self.fixture(tmp)
            before = self.git(repo, "rev-parse", "HEAD")
            real_git = host._git
            effects = []

            def boundary(cwd, args, *, env=None, check=True):
                if args[:2] == ["fetch", "origin"]:
                    effects.append(list(args))
                    return real_git(cwd, ["fetch", str(remote), args[2]], env=env, check=check)
                return real_git(cwd, args, env=env, check=check)

            with mock.patch.object(host, "_git", side_effect=boundary):
                code, out, err = self.invoke(repo, identity)
                self.assertEqual(code, 0, err)
                report = json.loads(out)
                self.assertEqual(report["old_oid"], before)
                self.assertEqual(report["new_oid"], expected)
                self.assertEqual(report["remote_oid"], expected)
                self.assertEqual(self.git(repo, "rev-parse", "HEAD"), expected)
                self.assertEqual(self.invoke(repo, identity)[0], 0)
            self.assertEqual(len(effects), 2)

    def test_cli_transport_and_scope_negatives_refuse_before_fetch_or_merge(self):
        cases = ["ssh", "scp", "file", "non_github", "rewrite", "push_url", "multiple_urls",
                 "wrong_repo", "wrong_branch", "wrong_upstream", "dirty", "hook", "git_env"]
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                repo, remote, identity, _ = self.fixture(tmp)
                env = {"PATH": os.environ["PATH"]}
                urls = {"ssh": "ssh://git@github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git",
                        "scp": "git@github.com:YuukiAS/GPT_Codex_AI_Bridge_Kit.git",
                        "file": str(remote), "non_github": "https://example.invalid/YuukiAS/GPT_Codex_AI_Bridge_Kit.git"}
                if case in urls:
                    self.git(repo, "remote", "set-url", "origin", urls[case])
                if case == "rewrite":
                    self.git(repo, "config", "url.ssh://git@github.com/.insteadOf", "https://github.com/")
                if case == "push_url":
                    self.git(repo, "remote", "set-url", "--push", "origin", str(remote))
                if case == "multiple_urls":
                    self.git(repo, "config", "--add", "remote.origin.url", "https://github.com/other/repo.git")
                if case == "wrong_repo":
                    identity = "YuukiAS/other"
                if case == "wrong_branch":
                    self.git(repo, "checkout", "main")
                if case == "wrong_upstream":
                    self.git(repo, "config", "branch.feature.merge", "refs/heads/main")
                if case == "dirty":
                    (repo / "unrelated.txt").write_text("preserve user-owned bytes\n")
                if case == "hook":
                    script = repo / ".git/hooks/post-merge"
                    script.write_text("#!/bin/sh\nexit 99\n")
                    script.chmod(0o700)
                if case == "git_env":
                    env["GIT_CONFIG_COUNT"] = "0"
                before = (self.git(repo, "show-ref"), (repo / "README.md").read_bytes())
                real_git = host._git
                effects = []

                def refuse_effect(cwd, args, *, env=None, check=True):
                    if args[0] in {"fetch", "merge", "push"}:
                        effects.append(list(args))
                        raise AssertionError("illegal effect before scope rejection")
                    return real_git(cwd, args, env=env, check=check)

                with mock.patch.object(host, "_git", side_effect=refuse_effect):
                    code, _, err = self.invoke(repo, identity, env=env)
                self.assertNotEqual(code, 0, err)
                self.assertEqual(effects, [])
                self.assertEqual(before, (self.git(repo, "show-ref"), (repo / "README.md").read_bytes()))

    def test_cli_divergence_does_not_merge_or_change_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, remote, identity, _ = self.fixture(tmp)
            (repo / "local.txt").write_text("local\n")
            self.git(repo, "add", "local.txt")
            self.git(repo, "commit", "-m", "diverge")
            before = self.git(repo, "rev-parse", "HEAD")
            real_git = host._git

            def boundary(cwd, args, *, env=None, check=True):
                if args[:2] == ["fetch", "origin"]:
                    return real_git(cwd, ["fetch", str(remote), args[2]], env=env, check=check)
                self.assertNotEqual(args[0], "merge")
                return real_git(cwd, args, env=env, check=check)

            with mock.patch.object(host, "_git", side_effect=boundary):
                code, _, err = self.invoke(repo, identity)
            self.assertNotEqual(code, 0)
            self.assertIn("DIVERGED", err)
            self.assertEqual(before, self.git(repo, "rev-parse", "HEAD"))

    def test_no_match_remains_unmatched_and_validation_discloses_native_unknown(self):
        self.assertEqual(host._effective_execpolicy_decision("no_match"), "no_match")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            host.install_host_policy(home)
            with mock.patch.object(host, "_codex_version", return_value=("test", None)), \
                 mock.patch.object(host, "_feature_availability", return_value=({"memories": True}, [])), \
                 mock.patch.object(host, "_execpolicy_decision", return_value=("no_match", '{"matchedRules": []}')):
                _, lines, code = host.validate_host_policy(home)
            self.assertEqual(code, 1)
            self.assertTrue(any("RULE_NO_MATCH; NATIVE_APPROVAL_UNVERIFIED" in line for line in lines))
            self.assertFalse(any("=> prompt" in line or "=> allow" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
