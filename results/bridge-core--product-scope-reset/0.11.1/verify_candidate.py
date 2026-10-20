"""Read-only production/document identity and patch-boundary audit."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
BASE = "391ff889ad156540727da168fb608c5f37dbbdfc"


def git(*argv):
    return subprocess.check_output(["git", *argv], cwd=ROOT, text=True).strip()


def source(ref, path):
    return subprocess.check_output(["git", "show", ref + ":" + path], cwd=ROOT)


def audit(candidate):
    assert git("rev-parse", candidate) == candidate and len(candidate) == 40
    assert subprocess.call(["git", "merge-base", "--is-ancestor", BASE, candidate], cwd=ROOT) == 0
    changed = git("diff", "--name-only", BASE, candidate).splitlines()
    todo_paths = [p for p in git("ls-tree", "-r", "--name-only", BASE, "docs/").splitlines()
                  if p.startswith("docs/TODO_") and p.endswith(".md")]
    allowed = {"ai_bridge_kit/persistent_run.py", "ai_bridge_kit/__init__.py", "pyproject.toml",
               "tests/test_persistent_cadence.py", "templates/persistent_run/README.md",
               "README.md", "QUICKSTART.md", "CHANGELOG.md", "docs/BRIDGE_TODO_CLOSURE_SUMMARY.md", *todo_paths}
    assert all(p in allowed or p.startswith("results/") for p in changed), changed
    ledger = {}
    for path in todo_paths:
        old, new = source(BASE, path).decode(), source(candidate, path).decode()
        assert "CLOSED" in "\n".join(new.splitlines()[:8]), path
        history = old[old.index("\n## "):]
        assert new.endswith(history), "Historical body altered: " + path
        ledger[path] = "CLOSED; original historical body preserved"
    summary = source(candidate, "docs/BRIDGE_TODO_CLOSURE_SUMMARY.md").decode()
    assert "ACTIVE_BRIDGE_SHORT_TERM_TODOS=0" in summary
    assert "INTENTIONALLY_EXCLUDED=Program Run" in summary
    assert 'version = "0.11.1"' in source(candidate, "pyproject.toml").decode()
    assert '__version__ = "0.11.1"' in source(candidate, "ai_bridge_kit/__init__.py").decode()
    old = source(BASE, "ai_bridge_kit/persistent_run.py").decode()
    new = source(candidate, "ai_bridge_kit/persistent_run.py").decode()
    def functions(text):
        return {node.name: ast.get_source_segment(text, node) for node in ast.parse(text).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    before, after = functions(old), functions(new)
    changed_functions = [name for name in before if before[name] != after[name]]
    assert set(changed_functions) == {"_delivery_decision", "report_progress_file", "supervise_binding"}, changed_functions
    identities = {}
    for path in git("ls-tree", "-r", "--name-only", candidate).splitlines():
        if path.startswith("results/") or path == ".gitignore":
            continue
        blob = source(candidate, path)
        assert (ROOT / path).read_bytes() == blob, "Candidate/worktree mismatch: " + path
        identities[path] = hashlib.sha256(blob).hexdigest()
    for path in ("README.md", "QUICKSTART.md", "CHANGELOG.md"):
        text = source(candidate, path).decode()
        assert "0.11.1" in text and "response-clarity" in text, path
        assert "source candidate; formal release pending" not in text
        assert "9db19b0409816c22042a246b35a33e1d34fedd0a" not in text
    return {"candidate_sha": candidate, "base_release": BASE, "result": "PASS",
            "version": "0.11.1", "changed_non_results_paths": [p for p in changed if not p.startswith("results/")],
            "changed_persistent_functions": changed_functions, "eta_estimator_unchanged": True,
            "all_other_production_owners_unchanged": True, "todo_ledger": ledger,
            "ACTIVE_BRIDGE_SHORT_TERM_TODOS": 0, "PROGRAM_RUN": "INTENTIONALLY_EXCLUDED",
            "candidate_worktree_identities": identities}


if __name__ == "__main__":
    print(json.dumps(audit(sys.argv[1]), ensure_ascii=False, indent=2, sort_keys=True))
