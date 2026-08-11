from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from ai_bridge_kit.host import (
    HOST_BEGIN_MARKER,
    HOST_END_MARKER,
    config_values,
    desired_agents_block,
    desired_rules_text,
    inspect_host_policy,
    install_host_policy,
    install_managed_block,
    patch_config_text,
    resolve_codex_home,
    validate_host_policy,
)


class HostPolicyTests(unittest.TestCase):
    def test_codex_home_resolution_priority(self) -> None:
        explicit = Path("/tmp/explicit-codex-home")
        env = {"CODEX_HOME": "/tmp/env-codex-home"}

        self.assertEqual(resolve_codex_home(explicit, env), explicit.resolve())
        self.assertEqual(resolve_codex_home(None, env), Path("/tmp/env-codex-home").resolve())

    def test_new_config_install_values(self) -> None:
        values = config_values(patch_config_text(""))

        self.assertEqual(values[("", "approval_policy")], '"on-request"')
        self.assertEqual(values[("", "sandbox_mode")], '"workspace-write"')
        self.assertEqual(values[("", "approvals_reviewer")], '"auto_review"')
        self.assertEqual(values[("sandbox_workspace_write", "network_access")], "true")
        self.assertEqual(values[("features", "default_mode_request_user_input")], "true")
        self.assertEqual(values[("features", "memories")], "true")

    def test_config_merge_preserves_unrelated_fields(self) -> None:
        source = """model = "gpt-5"
reasoning_effort = "high"

[mcp_servers.example]
command = "example"

[features]
apps = true
memories = false
"""
        patched = patch_config_text(source)

        self.assertIn('model = "gpt-5"', patched)
        self.assertIn('reasoning_effort = "high"', patched)
        self.assertIn("[mcp_servers.example]", patched)
        self.assertIn('command = "example"', patched)
        self.assertIn("apps = true", patched)
        self.assertLess(patched.index('approval_policy = "on-request"'), patched.index("[mcp_servers.example]"))
        values = config_values(patched)
        self.assertEqual(values[("features", "memories")], "true")
        self.assertEqual(values[("features", "default_mode_request_user_input")], "true")

    def test_existing_features_section_updates_only_target_keys(self) -> None:
        patched = patch_config_text("[features]\nmemories = false\nplugins = true\n")
        values = config_values(patched)

        self.assertEqual(patched.count("[features]"), 1)
        self.assertEqual(values[("features", "memories")], "true")
        self.assertEqual(values[("features", "default_mode_request_user_input")], "true")
        self.assertEqual(values[("features", "plugins")], "true")

    def test_existing_sandbox_section_updates_network_access(self) -> None:
        patched = patch_config_text("[sandbox_workspace_write]\nnetwork_access = false\n")
        values = config_values(patched)

        self.assertEqual(patched.count("[sandbox_workspace_write]"), 1)
        self.assertEqual(values[("sandbox_workspace_write", "network_access")], "true")

    def test_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            first_status, first_actions = install_host_policy(codex_home)
            second_status, second_actions = install_host_policy(codex_home)

            self.assertEqual(first_status.overall_state, "configured")
            self.assertEqual(second_status.overall_state, "configured")
            self.assertTrue(any(action.startswith("Backup:") for action in first_actions))
            self.assertEqual(second_actions, ["No changes needed; host policy is already configured."])

    def test_agents_block_create_append_update_preserves_user_content(self) -> None:
        block = desired_agents_block()

        self.assertEqual(install_managed_block(None, block), block)
        appended = install_managed_block("User rule\n", block)
        self.assertIn("User rule", appended)
        self.assertIn(block, appended)

        old = (
            "Header\n\n"
            f"{HOST_BEGIN_MARKER}\nold managed text\n{HOST_END_MARKER}\n\n"
            "Footer\n"
        )
        updated = install_managed_block(old, block)
        self.assertIn("Header", updated)
        self.assertIn("Footer", updated)
        self.assertIn(block, updated)
        self.assertNotIn("old managed text", updated)

    def test_rules_install_and_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            rules_path = codex_home / "rules" / "ai-bridge-global.rules"

            self.assertEqual(rules_path.read_text(encoding="utf-8"), desired_rules_text())
            _, actions = install_host_policy(codex_home)
            self.assertEqual(actions, ["No changes needed; host policy is already configured."])

    def test_status_missing_configured_drifted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            self.assertEqual(inspect_host_policy(codex_home).overall_state, "missing")

            install_host_policy(codex_home)
            self.assertEqual(inspect_host_policy(codex_home).overall_state, "configured")

            (codex_home / "rules" / "ai-bridge-global.rules").write_text("drift\n", encoding="utf-8")
            self.assertEqual(inspect_host_policy(codex_home).overall_state, "drifted")

    def test_validate_with_real_codex_cli_when_available(self) -> None:
        if shutil.which("codex") is None:
            self.skipTest("codex CLI is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            install_host_policy(codex_home)
            status, lines, exit_code = validate_host_policy(codex_home)

            self.assertEqual(status.overall_state, "configured")
            self.assertEqual(exit_code, 0, "\n".join(lines))
            self.assertTrue(any("git push origin main => allow" in line for line in lines))
            self.assertTrue(any("git push upstream main => no_match" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
