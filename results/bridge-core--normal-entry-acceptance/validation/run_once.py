"""The frozen Goal's only business child: inspect evidence, never invoke models."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
EXPORT = ROOT / "private/exports/bridge-core--normal-entry-acceptance"
PYTHON = EXPORT / "candidate-venv/bin/python"
CLI = EXPORT / "candidate-venv/bin/ai-bridge"
OUTPUT = ROOT / "results/bridge-core--normal-entry-acceptance/validation"
CAPABILITIES = ("Host", "Lite", "Review", "Control", "Persistent", "Notifier/Clear Writing",
                "Overleaf", "Visual Review", "Text Review", "Text Transform", "Plugin Replay", "发行与机器")
PLAN = "docs/design/0.11.1_normal_entry_capability_acceptance_execution_plan_v1.2_2026-10-22.md"
PLAN_HASH = "350577879b8c9a413ea4e18a696668d268c2692b250c70c03b619631bf6d8a4b"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_row(row, candidate, root=ROOT):
    """Consume every bound raw artifact; semantic findings stay explicit."""
    missing = []
    artifacts = []
    if row.get("candidate") != candidate or not row.get("consumer") or not row.get("normal_entry"):
        missing.append("candidate/consumer/normal-entry identity missing or wrong")
    if not row.get("rationale"):
        missing.append("no substantive evidence judgment")
    for item in row.get("raw_artifacts", []):
        path = Path(item.get("path", ""))
        path = path if path.is_absolute() else root / path
        if not path.is_file() or not item.get("sha256") or digest(path) != item["sha256"]:
            missing.append(f"missing or changed raw artifact: {path}")
            continue
        data = path.read_bytes()  # Read the full artifact, not a receipt-only proxy.
        artifacts.append({"path": str(path), "sha256": item["sha256"], "bytes_read": len(data)})
    if not artifacts:
        missing.append("no complete raw evidence")
    pending = row.get("capability") in {"Persistent", "Notifier/Clear Writing"}
    status = "PENDING_POST_EXIT" if pending else ("PASS" if row.get("judgment") == "PASS" and not missing else "NO")
    return {**row, "status": status, "missing_facts": missing, "consumed_artifacts": artifacts,
            "post_exit_facts": "PENDING_POST_EXIT" if pending else "not applicable"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    if args.plan != PLAN or digest(ROOT / PLAN) != PLAN_HASH:
        raise RuntimeError("frozen plan identity mismatch")
    if Path(sys.executable).absolute() != PYTHON or os.environ.get("AI_BRIDGE_RUNTIME_OWNER") != "persistent":
        raise RuntimeError("must run as the frozen candidate Persistent child")
    import ai_bridge_kit
    identity = json.loads((EXPORT / "CANDIDATE_INSTALL_IDENTITY.json").read_text())
    candidate = identity["source_sha"]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(["git", "diff", "--name-only", candidate, "HEAD"], cwd=ROOT, text=True).splitlines()
    if any(not name.startswith(("results/", "docs/")) for name in changed):
        raise RuntimeError("evidence HEAD changes candidate production bytes")
    script_rel = Path(__file__).resolve().relative_to(ROOT).as_posix()
    frozen_script = subprocess.check_output(["git", "show", f"{candidate}:{script_rel}"], cwd=ROOT)
    if frozen_script != Path(__file__).read_bytes():
        raise RuntimeError("candidate business-child bytes changed")
    if ai_bridge_kit.__version__ != "0.11.2" or Path(ai_bridge_kit.__file__).resolve() != Path(identity["module_path"]):
        raise RuntimeError("candidate source/install/HEAD mismatch")
    if Path(ai_bridge_kit.__file__).resolve().is_relative_to(ROOT / "ai_bridge_kit"):
        raise RuntimeError("editable or repository-source import is forbidden")
    inputs = json.loads((OUTPUT / "CAPABILITY_INPUTS.json").read_text())
    rows = inputs["rows"]
    if inputs.get("candidate") != candidate or [r.get("capability") for r in rows] != list(CAPABILITIES):
        raise RuntimeError("twelve-capability inputs not bound to this candidate")
    report = OUTPUT / "PRE_TERMINAL_FINDINGS.md"
    if report.exists():
        raise RuntimeError("existing final batch evidence; no automatic second run")
    checked = []
    for number, row in enumerate(rows, 1):
        checked.append(inspect_row(row, candidate))
        subprocess.run([str(CLI), "persistent-run", "progress", "update", "--stage", "evidence-inspection",
                        "--completed", str(number), "--total", "12"], check=True, cwd=ROOT,
                       stdout=subprocess.DEVNULL)
    index = {"candidate": candidate, "evidence_head": head, "phase": "PRE_TERMINAL", "checked_rows": 12,
             "count_meaning": "evidence rows inspected, not capabilities passed", "rows": checked,
             "persistent_terminal": "PENDING_POST_EXIT", "notifier_terminal": "PENDING_POST_EXIT",
             "all_formal_capabilities_accepted": False}
    (OUTPUT / "EVIDENCE_INDEX.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    lines = ["# 正常入口验收：退出前证据核查", "",
             "已核查十二行证据；这不代表十二项通过。本进程仍在运行，自身真实退出和最后通知须在退出后由现有执行任务核对。", ""]
    for row in checked:
        lines.extend([f"## {row['capability']}", "", f"{row.get('rationale', '缺少实质判断')}", "",
                      f"状态：{row['status']}；缺失事实：{'; '.join(row['missing_facts']) or '无退出前缺项'}。", ""])
    report.write_text("\n".join(lines), encoding="utf-8")
    return int(any(r["status"] == "NO" for r in checked))


if __name__ == "__main__":
    raise SystemExit(main())
