from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import overleaf


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def git_call(cwd: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class OverleafBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous_state_home = os.environ.get("AI_BRIDGE_STATE_HOME")
        os.environ["AI_BRIDGE_STATE_HOME"] = str(self.root / "state")

    def tearDown(self) -> None:
        if self.previous_state_home is None:
            os.environ.pop("AI_BRIDGE_STATE_HOME", None)
        else:
            os.environ["AI_BRIDGE_STATE_HOME"] = self.previous_state_home
        self.tmp.cleanup()

    def make_project(self) -> Path:
        target = self.root / f"research-{len(list(self.root.glob('research-*')))}"
        (target / "paper" / "manuscript" / "sections").mkdir(parents=True)
        (target / "code").mkdir()
        (target / "results").mkdir()
        (target / "paper" / "notes").mkdir(parents=True)
        (target / "paper" / "manuscript" / "main.tex").write_text("\\input{sections/intro}\n", encoding="utf-8")
        (target / "paper" / "manuscript" / "sections" / "intro.tex").write_text("Intro v1\n", encoding="utf-8")
        (target / "paper" / "manuscript" / "AGENTS.md").write_text("local manuscript rules\n", encoding="utf-8")
        (target / "paper" / "manuscript" / "main.pdf").write_text("compiled\n", encoding="utf-8")
        (target / "paper" / "notes" / "private.md").write_text("notes\n", encoding="utf-8")
        (target / "code" / "analysis.py").write_text("print('not paper')\n", encoding="utf-8")
        (target / "results" / "table.csv").write_text("x,y\n", encoding="utf-8")
        git_call(target, "init", "--initial-branch", "main")
        git_call(target, "config", "user.email", "test@example.org")
        git_call(target, "config", "user.name", "Test User")
        git_call(target, "add", ".")
        git_call(target, "commit", "-m", "initial")
        return target

    def make_empty_remote(self, branch: str = "master") -> Path:
        remote = self.root / f"overleaf-{len(list(self.root.glob('overleaf-*.git')))}.git"
        git_call(self.root, "init", "--bare", "--initial-branch", branch, str(remote))
        work = self.root / f"remote-empty-{len(list(self.root.glob('remote-empty-*')))}"
        git_call(self.root, "clone", str(remote), str(work))
        git_call(work, "config", "user.email", "remote@example.org")
        git_call(work, "config", "user.name", "Remote User")
        git_call(work, "checkout", "-B", branch)
        git_call(work, "commit", "--allow-empty", "-m", "empty remote")
        git_call(work, "push", "origin", branch)
        return remote

    def make_seeded_remote(self, files: dict[str, str], branch: str = "master") -> Path:
        remote = self.make_empty_remote(branch=branch)
        work = self.root / f"remote-work-{len(list(self.root.glob('remote-work-*')))}"
        git_call(self.root, "clone", str(remote), str(work))
        git_call(work, "config", "user.email", "remote@example.org")
        git_call(work, "config", "user.name", "Remote User")
        git_call(work, "checkout", "-B", branch)
        for rel, text in files.items():
            path = work / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git_call(work, "add", ".")
        git_call(work, "commit", "-m", "seed remote")
        git_call(work, "push", "origin", branch)
        return remote

    def remote_files(self, remote: Path, branch: str = "master") -> list[str]:
        return git(remote, "ls-tree", "-r", "--name-only", branch).splitlines()

    def remote_text(self, remote: Path, rel: str, branch: str = "master") -> str:
        return git(remote, "show", f"{branch}:{rel}")

    def install(self, target: Path) -> None:
        actions = overleaf.install_overleaf(target, paper_root="paper/manuscript")
        self.assertTrue(any("config.toml" in item for item in actions))

    def connect_bootstrap(self, target: Path, remote: Path) -> None:
        actions = overleaf.connect_overleaf(target, remote_url=str(remote), bootstrap=True)
        self.assertTrue(any("bootstrapped" in item for item in actions))

    def test_install_creates_config_readme_and_agents_block_idempotently(self) -> None:
        target = self.make_project()
        self.install(target)
        first_config = (target / "automation" / "overleaf" / "config.toml").read_text(encoding="utf-8")
        first_agents = (target / "AGENTS.md").read_text(encoding="utf-8")

        self.install(target)

        self.assertEqual(first_config, (target / "automation" / "overleaf" / "config.toml").read_text(encoding="utf-8"))
        self.assertEqual(first_agents, (target / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("paper_root = \"paper/manuscript\"", first_config)
        self.assertIn(overleaf.OVERLEAF_BEGIN_MARKER, first_agents)
        self.assertTrue((target / "automation" / "overleaf" / "README.md").exists())

    def test_unsafe_paths_and_symlink_escape_are_rejected(self) -> None:
        target = self.make_project()
        with self.assertRaisesRegex(overleaf.OverleafError, "paper_root"):
            overleaf.install_overleaf(target, paper_root="../paper")
        with self.assertRaisesRegex(overleaf.OverleafError, "main_document"):
            overleaf.install_overleaf(target, paper_root="paper/manuscript", main_document="../main.tex")
        self.install(target)
        config = target / "automation" / "overleaf" / "config.toml"
        config.write_text(config.read_text(encoding="utf-8").replace("exclude_paths = []", 'exclude_paths = ["../secret"]'), encoding="utf-8")
        lines, code = overleaf.validate_overleaf(target)
        self.assertEqual(code, 1)
        self.assertIn("exclude", "\n".join(lines))

        config.write_text(config.read_text(encoding="utf-8").replace('exclude_paths = ["../secret"]', "exclude_paths = []"), encoding="utf-8")
        (target / "outside.txt").write_text("outside\n", encoding="utf-8")
        os.symlink(target / "outside.txt", target / "paper" / "manuscript" / "outside-link.tex")
        git_call(target, "add", "paper/manuscript/outside-link.tex")
        git_call(target, "commit", "-m", "add unsafe symlink")
        lines, code = overleaf.validate_overleaf(target)
        self.assertEqual(code, 1)
        self.assertTrue(any("symlink" in item for item in lines))

    def test_bootstrap_empty_remote_flattens_publication_root_only(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)

        self.assertEqual(
            self.remote_files(remote),
            ["AGENTS.md", "main.pdf", "main.tex", "sections/intro.tex"],
        )
        self.assertEqual(self.remote_text(remote, "main.tex"), "\\input{sections/intro}")
        self.assertNotIn("paper/manuscript/main.tex", self.remote_files(remote))
        self.assertNotIn("code/analysis.py", self.remote_files(remote))
        self.assertNotIn("results/table.csv", self.remote_files(remote))
        self.assertTrue(overleaf.connection_path(target).exists())

    def test_bootstrap_refuses_non_empty_remote_and_preserves_content(self) -> None:
        target = self.make_project()
        remote = self.make_seeded_remote({"main.tex": "remote draft\n"})
        self.install(target)

        with self.assertRaisesRegex(overleaf.OverleafError, "not empty"):
            overleaf.connect_overleaf(target, remote_url=str(remote), bootstrap=True)

        self.assertEqual(self.remote_text(remote, "main.tex"), "remote draft")
        self.assertFalse(overleaf.connection_path(target).exists())

    def test_push_excludes_paths_and_propagates_deletion(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        config = target / "automation" / "overleaf" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace("exclude_paths = []", 'exclude_paths = ["AGENTS.md", "main.pdf"]'),
            encoding="utf-8",
        )
        self.connect_bootstrap(target, remote)
        self.assertEqual(self.remote_files(remote), ["main.tex", "sections/intro.tex"])

        (target / "paper" / "manuscript" / "sections" / "intro.tex").unlink()
        (target / "paper" / "manuscript" / "main.tex").write_text("Body only\n", encoding="utf-8")
        git_call(target, "add", "-A")
        git_call(target, "commit", "-m", "revise paper")
        result = overleaf.push_overleaf(target)

        self.assertTrue(any("Published" in item for item in result))
        self.assertEqual(self.remote_files(remote), ["main.tex"])
        self.assertEqual(self.remote_text(remote, "main.tex"), "Body only")

    def test_push_refuses_remote_ahead(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        self.make_remote_edit(remote, {"main.tex": "remote edit\n"})

        with self.assertRaisesRegex(overleaf.OverleafError, "remote is ahead"):
            overleaf.push_overleaf(target)

    def make_remote_edit(self, remote: Path, updates: dict[str, str | None], branch: str = "master") -> None:
        work = self.root / f"collab-{len(list(self.root.glob('collab-*')))}"
        git_call(self.root, "clone", str(remote), str(work))
        git_call(work, "config", "user.email", "remote@example.org")
        git_call(work, "config", "user.name", "Remote User")
        git_call(work, "checkout", branch)
        for rel, text in updates.items():
            path = work / rel
            if text is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
        git_call(work, "add", "-A")
        git_call(work, "commit", "-m", "remote edit")
        git_call(work, "push", "origin", branch)

    def test_pull_imports_remote_edit_add_delete_without_touching_outside_or_excludes(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        config = target / "automation" / "overleaf" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace("exclude_paths = []", 'exclude_paths = ["AGENTS.md"]'),
            encoding="utf-8",
        )
        self.connect_bootstrap(target, remote)
        self.make_remote_edit(
            remote,
            {
                "main.tex": "remote body\n",
                "sections/intro.tex": None,
                "sections/methods.tex": "Methods\n",
                "AGENTS.md": "remote should be ignored\n",
            },
        )

        result = overleaf.pull_overleaf(target)

        self.assertIn("Imported Overleaf changes", "\n".join(result))
        self.assertEqual((target / "paper" / "manuscript" / "main.tex").read_text(encoding="utf-8"), "remote body\n")
        self.assertFalse((target / "paper" / "manuscript" / "sections" / "intro.tex").exists())
        self.assertEqual((target / "paper" / "manuscript" / "sections" / "methods.tex").read_text(encoding="utf-8"), "Methods\n")
        self.assertEqual((target / "paper" / "manuscript" / "AGENTS.md").read_text(encoding="utf-8"), "local manuscript rules\n")
        self.assertEqual((target / "code" / "analysis.py").read_text(encoding="utf-8"), "print('not paper')\n")
        self.assertIn("sections/methods.tex", overleaf.changed_publishable_paths(overleaf.load_config(target)))

    def test_pull_refuses_untracked_conflict_without_touching_files_or_baseline(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        before_connection = json.loads(overleaf.connection_path(target).read_text(encoding="utf-8"))
        self.make_remote_edit(remote, {"sections/method.tex": "remote method\n"})
        local_path = target / "paper" / "manuscript" / "sections" / "method.tex"
        local_path.write_text("local untracked method\n", encoding="utf-8")

        with self.assertRaisesRegex(overleaf.OverleafError, "uncommitted or untracked changes"):
            overleaf.pull_overleaf(target)

        self.assertEqual(local_path.read_text(encoding="utf-8"), "local untracked method\n")
        after_connection = json.loads(overleaf.connection_path(target).read_text(encoding="utf-8"))
        self.assertEqual(after_connection["last_synced_digest"], before_connection["last_synced_digest"])

    def test_pull_refuses_ignored_publication_file_without_touching_it(self) -> None:
        target = self.make_project()
        (target / ".gitignore").write_text("paper/manuscript/cache/\n", encoding="utf-8")
        git_call(target, "add", ".gitignore")
        git_call(target, "commit", "-m", "ignore manuscript cache")
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        self.make_remote_edit(remote, {"cache/generated.tex": "remote generated\n"})
        local_path = target / "paper" / "manuscript" / "cache" / "generated.tex"
        local_path.parent.mkdir(parents=True)
        local_path.write_text("local ignored generated\n", encoding="utf-8")

        with self.assertRaisesRegex(overleaf.OverleafError, "uncommitted or untracked changes"):
            overleaf.pull_overleaf(target)

        self.assertEqual(local_path.read_text(encoding="utf-8"), "local ignored generated\n")

    def test_pull_refuses_tracked_uncommitted_modification_without_touching_file(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        self.make_remote_edit(remote, {"sections/method.tex": "remote method\n"})
        main = target / "paper" / "manuscript" / "main.tex"
        main.write_text("local dirty main\n", encoding="utf-8")

        with self.assertRaisesRegex(overleaf.OverleafError, "uncommitted or untracked changes"):
            overleaf.pull_overleaf(target)

        self.assertEqual(main.read_text(encoding="utf-8"), "local dirty main\n")
        self.assertFalse((target / "paper" / "manuscript" / "sections" / "method.tex").exists())

    def test_diverged_local_and_remote_fail_closed(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        self.make_remote_edit(remote, {"main.tex": "remote edit\n"})
        (target / "paper" / "manuscript" / "main.tex").write_text("local edit\n", encoding="utf-8")
        git_call(target, "add", "paper/manuscript/main.tex")
        git_call(target, "commit", "-m", "local edit")

        with self.assertRaisesRegex(overleaf.OverleafError, "diverged"):
            overleaf.push_overleaf(target)
        with self.assertRaisesRegex(overleaf.OverleafError, "diverged"):
            overleaf.pull_overleaf(target)
        self.assertEqual((target / "paper" / "manuscript" / "main.tex").read_text(encoding="utf-8"), "local edit\n")
        self.assertEqual(self.remote_text(remote, "main.tex"), "remote edit")

    def test_connect_bootstrap_refuses_dirty_publication_root(self) -> None:
        for dirty_kind in ["tracked", "untracked"]:
            with self.subTest(dirty_kind=dirty_kind):
                target = self.make_project()
                remote = self.make_empty_remote()
                self.install(target)
                if dirty_kind == "tracked":
                    (target / "paper" / "manuscript" / "main.tex").write_text("dirty tracked\n", encoding="utf-8")
                else:
                    (target / "paper" / "manuscript" / "sections" / "new.tex").write_text("dirty untracked\n", encoding="utf-8")

                with self.assertRaisesRegex(overleaf.OverleafError, "publication root has uncommitted or untracked changes"):
                    overleaf.connect_overleaf(target, remote_url=str(remote), bootstrap=True)

                self.assertFalse(overleaf.connection_path(target).exists())
                self.assertEqual(self.remote_files(remote), [])

    def test_connect_without_bootstrap_refuses_dirty_publication_root(self) -> None:
        target = self.make_project()
        remote = self.make_seeded_remote(
            {
                "main.tex": "\\input{sections/intro}\n",
                "sections/intro.tex": "Intro v1\n",
                "AGENTS.md": "local manuscript rules\n",
                "main.pdf": "compiled\n",
            }
        )
        self.install(target)
        (target / "paper" / "manuscript" / "main.tex").write_text("\\input{sections/intro}\n% dirty\n", encoding="utf-8")

        with self.assertRaisesRegex(overleaf.OverleafError, "publication root has uncommitted or untracked changes"):
            overleaf.connect_overleaf(target, remote_url=str(remote), bootstrap=False)

        self.assertFalse(overleaf.connection_path(target).exists())

    def test_push_refuses_dirty_publication_root(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        (target / "paper" / "manuscript" / "main.tex").write_text("dirty tracked\n", encoding="utf-8")

        with self.assertRaisesRegex(overleaf.OverleafError, "publication root has uncommitted or untracked changes"):
            overleaf.push_overleaf(target)

    def test_excluded_dirty_paths_do_not_block_status_or_sync(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        config = target / "automation" / "overleaf" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace("exclude_paths = []", 'exclude_paths = ["AGENTS.md"]'),
            encoding="utf-8",
        )
        self.connect_bootstrap(target, remote)
        (target / "paper" / "manuscript" / "AGENTS.md").write_text("local excluded dirty\n", encoding="utf-8")

        status = "\n".join(overleaf.status_overleaf(target))
        result = overleaf.push_overleaf(target)

        self.assertIn("publishable_uncommitted_changes: false", status)
        self.assertIn("Already synced", "\n".join(result))

    def test_status_dirty_next_action_prioritizes_local_cleanup(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        (target / "paper" / "manuscript" / "sections" / "draft.tex").write_text("untracked draft\n", encoding="utf-8")

        status = "\n".join(overleaf.status_overleaf(target))

        self.assertIn("publishable_uncommitted_changes: true", status)
        self.assertIn("changed_paths: sections/draft.tex", status)
        self.assertIn("next: review and commit or discard local manuscript changes before synchronization", status)
        self.assertNotIn("next: ai-bridge overleaf push", status)
        self.assertNotIn("next: ai-bridge overleaf pull", status)

    def test_connection_secret_like_fields_fail_closed_without_leakage(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        connection_path = overleaf.connection_path(target)
        payload = json.loads(connection_path.read_text(encoding="utf-8"))
        payload["token"] = "DO_NOT_PRINT_ME"
        connection_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        cfg = overleaf.load_config(target)

        with self.assertRaisesRegex(overleaf.OverleafError, "secret-like field: token") as caught:
            overleaf.load_connection(cfg)
        self.assertNotIn("DO_NOT_PRINT_ME", str(caught.exception))

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bridge_cli.main(["overleaf", "validate", "--target", str(target)])
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("secret-like field: token", combined)
        self.assertNotIn("DO_NOT_PRINT_ME", combined)

    def test_equivalent_content_refreshes_baseline_without_spurious_commit(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)
        self.make_remote_edit(remote, {"main.tex": "same edit\n"})
        before = git(remote, "rev-parse", "master")
        (target / "paper" / "manuscript" / "main.tex").write_text("same edit\n", encoding="utf-8")
        git_call(target, "add", "paper/manuscript/main.tex")
        git_call(target, "commit", "-m", "same edit")

        result = overleaf.push_overleaf(target)

        self.assertIn("Equivalent", "\n".join(result))
        self.assertEqual(git(remote, "rev-parse", "master"), before)
        conn = json.loads(overleaf.connection_path(target).read_text(encoding="utf-8"))
        cfg = overleaf.load_config(target)
        self.assertEqual(conn["last_synced_digest"], overleaf.local_projection(cfg).digest)

    def test_connect_bootstrap_resolves_main_remote_without_creating_master(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote(branch="main")
        self.install(target)

        self.connect_bootstrap(target, remote)

        conn = json.loads(overleaf.connection_path(target).read_text(encoding="utf-8"))
        self.assertEqual(conn["remote_branch"], "main")
        self.assertEqual(self.remote_files(remote, branch="main"), ["AGENTS.md", "main.pdf", "main.tex", "sections/intro.tex"])
        heads = git(remote, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
        self.assertEqual(heads, ["main"])

    def test_connect_bootstrap_resolves_master_remote(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote(branch="master")
        self.install(target)

        self.connect_bootstrap(target, remote)

        conn = json.loads(overleaf.connection_path(target).read_text(encoding="utf-8"))
        self.assertEqual(conn["remote_branch"], "master")
        self.assertEqual(self.remote_files(remote, branch="master"), ["AGENTS.md", "main.pdf", "main.tex", "sections/intro.tex"])

    def test_connect_bootstrap_allows_arbitrary_remote_branch_name(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote(branch="project")
        self.install(target)

        self.connect_bootstrap(target, remote)

        conn = json.loads(overleaf.connection_path(target).read_text(encoding="utf-8"))
        self.assertEqual(conn["remote_branch"], "project")
        self.assertEqual(self.remote_files(remote, branch="project"), ["AGENTS.md", "main.pdf", "main.tex", "sections/intro.tex"])
        self.assertFalse(git(remote, "for-each-ref", "--format=%(refname:short)", "refs/heads/master"))

    def test_resolve_remote_branch_uses_symbolic_head_when_multiple_heads_exist(self) -> None:
        remote = self.make_empty_remote(branch="main")
        work = self.root / "old-branch-work"
        git_call(self.root, "clone", str(remote), str(work))
        git_call(work, "config", "user.email", "remote@example.org")
        git_call(work, "config", "user.name", "Remote User")
        git_call(work, "checkout", "-B", "old")
        git_call(work, "commit", "--allow-empty", "-m", "old branch")
        git_call(work, "push", "origin", "old")

        self.assertEqual(overleaf.resolve_remote_branch(str(remote)), "main")

    def test_resolve_remote_branch_fails_when_multiple_heads_and_head_not_symbolic(self) -> None:
        remote = self.make_empty_remote(branch="main")
        work = self.root / "detached-head-work"
        git_call(self.root, "clone", str(remote), str(work))
        git_call(work, "config", "user.email", "remote@example.org")
        git_call(work, "config", "user.name", "Remote User")
        git_call(work, "checkout", "-B", "old")
        git_call(work, "commit", "--allow-empty", "-m", "old branch")
        git_call(work, "push", "origin", "old")
        main_commit = git(remote, "rev-parse", "main")
        (remote / "HEAD").write_text(main_commit + "\n", encoding="utf-8")

        with self.assertRaisesRegex(overleaf.OverleafError, "multiple branches"):
            overleaf.resolve_remote_branch(str(remote))

    def test_push_and_pull_use_resolved_main_branch(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote(branch="main")
        self.install(target)
        self.connect_bootstrap(target, remote)

        (target / "paper" / "manuscript" / "main.tex").write_text("Local update\n", encoding="utf-8")
        git_call(target, "add", "paper/manuscript/main.tex")
        git_call(target, "commit", "-m", "local update")
        overleaf.push_overleaf(target)
        self.assertEqual(self.remote_text(remote, "main.tex", branch="main"), "Local update")
        heads = git(remote, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
        self.assertEqual(heads, ["main"])

        self.make_remote_edit(remote, {"main.tex": "Remote update\n"}, branch="main")
        overleaf.pull_overleaf(target)
        self.assertEqual((target / "paper" / "manuscript" / "main.tex").read_text(encoding="utf-8"), "Remote update\n")

    def test_install_migrates_legacy_tracked_remote_branch_config(self) -> None:
        target = self.make_project()
        self.install(target)
        config = target / "automation" / "overleaf" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace("exclude_paths = []", 'remote_branch = "master"\nexclude_paths = ["AGENTS.md", "main.pdf"]'),
            encoding="utf-8",
        )

        actions = overleaf.install_overleaf(target, paper_root="paper/manuscript")

        migrated = config.read_text(encoding="utf-8")
        self.assertTrue(any("legacy remote_branch" in item for item in actions))
        self.assertIn('paper_root = "paper/manuscript"', migrated)
        self.assertIn('main_document = "main.tex"', migrated)
        self.assertIn('exclude_paths = ["AGENTS.md", "main.pdf"]', migrated)
        self.assertNotIn("remote_branch", migrated)

    def test_token_like_urls_are_rejected_without_leakage(self) -> None:
        target = self.make_project()
        self.install(target)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = bridge_cli.main(
                [
                    "overleaf",
                    "connect",
                    "--target",
                    str(target),
                    "--remote-url",
                    "https://git:SECRET_TOKEN@git.overleaf.com/project",
                    "--bootstrap",
                ]
            )
        self.assertEqual(code, 1)
        self.assertNotIn("SECRET_TOKEN", stdout.getvalue() + stderr.getvalue())
        self.assertNotIn("remote_url", (target / "automation" / "overleaf" / "config.toml").read_text(encoding="utf-8"))

    def test_connect_without_bootstrap_requires_equivalent_content(self) -> None:
        target = self.make_project()
        remote = self.make_seeded_remote({"main.tex": "\\input{sections/intro}\n", "sections/intro.tex": "Intro v1\n", "AGENTS.md": "local manuscript rules\n", "main.pdf": "compiled\n"})
        self.install(target)

        result = overleaf.connect_overleaf(target, remote_url=str(remote), bootstrap=False)

        self.assertIn("matching", "\n".join(result))
        self.assertTrue(overleaf.connection_path(target).exists())

    def test_status_and_validate_report_next_actions(self) -> None:
        target = self.make_project()
        remote = self.make_empty_remote()
        self.install(target)
        self.connect_bootstrap(target, remote)

        status = "\n".join(overleaf.status_overleaf(target))
        lines, code = overleaf.validate_overleaf(target)

        self.assertEqual(code, 0)
        self.assertIn("connected: true", status)
        self.assertIn("sync: synced", status)
        self.assertIn("Overleaf Bridge validation passed", "\n".join(lines))

    def test_cli_help_and_router_are_available(self) -> None:
        for argv in [
            ["overleaf", "--help"],
            ["overleaf", "install", "--help"],
            ["overleaf", "connect", "--help"],
            ["overleaf", "status", "--help"],
            ["overleaf", "push", "--help"],
            ["overleaf", "pull", "--help"],
            ["overleaf", "validate", "--help"],
        ]:
            with self.subTest(argv=argv):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as caught:
                        bridge_cli.main(argv)
                self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
