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
        target = self.root / "research"
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

    def make_empty_remote(self) -> Path:
        remote = self.root / "overleaf.git"
        git_call(self.root, "init", "--bare", "--initial-branch", "master", str(remote))
        return remote

    def make_seeded_remote(self, files: dict[str, str]) -> Path:
        remote = self.make_empty_remote()
        work = self.root / f"remote-work-{len(list(self.root.glob('remote-work-*')))}"
        git_call(self.root, "clone", str(remote), str(work))
        git_call(work, "config", "user.email", "remote@example.org")
        git_call(work, "config", "user.name", "Remote User")
        git_call(work, "checkout", "-B", "master")
        for rel, text in files.items():
            path = work / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        git_call(work, "add", ".")
        git_call(work, "commit", "-m", "seed remote")
        git_call(work, "push", "origin", "master")
        return remote

    def remote_files(self, remote: Path) -> list[str]:
        return git(remote, "ls-tree", "-r", "--name-only", "master").splitlines()

    def remote_text(self, remote: Path, rel: str) -> str:
        return git(remote, "show", f"master:{rel}")

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

    def make_remote_edit(self, remote: Path, updates: dict[str, str | None]) -> None:
        work = self.root / f"collab-{len(list(self.root.glob('collab-*')))}"
        git_call(self.root, "clone", str(remote), str(work))
        git_call(work, "config", "user.email", "remote@example.org")
        git_call(work, "config", "user.name", "Remote User")
        git_call(work, "checkout", "master")
        for rel, text in updates.items():
            path = work / rel
            if text is None:
                path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
        git_call(work, "add", "-A")
        git_call(work, "commit", "-m", "remote edit")
        git_call(work, "push", "origin", "master")

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
