from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

from ai_bridge_kit import cli, overleaf, persistent_run


def run(command: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, env=env, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    ).stdout.strip()


def make_repo(base: Path, name: str, begin: str | None = None, end: str | None = None) -> tuple[Path, bytes, bytes]:
    root = base / name
    root.mkdir()
    git(root, "init", "--initial-branch=main")
    git(root, "config", "user.email", "gate@example.invalid")
    git(root, "config", "user.name", "Gate")
    prefix = "# 用户规则  \r\n\r\n连续空行\n尾随空白 \t \r\n".encode("utf-8")
    suffix = "\r\n\r\n后置中文\n\n末尾空白  \t".encode("utf-8")
    if begin and end:
        content = prefix + begin.encode() + b"\r\nstale managed bytes\r\n" + end.encode() + suffix
    else:
        content = prefix + suffix
    (root / "AGENTS.md").write_bytes(content)
    git(root, "add", "AGENTS.md")
    git(root, "commit", "-m", "fixture")
    return root, prefix, suffix


def snapshot(root: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*")):
        if ".git" in path.relative_to(root).parts or not path.is_file():
            continue
        data = path.read_bytes()
        result[path.relative_to(root).as_posix()] = (stat.S_IMODE(path.stat().st_mode), hashlib.sha256(data).hexdigest())
    return result


def assert_external_bytes(root: Path, begin: str, end: str, prefix: bytes, suffix: bytes) -> None:
    raw = (root / "AGENTS.md").read_bytes()
    begin_bytes = begin.encode()
    end_bytes = end.encode()
    start = raw.index(begin_bytes)
    marker_end = raw.index(end_bytes, start) + len(end_bytes)
    assert raw[:start] == prefix
    assert raw[marker_end:] == suffix
    assert b"stale managed bytes" not in raw


def main() -> None:
    base = Path(tempfile.mkdtemp(prefix="bridge-c3-a609599-", dir="/tmp"))
    bridge = os.environ["AI_BRIDGE_GATE_BIN"]
    high_home = base / "high-codex-home"
    high_home.mkdir()
    (high_home / "config.toml").write_text("project_doc_max_bytes = 32768\n", encoding="utf-8")
    high_env = dict(os.environ, CODEX_HOME=str(high_home))

    core, core_prefix, core_suffix = make_repo(base, "core-under", cli.BEGIN_MARKER, cli.END_MARKER)
    core_result = run([bridge, "init", "--target", str(core), "--force", "--no-skill"], env=high_env)
    assert core_result.returncode == 0, core_result.stderr
    assert_external_bytes(core, cli.BEGIN_MARKER, cli.END_MARKER, core_prefix, core_suffix)

    persistent, persistent_prefix, persistent_suffix = make_repo(
        base,
        "persistent-under",
        persistent_run.PERSISTENT_RUN_BEGIN_MARKER,
        persistent_run.PERSISTENT_RUN_END_MARKER,
    )
    persistent_result = run([bridge, "persistent-run", "install", "--target", str(persistent)], env=high_env)
    assert persistent_result.returncode == 0, persistent_result.stderr
    assert_external_bytes(
        persistent,
        persistent_run.PERSISTENT_RUN_BEGIN_MARKER,
        persistent_run.PERSISTENT_RUN_END_MARKER,
        persistent_prefix,
        persistent_suffix,
    )

    leaf, leaf_prefix, leaf_suffix = make_repo(
        base, "overleaf-under", overleaf.OVERLEAF_BEGIN_MARKER, overleaf.OVERLEAF_END_MARKER
    )
    (leaf / "paper" / "manuscript").mkdir(parents=True)
    (leaf / "paper" / "manuscript" / "main.tex").write_text("fixture\n", encoding="utf-8")
    leaf_result = run(
        [bridge, "overleaf", "install", "--target", str(leaf), "--paper-root", "paper/manuscript"],
        env=high_env,
    )
    assert leaf_result.returncode == 0, leaf_result.stderr
    assert_external_bytes(
        leaf,
        overleaf.OVERLEAF_BEGIN_MARKER,
        overleaf.OVERLEAF_END_MARKER,
        leaf_prefix,
        leaf_suffix,
    )

    low_home = base / "low-codex-home"
    low_home.mkdir()
    (low_home / "config.toml").write_text("project_doc_max_bytes = 32\n", encoding="utf-8")
    low_env = dict(os.environ, CODEX_HOME=str(low_home))
    overflow_cases: list[dict[str, object]] = []
    specifications = [
        ("core", [bridge, "init", "--force", "--no-skill"]),
        ("persistent", [bridge, "persistent-run", "install"]),
        ("overleaf", [bridge, "overleaf", "install", "--paper-root", "paper/manuscript"]),
    ]
    for name, partial_command in specifications:
        target, _, _ = make_repo(base, f"{name}-overflow")
        if name == "overleaf":
            (target / "paper" / "manuscript").mkdir(parents=True)
            (target / "paper" / "manuscript" / "main.tex").write_text("fixture\n", encoding="utf-8")
        before = snapshot(target)
        command = [*partial_command, "--target", str(target)]
        result = run(command, env=low_env)
        after = snapshot(target)
        combined = result.stdout + result.stderr
        assert result.returncode != 0, (name, result.stdout, result.stderr)
        assert "BRIDGE_MANAGED_INSTRUCTION_PROJECTED_OVERFLOW" in combined, (name, combined)
        assert before == after, (name, before, after)
        overflow_cases.append(
            {
                "writer": name,
                "exit_code": result.returncode,
                "diagnostic": "BRIDGE_MANAGED_INSTRUCTION_PROJECTED_OVERFLOW",
                "project_snapshot_unchanged": True,
            }
        )

    cap_target, _, _ = make_repo(base, "overleaf-block-cap")
    cap_before = snapshot(cap_target)
    long_root = "paper/" + ("a" * 2100)
    cap_result = run(
        [bridge, "overleaf", "install", "--target", str(cap_target), "--paper-root", long_root],
        env=high_env,
    )
    cap_after = snapshot(cap_target)
    cap_output = cap_result.stdout + cap_result.stderr
    assert cap_result.returncode != 0, cap_output
    assert "BRIDGE_MANAGED_INSTRUCTION_BLOCK_OVERFLOW" in cap_output, cap_output
    assert cap_before == cap_after

    print(
        json.dumps(
            {
                "candidate_sha": git(Path.cwd(), "rev-parse", "HEAD"),
                "fixture_root": str(base),
                "under_limit": {
                    "core": {"exit_code": 0, "external_bytes_preserved": True},
                    "persistent": {"exit_code": 0, "external_bytes_preserved": True},
                    "overleaf": {"exit_code": 0, "external_bytes_preserved": True},
                },
                "projected_overflow": overflow_cases,
                "block_cap_overflow": {
                    "writer": "overleaf",
                    "diagnostic": "BRIDGE_MANAGED_INSTRUCTION_BLOCK_OVERFLOW",
                    "project_snapshot_unchanged": True,
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
