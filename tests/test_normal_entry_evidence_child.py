import importlib.util
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "results/bridge-core--normal-entry-acceptance/validation/run_once.py"
SPEC = importlib.util.spec_from_file_location("normal_entry_evidence_child", PATH)
CHILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHILD)


class NormalEntryEvidenceChildTests(unittest.TestCase):
    def test_child_cannot_claim_its_own_terminal_even_with_pass_input(self):
        for capability in ["Persistent", "Notifier/Clear Writing"]:
            row = CHILD.inspect_row({"capability": capability, "judgment": "PASS"}, "a" * 40)
            self.assertEqual(row["status"], "PENDING_POST_EXIT")
            self.assertEqual(row["post_exit_facts"], "PENDING_POST_EXIT")

    def test_missing_or_changed_raw_artifacts_are_no_not_proxy_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.json"
            raw.write_text('{"substantive_result": "public fixture"}')
            source = {"candidate": "a" * 40, "consumer": "fixture", "normal_entry": "fixture command",
                      "capability": "Review", "judgment": "PASS", "rationale": "Read actual review result",
                      "raw_artifacts": [{"path": str(raw), "sha256": CHILD.digest(raw)}]}
            self.assertEqual(CHILD.inspect_row(source, "a" * 40)["status"], "PASS")
            self.assertEqual(CHILD.inspect_row(source, "b" * 40)["status"], "NO")
            raw.write_text("changed")
            self.assertEqual(CHILD.inspect_row(source, "a" * 40)["status"], "NO")

    def test_plan_hash_is_frozen(self):
        self.assertEqual(CHILD.digest(CHILD.ROOT / CHILD.PLAN), CHILD.PLAN_HASH)
