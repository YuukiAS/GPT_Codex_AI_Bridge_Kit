from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from . import text_review
from . import visual_review


TEXT_TRANSFORM_MANIFEST_SCHEMA = "AI_BRIDGE_TEXT_TRANSFORM_MANIFEST_V1"
TEXT_TRANSFORM_RESULT_SCHEMA = "AI_BRIDGE_TEXT_TRANSFORM_V1"
AGE_SECRET_NAME = text_review.AGE_SECRET_NAME
OPENAI_TRANSFORM_KEY_ENV = text_review.OPENAI_REVIEW_KEY_ENV
LEGACY_OPENAI_KEY_ENV = text_review.LEGACY_OPENAI_KEY_ENV
MODEL_ENV = "OPENAI_TEXT_TRANSFORM_MODEL"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_PROMPT_VERSION = "ai-bridge.text-transform.v1"
PRIVATE_TEXT_POLICY = "PRIVATE_TEXT_TRANSFORM_AUTHORIZED"
PUBLIC_SAFE_POLICY = visual_review.DEFAULT_PRIVACY_POLICY
WORKFLOW_TYPES = visual_review.WORKFLOW_TYPES
API_URL = visual_review.API_URL
CANONICAL_BRIDGE_KIT_REPO = visual_review.CANONICAL_BRIDGE_KIT_REPO
DEFAULT_INPUT_RECIPIENT_PATH = text_review.DEFAULT_RECIPIENT_PATH
DEFAULT_STATE_DIRNAME = "text-transform"


class TextTransformError(ValueError):
    pass


def canonical_json(payload: Any, *, pretty: bool = False) -> str:
    return visual_review.canonical_json(payload, pretty=pretty)


def sha256_bytes(data: bytes) -> str:
    return visual_review.sha256_bytes(data)


def sha256_text(text: str) -> str:
    return visual_review.sha256_text(text)


def file_sha256(path: Path) -> str:
    return visual_review.file_sha256(path)


def load_json(path: Path) -> dict[str, Any]:
    return visual_review.load_json(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    visual_review.write_json(path, payload)


def repository_relative_path(path: Path | str) -> str:
    try:
        return visual_review.repository_relative_path(path)
    except visual_review.VisualReviewError as exc:
        raise TextTransformError(str(exc)) from exc


def validate_generated_text_transform_path(path: Path | str) -> str:
    rel = repository_relative_path(path)
    if not re.fullmatch(r"results/[^/]+/text_transform/.+", rel):
        raise TextTransformError("text transform write-back path must be under results/<task_key>/text_transform/")
    if rel.endswith("/"):
        raise TextTransformError("text transform write-back path must be a file path")
    blocked_names = {
        "CURRENT.json",
        "PLAN.md",
        "REQUEST.md",
        "RESULT.md",
        "FINAL_REPORT.md",
    }
    if Path(rel).name in blocked_names:
        raise TextTransformError("text transform output must be generated evidence, not workflow control files")
    blocked_parts = {".github", "src", "automation"}
    if blocked_parts.intersection(Path(rel).parts):
        raise TextTransformError("text transform output must not target source, automation, or workflow paths")
    return rel


def validate_manifest_path(path: Path | str) -> str:
    rel = validate_generated_text_transform_path(path)
    if not rel.endswith(".json"):
        raise TextTransformError("text transform manifest path must be a JSON file")
    return rel


def validate_result_path(path: Path | str) -> str:
    rel = validate_generated_text_transform_path(path)
    if not rel.endswith(".json"):
        raise TextTransformError("text transform result path must be a JSON file")
    return rel


def validate_encrypted_payload_path(path: Path | str) -> str:
    rel = validate_generated_text_transform_path(path)
    if not rel.endswith(".age"):
        raise TextTransformError("text transform encrypted payload must use a .age path")
    return rel


def validate_recipient_path(path: Path | str) -> str:
    rel = validate_generated_text_transform_path(path)
    if not rel.endswith(".pub"):
        raise TextTransformError("text transform output recipient path must use a .pub path")
    return rel


def _require_utf8_text(path: Path) -> tuple[str, bytes]:
    try:
        return text_review._require_utf8_text(path)
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def _logical_text_mime(path: Path) -> str:
    try:
        return text_review._logical_text_mime(path)
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def _age_binary() -> str:
    try:
        return text_review._age_binary()
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def _age_keygen_binary() -> str:
    try:
        return text_review._age_keygen_binary()
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def _run_age(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return text_review._run_age(args, input_text=input_text)
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def encrypt_with_age(input_path: Path, output_path: Path, *, recipient: str, force: bool = False) -> None:
    try:
        text_review.encrypt_with_age(input_path, output_path, recipient=recipient, force=force)
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def decrypt_with_age(payload_path: Path, output_path: Path, *, identity_file: Path, force: bool = False) -> None:
    try:
        text_review.decrypt_with_age(payload_path, output_path, identity_file=identity_file, force=force)
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def _extract_public_recipient(identity_text: str) -> str:
    try:
        return text_review._extract_public_recipient(identity_text)
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc)) from exc


def _read_recipient_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    recipient = next((line.strip() for line in text.splitlines() if line.strip().startswith("age1")), "")
    if not recipient:
        raise TextTransformError("age public recipient file does not contain an age1 recipient")
    return recipient


def _state_home() -> Path:
    return Path(os.environ.get("AI_BRIDGE_STATE_HOME") or Path.home() / ".ai-bridge").expanduser()


def _repo_state_slug(target: Path) -> str:
    slug = visual_review.gh_repo_slug(target)
    if slug:
        return slug.replace("/", "__")
    return sha256_text(str(target.resolve()))[:16]


def default_output_identity_path(target: Path, task_key: str) -> Path:
    return _state_home() / DEFAULT_STATE_DIRNAME / _repo_state_slug(target) / task_key / "output_identity.txt"


def default_output_recipient_path(task_key: str) -> Path:
    return Path("results") / task_key / "text_transform" / "output.age.pub"


def create_output_receiver(
    target: Path,
    *,
    task_key: str,
    identity_path: Path | None = None,
    recipient_path: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    target = target.resolve()
    selected_identity = identity_path or default_output_identity_path(target, task_key)
    selected_recipient_rel = validate_recipient_path(recipient_path or default_output_recipient_path(task_key))
    selected_recipient = target / selected_recipient_rel
    try:
        selected_identity.resolve().relative_to(target)
    except ValueError:
        pass
    else:
        raise TextTransformError("output private identity must not be written inside the target repository")
    if selected_identity.exists() and not force:
        raise TextTransformError(f"output private identity already exists: {selected_identity}")
    if selected_recipient.exists() and not force:
        raise TextTransformError(f"output public recipient already exists: {selected_recipient_rel}")
    selected_identity.parent.mkdir(parents=True, exist_ok=True)
    selected_recipient.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([_age_keygen_binary()], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise TextTransformError("age-keygen failed closed")
    identity_text = result.stdout
    recipient = _extract_public_recipient(identity_text + "\n" + result.stderr)
    if selected_identity.exists() and force:
        selected_identity.unlink()
    if selected_recipient.exists() and force:
        selected_recipient.unlink()
    selected_identity.write_text(identity_text, encoding="utf-8")
    selected_identity.chmod(0o600)
    selected_recipient.write_text(recipient + "\n", encoding="utf-8")
    return {
        "schema": "AI_BRIDGE_TEXT_TRANSFORM_OUTPUT_RECEIVER_V1",
        "task_key": task_key,
        "identity_path": str(selected_identity),
        "recipient_path": selected_recipient_rel,
        "recipient_sha256": file_sha256(selected_recipient),
        "private_identity_printed": False,
        "private_identity_committed": False,
    }


def instruction_bundle_identity(instructions: list[dict[str, Any]]) -> str:
    return sha256_text(
        canonical_json(
            [
                {
                    "path": item["path"],
                    "sha256": item["sha256"],
                }
                for item in instructions
            ]
        )
    )


def normalize_instruction_files(target: Path, files: list[str | Path]) -> tuple[list[dict[str, Any]], str]:
    if not files:
        raise TextTransformError("text transform requires at least one public instruction file")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in files:
        rel = repository_relative_path(raw)
        if rel in seen:
            raise TextTransformError(f"duplicate instruction file: {rel}")
        seen.add(rel)
        path = target / rel
        if not path.exists() or not path.is_file():
            raise TextTransformError(f"instruction file missing: {rel}")
        text, data = _require_utf8_text(path)
        if not text.strip():
            raise TextTransformError(f"instruction file is empty: {rel}")
        normalized.append(
            {
                "path": rel,
                "sha256": sha256_bytes(data),
                "size_bytes": len(data),
                "mime_type": _logical_text_mime(path),
            }
        )
    return normalized, instruction_bundle_identity(normalized)


def normalize_manifest(target: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema") != TEXT_TRANSFORM_MANIFEST_SCHEMA:
        raise TextTransformError(f"text transform manifest schema must be {TEXT_TRANSFORM_MANIFEST_SCHEMA}")
    workflow_type = manifest.get("workflow_type")
    if workflow_type not in WORKFLOW_TYPES:
        raise TextTransformError(f"text transform workflow_type must be one of {sorted(WORKFLOW_TYPES)}")
    task_key = str(manifest.get("task_key") or "").strip()
    if not task_key:
        raise TextTransformError("text transform manifest task_key is required")
    transform_kind = str(manifest.get("transform_kind") or "").strip()
    if not transform_kind:
        raise TextTransformError("text transform manifest transform_kind is required")
    privacy_policy = str(manifest.get("privacy_policy") or PRIVATE_TEXT_POLICY)
    if privacy_policy != PUBLIC_SAFE_POLICY and not str(manifest.get("external_upload_authorization") or "").strip():
        raise TextTransformError("non-public text transform requires explicit external_upload_authorization")
    instructions = manifest.get("instructions")
    if not isinstance(instructions, dict):
        raise TextTransformError("text transform manifest requires instructions object")
    goal = str(instructions.get("goal") or "").strip()
    if not goal:
        raise TextTransformError("text transform instructions.goal is required")
    raw_files = instructions.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise TextTransformError("text transform instructions.files must be non-empty")
    normalized_files: list[dict[str, Any]] = []
    for item in raw_files:
        if not isinstance(item, dict):
            raise TextTransformError("text transform instruction file entry must be an object")
        rel = repository_relative_path(str(item.get("path") or ""))
        path = target / rel
        if not path.exists() or not path.is_file():
            raise TextTransformError(f"instruction file missing: {rel}")
        sha = file_sha256(path)
        expected = str(item.get("sha256") or "").strip()
        if expected and expected != sha:
            raise TextTransformError(f"instruction file SHA-256 mismatch: {rel}")
        normalized_files.append(
            {
                "path": rel,
                "sha256": sha,
                "size_bytes": path.stat().st_size,
                "mime_type": str(item.get("mime_type") or _logical_text_mime(path)),
            }
        )
    bundle_sha = instruction_bundle_identity(normalized_files)
    expected_bundle = str(instructions.get("bundle_sha256") or "").strip()
    if expected_bundle and expected_bundle != bundle_sha:
        raise TextTransformError("instruction bundle SHA-256 mismatch")
    input_item = manifest.get("input")
    if not isinstance(input_item, dict):
        raise TextTransformError("text transform manifest requires input object")
    logical_id = str(input_item.get("logical_id") or "").strip()
    if not logical_id:
        raise TextTransformError("text transform input.logical_id is required")
    encrypted_rel = validate_encrypted_payload_path(str(input_item.get("encrypted_payload_path") or ""))
    encrypted_path = target / encrypted_rel
    if not encrypted_path.exists() or not encrypted_path.is_file():
        raise TextTransformError(f"encrypted text transform payload missing: {encrypted_rel}")
    ciphertext_sha = file_sha256(encrypted_path)
    expected_ciphertext_sha = str(input_item.get("ciphertext_sha256") or "").strip()
    if expected_ciphertext_sha and expected_ciphertext_sha != ciphertext_sha:
        raise TextTransformError("encrypted text transform payload sha256 mismatch")
    plaintext_sha = str(input_item.get("plaintext_sha256") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", plaintext_sha):
        raise TextTransformError("text transform input.plaintext_sha256 must be a SHA-256 hex digest")
    size_bytes = input_item.get("plaintext_size_bytes")
    if not isinstance(size_bytes, int) or size_bytes < 0:
        raise TextTransformError("text transform input.plaintext_size_bytes must be a non-negative integer")
    mime_type = str(input_item.get("mime_type") or "text/markdown; charset=utf-8")
    if mime_type not in {"text/markdown; charset=utf-8", "text/plain; charset=utf-8"}:
        raise TextTransformError("text transform input.mime_type must be UTF-8 Markdown/plain text")
    output_item = manifest.get("output")
    if not isinstance(output_item, dict):
        raise TextTransformError("text transform manifest requires output object")
    recipient_rel = validate_recipient_path(str(output_item.get("public_recipient_path") or ""))
    recipient_path = target / recipient_rel
    if not recipient_path.exists() or not recipient_path.is_file():
        raise TextTransformError(f"output public recipient missing: {recipient_rel}")
    recipient = _read_recipient_file(recipient_path)
    expected_recipient = str(output_item.get("public_recipient") or "").strip()
    if expected_recipient and expected_recipient != recipient:
        raise TextTransformError("output public recipient mismatch")
    recipient_sha = file_sha256(recipient_path)
    expected_recipient_sha = str(output_item.get("public_recipient_sha256") or "").strip()
    if expected_recipient_sha and expected_recipient_sha != recipient_sha:
        raise TextTransformError("output public recipient SHA-256 mismatch")
    return {
        "schema": TEXT_TRANSFORM_MANIFEST_SCHEMA,
        "task_key": task_key,
        "workflow_type": workflow_type,
        "transform_kind": transform_kind,
        "prompt_version": str(manifest.get("prompt_version") or DEFAULT_PROMPT_VERSION),
        "privacy_policy": privacy_policy,
        "external_upload_authorization": str(manifest.get("external_upload_authorization") or ""),
        "instructions": {
            "goal": goal,
            "files": normalized_files,
            "bundle_sha256": bundle_sha,
        },
        "identity_bindings": manifest.get("identity_bindings") if isinstance(manifest.get("identity_bindings"), dict) else {},
        "input": {
            "logical_id": logical_id,
            "encrypted_payload_path": encrypted_rel,
            "ciphertext_sha256": ciphertext_sha,
            "plaintext_sha256": plaintext_sha,
            "plaintext_size_bytes": size_bytes,
            "mime_type": mime_type,
            "source_basename": str(input_item.get("source_basename") or ""),
        },
        "output": {
            "public_recipient_path": recipient_rel,
            "public_recipient": recipient,
            "public_recipient_sha256": recipient_sha,
        },
    }


def manifest_identity(manifest: dict[str, Any]) -> str:
    identity_payload = {
        "schema": manifest.get("schema"),
        "task_key": manifest.get("task_key"),
        "workflow_type": manifest.get("workflow_type"),
        "transform_kind": manifest.get("transform_kind"),
        "prompt_version": manifest.get("prompt_version"),
        "privacy_policy": manifest.get("privacy_policy"),
        "instructions": manifest.get("instructions"),
        "identity_bindings": manifest.get("identity_bindings"),
        "input": {
            "logical_id": manifest.get("input", {}).get("logical_id"),
            "encrypted_payload_path": manifest.get("input", {}).get("encrypted_payload_path"),
            "ciphertext_sha256": manifest.get("input", {}).get("ciphertext_sha256"),
            "plaintext_sha256": manifest.get("input", {}).get("plaintext_sha256"),
            "plaintext_size_bytes": manifest.get("input", {}).get("plaintext_size_bytes"),
            "mime_type": manifest.get("input", {}).get("mime_type"),
        },
        "output": {
            "public_recipient_path": manifest.get("output", {}).get("public_recipient_path"),
            "public_recipient_sha256": manifest.get("output", {}).get("public_recipient_sha256"),
        },
    }
    return sha256_text(canonical_json(identity_payload))


def build_prompt(target: Path, manifest: dict[str, Any]) -> str:
    sections = [
        "You are producing a private text transform for AI Bridge Kit.",
        "Transform the complete supplied plaintext artifact according to the public instruction bundle.",
        "Return only the transformed plaintext artifact. Do not return JSON, commentary, markdown fences, analysis, or a summary unless the instructions explicitly require that as the artifact format.",
        "Do not reveal chain-of-thought.",
        f"Workflow: {manifest['workflow_type']}",
        f"Task: {manifest['task_key']}",
        f"Transform kind: {manifest['transform_kind']}",
        "Privacy statement: plaintext is decrypted in this ephemeral runner and sent to OpenAI Responses API with store=false under the recorded authorization.",
        "Input identity:",
        canonical_json(
            {
                "logical_id": manifest["input"]["logical_id"],
                "plaintext_sha256": manifest["input"]["plaintext_sha256"],
                "plaintext_size_bytes": manifest["input"]["plaintext_size_bytes"],
                "mime_type": manifest["input"]["mime_type"],
                "instruction_bundle_sha256": manifest["instructions"]["bundle_sha256"],
            }
        ),
        "Transform goal:",
        manifest["instructions"]["goal"],
        "Instruction files:",
    ]
    for item in manifest["instructions"]["files"]:
        path = target / item["path"]
        sections.extend(
            [
                f"--- BEGIN INSTRUCTION {item['path']} sha256={item['sha256']} ---",
                path.read_text(encoding="utf-8"),
                f"--- END INSTRUCTION {item['path']} ---",
            ]
        )
    return "\n".join(sections)


def build_responses_request(target: Path, manifest: dict[str, Any], plaintext: str, *, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": build_prompt(target, manifest)},
                    {"type": "input_text", "text": plaintext},
                ],
            }
        ],
    }


def call_openai_responses(
    request_payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float = 60.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    try:
        return text_review.call_openai_responses(request_payload, api_key=api_key, timeout=timeout, opener=opener)
    except text_review.TextReviewError as exc:
        raise TextTransformError(str(exc).replace("text review", "text transform")) from exc


def _extract_response_text(response_payload: dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    try:
        return visual_review.extract_response_text(response_payload)
    except visual_review.VisualReviewError as exc:
        raise TextTransformError(str(exc).replace("visual review", "text transform")) from exc


def assemble_text_transform_result(
    *,
    target: Path,
    manifest: dict[str, Any],
    output_age_rel: str,
    output_plaintext: str,
    output_age_path: Path,
    model: str,
    bridge_kit_commit: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    output_bytes = output_plaintext.encode("utf-8")
    identity = manifest_identity(manifest)
    return {
        "schema": TEXT_TRANSFORM_RESULT_SCHEMA,
        "evidence_id": f"text-transform-{manifest['task_key']}-{identity[:12]}",
        "task_key": manifest["task_key"],
        "workflow_type": manifest["workflow_type"],
        "transform_kind": manifest["transform_kind"],
        "model": model,
        "prompt_version": manifest["prompt_version"],
        "created_at": created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "store": False,
        "input_manifest": {
            "schema": manifest["schema"],
            "privacy_policy": manifest["privacy_policy"],
            "external_upload_authorization_recorded": bool(manifest["external_upload_authorization"]),
            "instructions": manifest["instructions"],
            "identity_bindings": manifest["identity_bindings"],
            "manifest_sha256": identity,
        },
        "encrypted_input": {
            "path": manifest["input"]["encrypted_payload_path"],
            "sha256": manifest["input"]["ciphertext_sha256"],
        },
        "source_plaintext_sha256": manifest["input"]["plaintext_sha256"],
        "source_plaintext_size_bytes": manifest["input"]["plaintext_size_bytes"],
        "output_public_recipient": {
            "path": manifest["output"]["public_recipient_path"],
            "sha256": manifest["output"]["public_recipient_sha256"],
        },
        "encrypted_output": {
            "path": output_age_rel,
            "sha256": file_sha256(output_age_path),
        },
        "output_plaintext_sha256": sha256_bytes(output_bytes),
        "output_plaintext_size_bytes": len(output_bytes),
        "transform_identity": identity,
        "bridge_kit_commit": bridge_kit_commit or git_current_commit(kit_root()) or "",
        "plaintext_committed": False,
    }


def validate_text_transform_result(payload: dict[str, Any], *, expected: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    expected = expected or {}
    if payload.get("schema") != TEXT_TRANSFORM_RESULT_SCHEMA:
        errors.append("TEXT_TRANSFORM.json schema mismatch")
    for key in [
        "evidence_id",
        "task_key",
        "workflow_type",
        "transform_kind",
        "model",
        "prompt_version",
        "created_at",
        "store",
        "input_manifest",
        "encrypted_input",
        "source_plaintext_sha256",
        "source_plaintext_size_bytes",
        "output_public_recipient",
        "encrypted_output",
        "output_plaintext_sha256",
        "output_plaintext_size_bytes",
        "transform_identity",
        "plaintext_committed",
    ]:
        if key not in payload:
            errors.append(f"TEXT_TRANSFORM.json missing {key}")
    if payload.get("workflow_type") not in WORKFLOW_TYPES:
        errors.append("TEXT_TRANSFORM.json workflow_type invalid")
    if payload.get("store") is not False:
        errors.append("TEXT_TRANSFORM.json store must be false")
    if payload.get("plaintext_committed") is not False:
        errors.append("TEXT_TRANSFORM.json plaintext_committed must be false")
    for key in ["source_plaintext_sha256", "output_plaintext_sha256"]:
        if not re.fullmatch(r"[0-9a-f]{64}", str(payload.get(key) or "")):
            errors.append(f"TEXT_TRANSFORM.json {key} invalid")
    if not isinstance(payload.get("source_plaintext_size_bytes"), int) or payload.get("source_plaintext_size_bytes", -1) < 0:
        errors.append("TEXT_TRANSFORM.json source_plaintext_size_bytes invalid")
    if not isinstance(payload.get("output_plaintext_size_bytes"), int) or payload.get("output_plaintext_size_bytes", -1) <= 0:
        errors.append("TEXT_TRANSFORM.json output_plaintext_size_bytes invalid")
    input_manifest = payload.get("input_manifest")
    if not isinstance(input_manifest, dict):
        errors.append("TEXT_TRANSFORM.json input_manifest must be an object")
        input_manifest = {}
    for key in ["encrypted_input", "encrypted_output", "output_public_recipient"]:
        item = payload.get(key)
        if not isinstance(item, dict):
            errors.append(f"TEXT_TRANSFORM.json {key} must be an object")
            continue
        if not item.get("path") or not item.get("sha256"):
            errors.append(f"TEXT_TRANSFORM.json {key} missing path or sha256")
    if input_manifest.get("manifest_sha256") != payload.get("transform_identity"):
        errors.append("TEXT_TRANSFORM.json transform_identity must match input manifest sha")
    for key, value in expected.items():
        if key in {"manifest_identity", "source_plaintext_sha256", "output_plaintext_sha256", "output_plaintext_size_bytes"}:
            continue
        bindings = input_manifest.get("identity_bindings") if isinstance(input_manifest.get("identity_bindings"), dict) else {}
        if payload.get(key) != value and bindings.get(key) != value:
            errors.append(f"TEXT_TRANSFORM.json identity binding mismatch: {key}")
    if "manifest_identity" in expected and payload.get("transform_identity") != expected["manifest_identity"]:
        errors.append("TEXT_TRANSFORM.json transform_identity is stale against current manifest")
    if "source_plaintext_sha256" in expected and payload.get("source_plaintext_sha256") != expected["source_plaintext_sha256"]:
        errors.append("TEXT_TRANSFORM.json source_plaintext_sha256 mismatch")
    if "output_plaintext_sha256" in expected and payload.get("output_plaintext_sha256") != expected["output_plaintext_sha256"]:
        errors.append("TEXT_TRANSFORM.json output_plaintext_sha256 mismatch")
    if "output_plaintext_size_bytes" in expected and payload.get("output_plaintext_size_bytes") != expected["output_plaintext_size_bytes"]:
        errors.append("TEXT_TRANSFORM.json output_plaintext_size_bytes mismatch")
    return errors


def run_text_transform(
    target: Path,
    manifest_path: Path,
    plaintext_path: Path,
    output_age_path: Path,
    result_path: Path,
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 120.0,
    opener: Callable[..., Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    target = target.resolve()
    manifest = normalize_manifest(target, load_json(manifest_path))
    output_age_rel = validate_encrypted_payload_path(output_age_path)
    result_rel = validate_result_path(result_path)
    absolute_output_age = target / output_age_rel
    absolute_result = target / result_rel
    if absolute_output_age.exists() and not force:
        raise TextTransformError(f"encrypted output already exists: {output_age_rel}")
    if absolute_result.exists() and not force:
        raise TextTransformError(f"text transform result already exists: {result_rel}")
    plaintext, plaintext_bytes = _require_utf8_text(plaintext_path)
    plaintext_sha = sha256_bytes(plaintext_bytes)
    if plaintext_sha != manifest["input"]["plaintext_sha256"]:
        raise TextTransformError("plaintext SHA-256 does not match text transform manifest")
    selected_model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    selected_key = api_key if api_key is not None else (
        os.environ.get(OPENAI_TRANSFORM_KEY_ENV, "") or os.environ.get(LEGACY_OPENAI_KEY_ENV, "") or os.environ.get("OPENAI_API_KEY", "")
    )
    request_payload = build_responses_request(target, manifest, plaintext, model=selected_model)
    response_payload = call_openai_responses(request_payload, api_key=selected_key, timeout=timeout, opener=opener)
    output_plaintext = _extract_response_text(response_payload)
    if not output_plaintext.strip():
        raise TextTransformError("OpenAI text transform output was empty")
    with tempfile.TemporaryDirectory() as tmp:
        temp_output = Path(tmp) / "transformed.md"
        temp_output.write_text(output_plaintext, encoding="utf-8")
        encrypt_with_age(temp_output, absolute_output_age, recipient=manifest["output"]["public_recipient"], force=force)
    artifact = assemble_text_transform_result(
        target=target,
        manifest=manifest,
        output_age_rel=output_age_rel,
        output_plaintext=output_plaintext,
        output_age_path=absolute_output_age,
        model=selected_model,
    )
    errors = validate_text_transform_result(
        artifact,
        expected={
            "implementation_commit": manifest["identity_bindings"].get("implementation_commit"),
            "manifest_identity": manifest_identity(manifest),
            "source_plaintext_sha256": plaintext_sha,
            "output_plaintext_sha256": sha256_text(output_plaintext),
            "output_plaintext_size_bytes": len(output_plaintext.encode("utf-8")),
        },
    )
    if errors:
        absolute_output_age.unlink(missing_ok=True)
        raise TextTransformError("; ".join(errors))
    write_json(absolute_result, artifact)
    return artifact


def encrypt_text_transform_input(
    target: Path,
    *,
    task_key: str,
    input_path: Path,
    input_recipient_file: Path,
    output_path: Path,
    manifest_path: Path,
    output_recipient_file: Path,
    instruction_files: list[Path],
    goal: str,
    workflow_type: str = "reviewed_handoff",
    transform_kind: str = "text-transform",
    implementation_commit: str = "",
    privacy_policy: str = PRIVATE_TEXT_POLICY,
    external_upload_authorization: str = "",
    force: bool = False,
) -> dict[str, Any]:
    target = target.resolve()
    if workflow_type not in WORKFLOW_TYPES:
        raise TextTransformError(f"workflow_type must be one of {sorted(WORKFLOW_TYPES)}")
    input_rel = validate_encrypted_payload_path(output_path)
    manifest_rel = validate_manifest_path(manifest_path)
    output_recipient_rel = validate_recipient_path(output_recipient_file)
    plaintext, plaintext_bytes = _require_utf8_text(input_path)
    if not plaintext.strip():
        raise TextTransformError("text transform plaintext source is empty")
    if privacy_policy != PUBLIC_SAFE_POLICY and not external_upload_authorization.strip():
        raise TextTransformError("non-public text transform requires explicit external_upload_authorization")
    input_recipient = _read_recipient_file(input_recipient_file)
    output_recipient_path = target / output_recipient_rel
    output_recipient = _read_recipient_file(output_recipient_path)
    instructions, bundle_sha = normalize_instruction_files(target, instruction_files)
    encrypted_path = target / input_rel
    encrypt_with_age(input_path, encrypted_path, recipient=input_recipient, force=force)
    manifest = {
        "schema": TEXT_TRANSFORM_MANIFEST_SCHEMA,
        "task_key": task_key,
        "workflow_type": workflow_type,
        "transform_kind": transform_kind,
        "prompt_version": DEFAULT_PROMPT_VERSION,
        "privacy_policy": privacy_policy,
        "external_upload_authorization": external_upload_authorization,
        "instructions": {
            "goal": goal,
            "files": instructions,
            "bundle_sha256": bundle_sha,
        },
        "identity_bindings": {"implementation_commit": implementation_commit} if implementation_commit else {},
        "input": {
            "logical_id": "source_text",
            "encrypted_payload_path": input_rel,
            "ciphertext_sha256": file_sha256(encrypted_path),
            "plaintext_sha256": sha256_bytes(plaintext_bytes),
            "plaintext_size_bytes": len(plaintext_bytes),
            "mime_type": _logical_text_mime(input_path),
            "source_basename": input_path.name,
        },
        "output": {
            "public_recipient_path": output_recipient_rel,
            "public_recipient": output_recipient,
            "public_recipient_sha256": file_sha256(output_recipient_path),
        },
    }
    normalized = normalize_manifest(target, manifest)
    write_json(target / manifest_rel, normalized)
    return normalized


def decrypt_text_transform_output(
    target: Path,
    *,
    result_path: Path,
    identity_file: Path,
    output_path: Path,
    force: bool = False,
) -> None:
    target = target.resolve()
    result = load_json(result_path)
    errors = validate_text_transform_result(result)
    if errors:
        raise TextTransformError("; ".join(errors))
    encrypted = result.get("encrypted_output", {})
    rel = validate_encrypted_payload_path(str(encrypted.get("path") or ""))
    payload_path = target / rel
    expected_ciphertext_sha = encrypted.get("sha256")
    if expected_ciphertext_sha and file_sha256(payload_path) != expected_ciphertext_sha:
        raise TextTransformError("encrypted text transform output sha256 mismatch")
    decrypt_with_age(payload_path, output_path, identity_file=identity_file, force=force)
    _, data = _require_utf8_text(output_path)
    if sha256_bytes(data) != result["output_plaintext_sha256"]:
        output_path.unlink(missing_ok=True)
        raise TextTransformError("decrypted output plaintext SHA-256 does not match TEXT_TRANSFORM.json")


def git_current_commit(path: Path) -> str | None:
    return visual_review.git_current_commit(path)


def bridge_kit_pip_spec(ref: str | None = None) -> str:
    selected_ref = ref or git_current_commit(kit_root())
    if not selected_ref:
        raise TextTransformError("cannot determine Bridge Kit Git commit; pass --bridge-kit-ref explicitly")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", selected_ref):
        raise TextTransformError("Bridge Kit ref contains unsupported characters")
    return f"gpt-codex-ai-bridge-kit[text-transform] @ git+{CANONICAL_BRIDGE_KIT_REPO}@{selected_ref}"


def text_transform_writeback_needed(target: Path, output_age_path: Path | str, result_path: Path | str) -> bool:
    output_rel = validate_encrypted_payload_path(output_age_path)
    result_rel = validate_result_path(result_path)
    subprocess.check_call(["git", "add", "--", output_rel, result_rel], cwd=target)
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", output_rel, result_rel],
        cwd=target,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(result.returncode, ["git", "diff", "--cached", "--quiet", "--", output_rel, result_rel])
    return result.returncode == 1


def workflow_status(target: Path) -> dict[str, Any]:
    workflows = sorted((target / ".github" / "workflows").glob("*.yml")) + sorted((target / ".github" / "workflows").glob("*.yaml"))
    matches: list[str] = []
    for path in workflows:
        text = path.read_text(encoding="utf-8", errors="replace")
        if AGE_SECRET_NAME in text and "text-transform" in text:
            matches.append(path.resolve().relative_to(target.resolve()).as_posix())
    return {"status": "PRESENT" if matches else "MISSING", "paths": matches}


def preflight(target: Path, *, repo: str | None = None) -> dict[str, Any]:
    target = target.resolve()
    return {
        "schema": "AI_BRIDGE_TEXT_TRANSFORM_PREFLIGHT_V1",
        "target": str(target),
        "github_workflow": workflow_status(target),
        "age": {
            "age": "PRESENT" if shutil.which("age") else "MISSING",
            "age-keygen": "PRESENT" if shutil.which("age-keygen") else "MISSING",
        },
        "secret": {
            "expected_age_identity_secret": AGE_SECRET_NAME,
            "age_identity_metadata_status": text_review.gh_secret_metadata_status(target, AGE_SECRET_NAME, repo=repo),
            "preferred_openai_secret": OPENAI_TRANSFORM_KEY_ENV,
            "backward_compatible_openai_secret": LEGACY_OPENAI_KEY_ENV,
            "preferred_openai_metadata_status": text_review.gh_secret_metadata_status(target, OPENAI_TRANSFORM_KEY_ENV, repo=repo),
            "legacy_openai_metadata_status": text_review.gh_secret_metadata_status(target, LEGACY_OPENAI_KEY_ENV, repo=repo),
            "value_read": False,
        },
        "model_env": MODEL_ENV,
        "default_model": DEFAULT_MODEL,
        "openai_project_recommendation": "AI Bridge Text Transform",
    }


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def copy_file(src: Path, dst: Path, *, force: bool, actions: list[str]) -> None:
    visual_review.copy_file(src, dst, force=force, actions=actions)


def write_rendered_file(src: Path, dst: Path, replacements: dict[str, str], *, force: bool, actions: list[str]) -> None:
    visual_review.write_rendered_file(src, dst, replacements, force=force, actions=actions)


def install_text_transform(target: Path, *, force: bool = False, bridge_kit_ref: str | None = None) -> list[str]:
    target = target.resolve()
    source = kit_root() / "templates" / "text_transform"
    if not source.exists():
        raise TextTransformError("text transform templates are missing from the Bridge Kit installation")
    actions: list[str] = []
    pip_spec = bridge_kit_pip_spec(bridge_kit_ref)
    copy_file(source / "README.md", target / "docs" / "AI_BRIDGE_TEXT_TRANSFORM.md", force=force, actions=actions)
    write_rendered_file(
        source / "github-actions" / "text-transform.yml",
        target / ".github" / "workflows" / "ai-bridge-text-transform.yml",
        {"__AI_BRIDGE_KIT_PIP_SPEC__": pip_spec},
        force=force,
        actions=actions,
    )
    copy_file(source / "text_transform_inputs.template.json", target / "docs" / "text_transform_inputs.template.json", force=force, actions=actions)
    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge text-transform")
    sub = parser.add_subparsers(dest="command")
    install_cmd = sub.add_parser("install")
    install_cmd.add_argument("--target", type=Path, default=Path.cwd())
    install_cmd.add_argument("--force", action="store_true")
    install_cmd.add_argument("--bridge-kit-ref")
    preflight_cmd = sub.add_parser("preflight")
    preflight_cmd.add_argument("--target", type=Path, default=Path.cwd())
    preflight_cmd.add_argument("--repo")
    receiver_cmd = sub.add_parser("create-output-receiver")
    receiver_cmd.add_argument("--target", type=Path, default=Path.cwd())
    receiver_cmd.add_argument("--task-key", required=True)
    receiver_cmd.add_argument("--identity-output", type=Path)
    receiver_cmd.add_argument("--recipient-output", type=Path)
    receiver_cmd.add_argument("--force", action="store_true")
    encrypt_cmd = sub.add_parser("encrypt")
    encrypt_cmd.add_argument("--target", type=Path, default=Path.cwd())
    encrypt_cmd.add_argument("--task-key", required=True)
    encrypt_cmd.add_argument("--input", type=Path, required=True)
    encrypt_cmd.add_argument("--input-recipient-file", type=Path, default=Path(DEFAULT_INPUT_RECIPIENT_PATH))
    encrypt_cmd.add_argument("--output", type=Path, required=True)
    encrypt_cmd.add_argument("--manifest", type=Path, required=True)
    encrypt_cmd.add_argument("--output-recipient-file", type=Path, required=True)
    encrypt_cmd.add_argument("--instruction-file", type=Path, action="append", required=True)
    encrypt_cmd.add_argument("--goal", required=True)
    encrypt_cmd.add_argument("--workflow-type", default="reviewed_handoff")
    encrypt_cmd.add_argument("--transform-kind", default="text-transform")
    encrypt_cmd.add_argument("--implementation-commit", default="")
    encrypt_cmd.add_argument("--privacy-policy", default=PRIVATE_TEXT_POLICY)
    encrypt_cmd.add_argument("--external-upload-authorization", default="")
    encrypt_cmd.add_argument("--force", action="store_true")
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--target", type=Path, default=Path.cwd())
    run_cmd.add_argument("--manifest", type=Path, required=True)
    run_cmd.add_argument("--plaintext", type=Path, required=True)
    run_cmd.add_argument("--output-age", type=Path, required=True)
    run_cmd.add_argument("--result", type=Path, required=True)
    run_cmd.add_argument("--model")
    run_cmd.add_argument("--timeout", type=float, default=120.0)
    run_cmd.add_argument("--force", action="store_true")
    decrypt_cmd = sub.add_parser("decrypt")
    decrypt_cmd.add_argument("--target", type=Path, default=Path.cwd())
    decrypt_cmd.add_argument("--result", type=Path, required=True)
    decrypt_cmd.add_argument("--identity-file", type=Path, required=True)
    decrypt_cmd.add_argument("--output", type=Path, required=True)
    decrypt_cmd.add_argument("--force", action="store_true")
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--path", type=Path, required=True)
    writeback_cmd = sub.add_parser("writeback-needed")
    writeback_cmd.add_argument("--target", type=Path, default=Path.cwd())
    writeback_cmd.add_argument("--output-age", type=Path, required=True)
    writeback_cmd.add_argument("--result", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "install":
        try:
            actions = install_text_transform(args.target, force=args.force, bridge_kit_ref=args.bridge_kit_ref)
        except TextTransformError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for action in actions:
            print(action)
        return 0
    if args.command == "preflight":
        print(canonical_json(preflight(args.target, repo=args.repo), pretty=True), end="")
        return 0
    if args.command == "create-output-receiver":
        try:
            result = create_output_receiver(
                args.target,
                task_key=args.task_key,
                identity_path=args.identity_output,
                recipient_path=args.recipient_output,
                force=args.force,
            )
        except TextTransformError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(canonical_json(result, pretty=True), end="")
        return 0
    if args.command == "encrypt":
        try:
            manifest = encrypt_text_transform_input(
                args.target,
                task_key=args.task_key,
                input_path=args.input,
                input_recipient_file=args.target / args.input_recipient_file if not args.input_recipient_file.is_absolute() else args.input_recipient_file,
                output_path=args.output,
                manifest_path=args.manifest,
                output_recipient_file=args.output_recipient_file,
                instruction_files=args.instruction_file,
                goal=args.goal,
                workflow_type=args.workflow_type,
                transform_kind=args.transform_kind,
                implementation_commit=args.implementation_commit,
                privacy_policy=args.privacy_policy,
                external_upload_authorization=args.external_upload_authorization,
                force=args.force,
            )
        except TextTransformError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(canonical_json(manifest, pretty=True), end="")
        return 0
    if args.command == "run":
        try:
            artifact = run_text_transform(
                args.target,
                args.manifest,
                args.plaintext,
                args.output_age,
                args.result,
                model=args.model,
                timeout=args.timeout,
                force=args.force,
            )
        except TextTransformError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(canonical_json(artifact, pretty=True), end="")
        return 0
    if args.command == "decrypt":
        try:
            decrypt_text_transform_output(
                args.target,
                result_path=args.result,
                identity_file=args.identity_file,
                output_path=args.output,
                force=args.force,
            )
        except TextTransformError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Decrypted text transform output to {args.output}")
        return 0
    if args.command == "validate":
        errors = validate_text_transform_result(load_json(args.path))
        if errors:
            for error in errors:
                print(f"ERROR {error}")
            return 1
        print("Text Transform validation passed.")
        return 0
    if args.command == "writeback-needed":
        try:
            needed = text_transform_writeback_needed(args.target, args.output_age, args.result)
        except (TextTransformError, subprocess.CalledProcessError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if needed:
            print("Text transform evidence changes staged.")
            return 1
        print("No text transform evidence changes.")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
