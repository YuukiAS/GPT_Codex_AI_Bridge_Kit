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
from ai_bridge_kit import text_transform


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class TextTransformTests(unittest.TestCase):
    def require_age(self) -> None:
        if shutil.which("age") and shutil.which("age-keygen"):
            return
        if os.environ.get("CI"):
            self.fail("age and age-keygen must be installed in CI for private text transform tests")
        self.skipTest("age CLI is not installed")

    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path, Path, Path]:
        self.require_age()
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        target = base / "project"
        target.mkdir()
        subprocess.check_call(["git", "init"], cwd=target, stdout=subprocess.DEVNULL)
        transform_dir = target / "results" / "048_text" / "text_transform"
        transform_dir.mkdir(parents=True)
        instruction = target / "docs" / "contract.md"
        instruction.parent.mkdir()
        instruction.write_text(
            "# Contract\n\nRewrite the complete source into natural Chinese while preserving every fact.\n",
            encoding="utf-8",
        )
        seed_instruction = target / "docs" / "seed-transformations.json"
        seed_instruction.write_text(
            json.dumps(
                [
                    {
                        "id": "seed-001",
                        "rewrite_problem": "workflow-language",
                        "source": "unit-test",
                    }
                ],
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        source = base / "private-source.md"
        source.write_text(
            "# Source\n\n"
            "本项目的 provenance 和 estimand 描述需要改成自然中文，但数字 42、模型 UNet 和 caveat 不能变。\n",
            encoding="utf-8",
        )
        input_identity = subprocess.check_output(["age-keygen"], text=True)
        input_recipient = text_review._extract_public_recipient(input_identity)
        input_recipient_file = target / text_transform.DEFAULT_INPUT_RECIPIENT_PATH
        input_recipient_file.parent.mkdir(parents=True)
        input_recipient_file.write_text(input_recipient + "\n", encoding="utf-8")
        output_identity = base / "output_identity.txt"
        receiver = text_transform.create_output_receiver(
            target,
            task_key="048_text",
            identity_path=output_identity,
            force=True,
        )
        manifest = Path("results/048_text/text_transform/text_transform_inputs.json")
        text_transform.encrypt_text_transform_input(
            target,
            task_key="048_text",
            input_path=source,
            input_recipient_file=input_recipient_file,
            output_path=Path("results/048_text/text_transform/input.age"),
            manifest_path=manifest,
            output_recipient_file=Path(receiver["recipient_path"]),
            instruction_files=[Path("docs/contract.md"), Path("docs/seed-transformations.json")],
            goal="Rewrite the complete source according to the bound contract.",
            implementation_commit="impl-048",
            external_upload_authorization="Unit test private text transform authorization.",
        )
        output_age = Path("results/048_text/text_transform/output.age")
        result = Path("results/048_text/text_transform/TEXT_TRANSFORM.json")
        return tmp, target, source, output_identity, output_age, result

    def test_mock_responses_api_uses_store_false_and_writes_only_encrypted_output_metadata(self) -> None:
        tmp, target, source, output_identity, output_age, result = self.make_project()
        with tmp:
            captured: dict = {}
            transformed = "# Rewritten\n\n本项目需要说明材料来源和目标估计量；数字 42、模型 UNet 和 caveat 保持不变。\n"

            def opener(request, timeout):
                captured["body"] = json.loads(request.data.decode("utf-8"))
                captured["auth"] = request.headers.get("Authorization")
                captured["timeout"] = timeout
                return FakeResponse({"status": "completed", "output_text": transformed})

            artifact = text_transform.run_text_transform(
                target,
                target / "results/048_text/text_transform/text_transform_inputs.json",
                source,
                output_age,
                result,
                api_key="sk-transform-secret",
                model="gpt-test-transform",
                timeout=17,
                opener=opener,
            )

            request_text = json.dumps(captured["body"], ensure_ascii=False)
            self.assertEqual(captured["body"]["model"], "gpt-test-transform")
            self.assertFalse(captured["body"]["store"])
            self.assertIn("provenance 和 estimand", request_text)
            self.assertIn("docs/contract.md", request_text)
            self.assertIn("docs/seed-transformations.json", request_text)
            self.assertNotIn("sk-transform-secret", request_text)
            self.assertEqual(captured["timeout"], 17)
            self.assertEqual(artifact["schema"], text_transform.TEXT_TRANSFORM_RESULT_SCHEMA)
            self.assertFalse(artifact["store"])
            self.assertFalse(artifact["plaintext_committed"])
            metadata_text = json.dumps(artifact, ensure_ascii=False)
            self.assertNotIn("本项目需要说明材料来源", metadata_text)
            self.assertEqual(artifact["source_plaintext_sha256"], text_transform.sha256_bytes(source.read_bytes()))

            decrypted = Path(tmp.name) / "decrypted.md"
            text_transform.decrypt_text_transform_output(
                target,
                result_path=target / result,
                identity_file=output_identity,
                output_path=decrypted,
            )
            self.assertEqual(decrypted.read_text(encoding="utf-8"), transformed)

    def test_default_model_and_review_key_precedence(self) -> None:
        tmp, target, source, _output_identity, output_age, result = self.make_project()
        with tmp, mock.patch.dict(
            os.environ,
            {
                text_transform.OPENAI_TRANSFORM_KEY_ENV: "sk-review",
                text_transform.LEGACY_OPENAI_KEY_ENV: "sk-visual",
            },
        ):
            captured: dict = {}

            def opener(request, timeout):
                captured["body"] = json.loads(request.data.decode("utf-8"))
                captured["auth"] = request.headers.get("Authorization")
                return FakeResponse({"status": "completed", "output_text": "rewritten text"})

            artifact = text_transform.run_text_transform(
                target,
                target / "results/048_text/text_transform/text_transform_inputs.json",
                source,
                output_age,
                result,
                opener=opener,
            )
            self.assertEqual(captured["auth"], "Bearer sk-review")
            self.assertEqual(captured["body"]["model"], text_transform.DEFAULT_MODEL)
            self.assertEqual(artifact["model"], text_transform.DEFAULT_MODEL)

    def test_source_sha_and_instruction_sha_mismatch_fail_closed(self) -> None:
        tmp, target, source, _output_identity, output_age, result = self.make_project()
        with tmp:
            source.write_text("# Changed\n\nDifferent source.\n", encoding="utf-8")
            with self.assertRaisesRegex(text_transform.TextTransformError, "plaintext SHA-256"):
                text_transform.run_text_transform(
                    target,
                    target / "results/048_text/text_transform/text_transform_inputs.json",
                    source,
                    output_age,
                    result,
                    api_key="sk",
                    opener=lambda *_args, **_kwargs: FakeResponse({"status": "completed", "output_text": "x"}),
                )
            self.assertFalse((target / output_age).exists())
            manifest = target / "results/048_text/text_transform/text_transform_inputs.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["instructions"]["files"][0]["sha256"] = "0" * 64
            text_transform.write_json(manifest, payload)
            with self.assertRaisesRegex(text_transform.TextTransformError, "instruction file SHA-256 mismatch"):
                text_transform.normalize_manifest(target, text_transform.load_json(manifest))

    def test_json_instruction_file_is_allowed_but_private_json_source_is_not(self) -> None:
        tmp, target, _source, _output_identity, _output_age, _result = self.make_project()
        with tmp:
            manifest = json.loads(
                (target / "results/048_text/text_transform/text_transform_inputs.json").read_text(encoding="utf-8")
            )
            mime_types = {item["path"]: item["mime_type"] for item in manifest["instructions"]["files"]}
            self.assertEqual(mime_types["docs/seed-transformations.json"], "application/json; charset=utf-8")

            private_json = Path(tmp.name) / "private-source.json"
            private_json.write_text('{"source": "private"}\n', encoding="utf-8")
            with self.assertRaisesRegex(text_transform.TextTransformError, "Markdown/plain text"):
                text_transform.encrypt_text_transform_input(
                    target,
                    task_key="048_text",
                    input_path=private_json,
                    input_recipient_file=target / text_transform.DEFAULT_INPUT_RECIPIENT_PATH,
                    output_path=Path("results/048_text/text_transform/input.age"),
                    manifest_path=Path("results/048_text/text_transform/text_transform_inputs.json"),
                    output_recipient_file=Path("results/048_text/text_transform/output.age.pub"),
                    instruction_files=[Path("docs/contract.md")],
                    goal="Private JSON input must stay out of this transport.",
                    implementation_commit="impl-048",
                    external_upload_authorization="Unit test private text transform authorization.",
                    force=True,
                )

    def test_output_receiver_private_identity_refuses_target_repo_path(self) -> None:
        self.require_age()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            with self.assertRaisesRegex(text_transform.TextTransformError, "must not be written inside"):
                text_transform.create_output_receiver(
                    target,
                    task_key="048_text",
                    identity_path=target / "results/048_text/text_transform/output_identity.txt",
                )

    def test_api_error_and_empty_output_fail_closed(self) -> None:
        tmp, target, source, _output_identity, output_age, result = self.make_project()
        with tmp:
            with self.assertRaisesRegex(text_transform.TextTransformError, "did not complete"):
                text_transform.run_text_transform(
                    target,
                    target / "results/048_text/text_transform/text_transform_inputs.json",
                    source,
                    output_age,
                    result,
                    api_key="sk",
                    opener=lambda *_args, **_kwargs: FakeResponse({"status": "incomplete", "output_text": "x"}),
                )
            with self.assertRaisesRegex(text_transform.TextTransformError, "output was empty"):
                text_transform.run_text_transform(
                    target,
                    target / "results/048_text/text_transform/text_transform_inputs.json",
                    source,
                    output_age,
                    result,
                    api_key="sk",
                    opener=lambda *_args, **_kwargs: FakeResponse({"status": "completed", "output_text": "   "}),
                )
            self.assertFalse((target / output_age).exists())

    def test_writeback_stages_only_output_age_and_result(self) -> None:
        tmp, target, source, _output_identity, output_age, result = self.make_project()
        with tmp:
            text_transform.run_text_transform(
                target,
                target / "results/048_text/text_transform/text_transform_inputs.json",
                source,
                output_age,
                result,
                api_key="sk",
                opener=lambda *_args, **_kwargs: FakeResponse({"status": "completed", "output_text": "rewritten text"}),
            )
            self.assertTrue(text_transform.text_transform_writeback_needed(target, output_age, result))
            staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=target, text=True).splitlines()
            self.assertEqual(
                staged,
                [
                    "results/048_text/text_transform/TEXT_TRANSFORM.json",
                    "results/048_text/text_transform/output.age",
                ],
            )

    def test_cli_routes_text_transform_preflight_and_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(bridge_cli.main(["text-transform", "preflight", "--target", str(target)]), 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], "AI_BRIDGE_TEXT_TRANSFORM_PREFLIGHT_V1")

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    bridge_cli.main(
                        [
                            "text-transform",
                            "install",
                            "--target",
                            str(target),
                            "--bridge-kit-ref",
                            "0123456789abcdef0123456789abcdef01234567",
                        ]
                    ),
                    0,
                )
            workflow = (target / ".github" / "workflows" / "ai-bridge-text-transform.yml").read_text(encoding="utf-8")
            self.assertIn(text_transform.AGE_SECRET_NAME, workflow)
            self.assertIn(text_transform.LEGACY_OPENAI_KEY_ENV, workflow)
            self.assertIn("      - 'reviewed/**'", workflow)
            self.assertIn("results/**/text_transform/text_transform_inputs.json", workflow)
            self.assertIn('git push origin "HEAD:${GITHUB_REF_NAME}"', workflow)

    def test_text_transform_workflow_triggers_only_for_input_manifest(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "text_transform"
            / "github-actions"
            / "text-transform.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("      - main", workflow)
        self.assertIn("      - 'reviewed/**'", workflow)
        self.assertIn("      - 'results/**/text_transform/text_transform_inputs.json'", workflow)
        self.assertNotIn("results/**/text_transform/**", workflow)
        self.assertIn('git push origin "HEAD:${GITHUB_REF_NAME}"', workflow)


if __name__ == "__main__":
    unittest.main()
