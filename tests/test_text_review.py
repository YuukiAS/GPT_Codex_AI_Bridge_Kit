from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ai_bridge_kit import bridge_cli
from ai_bridge_kit import text_review


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class TextReviewTests(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        target = Path(tmp.name) / "project"
        target.mkdir()
        text_dir = target / "results" / "001_text" / "text_review"
        text_dir.mkdir(parents=True)
        plaintext = Path(tmp.name) / "private-final.md"
        plaintext.write_text(
            "# Final\n\n"
            "这份面向普通读者的中文报告仍然反复使用 provenance、estimand、calibration 等抽象英文标签。\n",
            encoding="utf-8",
        )
        payload = text_dir / "payload.age"
        payload.write_bytes(b"synthetic ciphertext")
        data = plaintext.read_bytes()
        manifest = text_dir / "text_inputs.json"
        text_review.write_json(
            manifest,
            {
                "schema": text_review.TEXT_INPUT_MANIFEST_SCHEMA,
                "task_key": "001_text",
                "workflow_type": "reviewed_handoff",
                "review_kind": "user-facing-text",
                "privacy_policy": text_review.PRIVATE_TEXT_POLICY,
                "external_upload_authorization": "Unit test private text review authorization.",
                "rubric": {
                    "instructions": "Return REVISE if ordinary Chinese prose contains abstract English label pollution."
                },
                "identity_bindings": {"implementation_commit": "impl-1"},
                "input": {
                    "logical_id": "primary_text",
                    "encrypted_payload_path": "results/001_text/text_review/payload.age",
                    "ciphertext_sha256": text_review.file_sha256(payload),
                    "plaintext_sha256": text_review.sha256_bytes(data),
                    "plaintext_size_bytes": len(data),
                    "mime_type": "text/markdown; charset=utf-8",
                    "source_basename": plaintext.name,
                },
            },
        )
        output = Path("results/001_text/text_review/TEXT_REVIEW.json")
        return tmp, target, manifest, plaintext, output

    def model_payload(self, decision: str = "REVISE") -> dict:
        return {
            "overall_decision": decision,
            "item_reviews": [
                {
                    "item_id": "primary_text",
                    "decision": decision,
                    "summary": "Complete text reviewed.",
                    "requirement_ids": ["REQ_PLAIN_CHINESE"],
                }
            ],
            "blocking_findings": [
                {
                    "finding_id": "TXT-001",
                    "requirement_id": "REQ_PLAIN_CHINESE",
                    "severity": "blocking",
                    "summary": "Chinese reader-facing prose still uses abstract English labels.",
                    "evidence": "provenance / estimand / calibration remain visible.",
                    "recommendation": "Rewrite these labels into natural Chinese for ordinary readers.",
                }
            ]
            if decision == "REVISE"
            else [],
            "non_blocking_notes": [],
        }

    def test_mock_responses_api_reads_complete_plaintext_and_uses_store_false(self) -> None:
        tmp, target, manifest, plaintext, output = self.make_project()
        with tmp:
            captured: dict = {}

            def opener(request, timeout):
                captured["body"] = json.loads(request.data.decode("utf-8"))
                captured["auth"] = request.headers.get("Authorization")
                captured["timeout"] = timeout
                return FakeResponse({"status": "completed", "output_text": json.dumps(self.model_payload("REVISE"))})

            artifact = text_review.run_text_review(
                target,
                manifest,
                plaintext,
                output,
                api_key="sk-text-secret",
                model="gpt-test-text",
                timeout=13,
                opener=opener,
            )

            request_text = json.dumps(captured["body"], ensure_ascii=False)
            self.assertEqual(captured["body"]["model"], "gpt-test-text")
            self.assertFalse(captured["body"]["store"])
            self.assertIn("provenance、estimand、calibration", request_text)
            self.assertNotIn("sk-text-secret", request_text)
            self.assertEqual(captured["timeout"], 13)
            self.assertEqual(artifact["schema"], text_review.TEXT_REVIEW_SCHEMA)
            self.assertEqual(artifact["overall_decision"], "REVISE")
            self.assertEqual(artifact["model"], "gpt-test-text")
            self.assertEqual(artifact["plaintext_artifact_sha256"], text_review.sha256_bytes(plaintext.read_bytes()))
            self.assertNotIn("这份面向普通读者", json.dumps(artifact, ensure_ascii=False))

    def test_default_model_and_environment_override(self) -> None:
        tmp, target, manifest, plaintext, output = self.make_project()
        with tmp:
            previous = os.environ.pop(text_review.MODEL_ENV, None)
            captured: dict = {}

            def opener(request, timeout):
                captured["body"] = json.loads(request.data.decode("utf-8"))
                return FakeResponse({"status": "completed", "output_text": json.dumps(self.model_payload("PASS"))})

            try:
                artifact = text_review.run_text_review(target, manifest, plaintext, output, api_key="sk", opener=opener)
                self.assertEqual(captured["body"]["model"], text_review.DEFAULT_MODEL)
                self.assertEqual(artifact["model"], "gpt-5.6-terra")
                os.environ[text_review.MODEL_ENV] = "gpt-env-text"
                artifact = text_review.run_text_review(target, manifest, plaintext, output, api_key="sk", opener=opener)
                self.assertEqual(captured["body"]["model"], "gpt-env-text")
                self.assertEqual(artifact["model"], "gpt-env-text")
            finally:
                if previous is not None:
                    os.environ[text_review.MODEL_ENV] = previous
                else:
                    os.environ.pop(text_review.MODEL_ENV, None)

    def test_openai_review_key_precedes_visual_review_key(self) -> None:
        tmp, target, manifest, plaintext, output = self.make_project()
        with tmp, mock.patch.dict(
            os.environ,
            {
                text_review.OPENAI_REVIEW_KEY_ENV: "sk-review",
                text_review.LEGACY_OPENAI_KEY_ENV: "sk-visual",
            },
        ):
            captured: dict = {}

            def opener(request, timeout):
                captured["auth"] = request.headers.get("Authorization")
                return FakeResponse({"status": "completed", "output_text": json.dumps(self.model_payload("PASS"))})

            text_review.run_text_review(target, manifest, plaintext, output, opener=opener)
            self.assertEqual(captured["auth"], "Bearer sk-review")

    def test_visual_review_key_is_backward_compatible(self) -> None:
        tmp, target, manifest, plaintext, output = self.make_project()
        with tmp, mock.patch.dict(os.environ, {text_review.LEGACY_OPENAI_KEY_ENV: "sk-visual"}, clear=True):
            captured: dict = {}

            def opener(request, timeout):
                captured["auth"] = request.headers.get("Authorization")
                return FakeResponse({"status": "completed", "output_text": json.dumps(self.model_payload("PASS"))})

            text_review.run_text_review(target, manifest, plaintext, output, opener=opener)
            self.assertEqual(captured["auth"], "Bearer sk-visual")

    def test_plaintext_sha_stale_detection_fails_closed(self) -> None:
        tmp, target, manifest, plaintext, output = self.make_project()
        with tmp:
            plaintext.write_text("# Changed\n\nDifferent full text.\n", encoding="utf-8")

            def opener(*_args, **_kwargs):
                return FakeResponse({"status": "completed", "output_text": json.dumps(self.model_payload("PASS"))})

            with self.assertRaisesRegex(text_review.TextReviewError, "plaintext SHA-256"):
                text_review.run_text_review(target, manifest, plaintext, output, api_key="sk", opener=opener)
            self.assertFalse((target / output).exists())

    def test_validate_rejects_stale_manifest_identity(self) -> None:
        tmp, target, manifest, plaintext, output = self.make_project()
        with tmp:
            artifact = text_review.assemble_text_review(
                manifest=text_review.normalize_manifest(target, text_review.load_json(manifest)),
                model_output=self.model_payload("PASS"),
                model="gpt-test",
            )
            artifact["plaintext_artifact_sha256"] = "0" * 64
            errors = text_review.validate_text_review_payload(
                artifact,
                expected={
                    "implementation_commit": "impl-1",
                    "plaintext_sha256": text_review.sha256_bytes(plaintext.read_bytes()),
                    "manifest_identity": text_review.manifest_identity(text_review.normalize_manifest(target, text_review.load_json(manifest))),
                },
            )
            self.assertTrue(any("plaintext_artifact_sha256 mismatch" in error for error in errors), errors)

    def test_age_encrypt_decrypt_roundtrip_and_wrong_key_fail_closed(self) -> None:
        if not (shutil.which("age") and shutil.which("age-keygen")):
            if os.environ.get("CI"):
                self.fail("age and age-keygen must be installed in CI for private text transport tests")
            self.skipTest("age CLI is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            plaintext = base / "input.md"
            plaintext.write_text("# Private\n\nFull private text.\n", encoding="utf-8")
            key_a = subprocess.check_output(["age-keygen"], text=True)
            key_b = subprocess.check_output(["age-keygen"], text=True)
            recipient_a = text_review._extract_public_recipient(key_a)
            identity_a = base / "identity-a.txt"
            identity_b = base / "identity-b.txt"
            identity_a.write_text(key_a, encoding="utf-8")
            identity_b.write_text(key_b, encoding="utf-8")
            encrypted = base / "payload.age"
            decrypted = base / "decrypted.md"

            text_review.encrypt_with_age(plaintext, encrypted, recipient=recipient_a)
            text_review.decrypt_with_age(encrypted, decrypted, identity_file=identity_a)
            self.assertEqual(decrypted.read_text(encoding="utf-8"), plaintext.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(text_review.TextReviewError, "failed closed"):
                text_review.decrypt_with_age(encrypted, base / "wrong.md", identity_file=identity_b)
            corrupt = base / "corrupt.age"
            corrupt.write_bytes(encrypted.read_bytes()[:16] + b"corrupt")
            with self.assertRaisesRegex(text_review.TextReviewError, "failed closed"):
                text_review.decrypt_with_age(corrupt, base / "corrupt.md", identity_file=identity_a)

    def test_ciphertext_sha_mismatch_fails_closed(self) -> None:
        tmp, target, manifest, _plaintext, _output = self.make_project()
        with tmp:
            payload = target / "results/001_text/text_review/payload.age"
            payload.write_bytes(b"different ciphertext bytes")
            with self.assertRaisesRegex(text_review.TextReviewError, "encrypted text review payload sha256 mismatch"):
                text_review.normalize_manifest(target, text_review.load_json(manifest))

    def test_main_ci_installs_age_so_transport_tests_do_not_skip(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("Install age transport dependency", workflow)
        self.assertIn("sudo apt-get install -y age", workflow)

    def test_text_review_workflow_triggers_on_main_and_reviewed_branches_only_for_input_manifest(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "text_review"
            / "github-actions"
            / "text-review.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("      - main", workflow)
        self.assertIn("      - 'reviewed/**'", workflow)
        self.assertIn("      - 'results/**/text_review/text_inputs.json'", workflow)
        self.assertNotIn("results/**/text_review/**", workflow)
        self.assertIn('git push origin "HEAD:${GITHUB_REF_NAME}"', workflow)
        self.assertIn('if [ "${GITHUB_REF_TYPE}" != "branch" ]; then', workflow)

    def test_cli_routes_text_review_preflight_and_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(bridge_cli.main(["text-review", "preflight", "--target", str(target)]), 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], "AI_BRIDGE_TEXT_REVIEW_PREFLIGHT_V1")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    bridge_cli.main(
                        [
                            "text-review",
                            "install",
                            "--target",
                            str(target),
                            "--bridge-kit-ref",
                            "0123456789abcdef0123456789abcdef01234567",
                        ]
                    ),
                    0,
                )
            workflow = (target / ".github" / "workflows" / "ai-bridge-text-review.yml").read_text(encoding="utf-8")
            self.assertIn(text_review.AGE_SECRET_NAME, workflow)
            self.assertIn(text_review.LEGACY_OPENAI_KEY_ENV, workflow)
            self.assertIn("      - 'reviewed/**'", workflow)
            self.assertIn('git push origin "HEAD:${GITHUB_REF_NAME}"', workflow)
