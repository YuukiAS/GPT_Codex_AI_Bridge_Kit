"""Read-only machine discovery and isolated candidate regressions; never live."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import ai_bridge_kit
from ai_bridge_kit import clear_writing, host, notifier, persistent_run

ROOT = Path(__file__).resolve().parents[3]
EXPORT = ROOT / "private/exports/bridge-core--normal-entry-acceptance"
OUTPUT = ROOT / "results/bridge-core--normal-entry-acceptance/validation"
CODEX_HOME = Path("/users/a/e/aereinh/.codex")
CODEX = "/users/a/e/aereinh/bin/codex"
CLI = EXPORT / "candidate-venv/bin/ai-bridge"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv, cwd=ROOT, env=None):
    result = subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)
    return {"argv": list(map(str, argv)), "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    installed = json.loads((EXPORT / "CANDIDATE_INSTALL_IDENTITY.json").read_text())
    candidate = installed["source_sha"]
    assert Path(sys.executable) == EXPORT / "candidate-venv/bin/python"
    assert ai_bridge_kit.__version__ == importlib.metadata.version("gpt-codex-ai-bridge-kit") == "0.11.2"
    module_path = Path(ai_bridge_kit.__file__).resolve()
    assert module_path.is_relative_to(EXPORT / "candidate-venv")
    package_root = module_path.parent.parent
    for rel, digest in installed["runtime_files"].items():
        assert sha(package_root / rel) == digest, rel
    # Fresh identity canonicalizes the platform's lib/lib64 alias, not the bytes.
    installed["module_path"] = str(module_path)
    installed["cli_launcher_lines"] = CLI.read_text().splitlines()[:3]
    (EXPORT / "CANDIDATE_INSTALL_IDENTITY.json").write_text(json.dumps(installed, indent=2) + "\n")
    protected = [CODEX_HOME / "config.toml", CODEX_HOME / "AGENTS.md", CODEX_HOME / "rules/ai-bridge-global.rules"]
    before = {str(p): sha(p) for p in protected}
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("LD_LIBRARY_PATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    bare = command([str(CLI), "where"], cwd=EXPORT, env=env)
    assert bare["returncode"] == 0, bare
    writing = clear_writing.resolve_installed_writing_style(codex_bin=CODEX)
    assert writing["version"] == "0.5" and set(writing["skills"]) == {"writing-fidelity", "response-clarity"}
    readiness = notifier.notifier_readiness(config_root=Path("/users/a/e/aereinh/.ai-bridge"),
                                            state_root=Path("/users/a/e/aereinh/.ai-bridge"))
    values = notifier.notifier_env(config_root=Path("/users/a/e/aereinh/.ai-bridge"))
    transport = {key: values.get("AI_BRIDGE_NOTIFY_" + key, "") for key in ["SMTP_USER", "FROM", "TO", "SUBJECT_PREFIX"]}
    del values  # Never serialize configuration wholesale or copy credentials.
    rules = CODEX_HOME / "rules/ai-bridge-global.rules"
    native_rules = []
    for argv in [["git", "status", "--short"], ["git", "add", "task-owned.txt"], ["git", "commit", "-m", "task-owned"],
                 ["git", "push", "origin", "main"],
                 ["/users/a/e/aereinh/bin/ai-bridge", "host", "publish-current-branch", "--expected-repo",
                  "YuukiAS/GPT_Codex_AI_Bridge_Kit", "--expected-branch", "work/bridge-core--product-scope-reset"],
                 [str(CLI), "host", "sync-current-branch", "--expected-repo", "YuukiAS/AI_Skills_Collection",
                  "--expected-branch", "work/bridge-core--normal-entry-acceptance-text-transform"]]:
        decision, raw = host._execpolicy_decision(rules, argv)
        native_rules.append({"argv": argv, "rule_decision": decision, "raw": raw,
                             "native_approval": "UNVERIFIED_BY_RULE_CHECK"})
    goal = "docs/goals/bridge-core--normal-entry-acceptance_persistent_final_v1.2_2026-10-22.md"
    contract = persistent_run.parse_persistent_contract(ROOT, goal,
        expected_goal_sha256="53258ed917000e6e058d95fec4980fb7e36116e38df229611386f7f9381373c8")
    assert contract["launch_argv"][0] == sys.executable and contract["notification_attempt_cap"] == 6
    # Installed production imports first; only test fixtures are then found in source.
    sys.path.append(str(ROOT))
    from tests.test_host_normal_entry import HostNormalEntryTests
    cli_negative_fixtures = []
    for url in ["git@github.com:YuukiAS/GPT_Codex_AI_Bridge_Kit.git", "ssh://git@github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git",
                "https://example.invalid/YuukiAS/GPT_Codex_AI_Bridge_Kit.git", "file:///tmp/forbidden.git"]:
        temporary = tempfile.mkdtemp(prefix="bridge-nac-installed-cli-")
        fixture = HostNormalEntryTests()
        repo, _, identity, _ = fixture.fixture(temporary)
        fixture.git(repo, "remote", "set-url", "origin", url)
        cli_negative_fixtures.append({"cwd": str(repo), "origin": url, "refs_before": fixture.git(repo, "show-ref"),
            "argv": [str(CLI), "host", "sync-current-branch", "--expected-repo", identity, "--expected-branch", "feature"],
            "execution": "PENDING_DIRECT_PLATFORM_TOOL_CALL; no Python approval trampoline"})
    names = ["tests.test_host_normal_entry", "tests.test_persistent_progress_truth", "tests.test_persistent_notification_budget",
             "tests.test_text_transform", "tests.test_text_transform_budget", "tests.test_normal_entry_evidence_child"]
    with tempfile.TemporaryDirectory(prefix="bridge-nac-installed-state-") as state:
        os.environ["AI_BRIDGE_STATE_HOME"] = state
        with (OUTPUT / "INSTALLED_TARGETED_TESTS.log").open("w") as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
        assert result.wasSuccessful() and not result.skipped
    assert module_path == Path(ai_bridge_kit.__file__).resolve()
    after = {str(p): sha(p) for p in protected}
    assert after == before, "machine policy changed"
    evidence = {"candidate": candidate, "installed_module": str(module_path), "installed_version": ai_bridge_kit.__version__,
                "bare_absolute_cli": bare, "writing_style": writing, "notifier": readiness, "safe_transport_addresses": transport,
                "codex_version": command([CODEX, "--version"]), "rules": native_rules,
                "rule_check_is_not_loaded_session_approval": True,
                "candidate_cli_negative_fixtures": cli_negative_fixtures, "frozen_goal": goal, "contract": contract,
                "installed_tests": {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
                "protected_machine_hashes_before": before, "protected_machine_hashes_after": after,
                "real_model_calls": 0, "real_smtp_attempts": 0, "real_paid_api_calls": 0, "final_batch": "NOT_RUN"}
    (OUTPUT / "MACHINE_AND_CANDIDATE_PREFLIGHT.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"candidate": candidate, "installed_tests": result.testsRun, "writing_style": writing["version"],
                      "notifier_status": readiness["status"], "transport_ready": readiness["transport_ready"], "live": "NOT_RUN"}))


if __name__ == "__main__":
    main()
