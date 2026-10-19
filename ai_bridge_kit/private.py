from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .notifier import atomic_write_bytes, load_env_file, machine_config_path, require_email_config


REQUIRED_NOTIFIER_KEYS = {
    "AI_BRIDGE_NOTIFY_SMTP_USER",
    "AI_BRIDGE_NOTIFY_SMTP_PASSWORD",
    "AI_BRIDGE_NOTIFY_FROM",
    "AI_BRIDGE_NOTIFY_TO",
}


def sync_private(
    profile: str,
    env: dict[str, str] | None = None,
    *,
    config_root: Path | None = None,
) -> tuple[int, list[str]]:
    env = os.environ if env is None else env
    if profile != "notifier":
        return 2, [f"UNSUPPORTED_PROFILE: {profile}"]
    if shutil.which("rclone") is None:
        return 1, ["RCLONE_NOT_CONFIGURED"]
    source = env.get("AI_BRIDGE_PRIVATE_RCLONE_SOURCE", "").strip()
    if not source:
        return 1, ["PRIVATE_SOURCE_UNAVAILABLE: AI_BRIDGE_PRIVATE_RCLONE_SOURCE is not set"]
    target = machine_config_path(config_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai-bridge-private-") as tmp:
        downloaded = Path(tmp) / "notifier.env"
        result = subprocess.run(
            ["rclone", "copyto", source, str(downloaded)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            return 1, ["PRIVATE_SOURCE_UNAVAILABLE"]
        values = load_env_file(downloaded)
        missing = sorted(REQUIRED_NOTIFIER_KEYS - set(values))
        email_missing = require_email_config(values)
        missing = sorted(set(missing) | set(email_missing))
        if missing:
            return 1, ["PRIVATE_KEYS_MISSING: " + ", ".join(missing)]
        atomic_write_bytes(target, downloaded.read_bytes(), mode=0o600)
    return 0, [f"Synced profile: {profile}", f"Target: {target}", "Mode: pull-only", "Secrets: redacted"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge private")
    subparsers = parser.add_subparsers(dest="private_command")
    sync_parser = subparsers.add_parser("sync", help="Pull private config from an existing rclone remote.")
    sync_parser.add_argument("--profile", required=True, choices=["notifier"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.private_command == "sync":
        code, lines = sync_private(args.profile)
        for line in lines:
            print(line)
        return code
    parser.print_help()
    return 0
