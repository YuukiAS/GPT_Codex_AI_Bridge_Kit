from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import paid_review
from ai_bridge_kit import visual_review


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class VisualReviewTests(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        target = Path(tmp.name) / "project"
        target.mkdir()
        image = target / "results" / "001_visual" / "visual_review" / "primary.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(PNG_1X1)
        manifest = image.parent / "visual_inputs.json"
        visual_review.write_json(
            manifest,
            {
                "schema": visual_review.VISUAL_INPUT_MANIFEST_SCHEMA,
                "task_key": "001_visual",
                "workflow_type": "reviewed_handoff",
                "review_kind": "synthetic-image",
                "privacy_policy": "PUBLIC_SAFE_ONLY",
                "rubric": {"instructions": "The image must be a nonblank synthetic fixture."},
                "identity_bindings": {"implementation_commit": "impl-1"},
                "inputs": [{"logical_id": "primary", "path": "results/001_visual/visual_review/primary.png"}],
            },
        )
        return tmp, target, manifest, Path("results/001_visual/visual_review/VISUAL_REVIEW.json")

    def model_payload(self, decision: str = "PASS") -> dict:
        return {
            "overall_decision": decision,
            "item_reviews": [
                {
                    "item_id": "primary",
                    "decision": decision,
                    "summary": "Synthetic image reviewed.",
                    "observations": ["Pixels were supplied to the model."],
                    "requirement_ids": ["REQ_SYNTHETIC"],
                }
            ],
            "blocking_findings": [],
            "non_blocking_notes": [],
        }

    def opener_for(self, captured: dict, decision: str = "PASS", *, input_tokens: int = 2048):
        def opener(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            if request.full_url.endswith("/responses/input_tokens"):
                captured.setdefault("urls", []).append(request.full_url)
                captured["token_body"] = body
                captured["token_auth"] = request.headers.get("Authorization")
                return FakeResponse({"input_tokens": input_tokens})
            captured.setdefault("urls", []).append(request.full_url)
            captured["body"] = body
            captured["auth"] = request.headers.get("Authorization")
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "status": "completed",
                    "usage": {"input_tokens": input_tokens, "output_tokens": 91, "total_tokens": input_tokens + 91},
                    "output_text": json.dumps(self.model_payload(decision)),
                }
            )

        return opener

    def test_missing_api_key_fails_closed_before_network(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            calls = []

            def opener(*args, **kwargs):
                calls.append((args, kwargs))
                return FakeResponse({})

            with self.assertRaisesRegex(visual_review.VisualReviewError, visual_review.SECRET_NAME):
                visual_review.run_visual_review(target, manifest, output, api_key="", opener=opener)
            self.assertEqual(calls, [])
            self.assertFalse((target / output).exists())

    def test_mock_responses_api_generates_schema_compliant_review(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            captured: dict = {}

            artifact = visual_review.run_visual_review(
                target,
                manifest,
                output,
                api_key="sk-test-secret",
                model=visual_review.DEFAULT_MODEL,
                timeout=12,
                opener=self.opener_for(captured),
            )
            self.assertEqual(artifact["schema"], visual_review.VISUAL_REVIEW_SCHEMA)
            self.assertEqual(artifact["overall_decision"], "PASS")
            self.assertEqual(artifact["status"], "PASS")
            self.assertEqual(artifact["review_model"], visual_review.DEFAULT_MODEL)
            self.assertEqual(visual_review.validate_visual_review_payload(artifact, expected={"implementation_commit": "impl-1"}), [])
            self.assertEqual(set(captured["token_body"]), {"model", "input"})
            self.assertEqual(captured["token_body"]["model"], captured["body"]["model"])
            self.assertEqual(captured["token_body"]["input"], captured["body"]["input"])
            self.assertNotIn("max_output_tokens", captured["token_body"])
            self.assertNotIn("text", captured["token_body"])
            self.assertNotIn("store", captured["token_body"])
            self.assertEqual(captured["urls"], [paid_review.INPUT_TOKENS_URL, visual_review.API_URL])
            self.assertFalse(captured["body"]["store"])
            self.assertIn("input_image", json.dumps(captured["body"]))
            self.assertNotIn("tools", captured["body"])
            self.assertEqual(captured["body"]["max_output_tokens"], paid_review.DEFAULT_MAX_OUTPUT_TOKENS)
            self.assertEqual(captured["timeout"], 12)
            self.assertNotIn("sk-test-secret", json.dumps(captured["body"]))
            self.assertEqual(artifact["paid_review"]["campaign_identity"], "001_visual")
            self.assertEqual(artifact["paid_review"]["exact_input_token_preflight"]["input_tokens"], 2048)
            self.assertEqual(artifact["paid_review"]["actual_response_usage"]["output_tokens"], 91)

    def test_default_model_uses_shared_production_default(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            previous = os.environ.pop(visual_review.MODEL_ENV, None)
            captured: dict = {}

            try:
                artifact = visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=self.opener_for(captured))
            finally:
                if previous is not None:
                    os.environ[visual_review.MODEL_ENV] = previous

            self.assertEqual(visual_review.DEFAULT_MODEL, "gpt-5.6-terra")
            self.assertEqual(captured["body"]["model"], "gpt-5.6-terra")
            self.assertEqual(artifact["review_model"], "gpt-5.6-terra")

    def test_environment_model_override_fails_closed_before_network(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            previous = os.environ.get(visual_review.MODEL_ENV)
            os.environ[visual_review.MODEL_ENV] = "gpt-test-override"
            captured: dict = {}

            try:
                with self.assertRaisesRegex(visual_review.VisualReviewError, "model/pricing mismatch"):
                    visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=self.opener_for(captured))
            finally:
                if previous is None:
                    os.environ.pop(visual_review.MODEL_ENV, None)
                else:
                    os.environ[visual_review.MODEL_ENV] = previous

            self.assertEqual(captured, {})

    def test_explicit_unknown_model_override_fails_closed_before_network(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            previous = os.environ.get(visual_review.MODEL_ENV)
            os.environ[visual_review.MODEL_ENV] = visual_review.DEFAULT_MODEL
            captured: dict = {}

            try:
                with self.assertRaisesRegex(visual_review.VisualReviewError, "model/pricing mismatch"):
                    visual_review.run_visual_review(
                        target,
                        manifest,
                        output,
                        api_key="sk-secret",
                        model="gpt-explicit",
                        opener=self.opener_for(captured),
                    )
            finally:
                if previous is None:
                    os.environ.pop(visual_review.MODEL_ENV, None)
                else:
                    os.environ[visual_review.MODEL_ENV] = previous

            self.assertEqual(captured, {})

    def test_malformed_model_output_fails_closed(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            def opener(request, timeout):
                if request.full_url.endswith("/responses/input_tokens"):
                    return FakeResponse({"input_tokens": 10})
                return FakeResponse({"status": "completed", "output_text": "{not json"})

            with self.assertRaisesRegex(visual_review.VisualReviewError, "not valid JSON"):
                visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=opener)
            self.assertFalse((target / output).exists())

            def incomplete_opener(request, timeout):
                if request.full_url.endswith("/responses/input_tokens"):
                    return FakeResponse({"input_tokens": 10})
                return FakeResponse({"status": "completed", "output_text": json.dumps({"overall_decision": "PASS"})})

            with self.assertRaisesRegex(visual_review.VisualReviewError, "missing item_reviews"):
                visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=incomplete_opener)
            self.assertFalse((target / output).exists())

    def test_api_failure_fails_closed_without_secret_in_error(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            def opener(request, timeout):
                if request.full_url.endswith("/responses/input_tokens"):
                    return FakeResponse({"input_tokens": 10})
                raise urllib.error.URLError("rate limited")

            with self.assertRaises(visual_review.VisualReviewError) as caught:
                visual_review.run_visual_review(target, manifest, output, api_key="sk-secret-value", opener=opener)
            self.assertNotIn("sk-secret-value", str(caught.exception))
            self.assertFalse((target / output).exists())

    def test_identity_and_image_sha_mismatch_are_rejected(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            opener = self.opener_for({})

            artifact = visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=opener)
            artifact["images"][0]["sha256"] = "bad"
            visual_review.write_json(target / output, artifact)
            errors = visual_review.validate_visual_review_payload(
                visual_review.load_json(target / output),
                expected={"implementation_commit": "other-impl"},
            )
            self.assertTrue(any("identity binding mismatch" in item for item in errors))
            self.assertTrue(any("review_identity is stale" in item for item in errors))

            manifest_payload = visual_review.load_json(manifest)
            manifest_payload["inputs"][0]["sha256"] = "bad"
            visual_review.write_json(manifest, manifest_payload)
            with self.assertRaisesRegex(visual_review.VisualReviewError, "sha256 mismatch"):
                visual_review.normalize_manifest(target, visual_review.load_json(manifest))

    def test_cli_routes_visual_review_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            code = bridge_cli.main(["visual-review", "preflight", "--target", str(target)])
            self.assertEqual(code, 0)

    def test_install_renders_pinned_bridge_kit_source_for_consumer_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            consumer = Path(tmp) / "consumer"
            consumer.mkdir()
            (consumer / "pyproject.toml").write_text("[project]\nname = 'consumer'\n", encoding="utf-8")
            pinned_ref = "0123456789abcdef0123456789abcdef01234567"

            actions = visual_review.install_visual_review(consumer, bridge_kit_ref=pinned_ref)
            workflow = (consumer / ".github" / "workflows" / "ai-bridge-visual-review.yml").read_text(encoding="utf-8")

            self.assertTrue(any("ai-bridge-visual-review.yml" in action for action in actions))
            self.assertFalse((consumer / "ai_bridge_kit").exists())
            self.assertIn(f"git+{visual_review.CANONICAL_BRIDGE_KIT_REPO}@{pinned_ref}", workflow)
            self.assertNotIn("pip install -e '.[visual-review]'", workflow)
            self.assertIn("'results/**/visual_review/visual_inputs.json'", workflow)
            self.assertIn("      - 'reviewed/**'", workflow)
            self.assertIn('git push origin "HEAD:${GITHUB_REF_NAME}"', workflow)
            self.assertNotIn("paths-ignore", workflow)
            self.assertIn("No visual review manifest changed; not required.", workflow)
            self.assertNotIn("pip install -e .", workflow)

    def test_visual_review_workflow_triggers_on_main_and_reviewed_branches_only_for_input_manifest(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "visual_review"
            / "github-actions"
            / "visual-review.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("      - main", workflow)
        self.assertIn("      - 'reviewed/**'", workflow)
        self.assertIn("      - 'results/**/visual_review/visual_inputs.json'", workflow)
        self.assertNotIn("results/**/visual_review/**", workflow)
        self.assertIn("group: ai-bridge-paid-review-${{ github.repository }}-${{ github.ref }}", workflow)
        self.assertIn('AI_BRIDGE_PAID_REVIEW_GIT_RESERVE: "1"', workflow)
        self.assertIn("cannot run live visual review", workflow)
        self.assertIn('git push origin "HEAD:${GITHUB_REF_NAME}"', workflow)
        self.assertIn('if [ "${GITHUB_REF_TYPE}" != "branch" ]; then', workflow)

    def make_git_consumer(self) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        tmp = tempfile.TemporaryDirectory()
        target = Path(tmp.name) / "consumer"
        target.mkdir()
        subprocess.check_call(["git", "init", "--initial-branch", "main"], cwd=target, stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "config", "user.email", "test@example.org"], cwd=target)
        subprocess.check_call(["git", "config", "user.name", "Test User"], cwd=target)
        (target / "README.md").write_text("# Consumer\n", encoding="utf-8")
        subprocess.check_call(["git", "add", "README.md"], cwd=target)
        subprocess.check_call(["git", "commit", "-m", "initial"], cwd=target, stdout=subprocess.DEVNULL)
        return tmp, target, "results/001_visual/visual_review/VISUAL_REVIEW.json"

    def test_visual_evidence_writeback_detects_untracked_unchanged_and_modified(self) -> None:
        tmp, target, output = self.make_git_consumer()
        with tmp:
            output_path = target / output
            output_path.parent.mkdir(parents=True)
            output_path.write_text('{"schema":"test","status":"PASS"}\n', encoding="utf-8")
            self.assertTrue(visual_review.visual_evidence_commit_needed(target, output))
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=target, text=True)
            self.assertIn(output, staged.splitlines())
            subprocess.check_call(["git", "commit", "-m", "add visual evidence"], cwd=target, stdout=subprocess.DEVNULL)

            self.assertFalse(visual_review.visual_evidence_commit_needed(target, output))
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=target, text=True)
            self.assertEqual(staged.strip(), "")

            output_path.write_text('{"schema":"test","status":"REVISE"}\n', encoding="utf-8")
            self.assertTrue(visual_review.visual_evidence_commit_needed(target, output))
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=target, text=True)
            self.assertIn(output, staged.splitlines())
            subprocess.check_call(["git", "commit", "-m", "update visual evidence"], cwd=target, stdout=subprocess.DEVNULL)
            latest_subject = subprocess.check_output(["git", "log", "-1", "--pretty=%s"], cwd=target, text=True).strip()
            self.assertEqual(latest_subject, "update visual evidence")

    def test_visual_evidence_writeback_stages_shared_campaign_budget(self) -> None:
        tmp, target, output = self.make_git_consumer()
        with tmp:
            output_path = target / output
            output_path.parent.mkdir(parents=True)
            output_path.write_text(
                json.dumps({"schema": "test", "status": "PASS", "paid_review": {"campaign_identity": "shared_campaign"}}) + "\n",
                encoding="utf-8",
            )
            budget = target / "results/shared_campaign/paid_review_budget.json"
            budget.parent.mkdir(parents=True)
            budget.write_text("{}\n", encoding="utf-8")

            self.assertTrue(visual_review.visual_evidence_commit_needed(target, output))
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=target, text=True)
            self.assertIn(output, staged.splitlines())
            self.assertIn("results/shared_campaign/paid_review_budget.json", staged.splitlines())

    def test_arbitrary_visual_review_output_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            bad_paths = [
                "../VISUAL_REVIEW.json",
                "src/VISUAL_REVIEW.json",
                "automation/agent_flow/tasks/001/CURRENT.json",
                ".github/workflows/visual.yml",
                "results/other/visual_review/VISUAL_REVIEW.json",
                "results/001_visual/visual_review/CURRENT.json",
                "results/001_visual/visual_review/FROZEN_CONTRACT.md",
                "results/001_visual/visual_review/REQUIREMENT_LEDGER.json",
            ]
            for bad in bad_paths:
                with self.subTest(path=bad):
                    with self.assertRaises(visual_review.VisualReviewError):
                        visual_review.validate_visual_output_path(target, "001_visual", bad)

            allowed = visual_review.validate_visual_output_path(
                target,
                "001_visual",
                "results/001_visual/visual_review/VISUAL_REVIEW.json",
            )
            self.assertEqual(allowed, target / "results/001_visual/visual_review/VISUAL_REVIEW.json")
