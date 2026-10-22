"""Offline, non-editable install of one frozen source commit; no machine update."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
EXPORT = ROOT / "private/exports/bridge-core--normal-entry-acceptance"


def run(argv, *, cwd=ROOT, env=None):
    return subprocess.check_output(argv, cwd=cwd, env=env, text=True, stderr=subprocess.STDOUT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--venv-python", default="/usr/bin/python3.9")
    args = parser.parse_args()
    candidate = args.candidate
    if run(["git", "rev-parse", "HEAD"]).strip() != candidate:
        raise RuntimeError("freeze HEAD before installing candidate")
    source = EXPORT / "source" / candidate
    venv = EXPORT / "candidate-venv"
    if source.exists() or venv.exists():
        raise RuntimeError("candidate install already exists; no silent replacement")
    source.mkdir(parents=True)
    archive = subprocess.check_output(["git", "archive", candidate], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        # Only our own reviewed Git tree, never caller-controlled archive paths.
        bundle.extractall(source)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_NO_INDEX"] = "1"
    wheel_dir = EXPORT / "wheels" / candidate
    wheel_dir.mkdir(parents=True)
    log = run([sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation",
               "--wheel-dir", str(wheel_dir), str(source)], env=env)
    run([args.venv_python, "-m", "venv", str(venv)], env=env)
    python = venv / "bin/python"
    cli = venv / "bin/ai-bridge"
    wheels = list(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("exactly one wheel required")
    wheel = wheels[0]
    log += run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", "--no-build-isolation",
                str(wheel)], cwd=EXPORT, env=env)
    code = """import sys,json,importlib.metadata as m,ai_bridge_kit
d=m.distribution('gpt-codex-ai-bridge-kit')
print(json.dumps(dict(sys_executable=sys.executable,module_path=ai_bridge_kit.__file__,
 version=ai_bridge_kit.__version__,metadata_version=d.version,
 direct_url=json.loads(d.read_text('direct_url.json')),user_site_enabled=__import__('site').ENABLE_USER_SITE)))
"""
    identity = json.loads(run([str(python), "-I", "-c", code], cwd=EXPORT, env=env))
    identity["module_path"] = str(Path(identity["module_path"]).resolve())
    assert identity["version"] == identity["metadata_version"] == "0.11.2"
    assert identity["sys_executable"] == str(python)
    assert identity["direct_url"].get("dir_info", {}).get("editable") is not True
    assert identity["user_site_enabled"] is False
    package_root = Path(identity["module_path"]).parent.parent
    installed = {}
    for directory in ("ai_bridge_kit", "templates", "codex"):
        for path in (source / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                rel = path.relative_to(source)
                destination = package_root / rel
                assert destination.read_bytes() == path.read_bytes(), str(rel)
                installed[str(rel)] = hashlib.sha256(destination.read_bytes()).hexdigest()
    identity.update(source_sha=candidate, wheel=str(wheel), wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    cli_path=str(cli), cli_realpath=str(cli.resolve()), cli_shebang=cli.read_text().splitlines()[0],
                    runtime_files=installed, where=run([str(cli), "where"], cwd=EXPORT, env=env).strip())
    (EXPORT / "CANDIDATE_INSTALL_IDENTITY.json").write_text(json.dumps(identity, indent=2) + "\n")
    (EXPORT / "OFFLINE_INSTALL.log").write_text(log)
    print(json.dumps({k: v for k, v in identity.items() if k != "runtime_files"}, indent=2))


if __name__ == "__main__":
    main()
