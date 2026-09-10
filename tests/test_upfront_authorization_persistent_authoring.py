from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit.host import (
    _effective_execpolicy_decision,
    _execpolicy_decision,
    desired_rules_text,
)
from ai_bridge_kit.persistent_run import install_persistent_run


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_repo_text(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def assert_contains_all(test: unittest.TestCase, text: str, needles: list[str]) -> None:
    normalized_text = " ".join(text.split())
    for needle in needles:
        test.assertIn(" ".join(needle.split()), normalized_text)


def frontmatter(text: str) -> str:
    marker = "---"
    parts = text.split(marker, 2)
    if len(parts) < 3:
        return ""
    return parts[1]


def replace_first(text: str, old: str, new: str) -> str:
    return text.replace(old, new, 1)


class UpfrontAuthorizationPersistentAuthoringTests(unittest.TestCase):
    def test_gpt_repo_instructions_read_persistent_templates_in_order(self) -> None:
        text = read_repo_text("chatgpt/GITHUB_MCP_REPO_INSTRUCTIONS.md")

        ag = text.index("`AGENTS.md`")
        chatgpt_rules = text.index("`prompts/CHATGPT_RULES.md`")
        agent_rules = text.index("`prompts/AGENT_RULES.md`")
        persistent_readme = text.index("`automation/persistent_run/README.md`")
        persistent_contract = text.index("`automation/persistent_run/CONTRACT_TEMPLATE.md`")

        self.assertLess(ag, chatgpt_rules)
        self.assertLess(chatgpt_rules, agent_rules)
        self.assertLess(agent_rules, persistent_readme)
        self.assertLess(persistent_readme, persistent_contract)
        assert_contains_all(
            self,
            text,
            [
                "execution lifetime",
                "Persistent execution: REQUIRED",
                "Backend: tmux",
                "Run/session key",
                "heartbeat/stage-state/checkpoint/resume semantics",
                "缺少 Persistent Run capability",
            ],
        )

    def test_task_writer_classifies_persistence_independent_of_workflow(self) -> None:
        text = read_repo_text("chatgpt/TASK_WRITER_PROMPT.md")

        assert_contains_all(
            self,
            text,
            [
                "Decide Execution Lifetime Separately",
                "Task type and execution lifetime are different decisions",
                "overnight",
                "unattended",
                "survive disconnect",
                "automation/persistent_run/README.md",
                "automation/persistent_run/CONTRACT_TEMPLATE.md",
                "Persistent execution: REQUIRED",
                "Backend: tmux",
                "Goal source: <repo-relative goal/task path>",
                "Run/session key: <project-owned stable key>",
                "resource boundary",
                "original positive completion criteria",
                "Do not silently",
            ],
        )
        self.assertNotIn("task_type: \"persistent\"", text)
        self.assertNotIn("workflow: \"Persistent Run\"", text)

    def test_task_template_can_author_harmless_persistent_goal_without_new_workflow(self) -> None:
        template = read_repo_text("templates/prompts/templates/TASK_TEMPLATE.md")
        contract = read_repo_text("templates/persistent_run/CONTRACT_TEMPLATE.md")

        assert_contains_all(
            self,
            template,
            [
                "## Persistent Run Contract",
                "Persistent execution: NOT_REQUIRED",
                "Backend: none",
                "automation/persistent_run/CONTRACT_TEMPLATE.md",
            ],
        )
        assert_contains_all(
            self,
            contract,
            [
                "Persistent execution: REQUIRED",
                "Backend: tmux",
                "Goal source: <repo-relative path>",
                "Run/session key: <project-owned stable key>",
                "## Resource Boundary",
                "## Heartbeat / Stage-State / Checkpoint / Resume Semantics",
                "The original Goal's positive completion criteria remain authoritative.",
            ],
        )

        authored = replace_first(template, 'task_key: "000_short_task"', 'task_key: "099_overnight_smoke"')
        authored = replace_first(authored, "# Task 000 Short Task", "# Task 099 Overnight Smoke")
        authored = authored.replace(
            "Persistent execution: NOT_REQUIRED\n"
            "Backend: none\n"
            "Goal source: prompts/tasks/000_short_task.md\n"
            "Run/session key: none",
            "Persistent execution: REQUIRED\n"
            "Backend: tmux\n"
            "Goal source: prompts/tasks/099_overnight_smoke.md\n"
            "Run/session key: ai_bridge_099_overnight_smoke",
            1,
        )
        self.assertNotIn(
            "Persistent execution: NOT_REQUIRED\n"
            "Backend: none\n"
            "Goal source: prompts/tasks/000_short_task.md\n"
            "Run/session key: none",
            authored,
        )
        authored = replace_first(
            authored,
            "Use only ordinary live Codex resources.",
            "Use CPU-only local smoke resources.",
        )
        authored = replace_first(authored, "- none", "- Write heartbeat, progress, and completion artifacts.")

        assert_contains_all(
            self,
            authored,
            [
                'task_type: "execution"',
                "Persistent execution: REQUIRED",
                "Backend: tmux",
                "Goal source: prompts/tasks/099_overnight_smoke.md",
                "Run/session key: ai_bridge_099_overnight_smoke",
                "Use CPU-only local smoke resources.",
            ],
        )
        self.assertNotIn('task_type: "controller"', frontmatter(authored))
        self.assertNotIn("Review / Control", authored.split("## Persistent Run Contract", 1)[0])

    def test_next_task_prompt_carries_forward_persistent_requirement(self) -> None:
        text = read_repo_text("chatgpt/NEXT_TASK_PROMPT.md")

        assert_contains_all(
            self,
            text,
            [
                "Persistent execution: REQUIRED",
                "## Persistent Run Contract",
                "automation/persistent_run/README.md",
                "automation/persistent_run/CONTRACT_TEMPLATE.md",
                "any existing Persistent Run requirement",
                "Backend: tmux",
                "run/session key",
                "resource boundary",
                "original positive completion criteria",
                "Do not silently degrade",
            ],
        )

    def test_chatgpt_rules_cover_authoring_and_carry_forward(self) -> None:
        text = read_repo_text("templates/prompts/CHATGPT_RULES.md")

        assert_contains_all(
            self,
            text,
            [
                "`automation/persistent_run/`",
                "execution-lifetime",
                "Long runtime is not a workflow selector",
                "Persistent execution: REQUIRED",
                "Backend: tmux",
                "`Goal source`",
                "`Run/session key`",
                "not create a fourth workflow",
                "If a previous task had `Persistent execution: REQUIRED`",
                "carry that requirement",
            ],
        )
        self.assertNotIn("task_type: \"persistent\"", text)

    def test_codex_start_preflights_declared_effects_before_substantial_work(self) -> None:
        text = read_repo_text("codex/CODEX_START_PROMPT.md")

        preflight = text.index("## Upfront Authorization Preflight")
        permissions = text.index("## Permission Rules")
        self.assertLess(preflight, permissions)
        assert_contains_all(
            self,
            text,
            [
                "Before substantive execution",
                "`Allowed Actions`",
                "`Forbidden Actions`",
                "`Human Decision Points`",
                "`Persistent Run Contract`",
                "Persistent Run kickoff or canonical `tmux` launch",
                "Specific private external transfer",
                "Specific paid/external API call",
                "repository task, Plan, Goal, or Persistent Run contract",
                "not by itself current-user-visible authorization",
                "exact bounded authorization for the same frozen effect",
                "do not ask again",
                "A new artifact",
                "requires a fresh authorization",
            ],
        )

    def test_host_agents_preflight_guidance_without_execpolicy_expansion(self) -> None:
        agents = read_repo_text("templates/host/GLOBAL_AGENTS_SNIPPET.md")
        rules = read_repo_text("templates/host/rules/ai-bridge-global.rules")

        assert_contains_all(
            self,
            agents,
            [
                "Before substantive execution",
                "approval-sensitive effects",
                "canonical `tmux` launch",
                "private external transfer",
                "paid/external API call",
                "frozen scope evidence",
                "not by themselves current-user-visible authorization",
                "exact bounded authorization",
                "A new artifact",
            ],
        )
        self.assertNotIn('pattern = ["tmux", "new-session"]', rules)
        self.assertNotIn('pattern = ["tmux", "send-keys"]', rules)
        self.assertNotIn('pattern = ["setsid"]', rules)
        self.assertNotIn('pattern = ["nohup"]', rules)
        self.assertNotIn('pattern = ["screen"]', rules)
        self.assertNotIn('pattern = ["python"]', rules)
        self.assertIn('pattern = ["tmux", ["ls", "list-sessions", "has-session"]]', rules)

    def test_execpolicy_still_prompts_tmux_mutation_and_fallbacks(self) -> None:
        expectations = {
            ("tmux", "ls"): "allow",
            ("tmux", "has-session", "-t", "example"): "allow",
            ("tmux", "new-session", "-d", "-s", "example"): "prompt",
            ("tmux", "send-keys", "-t", "example", "ls", "Enter"): "prompt",
            ("setsid", "bash"): "prompt",
            ("nohup", "python", "job.py"): "prompt",
            ("screen", "-dmS", "job", "bash"): "prompt",
        }

        with tempfile.TemporaryDirectory() as tmp:
            rules_path = Path(tmp) / "ai-bridge-global.rules"
            rules_path.write_text(desired_rules_text(), encoding="utf-8")
            for command, expected in expectations.items():
                with self.subTest(command=" ".join(command)):
                    decision, raw = _execpolicy_decision(rules_path, list(command))
                    self.assertEqual(_effective_execpolicy_decision(decision), expected, raw)

    def test_acceptance_fixture_installed_repo_gets_authorable_persistent_goal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "smoke-repo"
            repo.mkdir()
            subprocess.check_call(["git", "init"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            install_persistent_run(repo)
            task_path = repo / "prompts" / "tasks" / "099_overnight_smoke.md"
            task_path.parent.mkdir(parents=True)
            template = read_repo_text("templates/prompts/templates/TASK_TEMPLATE.md")
            task = replace_first(template, 'task_key: "000_short_task"', 'task_key: "099_overnight_smoke"')
            task = replace_first(task, "# Task 000 Short Task", "# Task 099 Overnight Smoke")
            task = task.replace(
                "Persistent execution: NOT_REQUIRED\n"
                "Backend: none\n"
                "Goal source: prompts/tasks/000_short_task.md\n"
                "Run/session key: none",
                "Persistent execution: REQUIRED\n"
                "Backend: tmux\n"
                "Goal source: prompts/tasks/099_overnight_smoke.md\n"
                "Run/session key: ai_bridge_099_overnight_smoke",
                1,
            )
            task = replace_first(
                task,
                "- Use only ordinary live Codex resources.",
                "- Use local CPU-only smoke resources.",
            )
            task_path.write_text(task, encoding="utf-8")

            written = task_path.read_text(encoding="utf-8")
            assert_contains_all(
                self,
                written,
                [
                    'task_type: "execution"',
                    "Persistent execution: REQUIRED",
                    "Backend: tmux",
                    "Goal source: prompts/tasks/099_overnight_smoke.md",
                    "Run/session key: ai_bridge_099_overnight_smoke",
                    "Use local CPU-only smoke resources.",
                ],
            )
            self.assertFalse((repo / ".codex" / "rules").exists())
            self.assertNotIn('task_type: "controller"', frontmatter(written))


if __name__ == "__main__":
    unittest.main()
