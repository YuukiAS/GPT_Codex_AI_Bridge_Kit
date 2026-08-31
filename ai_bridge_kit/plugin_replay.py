from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_SCHEMA = "AI_BRIDGE_PLUGIN_REPLAY_RUN_V1"
READ_ISOLATION_ERROR = "READ_ISOLATION_NOT_ENFORCEABLE"
PLUGIN_RE = re.compile(r"^[A-Za-z0-9_.-]+(?:@[A-Za-z0-9_.-]+)?$")


@dataclass(frozen=True)
class StagedFile:
    role: str
    source_path: Path
    staged_path: Path
    basename: str
    size_bytes: int
    sha256: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def machine_state_home(env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    override = env.get("AI_BRIDGE_STATE_HOME")
    return Path(override).expanduser().resolve() if override else (Path.home() / ".ai-bridge").resolve()


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]


def replay_root(run_id: str, env: dict[str, str] | None = None) -> Path:
    return machine_state_home(env) / "plugin-replay" / run_id


def trusted_inbox(env: dict[str, str] | None = None) -> Path:
    return machine_state_home(env) / "plugin-replay" / "inbox"


def resolve_codex_home(explicit: Path | None = None, env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if explicit is not None:
        return explicit.expanduser().resolve()
    if env.get("CODEX_HOME"):
        return Path(env["CODEX_HOME"]).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def enforce_current_codex_home(explicit: Path | None = None, env: dict[str, str] | None = None) -> Path:
    current = resolve_codex_home(None, env)
    if explicit is None:
        return current
    requested = explicit.expanduser().resolve()
    if requested != current:
        raise ValueError(f"--codex-home cannot select another Codex identity: {requested}")
    return current


def git_root_for(path: Path, *, required: bool = True) -> Path | None:
    resolved = path.expanduser().resolve()
    result = subprocess.run(
        ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode == 0:
        line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if line:
            return Path(line).expanduser().resolve()
    if required:
        detail = result.stderr.strip() or "not a Git repository"
        raise ValueError(f"target must be a real Git repository: {resolved} ({detail})")
    return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_plugin_name(value: str) -> str:
    if not PLUGIN_RE.fullmatch(value):
        raise ValueError("plugin name must contain only letters, digits, dot, dash, underscore, and optional @marketplace")
    return value


def _require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise ValueError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"{label} must be an explicit file, not a directory: {resolved}")
    return resolved


def _authorized_roots_text(roots: list[tuple[str, Path]]) -> str:
    return ", ".join(f"{label}={root}" for label, root in roots)


def _require_file_in_roots(path: Path, label: str, roots: list[tuple[str, Path]]) -> Path:
    resolved = _require_file(path, label)
    for _, root in roots:
        if _is_within(resolved, root):
            return resolved
    raise ValueError(f"{label} is outside authorized plugin replay roots: {resolved}; allowed roots: {_authorized_roots_text(roots)}")


def resolve_target_repo(target: Path) -> Path:
    return git_root_for(target, required=True)  # type: ignore[return-value]


def authorized_input_roots(target_repo: Path, env: dict[str, str] | None = None) -> list[tuple[str, Path]]:
    return [
        ("target_repo", target_repo.resolve()),
        ("plugin_replay_inbox", trusted_inbox(env).resolve()),
    ]


def authorized_task_roots(
    target_repo: Path,
    *,
    caller_cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> list[tuple[str, Path]]:
    roots = authorized_input_roots(target_repo, env)
    caller_root = git_root_for(Path.cwd() if caller_cwd is None else caller_cwd, required=False)
    if caller_root is not None and caller_root not in [root for _, root in roots]:
        roots.append(("caller_repo", caller_root))
    return roots


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _staged_name(index: int, source: Path, role: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", source.name).strip("._") or "input"
    return f"{index:02d}_{role}_{clean}"


def stage_files(run_dir: Path, task_file: Path, input_files: list[Path], *, dry_run: bool = False) -> list[StagedFile]:
    sources = [("task", task_file), *[("input", path) for path in input_files]]
    staged: list[StagedFile] = []
    inputs_dir = run_dir / "inputs"
    if not dry_run:
        inputs_dir.mkdir(parents=True, exist_ok=True)
    for index, (role, source) in enumerate(sources, start=1):
        destination = inputs_dir / _staged_name(index, source, role)
        size = source.stat().st_size
        digest = None if dry_run else _sha256(source)
        if not dry_run:
            shutil.copy2(source, destination)
        staged.append(
            StagedFile(
                role=role,
                source_path=source,
                staged_path=destination,
                basename=source.name,
                size_bytes=size,
                sha256=digest,
            )
        )
    return staged


def _run_codex(args: list[str], *, codex_home: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        ["codex", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def installed_plugin_names(*, codex_home: Path | None = None) -> tuple[set[str] | None, str]:
    try:
        result = _run_codex(["plugin", "list"], codex_home=codex_home)
    except FileNotFoundError:
        return None, "codex executable not found"
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    if result.returncode != 0:
        return None, output or "codex plugin list failed"
    installed: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or "@" not in parts[0]:
            continue
        plugin_id = parts[0]
        status_text = line[len(plugin_id):].lower()
        if "installed" in status_text and "not installed" not in status_text:
            installed.add(plugin_id)
            installed.add(plugin_id.split("@", 1)[0])
    return installed, output


def ensure_plugin_installed(plugin: str, *, codex_home: Path | None = None) -> dict[str, Any]:
    installed, raw = installed_plugin_names(codex_home=codex_home)
    if installed is None:
        return {"checked": False, "installed": None, "reason": raw}
    if plugin not in installed:
        raise ValueError(f"requested production plugin is not installed or enabled in this Codex identity: {plugin}")
    return {"checked": True, "installed": True}


def resolved_executable(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise ValueError(f"{name} executable not found on PATH")
    return str(Path(resolved).resolve())


def build_child_argv(
    *,
    workspace: Path,
    outputs_dir: Path,
    codex_executable: str = "codex",
    last_message_name: str = "last-message.txt",
) -> list[str]:
    return [
        codex_executable,
        "exec",
        "-c",
        'approval_policy="never"',
        "-c",
        "sandbox_workspace_write.network_access=false",
        "--disable",
        "memories",
        "-s",
        "workspace-write",
        "-C",
        str(workspace),
        "--add-dir",
        str(outputs_dir),
        "--skip-git-repo-check",
        "--ephemeral",
        "-o",
        str(outputs_dir / last_message_name),
        "-",
    ]


def child_contract_errors(output: str) -> list[str]:
    errors: list[str] = []
    if "approval: never" not in output:
        errors.append("child Codex did not report approval: never")
    if "sandbox: workspace-write" not in output:
        errors.append("child Codex did not report sandbox: workspace-write")
    if "danger-full-access" in output:
        errors.append("child Codex reported danger-full-access")
    if "(network access enabled)" in output:
        errors.append("child Codex reported network access enabled")
    return errors


def run_child_command(
    command: list[str],
    *,
    workspace: Path,
    prompt: str,
    codex_home: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    return subprocess.run(
        command,
        cwd=workspace,
        input=prompt,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        check=False,
    )


def child_prompt(plugin: str, staged: list[StagedFile], outputs_dir: Path) -> str:
    task = next(item for item in staged if item.role == "task")
    inputs = [item for item in staged if item.role == "input"]
    input_lines = "\n".join(f"- `{item.staged_path}`" for item in inputs) or "- none"
    return f"""You are running a bounded Bridge Kit production plugin replay.

Use the installed production Codex plugin named `{plugin}` if the replay task requires plugin behavior. Do not read or paste a source-tree SKILL.md as a substitute for the installed plugin.

Read the replay instruction file:

`{task.staged_path}`

Explicit input files copied for this run:

{input_lines}

Keep all generated artifacts under:

`{outputs_dir}`

Do not access the original caller repository or parent input directories. Do not upload files externally. Treat network access as unavailable for this local replay. In the final answer, summarize what happened and point to any local artifacts; do not print private input contents.
"""


def read_isolation_probe_prompt(secret_path: Path, result_path: Path) -> str:
    return f"""Bridge Kit read-isolation preflight.

Attempt to read this exact path outside the replay workspace:

`{secret_path}`

Do not print the file contents. If the read succeeds, write exactly `READABLE` to:

`{result_path}`

If the sandbox blocks the read, write exactly `BLOCKED` to that same path.
"""


def verify_child_read_isolation(
    *,
    child_argv: list[str],
    workspace: Path,
    outputs_dir: Path,
    codex_home: Path,
) -> dict[str, Any]:
    secret_path = workspace.parent / "read-isolation-neighbor-secret.txt"
    result_path = outputs_dir / "read-isolation-result.txt"
    output_path = outputs_dir / "read-isolation-child-output.txt"
    secret_path.write_text("AI_BRIDGE_READ_ISOLATION_PROBE_MARKER\n", encoding="utf-8")
    prompt = read_isolation_probe_prompt(secret_path, result_path)
    result = run_child_command(
        child_argv,
        workspace=workspace,
        prompt=prompt,
        codex_home=codex_home,
    )
    child_output = result.stdout or ""
    output_path.write_text(child_output, encoding="utf-8")
    marker = result_path.read_text(encoding="utf-8").strip() if result_path.exists() else ""
    contract_errors = child_contract_errors(child_output)
    passed = result.returncode == 0 and marker == "BLOCKED" and not contract_errors
    return {
        "status": "passed" if passed else "failed",
        "error_code": None if passed else READ_ISOLATION_ERROR,
        "exit_code": result.returncode,
        "result_marker": marker,
        "contract_errors": contract_errors,
        "secret_path": str(secret_path),
        "result_path": str(result_path),
        "child_output_path": str(output_path),
    }


def _metadata_for(staged: list[StagedFile]) -> list[dict[str, Any]]:
    return [
        {
            "role": item.role,
            "source_path": str(item.source_path),
            "basename": item.basename,
            "staged_path": str(item.staged_path),
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
        }
        for item in staged
    ]


def write_run_json(run_dir: Path, payload: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def replay_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": payload["run_id"],
        "status": payload["status"],
        "plugin": payload["plugin"],
        "target": payload["target"],
        "run_dir": payload["run_dir"],
        "workspace": payload["workspace"],
        "outputs_dir": payload["outputs_dir"],
        "run_json": str(Path(payload["run_dir"]) / "run.json"),
        "codex_executable": payload["codex_executable"],
        "ai_bridge_executable": payload["ai_bridge_executable"],
        "child_argv": payload["child_argv"],
        "inputs": [
            {
                "role": item["role"],
                "source_path": item["source_path"],
                "basename": item["basename"],
                "staged_path": item["staged_path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
            }
            for item in payload["inputs"]
        ],
        "exit_code": payload.get("exit_code"),
        "child_output_path": payload.get("child_output_path"),
        "last_message_path": payload.get("last_message_path"),
        "error_code": payload.get("error_code"),
        "read_isolation": payload.get("read_isolation"),
    }


def run_plugin_replay(
    *,
    target: Path,
    plugin: str,
    task_file: Path,
    input_files: list[Path],
    codex_home: Path | None = None,
    caller_cwd: Path | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], int]:
    plugin = _safe_plugin_name(plugin)
    target_repo = resolve_target_repo(target)
    selected_codex_home = enforce_current_codex_home(codex_home)
    task = _require_file_in_roots(
        task_file,
        "task file",
        authorized_task_roots(target_repo, caller_cwd=caller_cwd),
    )
    inputs = [
        _require_file_in_roots(path, "input", authorized_input_roots(target_repo))
        for path in input_files
    ]
    if not inputs:
        raise ValueError("at least one --input file is required")

    plugin_check = ensure_plugin_installed(plugin, codex_home=selected_codex_home)
    run_id = new_run_id()
    run_dir = replay_root(run_id)
    workspace = run_dir / "workspace"
    outputs_dir = run_dir / "outputs"
    workspace.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    staged = stage_files(run_dir, task, inputs, dry_run=True)
    codex_executable = resolved_executable("codex")
    ai_bridge_executable = resolved_executable("ai-bridge")
    child_argv = build_child_argv(
        workspace=workspace,
        outputs_dir=outputs_dir,
        codex_executable=codex_executable,
    )
    now = utc_now()
    payload: dict[str, Any] = {
        "schema": RUN_SCHEMA,
        "run_id": run_id,
        "status": "dry_run" if dry_run else "running",
        "created_at": now,
        "started_at": None if dry_run else now,
        "completed_at": None,
        "plugin": plugin,
        "plugin_check": plugin_check,
        "target": str(target_repo),
        "codex_home": str(selected_codex_home),
        "run_dir": str(run_dir),
        "workspace": str(workspace),
        "outputs_dir": str(outputs_dir),
        "inputs": _metadata_for(staged),
        "codex_executable": codex_executable,
        "ai_bridge_executable": ai_bridge_executable,
        "child_argv": child_argv,
        "child_output_path": str(outputs_dir / "child-output.txt"),
        "last_message_path": str(outputs_dir / "last-message.txt"),
        "exit_code": None,
        "error_code": None,
        "read_isolation": {"status": "not_run_dry_run"} if dry_run else {"status": "pending"},
    }
    write_run_json(run_dir, payload)
    if dry_run:
        return replay_summary(payload), 0

    read_isolation_argv = build_child_argv(
        workspace=workspace,
        outputs_dir=outputs_dir,
        codex_executable=codex_executable,
        last_message_name="read-isolation-last-message.txt",
    )
    read_isolation = verify_child_read_isolation(
        child_argv=read_isolation_argv,
        workspace=workspace,
        outputs_dir=outputs_dir,
        codex_home=selected_codex_home,
    )
    payload["read_isolation"] = read_isolation
    if read_isolation["status"] != "passed":
        payload["status"] = "failed"
        payload["completed_at"] = utc_now()
        payload["exit_code"] = 71
        payload["error_code"] = READ_ISOLATION_ERROR
        payload["contract_errors"] = read_isolation.get("contract_errors", [])
        write_run_json(run_dir, payload)
        return replay_summary(payload), 71

    staged = stage_files(run_dir, task, inputs, dry_run=False)
    payload["inputs"] = _metadata_for(staged)
    write_run_json(run_dir, payload)

    prompt = child_prompt(plugin, staged, outputs_dir)
    output_path = outputs_dir / "child-output.txt"
    result = run_child_command(
        child_argv,
        workspace=workspace,
        prompt=prompt,
        codex_home=selected_codex_home,
    )
    child_output = result.stdout or ""
    contract_errors = child_contract_errors(child_output)
    if contract_errors:
        child_output += "\nBridge Kit plugin-replay contract failure:\n"
        child_output += "\n".join(f"- {message}" for message in contract_errors)
        child_output += "\n"
    output_path.write_text(child_output, encoding="utf-8")
    payload["contract_errors"] = contract_errors
    payload["status"] = "completed" if result.returncode == 0 and not contract_errors else "failed"
    payload["completed_at"] = utc_now()
    payload["exit_code"] = result.returncode if not contract_errors else 70
    write_run_json(run_dir, payload)
    return replay_summary(payload), int(payload["exit_code"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge plugin-replay")
    parser.add_argument("--target", type=Path, required=True, help="Source repository identity; not used as child cwd.")
    parser.add_argument("--plugin", required=True, help="Installed production plugin name, for example sites or sites@openai-bundled.")
    parser.add_argument("--task", type=Path, required=True, help="Explicit replay instruction/task file.")
    parser.add_argument("--input", dest="inputs", type=Path, action="append", required=True, help="Explicit input file to copy into the replay run. Repeat for multiple files.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the planned replay without launching child Codex.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary, exit_code = run_plugin_replay(
            target=args.target,
            plugin=args.plugin,
            task_file=args.task,
            input_files=args.inputs,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
