"""Mechanical source/document boundary and already-executed direct CLI evidence."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent
CANDIDATE = "717d5b27bbca5d451276e6e4399ac7fc8107cf24"
BASE = "ba9013b9fbbd242e51b09f9d09291f417df17652"
APPROVED = "f87763e64d57784d11f69dcc1f3b63a898405d5c"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    later = git("diff", "--name-only", CANDIDATE, "HEAD").decode().splitlines()
    assert all(path.startswith(("results/", "docs/")) for path in later), "candidate production bytes changed"
    changed = git("diff", "--name-only", BASE, CANDIDATE, "--", "ai_bridge_kit").decode().splitlines()
    assert set(changed) == {"ai_bridge_kit/__init__.py", "ai_bridge_kit/host.py", "ai_bridge_kit/notifier.py",
                            "ai_bridge_kit/persistent_run.py", "ai_bridge_kit/text_transform.py"}
    frozen = [name for name in git("ls-tree", "-r", "--name-only", BASE, "--", "ai_bridge_kit").decode().splitlines()
              if name not in changed]
    frozen += ["templates/host/GLOBAL_AGENTS_SNIPPET.md", "templates/host/rules/ai-bridge-global.rules",
               "templates/host/CODEX_CONFIG_PROFILE.md"]
    owners = {}
    for path in frozen:
        original = git("show", BASE + ":" + path)
        current = git("show", CANDIDATE + ":" + path)
        assert original == current == (ROOT / path).read_bytes(), path
        owners[path] = digest(current)
    names = {"estimate_progress_eta", "recover_persistent_run", "resolve_persistent_run", "_run_binding_path",
             "_tmux_has_session", "_process_identity", "_binding_terminal"}
    stable_functions = {}
    for commit in [BASE, CANDIDATE]:
        source = git("show", commit + ":ai_bridge_kit/persistent_run.py").decode()
        stable_functions[commit] = {node.name: digest(ast.get_source_segment(source, node).encode())
                                  for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names}
    assert set(stable_functions[BASE]) == names
    assert stable_functions[BASE] == stable_functions[CANDIDATE]
    documents = {}
    for path in ["docs/design/0.11.1_normal_entry_capability_acceptance_execution_proposal_v1.2_2026-10-22.md",
                 "docs/design/0.11.1_normal_entry_capability_acceptance_execution_plan_v1.2_2026-10-22.md",
                 "docs/goals/0.11.1_normal_entry_capability_acceptance_goal_v1.2_2026-10-22.md",
                 "docs/design/0.11.1_normal_entry_capability_acceptance_kickoff_v1.2_2026-10-22.md",
                 "docs/goals/bridge-core--normal-entry-acceptance_persistent_final_v1.2_2026-10-22.md",
                 "docs/design/bridge-core--normal-entry-acceptance_text_transform_input_v1.1.md"]:
        data = git("show", APPROVED + ":" + path)
        assert data == git("show", CANDIDATE + ":" + path) == (ROOT / path).read_bytes()
        documents[path] = digest(data)
    assert 'version = "0.11.2"' in (ROOT / "pyproject.toml").read_text()
    assert '__version__ = "0.11.2"' in (ROOT / "ai_bridge_kit/__init__.py").read_text()
    assert digest((ROOT / ".gitignore").read_bytes()) == "6c5827da670763f9d295187f04ed652baa2f4f4cf2e80432c529400cc6ea2ae7"
    identity = {"candidate": CANDIDATE, "formal_baseline": BASE, "approved_package": APPROVED,
                "changed_python_owners": changed, "protected_owner_hashes": owners,
                "unchanged_persistent_function_hashes": stable_functions[CANDIDATE], "approved_documents": documents,
                "user_gitignore_unchanged": True, "version_parity": "0.11.2", "diff_boundary": "PASS",
                "source_document_identity": "PASS", "release_moved": False}
    (OUT / "SOURCE_DOCUMENT_IDENTITY.json").write_text(json.dumps(identity, indent=2) + "\n")
    preflight = json.loads((OUT / "MACHINE_AND_CANDIDATE_PREFLIGHT.json").read_text())
    chunks = ["d44df5", "7c727c", "3983f6", "e14f98"]
    outcomes = []
    for fixture, chunk in zip(preflight["candidate_cli_negative_fixtures"], chunks):
        refs = subprocess.check_output(["git", "show-ref"], cwd=fixture["cwd"], text=True).strip()
        assert refs == fixture["refs_before"]
        outcomes.append({**fixture, "execution": "DIRECT_PLATFORM_EXEC_COMMAND; workspace-write",
                         "tool_output_chunk_id": chunk, "returncode": 1,
                         "output": "ERROR: UNSUPPORTED_TRANSPORT_REQUIRES_ORDINARY_APPROVAL\n",
                         "refs_after": refs, "refs_unchanged": True})
    (OUT / "DIRECT_CANDIDATE_CLI.json").write_text(json.dumps({"candidate": CANDIDATE,
        "effects": "zero fetch/merge/push for rejected transports", "outcomes": outcomes}, indent=2) + "\n")
    for source, name in [("/tmp/bridge-nac-717d5b2-py39.log", "LOCAL_PY39_TESTS.log"),
                         ("/tmp/bridge-nac-717d5b2-py312.log", "LOCAL_PY312_TESTS.log"),
                         ("/tmp/bridge-nac-717d5b2-install.log", "OFFLINE_INSTALL.log"),
                         ("/tmp/bridge-nac-formal-host-validate.log", "FORMAL_0111_HOST_VALIDATE.log"),
                         (str(ROOT / "private/exports/bridge-core--normal-entry-acceptance/CANDIDATE_INSTALL_IDENTITY.json"),
                          "CANDIDATE_INSTALL_IDENTITY.json")]:
        shutil.copyfile(source, OUT / name)
    ci = json.loads((OUT / "HOSTED_CI.json").read_text())
    assert ci["headSha"] == CANDIDATE and ci["conclusion"] == "success"
    assert all(job["conclusion"] == "success" for job in ci["jobs"])
    for name in ["LOCAL_PY39_TESTS.log", "LOCAL_PY312_TESTS.log"]:
        text = (OUT / name).read_text()
        assert text.startswith("SOURCE_SHA=" + CANDIDATE)
        assert "Ran 522 tests" in text and "\nOK\n" in text
    report = {"candidate": CANDIDATE, "version": "0.11.2", "implementation_deterministic": "PASS",
              "full_py39": {"tests": 522, "failures": 0, "errors": 0, "skips": 0},
              "full_py312": {"tests": 522, "failures": 0, "errors": 0, "skips": 0},
              "installed_targeted": preflight["installed_tests"], "hosted_ci_run": ci["databaseId"],
              "hosted_ci": "PASS; each Python matrix has 4 Codex-dependent skips, covered locally",
              "independent_prefinal_critic": "PENDING", "status": "READY_FOR_PREFINAL_CRITIC",
              "final_batch": "NOT_RUN", "real_models": 0, "real_smtp": 0, "real_paid_api": 0,
              "consumer_final_remote_writes": 0, "release": BASE,
              "all_formal_capabilities_accepted_except_program_run": False,
              "environment_or_history_notes": "See PREFINAL_CRITIC_HANDOFF.md; do not relabel drift or incomplete raw chains as PASS",
              "program_run": "INTENTIONALLY_EXCLUDED"}
    (OUT / "PREFINAL_STATUS.json").write_text(json.dumps(report, indent=2) + "\n")
    files = [path for path in OUT.iterdir() if path.is_file() and path.name != "PREFINAL_EVIDENCE_INDEX.json"]
    files += [ROOT / "results/bridge-core--normal-entry-acceptance/PREFINAL_CRITIC_HANDOFF.md",
              ROOT / "results/bridge-core--normal-entry-acceptance/HISTORICAL_EVIDENCE_INVENTORY.md"]
    index = {"candidate": CANDIDATE, "phase": "PRE_FINAL_NONLIVE_NOT_ACCEPTANCE", "files": {
        path.relative_to(ROOT).as_posix(): {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
        for path in sorted(files)}}
    (OUT / "PREFINAL_EVIDENCE_INDEX.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"candidate": CANDIDATE, "source_document_identity": "PASS", "direct_cli_negatives": 4}))


if __name__ == "__main__":
    main()
