from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class HumanGateContractTests(unittest.TestCase):
    def test_bridge_does_not_ship_parallel_human_gate_state_machine(self) -> None:
        self.assertFalse((REPO_ROOT / "ai_bridge_kit/human_gate.py").exists())

        shipped_python = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (REPO_ROOT / "ai_bridge_kit").glob("*.py")
            if path.name != "__init__.py"
        )
        for forbidden in [
            "HumanGateState",
            "HUMAN_BLOCKED_RECOVERABLE",
            "RESUMED_EXACT_ONCE",
            "UNSUPPORTED_CLOSED",
            "SAFETY_OR_AUTHORITY_BLOCKED",
        ]:
            self.assertNotIn(forbidden, shipped_python)

    def test_default_human_only_contract_uses_existing_legal_recovery_states(self) -> None:
        global_snippet = (REPO_ROOT / "templates/host/GLOBAL_AGENTS_SNIPPET.md").read_text(encoding="utf-8")
        lite_rules = (REPO_ROOT / "templates/prompts/AGENT_RULES.md").read_text(encoding="utf-8")
        combined = global_snippet + "\n" + lite_rules

        for required in [
            "one concise plain-text question",
            "GOAL_BLOCKED=YES",
            "GOAL_ACHIEVED=NO",
            "COMPLETE=NO",
            "READY_FOR_USER_REVIEW=NO",
            "DEPENDENT_EXECUTION_BLOCKED=YES",
            "same Goal exactly",
            "NEEDS_HUMAN_APPROVAL",
            "AWAIT_HUMAN_DECISION",
        ]:
            self.assertIn(required, combined)

        self.assertIn("do not invent another runtime", lite_rules)
        self.assertIn("do not invent a new `BLOCKED` enum, transcript", global_snippet)


if __name__ == "__main__":
    unittest.main()
