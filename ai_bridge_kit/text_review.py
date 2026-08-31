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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from . import visual_review


TEXT_INPUT_MANIFEST_SCHEMA = "AI_BRIDGE_TEXT_INPUT_MANIFEST_V1"
TEXT_REVIEW_SCHEMA = "AI_BRIDGE_TEXT_REVIEW_V1"
AGE_SECRET_NAME = "AI_BRIDGE_PRIVATE_REVIEW_AGE_KEY"
OPENAI_REVIEW_KEY_ENV = "OPENAI_REVIEW_API_KEY"
LEGACY_OPENAI_KEY_ENV = visual_review.SECRET_NAME
MODEL_ENV = "OPENAI_TEXT_REVIEW_MODEL"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_PROMPT_VERSION = "ai-bridge.text-review.v1"
PRIVATE_TEXT_POLICY = "PRIVATE_TEXT_REVIEW_AUTHORIZED"
PUBLIC_SAFE_POLICY = visual_review.DEFAULT_PRIVACY_POLICY
DECISIONS = visual_review.DECISIONS
WORKFLOW_TYPES = visual_review.WORKFLOW_TYPES
API_URL = visual_review.API_URL
CANONICAL_BRIDGE_KIT_REPO = visual_review.CANONICAL_BRIDGE_KIT_REPO
DEFAULT_RECIPIENT_PATH = "automation/reviewed_handoff/private_text_review.age.pub"


class TextReviewError(ValueError):
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
        raise TextReviewError(str(exc)) from exc


def validate_generated_text_review_path(path: Path | str) -> str:
    rel = repository_relative_path(path)
    if not re.fullmatch(r"results/[^/]+/text_review/.+", rel):
        raise TextReviewError("text review write-back path must be under results/<task_key>/text_review/")
    if rel.endswith("/"):
        raise TextReviewError("text review write-back path must be a file path")
    blocked_names = {
        "CURRENT.json",
        "PLAN.md",
        "REQUEST.md",
        "RESULT.md",
        "FINAL_REPORT.md",
    }
    if Path(rel).name in blocked_names:
        raise TextReviewError("text review output must be generated evidence, not workflow control files")
    blocked_parts = {".github", "src", "automation"}
    if blocked_parts.intersection(Path(rel).parts):
        raise TextReviewError("text review output must not target source, automation, or workflow paths")
    return rel


def validate_text_output_path(target: Path, task_key: str, output_path: Path | str) -> Path:
    rel = validate_generated_text_review_path(output_path)
    expected_prefix = f"results/{task_key}/text_review/"
    if not rel.startswith(expected_prefix):
        raise TextReviewError(f"text review output must be under {expected_prefix}")
    return target.resolve() / rel


def validate_text_manifest_path(path: Path | str) -> str:
    rel = validate_generated_text_review_path(path)
    if not rel.endswith(".json"):
        raise TextReviewError("text review manifest path must be a JSON file")
    return rel


def validate_encrypted_payload_path(path: Path | str) -> str:
    rel = validate_generated_text_review_path(path)
    if not rel.endswith(".age"):
        raise TextReviewError("encrypted text review payload must use a .age path")
    return rel


def _require_utf8_text(path: Path) -> tuple[str, bytes]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TextReviewError("text review supports UTF-8 Markdown/plain text only") from exc
    return text, data


def _logical_text_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".mdown"}:
        return "text/markdown; charset=utf-8"
    if suffix in {".txt", ".text"}:
        return "text/plain; charset=utf-8"
    raise TextReviewError("text review supports UTF-8 Markdown/plain text only")


def _age_binary() -> str:
    binary = shutil.which("age")
    if not binary:
        raise TextReviewError("age executable is required for private text review transport")
    return binary


def _age_keygen_binary() -> str:
    binary = shutil.which("age-keygen")
    if not binary:
        raise TextReviewError("age-keygen executable is required to configure private text review transport")
    return binary


def _run_age(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise TextReviewError("age executable is required for private text review transport") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        message = detail[-1] if detail else "age command failed"
        raise TextReviewError(f"age transport failed closed: {message}")
    return result


def encrypt_with_age(input_path: Path, output_path: Path, *, recipient: str, force: bool = False) -> None:
    if not recipient.startswith("age1"):
        raise TextReviewError("age public recipient must start with age1")
    if output_path.exists() and not force:
        raise TextReviewError(f"encrypted payload already exists: {output_path}")
    if output_path.exists() and force:
        output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run_age([_age_binary(), "-r", recipient, "-o", str(output_path), str(input_path)])


def decrypt_with_age(payload_path: Path, output_path: Path, *, identity_file: Path, force: bool = False) -> None:
    if output_path.exists() and not force:
        raise TextReviewError(f"plaintext output already exists: {output_path}")
    if output_path.exists() and force:
        output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run_age([_age_binary(), "-d", "-i", str(identity_file), "-o", str(output_path), str(payload_path)])


def text_review_response_schema() -> dict[str, Any]:
    finding_schema = {
        "type": "object",
        "properties": {
            "finding_id": {"type": "string"},
            "requirement_id": {"type": "string"},
            "severity": {"type": "string", "enum": ["blocking", "non_blocking"]},
            "summary": {"type": "string"},
            "evidence": {"type": "string"},
            "recommendation": {"type": "string"},
        },
        "required": ["finding_id", "requirement_id", "severity", "summary", "evidence", "recommendation"],
        "additionalProperties": False,
    }
    item_schema = {
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "decision": {"type": "string", "enum": sorted(DECISIONS)},
            "summary": {"type": "string"},
            "requirement_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["item_id", "decision", "summary", "requirement_ids"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "overall_decision": {"type": "string", "enum": sorted(DECISIONS)},
            "item_reviews": {"type": "array", "items": item_schema},
            "blocking_findings": {"type": "array", "items": finding_schema},
            "non_blocking_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["overall_decision", "item_reviews", "blocking_findings", "non_blocking_notes"],
        "additionalProperties": False,
    }


def normalize_manifest(target: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema") != TEXT_INPUT_MANIFEST_SCHEMA:
        raise TextReviewError(f"text input manifest schema must be {TEXT_INPUT_MANIFEST_SCHEMA}")
    workflow_type = manifest.get("workflow_type")
    if workflow_type not in WORKFLOW_TYPES:
        raise TextReviewError(f"text input manifest workflow_type must be one of {sorted(WORKFLOW_TYPES)}")
    task_key = str(manifest.get("task_key") or "").strip()
    if not task_key:
        raise TextReviewError("text input manifest task_key is required")
    review_kind = str(manifest.get("review_kind") or "").strip()
    if not review_kind:
        raise TextReviewError("text input manifest review_kind is required")
    privacy_policy = str(manifest.get("privacy_policy") or PRIVATE_TEXT_POLICY)
    if privacy_policy != PUBLIC_SAFE_POLICY and not str(manifest.get("external_upload_authorization") or "").strip():
        raise TextReviewError("non-public text review requires explicit external_upload_authorization")
    rubric = manifest.get("rubric") if isinstance(manifest.get("rubric"), dict) else {}
    if not str(rubric.get("instructions") or "").strip():
        raise TextReviewError("text input manifest rubric.instructions is required")
    input_item = manifest.get("input")
    if not isinstance(input_item, dict):
        raise TextReviewError("text input manifest requires input object")
    logical_id = str(input_item.get("logical_id") or "").strip()
    if not logical_id:
        raise TextReviewError("text input manifest input.logical_id is required")
    encrypted_rel = str(input_item.get("encrypted_payload_path") or input_item.get("path") or "").strip()
    if not encrypted_rel:
        raise TextReviewError("text input manifest input.encrypted_payload_path is required")
    encrypted_rel = validate_encrypted_payload_path(encrypted_rel)
    encrypted_path = target.resolve() / encrypted_rel
    if not encrypted_path.exists() or not encrypted_path.is_file():
        raise TextReviewError(f"encrypted text review payload missing: {encrypted_rel}")
    ciphertext_sha = file_sha256(encrypted_path)
    expected_ciphertext_sha = str(input_item.get("ciphertext_sha256") or "").strip()
    if expected_ciphertext_sha and expected_ciphertext_sha != ciphertext_sha:
        raise TextReviewError("encrypted text review payload sha256 mismatch")
    plaintext_sha = str(input_item.get("plaintext_sha256") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", plaintext_sha):
        raise TextReviewError("text input manifest input.plaintext_sha256 must be a SHA-256 hex digest")
    size_bytes = input_item.get("plaintext_size_bytes")
    if not isinstance(size_bytes, int) or size_bytes < 0:
        raise TextReviewError("text input manifest input.plaintext_size_bytes must be a non-negative integer")
    mime_type = str(input_item.get("mime_type") or "text/markdown; charset=utf-8")
    if mime_type not in {"text/markdown; charset=utf-8", "text/plain; charset=utf-8"}:
        raise TextReviewError("text input manifest input.mime_type must be UTF-8 Markdown/plain text")
    return {
        "schema": TEXT_INPUT_MANIFEST_SCHEMA,
        "task_key": task_key,
        "workflow_type": workflow_type,
        "review_kind": review_kind,
        "prompt_version": str(manifest.get("prompt_version") or DEFAULT_PROMPT_VERSION),
        "privacy_policy": privacy_policy,
        "external_upload_authorization": str(manifest.get("external_upload_authorization") or ""),
        "rubric": rubric,
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
    }


def manifest_identity(manifest: dict[str, Any]) -> str:
    identity_payload = {
        "schema": manifest.get("schema"),
        "task_key": manifest.get("task_key"),
        "workflow_type": manifest.get("workflow_type"),
        "review_kind": manifest.get("review_kind"),
        "prompt_version": manifest.get("prompt_version"),
        "privacy_policy": manifest.get("privacy_policy"),
        "rubric": manifest.get("rubric"),
        "identity_bindings": manifest.get("identity_bindings"),
        "input": {
            "logical_id": manifest.get("input", {}).get("logical_id"),
            "encrypted_payload_path": manifest.get("input", {}).get("encrypted_payload_path"),
            "ciphertext_sha256": manifest.get("input", {}).get("ciphertext_sha256"),
            "plaintext_sha256": manifest.get("input", {}).get("plaintext_sha256"),
            "plaintext_size_bytes": manifest.get("input", {}).get("plaintext_size_bytes"),
            "mime_type": manifest.get("input", {}).get("mime_type"),
        },
    }
    return sha256_text(canonical_json(identity_payload))


def build_prompt(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are producing text review evidence for AI Bridge Kit.",
            "Read the complete supplied plaintext artifact. Do not infer PASS from summaries, file names, hashes, or metadata.",
            "Do not reveal chain-of-thought. Return concise observable findings only.",
            "Do not quote long passages from the private input; cite short local evidence snippets only when needed.",
            f"Workflow: {manifest['workflow_type']}",
            f"Task: {manifest['task_key']}",
            f"Review kind: {manifest['review_kind']}",
            "Rubric:",
            str(manifest["rubric"].get("instructions") or ""),
            "Input identity:",
            canonical_json(
                {
                    "logical_id": manifest["input"]["logical_id"],
                    "plaintext_sha256": manifest["input"]["plaintext_sha256"],
                    "plaintext_size_bytes": manifest["input"]["plaintext_size_bytes"],
                    "mime_type": manifest["input"]["mime_type"],
                }
            ),
        ]
    )


def build_responses_request(manifest: dict[str, Any], plaintext: str, *, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": build_prompt(manifest)},
                    {"type": "input_text", "text": plaintext},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "text_review",
                "strict": True,
                "schema": text_review_response_schema(),
            }
        },
    }


def call_openai_responses(
    request_payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float = 60.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise TextReviewError(f"{OPENAI_REVIEW_KEY_ENV} or {LEGACY_OPENAI_KEY_ENV} is not available")
    body = canonical_json(request_payload).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    urlopen = urllib.request.urlopen if opener is None else opener
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = getattr(exc, "code", "UNKNOWN")
        raise TextReviewError(f"OpenAI text review API failed closed: HTTP {status}") from exc
    except Exception as exc:
        raise TextReviewError(f"OpenAI text review API failed closed: {exc.__class__.__name__}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise TextReviewError("OpenAI text review API returned malformed JSON") from exc
    status = payload.get("status")
    if status and status != "completed":
        raise TextReviewError(f"OpenAI text review API did not complete: {status}")
    return payload


def _extract_response_text(response_payload: dict[str, Any]) -> str:
    try:
        return visual_review.extract_response_text(response_payload)
    except visual_review.VisualReviewError as exc:
        raise TextReviewError(str(exc).replace("visual review", "text review")) from exc


def assemble_text_review(
    *,
    manifest: dict[str, Any],
    model_output: dict[str, Any],
    model: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    for key in ["overall_decision", "item_reviews", "blocking_findings", "non_blocking_notes"]:
        if key not in model_output:
            raise TextReviewError(f"model text review missing {key}")
    decision = model_output.get("overall_decision")
    if decision not in DECISIONS:
        raise TextReviewError("model text review overall_decision is invalid")
    for key in ["item_reviews", "blocking_findings", "non_blocking_notes"]:
        if not isinstance(model_output.get(key), list):
            raise TextReviewError(f"model text review {key} must be a list")
    identity = manifest_identity(manifest)
    input_item = manifest["input"]
    return {
        "schema": TEXT_REVIEW_SCHEMA,
        "evidence_id": f"text-review-{manifest['task_key']}-{identity[:12]}",
        "task_key": manifest["task_key"],
        "workflow_type": manifest["workflow_type"],
        "review_kind": manifest["review_kind"],
        "model": model,
        "review_model": model,
        "prompt_version": manifest["prompt_version"],
        "created_at": created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_manifest": {
            "schema": manifest["schema"],
            "privacy_policy": manifest["privacy_policy"],
            "rubric": manifest["rubric"],
            "identity_bindings": manifest["identity_bindings"],
            "manifest_sha256": identity,
        },
        "encrypted_payload": {
            "path": input_item["encrypted_payload_path"],
            "sha256": input_item["ciphertext_sha256"],
        },
        "plaintext_artifact_sha256": input_item["plaintext_sha256"],
        "reviewed_input_identity": identity,
        "review_identity": identity,
        "overall_decision": decision,
        "status": decision,
        "item_reviews": model_output.get("item_reviews", []),
        "blocking_findings": model_output.get("blocking_findings", []),
        "non_blocking_notes": model_output.get("non_blocking_notes", []),
    }


def validate_text_review_payload(payload: dict[str, Any], *, expected: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    expected = expected or {}
    if payload.get("schema") != TEXT_REVIEW_SCHEMA:
        errors.append("TEXT_REVIEW.json schema mismatch")
    for key in [
        "evidence_id",
        "task_key",
        "workflow_type",
        "review_kind",
        "model",
        "prompt_version",
        "created_at",
        "input_manifest",
        "encrypted_payload",
        "plaintext_artifact_sha256",
        "reviewed_input_identity",
        "overall_decision",
        "status",
        "item_reviews",
        "blocking_findings",
        "non_blocking_notes",
    ]:
        if key not in payload:
            errors.append(f"TEXT_REVIEW.json missing {key}")
    if payload.get("overall_decision") not in DECISIONS:
        errors.append("TEXT_REVIEW.json overall_decision invalid")
    if payload.get("status") != payload.get("overall_decision"):
        errors.append("TEXT_REVIEW.json status must equal overall_decision")
    if payload.get("workflow_type") not in WORKFLOW_TYPES:
        errors.append("TEXT_REVIEW.json workflow_type invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("plaintext_artifact_sha256") or "")):
        errors.append("TEXT_REVIEW.json plaintext_artifact_sha256 invalid")
    input_manifest = payload.get("input_manifest")
    if not isinstance(input_manifest, dict):
        errors.append("TEXT_REVIEW.json input_manifest must be an object")
        input_manifest = {}
    bindings = input_manifest.get("identity_bindings")
    if not isinstance(bindings, dict):
        errors.append("TEXT_REVIEW.json identity_bindings must be an object")
        bindings = {}
    for key, value in expected.items():
        if key in {"plaintext_sha256", "manifest_identity", "logical_id", "plaintext_size_bytes", "mime_type"}:
            continue
        if payload.get(key) != value and bindings.get(key) != value:
            errors.append(f"TEXT_REVIEW.json identity binding mismatch: {key}")
    encrypted_payload = payload.get("encrypted_payload")
    if not isinstance(encrypted_payload, dict):
        errors.append("TEXT_REVIEW.json encrypted_payload must be an object")
        encrypted_payload = {}
    reconstructed = {
        "schema": input_manifest.get("schema"),
        "task_key": payload.get("task_key"),
        "workflow_type": payload.get("workflow_type"),
        "review_kind": payload.get("review_kind"),
        "prompt_version": payload.get("prompt_version"),
        "privacy_policy": input_manifest.get("privacy_policy"),
        "rubric": input_manifest.get("rubric"),
        "identity_bindings": bindings,
        "input": {
            "logical_id": expected.get("logical_id") or payload.get("review_kind"),
            "encrypted_payload_path": encrypted_payload.get("path"),
            "ciphertext_sha256": encrypted_payload.get("sha256"),
            "plaintext_sha256": payload.get("plaintext_artifact_sha256"),
            "plaintext_size_bytes": expected.get("plaintext_size_bytes"),
            "mime_type": expected.get("mime_type"),
        },
    }
    manifest_sha = input_manifest.get("manifest_sha256")
    if manifest_sha != payload.get("reviewed_input_identity"):
        errors.append("TEXT_REVIEW.json reviewed_input_identity must match input manifest sha")
    if payload.get("review_identity") and payload.get("review_identity") != payload.get("reviewed_input_identity"):
        errors.append("TEXT_REVIEW.json review_identity must match reviewed_input_identity")
    if "manifest_identity" in expected and payload.get("reviewed_input_identity") != expected["manifest_identity"]:
        errors.append("TEXT_REVIEW.json reviewed_input_identity is stale against current manifest")
    else:
        if all(reconstructed["input"].get(key) is not None for key in ["logical_id", "plaintext_size_bytes", "mime_type"]):
            if manifest_identity(reconstructed) != payload.get("reviewed_input_identity"):
                errors.append("TEXT_REVIEW.json reviewed_input_identity is stale against plaintext or manifest content")
    for key in ["item_reviews", "blocking_findings", "non_blocking_notes"]:
        if not isinstance(payload.get(key), list):
            errors.append(f"TEXT_REVIEW.json {key} must be a list")
    if payload.get("overall_decision") == "PASS" and payload.get("blocking_findings"):
        errors.append("TEXT_REVIEW.json PASS cannot contain blocking_findings")
    if "plaintext_sha256" in expected and payload.get("plaintext_artifact_sha256") != expected["plaintext_sha256"]:
        errors.append("TEXT_REVIEW.json plaintext_artifact_sha256 mismatch")
    return errors


def run_text_review(
    target: Path,
    manifest_path: Path,
    plaintext_path: Path,
    output_path: Path,
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    target = target.resolve()
    manifest = normalize_manifest(target, load_json(manifest_path))
    output_file = validate_text_output_path(target, str(manifest["task_key"]), output_path)
    plaintext, plaintext_bytes = _require_utf8_text(plaintext_path)
    plaintext_sha = sha256_bytes(plaintext_bytes)
    if plaintext_sha != manifest["input"]["plaintext_sha256"]:
        raise TextReviewError("plaintext SHA-256 does not match text review manifest")
    selected_model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    selected_key = api_key if api_key is not None else (
        os.environ.get(OPENAI_REVIEW_KEY_ENV, "") or os.environ.get(LEGACY_OPENAI_KEY_ENV, "") or os.environ.get("OPENAI_API_KEY", "")
    )
    request_payload = build_responses_request(manifest, plaintext, model=selected_model)
    response_payload = call_openai_responses(request_payload, api_key=selected_key, timeout=timeout, opener=opener)
    try:
        model_output = json.loads(_extract_response_text(response_payload))
    except json.JSONDecodeError as exc:
        raise TextReviewError("OpenAI text review output was not valid JSON") from exc
    artifact = assemble_text_review(manifest=manifest, model_output=model_output, model=selected_model)
    errors = validate_text_review_payload(
        artifact,
        expected={
            "implementation_commit": manifest["identity_bindings"].get("implementation_commit"),
            "plaintext_sha256": plaintext_sha,
            "manifest_identity": manifest_identity(manifest),
            "logical_id": manifest["input"]["logical_id"],
            "plaintext_size_bytes": manifest["input"]["plaintext_size_bytes"],
            "mime_type": manifest["input"]["mime_type"],
        },
    )
    if errors:
        raise TextReviewError("; ".join(errors))
    write_json(output_file, artifact)
    return artifact


def encrypt_text_payload(
    target: Path,
    *,
    task_key: str,
    input_path: Path,
    recipient_file: Path,
    output_path: Path,
    manifest_path: Path,
    workflow_type: str = "reviewed_handoff",
    review_kind: str = "text-artifact",
    rubric: str,
    implementation_commit: str = "",
    privacy_policy: str = PRIVATE_TEXT_POLICY,
    external_upload_authorization: str = "",
    force: bool = False,
) -> dict[str, Any]:
    target = target.resolve()
    if workflow_type not in WORKFLOW_TYPES:
        raise TextReviewError(f"workflow_type must be one of {sorted(WORKFLOW_TYPES)}")
    output_rel = validate_encrypted_payload_path(output_path)
    manifest_rel = validate_text_manifest_path(manifest_path)
    plaintext, plaintext_bytes = _require_utf8_text(input_path)
    if not plaintext.strip():
        raise TextReviewError("text review plaintext artifact is empty")
    if privacy_policy != PUBLIC_SAFE_POLICY and not external_upload_authorization.strip():
        raise TextReviewError("non-public text review requires explicit external_upload_authorization")
    recipient_text = recipient_file.read_text(encoding="utf-8").strip()
    recipient = next((line.strip() for line in recipient_text.splitlines() if line.strip().startswith("age1")), "")
    if not recipient:
        raise TextReviewError("age public recipient file does not contain an age1 recipient")
    encrypted_path = target / output_rel
    encrypt_with_age(input_path, encrypted_path, recipient=recipient, force=force)
    manifest = {
        "schema": TEXT_INPUT_MANIFEST_SCHEMA,
        "task_key": task_key,
        "workflow_type": workflow_type,
        "review_kind": review_kind,
        "prompt_version": DEFAULT_PROMPT_VERSION,
        "privacy_policy": privacy_policy,
        "external_upload_authorization": external_upload_authorization,
        "rubric": {"instructions": rubric},
        "identity_bindings": {"implementation_commit": implementation_commit} if implementation_commit else {},
        "input": {
            "logical_id": "primary_text",
            "encrypted_payload_path": output_rel,
            "ciphertext_sha256": file_sha256(encrypted_path),
            "plaintext_sha256": sha256_bytes(plaintext_bytes),
            "plaintext_size_bytes": len(plaintext_bytes),
            "mime_type": _logical_text_mime(input_path),
            "source_basename": input_path.name,
        },
    }
    normalized = normalize_manifest(target, manifest)
    write_json(target / manifest_rel, normalized)
    return normalized


def git_current_commit(path: Path) -> str | None:
    return visual_review.git_current_commit(path)


def bridge_kit_pip_spec(ref: str | None = None) -> str:
    selected_ref = ref or git_current_commit(kit_root())
    if not selected_ref:
        raise TextReviewError("cannot determine Bridge Kit Git commit; pass --bridge-kit-ref explicitly")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", selected_ref):
        raise TextReviewError("Bridge Kit ref contains unsupported characters")
    return f"gpt-codex-ai-bridge-kit[text-review] @ git+{CANONICAL_BRIDGE_KIT_REPO}@{selected_ref}"


def text_evidence_commit_needed(target: Path, output_path: Path | str) -> bool:
    rel = validate_generated_text_review_path(output_path)
    subprocess.check_call(["git", "add", "--", rel], cwd=target)
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", rel],
        cwd=target,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(result.returncode, ["git", "diff", "--cached", "--quiet", "--", rel])
    return result.returncode == 1


def _gh_repo_slug(target: Path) -> str | None:
    return visual_review.gh_repo_slug(target)


def gh_secret_metadata_status(target: Path, secret_name: str, *, repo: str | None = None) -> dict[str, str]:
    selected_repo = repo or _gh_repo_slug(target)
    if not selected_repo:
        return {"status": "UNKNOWN", "reason": "repository slug unavailable"}
    try:
        result = subprocess.run(
            ["gh", "secret", "list", "--repo", selected_repo],
            cwd=target,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
    except FileNotFoundError:
        return {"status": "CANNOT_VERIFY", "reason": "gh CLI not installed"}
    except Exception as exc:
        return {"status": "CANNOT_VERIFY", "reason": exc.__class__.__name__}
    if result.returncode != 0:
        return {"status": "CANNOT_VERIFY", "reason": "gh secret list failed"}
    names = {line.split()[0] for line in result.stdout.splitlines() if line.strip()}
    return {"status": "PRESENT" if secret_name in names else "MISSING", "reason": "metadata only"}


def workflow_status(target: Path) -> dict[str, Any]:
    workflows = sorted((target / ".github" / "workflows").glob("*.yml")) + sorted((target / ".github" / "workflows").glob("*.yaml"))
    matches: list[str] = []
    for path in workflows:
        text = path.read_text(encoding="utf-8", errors="replace")
        if AGE_SECRET_NAME in text and "text-review" in text:
            matches.append(path.resolve().relative_to(target.resolve()).as_posix())
    return {"status": "PRESENT" if matches else "MISSING", "paths": matches}


def installed_text_review_status(target: Path) -> dict[str, Any]:
    reviewed_tasks = []
    reviewed_dir = target.resolve() / "automation" / "reviewed_handoff" / "tasks"
    if reviewed_dir.exists():
        for current_path in sorted(reviewed_dir.glob("*/CURRENT.json")):
            try:
                current = load_json(current_path)
            except Exception:
                continue
            if current.get("text_review_required"):
                reviewed_tasks.append(current_path.parent.name)
    recipient_path = target.resolve() / DEFAULT_RECIPIENT_PATH
    return {
        "enabled": bool(reviewed_tasks),
        "reviewed_handoff_tasks": reviewed_tasks,
        "age_recipient_path": DEFAULT_RECIPIENT_PATH,
        "age_recipient_present": recipient_path.exists(),
    }


def preflight(target: Path, *, repo: str | None = None) -> dict[str, Any]:
    target = target.resolve()
    return {
        "schema": "AI_BRIDGE_TEXT_REVIEW_PREFLIGHT_V1",
        "target": str(target),
        "text_review": installed_text_review_status(target),
        "github_workflow": workflow_status(target),
        "age": {
            "age": "PRESENT" if shutil.which("age") else "MISSING",
            "age-keygen": "PRESENT" if shutil.which("age-keygen") else "MISSING",
        },
        "secret": {
            "expected_age_identity_secret": AGE_SECRET_NAME,
            "age_identity_metadata_status": gh_secret_metadata_status(target, AGE_SECRET_NAME, repo=repo),
            "preferred_openai_secret": OPENAI_REVIEW_KEY_ENV,
            "backward_compatible_openai_secret": LEGACY_OPENAI_KEY_ENV,
            "preferred_openai_metadata_status": gh_secret_metadata_status(target, OPENAI_REVIEW_KEY_ENV, repo=repo),
            "legacy_openai_metadata_status": gh_secret_metadata_status(target, LEGACY_OPENAI_KEY_ENV, repo=repo),
            "value_read": False,
        },
        "model_env": MODEL_ENV,
        "default_model": DEFAULT_MODEL,
        "openai_project_recommendation": "AI Bridge Text Review",
    }


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def copy_file(src: Path, dst: Path, *, force: bool, actions: list[str]) -> None:
    visual_review.copy_file(src, dst, force=force, actions=actions)


def write_rendered_file(src: Path, dst: Path, replacements: dict[str, str], *, force: bool, actions: list[str]) -> None:
    visual_review.write_rendered_file(src, dst, replacements, force=force, actions=actions)


def install_text_review(target: Path, *, force: bool = False, bridge_kit_ref: str | None = None) -> list[str]:
    target = target.resolve()
    source = kit_root() / "templates" / "text_review"
    if not source.exists():
        raise TextReviewError("text review templates are missing from the Bridge Kit installation")
    actions: list[str] = []
    pip_spec = bridge_kit_pip_spec(bridge_kit_ref)
    copy_file(source / "README.md", target / "docs" / "AI_BRIDGE_TEXT_REVIEW.md", force=force, actions=actions)
    write_rendered_file(
        source / "github-actions" / "text-review.yml",
        target / ".github" / "workflows" / "ai-bridge-text-review.yml",
        {"__AI_BRIDGE_KIT_PIP_SPEC__": pip_spec},
        force=force,
        actions=actions,
    )
    copy_file(source / "text_inputs.template.json", target / "docs" / "text_inputs.template.json", force=force, actions=actions)
    return actions


def _extract_public_recipient(identity_text: str) -> str:
    for line in identity_text.splitlines():
        match = re.search(r"\b(age1[0-9a-z]+)\b", line.strip())
        if match:
            return match.group(1)
    raise TextReviewError("age-keygen output did not contain a public age recipient")


def configure_transport(target: Path, *, repo: str | None = None, recipient: str | None = None, force: bool = False) -> dict[str, Any]:
    target = target.resolve()
    recipient_path = target / DEFAULT_RECIPIENT_PATH
    if recipient_path.exists() and not force:
        raise TextReviewError(f"age public recipient already exists: {recipient_path}")
    if recipient:
        if not recipient.startswith("age1"):
            raise TextReviewError("age public recipient must start with age1")
        recipient_path.parent.mkdir(parents=True, exist_ok=True)
        recipient_path.write_text(recipient.strip() + "\n", encoding="utf-8")
        return {"configured": True, "age_secret_set": False, "recipient_path": DEFAULT_RECIPIENT_PATH}
    keygen = _age_keygen_binary()
    result = subprocess.run([keygen], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise TextReviewError("age-keygen failed closed")
    identity_text = result.stdout
    public_recipient = _extract_public_recipient(identity_text + "\n" + result.stderr)
    selected_repo = repo or _gh_repo_slug(target)
    if not selected_repo:
        raise TextReviewError("GitHub repository slug unavailable; pass --repo owner/name")
    try:
        gh_result = subprocess.run(
            ["gh", "secret", "set", AGE_SECRET_NAME, "--repo", selected_repo],
            input=identity_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise TextReviewError(f"gh CLI is required to set {AGE_SECRET_NAME}; configure this one GitHub Secret manually") from exc
    if gh_result.returncode != 0:
        raise TextReviewError(f"could not set {AGE_SECRET_NAME}; configure this one GitHub Secret manually")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        temp_key = Path(handle.name)
        handle.write(identity_text)
    try:
        temp_key.unlink(missing_ok=True)
    finally:
        pass
    recipient_path.parent.mkdir(parents=True, exist_ok=True)
    recipient_path.write_text(public_recipient + "\n", encoding="utf-8")
    status = gh_secret_metadata_status(target, AGE_SECRET_NAME, repo=selected_repo)
    return {
        "configured": True,
        "age_secret_set": status.get("status") == "PRESENT",
        "age_secret_metadata_status": status,
        "recipient_path": DEFAULT_RECIPIENT_PATH,
        "private_identity_value_read": False,
        "private_identity_printed": False,
        "temporary_private_key_deleted": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge text-review")
    sub = parser.add_subparsers(dest="command")
    install_cmd = sub.add_parser("install")
    install_cmd.add_argument("--target", type=Path, default=Path.cwd())
    install_cmd.add_argument("--force", action="store_true")
    install_cmd.add_argument("--bridge-kit-ref")
    configure_cmd = sub.add_parser("configure")
    configure_cmd.add_argument("--target", type=Path, default=Path.cwd())
    configure_cmd.add_argument("--repo")
    configure_cmd.add_argument("--recipient")
    configure_cmd.add_argument("--force", action="store_true")
    preflight_cmd = sub.add_parser("preflight")
    preflight_cmd.add_argument("--target", type=Path, default=Path.cwd())
    preflight_cmd.add_argument("--repo")
    encrypt_cmd = sub.add_parser("encrypt")
    encrypt_cmd.add_argument("--target", type=Path, default=Path.cwd())
    encrypt_cmd.add_argument("--task-key", required=True)
    encrypt_cmd.add_argument("--input", type=Path, required=True)
    encrypt_cmd.add_argument("--recipient-file", type=Path, default=Path(DEFAULT_RECIPIENT_PATH))
    encrypt_cmd.add_argument("--output", type=Path, required=True)
    encrypt_cmd.add_argument("--manifest", type=Path, required=True)
    encrypt_cmd.add_argument("--workflow-type", default="reviewed_handoff")
    encrypt_cmd.add_argument("--review-kind", default="text-artifact")
    encrypt_cmd.add_argument("--rubric", required=True)
    encrypt_cmd.add_argument("--implementation-commit", default="")
    encrypt_cmd.add_argument("--privacy-policy", default=PRIVATE_TEXT_POLICY)
    encrypt_cmd.add_argument("--external-upload-authorization", default="")
    encrypt_cmd.add_argument("--force", action="store_true")
    decrypt_cmd = sub.add_parser("decrypt")
    decrypt_cmd.add_argument("--target", type=Path, default=Path.cwd())
    decrypt_cmd.add_argument("--manifest", type=Path, required=True)
    decrypt_cmd.add_argument("--identity-file", type=Path, required=True)
    decrypt_cmd.add_argument("--output", type=Path, required=True)
    decrypt_cmd.add_argument("--force", action="store_true")
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--target", type=Path, default=Path.cwd())
    run_cmd.add_argument("--manifest", type=Path, required=True)
    run_cmd.add_argument("--plaintext", type=Path, required=True)
    run_cmd.add_argument("--output", type=Path, required=True)
    run_cmd.add_argument("--model")
    run_cmd.add_argument("--timeout", type=float, default=60.0)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("--path", type=Path, required=True)
    writeback_cmd = sub.add_parser("writeback-needed")
    writeback_cmd.add_argument("--target", type=Path, default=Path.cwd())
    writeback_cmd.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "install":
        try:
            actions = install_text_review(args.target, force=args.force, bridge_kit_ref=args.bridge_kit_ref)
        except TextReviewError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for action in actions:
            print(action)
        return 0
    if args.command == "configure":
        try:
            result = configure_transport(args.target, repo=args.repo, recipient=args.recipient, force=args.force)
        except TextReviewError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(canonical_json(result, pretty=True), end="")
        return 0
    if args.command == "preflight":
        print(canonical_json(preflight(args.target, repo=args.repo), pretty=True), end="")
        return 0
    if args.command == "encrypt":
        try:
            manifest = encrypt_text_payload(
                args.target,
                task_key=args.task_key,
                input_path=args.input,
                recipient_file=args.target / args.recipient_file if not args.recipient_file.is_absolute() else args.recipient_file,
                output_path=args.output,
                manifest_path=args.manifest,
                workflow_type=args.workflow_type,
                review_kind=args.review_kind,
                rubric=args.rubric,
                implementation_commit=args.implementation_commit,
                privacy_policy=args.privacy_policy,
                external_upload_authorization=args.external_upload_authorization,
                force=args.force,
            )
        except TextReviewError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(canonical_json(manifest, pretty=True), end="")
        return 0
    if args.command == "decrypt":
        try:
            manifest = normalize_manifest(args.target, load_json(args.manifest))
            payload = args.target / manifest["input"]["encrypted_payload_path"]
            decrypt_with_age(payload, args.output, identity_file=args.identity_file, force=args.force)
            _, data = _require_utf8_text(args.output)
            if sha256_bytes(data) != manifest["input"]["plaintext_sha256"]:
                args.output.unlink(missing_ok=True)
                raise TextReviewError("decrypted plaintext SHA-256 does not match text review manifest")
        except TextReviewError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Decrypted text review payload to {args.output}")
        return 0
    if args.command == "run":
        try:
            artifact = run_text_review(args.target, args.manifest, args.plaintext, args.output, model=args.model, timeout=args.timeout)
        except TextReviewError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(canonical_json(artifact, pretty=True), end="")
        return 0
    if args.command == "validate":
        errors = validate_text_review_payload(load_json(args.path))
        if errors:
            for error in errors:
                print(f"ERROR {error}")
            return 1
        print("Text Review validation passed.")
        return 0
    if args.command == "writeback-needed":
        try:
            needed = text_evidence_commit_needed(args.target, args.output)
        except (TextReviewError, subprocess.CalledProcessError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if needed:
            print("Text review evidence changes staged.")
            return 1
        print("No text review evidence changes.")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
