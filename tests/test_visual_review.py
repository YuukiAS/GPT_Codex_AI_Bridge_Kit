from __future__ import annotations

import base64
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from ai_bridge_kit import bridge_cli
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
        return tmp, target, manifest, image.parent / "VISUAL_REVIEW.json"

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
            self.assertFalse(output.exists())

    def test_mock_responses_api_generates_schema_compliant_review(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            captured: dict = {}

            def opener(request, timeout):
                captured["body"] = json.loads(request.data.decode("utf-8"))
                captured["auth"] = request.headers.get("Authorization")
                captured["timeout"] = timeout
                return FakeResponse({"status": "completed", "output_text": json.dumps(self.model_payload())})

            artifact = visual_review.run_visual_review(
                target,
                manifest,
                output,
                api_key="sk-test-secret",
                model="gpt-test-vision",
                timeout=12,
                opener=opener,
            )
            self.assertEqual(artifact["schema"], visual_review.VISUAL_REVIEW_SCHEMA)
            self.assertEqual(artifact["overall_decision"], "PASS")
            self.assertEqual(artifact["status"], "PASS")
            self.assertEqual(artifact["review_model"], "gpt-test-vision")
            self.assertEqual(visual_review.validate_visual_review_payload(artifact, expected={"implementation_commit": "impl-1"}), [])
            self.assertFalse(captured["body"]["store"])
            self.assertIn("input_image", json.dumps(captured["body"]))
            self.assertEqual(captured["timeout"], 12)
            self.assertNotIn("sk-test-secret", json.dumps(captured["body"]))

    def test_malformed_model_output_fails_closed(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            def opener(*_args, **_kwargs):
                return FakeResponse({"status": "completed", "output_text": "{not json"})

            with self.assertRaisesRegex(visual_review.VisualReviewError, "not valid JSON"):
                visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=opener)
            self.assertFalse(output.exists())

            def incomplete_opener(*_args, **_kwargs):
                return FakeResponse({"status": "completed", "output_text": json.dumps({"overall_decision": "PASS"})})

            with self.assertRaisesRegex(visual_review.VisualReviewError, "missing item_reviews"):
                visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=incomplete_opener)
            self.assertFalse(output.exists())

    def test_api_failure_fails_closed_without_secret_in_error(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            def opener(*_args, **_kwargs):
                raise urllib.error.URLError("rate limited")

            with self.assertRaises(visual_review.VisualReviewError) as caught:
                visual_review.run_visual_review(target, manifest, output, api_key="sk-secret-value", opener=opener)
            self.assertNotIn("sk-secret-value", str(caught.exception))
            self.assertFalse(output.exists())

    def test_identity_and_image_sha_mismatch_are_rejected(self) -> None:
        tmp, target, manifest, output = self.make_project()
        with tmp:
            def opener(*_args, **_kwargs):
                return FakeResponse({"status": "completed", "output_text": json.dumps(self.model_payload())})

            artifact = visual_review.run_visual_review(target, manifest, output, api_key="sk-secret", opener=opener)
            artifact["images"][0]["sha256"] = "bad"
            visual_review.write_json(output, artifact)
            errors = visual_review.validate_visual_review_payload(
                visual_review.load_json(output),
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
