from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from . import paid_review


VISUAL_REVIEW_SCHEMA = "AI_BRIDGE_VISUAL_REVIEW_V1"
VISUAL_INPUT_MANIFEST_SCHEMA = "AI_BRIDGE_VISUAL_INPUT_MANIFEST_V1"
SECRET_NAME = "OPENAI_VISUAL_REVIEW_API_KEY"
MODEL_ENV = "OPENAI_VISUAL_REVIEW_MODEL"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_PROMPT_VERSION = "ai-bridge.visual-review.v1"
DEFAULT_PRIVACY_POLICY = "PUBLIC_SAFE_ONLY"
DEFAULT_MAX_OUTPUT_TOKENS = paid_review.DEFAULT_MAX_OUTPUT_TOKENS
DECISIONS = {"PASS", "REVISE", "BLOCKED"}
WORKFLOW_TYPES = {"reviewed_handoff", "agent_flow", "generic"}
API_URL = "https://api.openai.com/v1/responses"
CANONICAL_BRIDGE_KIT_REPO = "https://github.com/YuukiAS/GPT_Codex_AI_Bridge_Kit.git"


class VisualReviewError(ValueError):
    pass


def canonical_json(payload: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload, pretty=True), encoding="utf-8")


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def repository_relative_path(path: Path | str) -> str:
    raw = Path(path)
    if raw.is_absolute() or ".." in raw.parts:
        raise VisualReviewError("path must be repository-relative and must not contain '..'")
    rel = raw.as_posix().strip()
    if not rel or rel == ".":
        raise VisualReviewError("path must be a repository-relative file path")
    return rel


def validate_visual_output_path(target: Path, task_key: str, output_path: Path | str) -> Path:
    rel = validate_generated_visual_evidence_path(output_path)
    expected_prefix = f"results/{task_key}/visual_review/"
    if not rel.startswith(expected_prefix):
        raise VisualReviewError(f"visual review output must be under {expected_prefix}")
    return target / rel


def validate_generated_visual_evidence_path(output_path: Path | str) -> str:
    rel = repository_relative_path(output_path)
    if not re.fullmatch(r"results/[^/]+/visual_review/.+", rel):
        raise VisualReviewError("visual review write-back path must be under results/<task_key>/visual_review/")
    if rel.endswith("/"):
        raise VisualReviewError("visual review write-back path must be a file path")
    protected_names = {
        "CURRENT.json",
        "FROZEN_CONTRACT.md",
        "FROZEN_CONTRACT.json",
        "REQUIREMENT_LEDGER.md",
        "REQUIREMENT_LEDGER.json",
    }
    if Path(rel).name in protected_names:
        raise VisualReviewError("visual review output must be generated visual evidence, not workflow control files")
    blocked_parts = {".github", "src", "automation"}
    if blocked_parts.intersection(Path(rel).parts):
        raise VisualReviewError("visual review output must not target source, automation, or workflow paths")
    return rel


def logical_mime_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        return guessed
    raise VisualReviewError(f"unsupported visual input image type: {path}")


def data_url_for_image(path: Path) -> str:
    mime_type = logical_mime_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def visual_review_response_schema() -> dict[str, Any]:
    finding_schema = {
        "type": "object",
        "properties": {
            "finding_id": {"type": "string"},
            "item_id": {"type": "string"},
            "requirement_id": {"type": "string"},
            "severity": {"type": "string", "enum": ["blocking", "non_blocking"]},
            "summary": {"type": "string"},
            "evidence": {"type": "string"},
            "recommendation": {"type": "string"},
        },
        "required": ["finding_id", "item_id", "requirement_id", "severity", "summary", "evidence", "recommendation"],
        "additionalProperties": False,
    }
    item_schema = {
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "decision": {"type": "string", "enum": sorted(DECISIONS)},
            "summary": {"type": "string"},
            "observations": {"type": "array", "items": {"type": "string"}},
            "requirement_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["item_id", "decision", "summary", "observations", "requirement_ids"],
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
    if manifest.get("schema") != VISUAL_INPUT_MANIFEST_SCHEMA:
        raise VisualReviewError(f"visual input manifest schema must be {VISUAL_INPUT_MANIFEST_SCHEMA}")
    workflow_type = manifest.get("workflow_type")
    if workflow_type not in WORKFLOW_TYPES:
        raise VisualReviewError(f"visual input manifest workflow_type must be one of {sorted(WORKFLOW_TYPES)}")
    task_key = str(manifest.get("task_key") or "").strip()
    if not task_key:
        raise VisualReviewError("visual input manifest task_key is required")
    review_kind = str(manifest.get("review_kind") or "").strip()
    if not review_kind:
        raise VisualReviewError("visual input manifest review_kind is required")
    privacy_policy = manifest.get("privacy_policy") or DEFAULT_PRIVACY_POLICY
    if privacy_policy != DEFAULT_PRIVACY_POLICY:
        if not manifest.get("external_upload_authorization"):
            raise VisualReviewError("non-public visual review requires explicit external_upload_authorization")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise VisualReviewError("visual input manifest requires non-empty inputs")
    normalized_inputs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            raise VisualReviewError(f"visual input {index} must be an object")
        logical_id = str(item.get("logical_id") or "").strip()
        if not logical_id:
            raise VisualReviewError(f"visual input {index} missing logical_id")
        if logical_id in seen_ids:
            raise VisualReviewError(f"duplicate visual input logical_id: {logical_id}")
        seen_ids.add(logical_id)
        rel = str(item.get("path") or "").strip()
        if not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise VisualReviewError(f"visual input {logical_id} path must be repository-relative")
        path = target / rel
        if not path.exists() or not path.is_file():
            raise VisualReviewError(f"visual input file missing: {rel}")
        mime_type = str(item.get("mime_type") or logical_mime_type(path))
        if mime_type != logical_mime_type(path):
            raise VisualReviewError(f"visual input {logical_id} mime_type mismatch")
        sha = file_sha256(path)
        if item.get("sha256") and item.get("sha256") != sha:
            raise VisualReviewError(f"visual input {logical_id} sha256 mismatch")
        normalized_inputs.append(
            {
                "logical_id": logical_id,
                "path": rel,
                "mime_type": mime_type,
                "sha256": sha,
                "description": str(item.get("description") or ""),
            }
        )
    normalized = {
        "schema": VISUAL_INPUT_MANIFEST_SCHEMA,
        "task_key": task_key,
        "paid_review_campaign_id": str(manifest.get("paid_review_campaign_id") or task_key).strip(),
        "workflow_type": workflow_type,
        "review_kind": review_kind,
        "prompt_version": str(manifest.get("prompt_version") or DEFAULT_PROMPT_VERSION),
        "privacy_policy": privacy_policy,
        "external_upload_authorization": str(manifest.get("external_upload_authorization") or ""),
        "rubric": manifest.get("rubric") if isinstance(manifest.get("rubric"), dict) else {},
        "identity_bindings": manifest.get("identity_bindings") if isinstance(manifest.get("identity_bindings"), dict) else {},
        "inputs": normalized_inputs,
    }
    if not normalized["rubric"].get("instructions"):
        raise VisualReviewError("visual input manifest rubric.instructions is required")
    return normalized


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
        "inputs": [
            {
                "logical_id": item.get("logical_id"),
                "path": item.get("path"),
                "mime_type": item.get("mime_type"),
                "sha256": item.get("sha256"),
            }
            for item in manifest.get("inputs", [])
        ],
    }
    return sha256_text(canonical_json(identity_payload))


def build_prompt(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "You are producing visual review evidence for AI Bridge Kit.",
            "Inspect the provided image pixels directly. Do not infer PASS from file names, hashes, dimensions, OCR-only text, or metadata.",
            "Do not reveal chain-of-thought. Return concise observable findings only.",
            f"Workflow: {manifest['workflow_type']}",
            f"Task: {manifest['task_key']}",
            f"Review kind: {manifest['review_kind']}",
            "Rubric:",
            str(manifest["rubric"].get("instructions") or ""),
            "Input logical IDs:",
            canonical_json([{"logical_id": item["logical_id"], "description": item.get("description", "")} for item in manifest["inputs"]]),
        ]
    )


def build_responses_request(manifest: dict[str, Any], *, model: str) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": build_prompt(manifest)}]
    for item in manifest["inputs"]:
        content.append(
            {
                "type": "input_image",
                "image_url": data_url_for_image(Path(item["_absolute_path"])),
                "detail": "auto",
            }
        )
    return {
        "model": model,
        "store": False,
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "visual_review",
                "strict": True,
                "schema": visual_review_response_schema(),
            }
        },
        "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
    }


def _manifest_with_absolute_paths(target: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(canonical_json(manifest))
    for item in copy["inputs"]:
        item["_absolute_path"] = str((target / item["path"]).resolve())
    return copy


def extract_response_text(response_payload: dict[str, Any]) -> str:
    output_text = response_payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    chunks: list[str] = []
    for item in response_payload.get("output", []) if isinstance(response_payload.get("output"), list) else []:
        for content in item.get("content", []) if isinstance(item, dict) and isinstance(item.get("content"), list) else []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    text = "".join(chunks).strip()
    if text:
        return text
    raise VisualReviewError("OpenAI response did not contain structured output text")


def call_openai_responses(
    request_payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float = 60.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise VisualReviewError(f"{SECRET_NAME} is not available")
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
        suffix = paid_review.billing_error_suffix_from_http_error(exc)
        raise VisualReviewError(f"OpenAI visual review API failed closed: HTTP {status}{suffix}") from exc
    except Exception as exc:
        raise VisualReviewError(f"OpenAI visual review API failed closed: {exc.__class__.__name__}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise VisualReviewError("OpenAI visual review API returned malformed JSON") from exc
    status = payload.get("status")
    if status and status not in {"completed"}:
        raise VisualReviewError(f"OpenAI visual review API did not complete: {status}")
    return payload


def assemble_visual_review(
    *,
    manifest: dict[str, Any],
    model_output: dict[str, Any],
    model: str,
    paid_review_receipt: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    for key in ["overall_decision", "item_reviews", "blocking_findings", "non_blocking_notes"]:
        if key not in model_output:
            raise VisualReviewError(f"model visual review missing {key}")
    decision = model_output.get("overall_decision")
    if decision not in DECISIONS:
        raise VisualReviewError("model visual review overall_decision is invalid")
    for key in ["item_reviews", "blocking_findings", "non_blocking_notes"]:
        if not isinstance(model_output.get(key), list):
            raise VisualReviewError(f"model visual review {key} must be a list")
    review_identity = manifest_identity(manifest)
    artifact = {
        "schema": VISUAL_REVIEW_SCHEMA,
        "evidence_id": f"visual-review-{manifest['task_key']}-{review_identity[:12]}",
        "task_key": manifest["task_key"],
        "workflow_type": manifest["workflow_type"],
        "review_kind": manifest["review_kind"],
        "review_model": model,
        "prompt_version": manifest["prompt_version"],
        "created_at": created_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input_manifest": {
            "schema": manifest["schema"],
            "privacy_policy": manifest["privacy_policy"],
            "rubric": manifest["rubric"],
            "identity_bindings": manifest["identity_bindings"],
            "manifest_sha256": review_identity,
        },
        "images": [
            {
                "logical_id": item["logical_id"],
                "path": item["path"],
                "mime_type": item["mime_type"],
                "sha256": item["sha256"],
            }
            for item in manifest["inputs"]
        ],
        "review_identity": review_identity,
        "overall_decision": decision,
        "status": decision,
        "item_reviews": model_output.get("item_reviews", []),
        "blocking_findings": model_output.get("blocking_findings", []),
        "non_blocking_notes": model_output.get("non_blocking_notes", []),
    }
    if paid_review_receipt is not None:
        artifact["paid_review"] = paid_review_receipt
    return artifact


def validate_visual_review_payload(payload: dict[str, Any], *, expected: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    expected = expected or {}
    if payload.get("schema") != VISUAL_REVIEW_SCHEMA:
        errors.append("VISUAL_REVIEW.json schema mismatch")
    for key in [
        "evidence_id",
        "task_key",
        "workflow_type",
        "review_kind",
        "review_model",
        "prompt_version",
        "created_at",
        "input_manifest",
        "images",
        "review_identity",
        "overall_decision",
        "status",
        "item_reviews",
        "blocking_findings",
        "non_blocking_notes",
    ]:
        if key not in payload:
            errors.append(f"VISUAL_REVIEW.json missing {key}")
    if payload.get("overall_decision") not in DECISIONS:
        errors.append("VISUAL_REVIEW.json overall_decision invalid")
    if payload.get("status") != payload.get("overall_decision"):
        errors.append("VISUAL_REVIEW.json status must equal overall_decision")
    if payload.get("workflow_type") not in WORKFLOW_TYPES:
        errors.append("VISUAL_REVIEW.json workflow_type invalid")
    if not isinstance(payload.get("images"), list) or not payload.get("images"):
        errors.append("VISUAL_REVIEW.json images must be non-empty")
    for item in payload.get("images", []) if isinstance(payload.get("images"), list) else []:
        if not isinstance(item, dict):
            errors.append("VISUAL_REVIEW.json image entry must be an object")
            continue
        for key in ["logical_id", "path", "mime_type", "sha256"]:
            if not item.get(key):
                errors.append(f"VISUAL_REVIEW.json image entry missing {key}")
    if not isinstance(payload.get("input_manifest"), dict):
        errors.append("VISUAL_REVIEW.json input_manifest must be an object")
    else:
        bindings = payload["input_manifest"].get("identity_bindings")
        if not isinstance(bindings, dict):
            errors.append("VISUAL_REVIEW.json identity_bindings must be an object")
            bindings = {}
        for key, value in expected.items():
            if payload.get(key) != value and bindings.get(key) != value:
                errors.append(f"VISUAL_REVIEW.json identity binding mismatch: {key}")
        manifest_sha = payload["input_manifest"].get("manifest_sha256")
        if manifest_sha != payload.get("review_identity"):
            errors.append("VISUAL_REVIEW.json review_identity must match input manifest sha")
        if isinstance(payload.get("images"), list):
            reconstructed = {
                "schema": payload["input_manifest"].get("schema"),
                "task_key": payload.get("task_key"),
                "workflow_type": payload.get("workflow_type"),
                "review_kind": payload.get("review_kind"),
                "prompt_version": payload.get("prompt_version"),
                "privacy_policy": payload["input_manifest"].get("privacy_policy"),
                "rubric": payload["input_manifest"].get("rubric"),
                "identity_bindings": bindings,
                "inputs": [
                    {
                        "logical_id": item.get("logical_id"),
                        "path": item.get("path"),
                        "mime_type": item.get("mime_type"),
                        "sha256": item.get("sha256"),
                    }
                    for item in payload.get("images", [])
                    if isinstance(item, dict)
                ],
            }
            if sha256_text(canonical_json(reconstructed)) != payload.get("review_identity"):
                errors.append("VISUAL_REVIEW.json review_identity is stale against image hashes or manifest content")
    for key in ["item_reviews", "blocking_findings", "non_blocking_notes"]:
        if not isinstance(payload.get(key), list):
            errors.append(f"VISUAL_REVIEW.json {key} must be a list")
    if payload.get("overall_decision") == "PASS" and payload.get("blocking_findings"):
        errors.append("VISUAL_REVIEW.json PASS cannot contain blocking_findings")
    paid_receipt = payload.get("paid_review")
    if paid_receipt is not None:
        if not isinstance(paid_receipt, dict):
            errors.append("VISUAL_REVIEW.json paid_review must be an object")
        else:
            for key in [
                "campaign_identity",
                "model_identity",
                "exact_input_token_preflight",
                "call_reservations",
                "worst_case_reserved_cost_usd",
                "cumulative_reserved_cost_usd",
            ]:
                if key not in paid_receipt:
                    errors.append(f"VISUAL_REVIEW.json paid_review missing {key}")
    return errors


def run_visual_review(
    target: Path,
    manifest_path: Path,
    output_path: Path,
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    target = target.resolve()
    manifest = normalize_manifest(target, load_json(manifest_path))
    output_file = validate_visual_output_path(target, str(manifest["task_key"]), output_path)
    manifest_for_request = _manifest_with_absolute_paths(target, manifest)
    selected_model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
    selected_key = api_key if api_key is not None else (os.environ.get(SECRET_NAME, "") or os.environ.get("OPENAI_API_KEY", ""))
    if not selected_key:
        raise VisualReviewError(f"{SECRET_NAME} is not available")
    try:
        paid_review.validate_model_pricing(selected_model)
    except paid_review.PaidReviewBudgetError as exc:
        raise VisualReviewError(str(exc)) from exc
    request_payload = build_responses_request(manifest_for_request, model=selected_model)
    try:
        campaign_identity = paid_review.campaign_identity_from_manifest(manifest)
        token_preflight = paid_review.count_input_tokens(request_payload, api_key=selected_key, timeout=timeout, opener=opener)
        reservation_bundle = paid_review.reserve_paid_review_call(
            target=target,
            campaign_identity=campaign_identity,
            review_type="visual_review",
            model=selected_model,
            request_payload=request_payload,
            input_token_preflight=token_preflight,
        )
        paid_review.persist_reservation_to_git_if_requested(target, reservation_bundle["state_path"])
    except paid_review.PaidReviewBudgetError as exc:
        raise VisualReviewError(str(exc)) from exc
    try:
        response_payload = call_openai_responses(request_payload, api_key=selected_key, timeout=timeout, opener=opener)
    except VisualReviewError as exc:
        code = paid_review.zero_billing_error_code_from_message(str(exc))
        if code:
            status_match = re.search(r"HTTP ([0-9A-Z]+)", str(exc))
            try:
                paid_review.record_zero_billing_failure(
                    target=target,
                    campaign_identity=campaign_identity,
                    reservation_id=reservation_bundle["reservation"]["reservation_id"],
                    error_code=code,
                    http_status=status_match.group(1) if status_match else "UNKNOWN",
                )
                paid_review.persist_reservation_to_git_if_requested(
                    target,
                    reservation_bundle["state_path"],
                    message="Record AI Bridge paid review zero-billing failure",
                )
            except paid_review.PaidReviewBudgetError as budget_exc:
                raise VisualReviewError(str(budget_exc)) from exc
        raise
    paid_review.record_actual_usage(
        target=target,
        campaign_identity=campaign_identity,
        reservation_id=reservation_bundle["reservation"]["reservation_id"],
        response_payload=response_payload,
    )
    paid_review_receipt = paid_review.receipt_from_reservation(
        campaign_identity=campaign_identity,
        review_type="visual_review",
        model=selected_model,
        reservation_bundle=reservation_bundle,
        response_payload=response_payload,
    )
    try:
        model_output = json.loads(extract_response_text(response_payload))
    except json.JSONDecodeError as exc:
        raise VisualReviewError("OpenAI visual review output was not valid JSON") from exc
    artifact = assemble_visual_review(
        manifest=manifest,
        model_output=model_output,
        model=selected_model,
        paid_review_receipt=paid_review_receipt,
    )
    errors = validate_visual_review_payload(artifact)
    if errors:
        raise VisualReviewError("; ".join(errors))
    write_json(output_file, artifact)
    return artifact


def git_current_commit(path: Path) -> str | None:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None
    return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None


def bridge_kit_pip_spec(ref: str | None = None) -> str:
    selected_ref = ref or git_current_commit(kit_root())
    if not selected_ref:
        raise VisualReviewError("cannot determine Bridge Kit Git commit; pass --bridge-kit-ref explicitly")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", selected_ref):
        raise VisualReviewError("Bridge Kit ref contains unsupported characters")
    return f"gpt-codex-ai-bridge-kit[visual-review] @ git+{CANONICAL_BRIDGE_KIT_REPO}@{selected_ref}"


def visual_evidence_commit_needed(target: Path, output_path: Path | str) -> bool:
    rel = validate_generated_visual_evidence_path(output_path)
    task_key = Path(rel).parts[1]
    paths = [rel]
    budget_rel = f"results/{task_key}/paid_review_budget.json"
    if (target / budget_rel).exists():
        paths.append(budget_rel)
    if (target / rel).exists():
        try:
            payload = load_json(target / rel)
        except Exception:
            payload = {}
        paid = payload.get("paid_review") if isinstance(payload, dict) else {}
        campaign = paid.get("campaign_identity") if isinstance(paid, dict) else ""
        if isinstance(campaign, str) and re.fullmatch(r"[A-Za-z0-9._-]+", campaign):
            campaign_budget_rel = f"results/{campaign}/paid_review_budget.json"
            if campaign_budget_rel not in paths and (target / campaign_budget_rel).exists():
                paths.append(campaign_budget_rel)
    subprocess.check_call(["git", "add", "--", *paths], cwd=target)
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", *paths],
        cwd=target,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(
            result.returncode,
            ["git", "diff", "--cached", "--quiet", "--", *paths],
        )
    return result.returncode == 1


def gh_repo_slug(target: Path) -> str | None:
    try:
        remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=target, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$", remote)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}"


def gh_secret_metadata_status(target: Path, *, repo: str | None = None) -> dict[str, str]:
    selected_repo = repo or gh_repo_slug(target)
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
    return {"status": "PRESENT" if SECRET_NAME in names else "MISSING", "reason": "metadata only"}


def workflow_status(target: Path) -> dict[str, Any]:
    workflows = sorted((target / ".github" / "workflows").glob("*.yml")) + sorted((target / ".github" / "workflows").glob("*.yaml"))
    matches: list[str] = []
    for path in workflows:
        text = path.read_text(encoding="utf-8", errors="replace")
        if SECRET_NAME in text and "visual-review" in text:
            matches.append(rel_path(path, target))
    return {"status": "PRESENT" if matches else "MISSING", "paths": matches}


def installed_visual_review_status(target: Path) -> dict[str, Any]:
    target = target.resolve()
    reviewed_tasks = []
    reviewed_dir = target / "automation" / "reviewed_handoff" / "tasks"
    if reviewed_dir.exists():
        for current_path in sorted(reviewed_dir.glob("*/CURRENT.json")):
            try:
                current = load_json(current_path)
            except Exception:
                continue
            if current.get("visual_review_required"):
                reviewed_tasks.append(current_path.parent.name)
    agent_policy: dict[str, Any] = {"enabled": False}
    profile_path = target / "automation" / "agent_flow" / "PROJECT_PROFILE.json"
    if profile_path.exists():
        try:
            profile = load_json(profile_path)
            policy = profile.get("optional_visual_source_policy")
            if isinstance(policy, dict):
                agent_policy = dict(policy)
        except Exception:
            agent_policy = {"enabled": "UNKNOWN"}
    enabled = bool(reviewed_tasks) or agent_policy.get("enabled") is True
    return {
        "enabled": enabled,
        "reviewed_handoff_tasks": reviewed_tasks,
        "agent_flow_optional_visual_source_policy": agent_policy,
    }


def preflight(target: Path, *, repo: str | None = None) -> dict[str, Any]:
    target = target.resolve()
    return {
        "schema": "AI_BRIDGE_VISUAL_REVIEW_PREFLIGHT_V1",
        "target": str(target),
        "visual_review": installed_visual_review_status(target),
        "github_workflow": workflow_status(target),
        "secret": {
            "expected_name": SECRET_NAME,
            "metadata_status": gh_secret_metadata_status(target, repo=repo),
            "value_read": False,
        },
        "model_env": MODEL_ENV,
        "default_model": DEFAULT_MODEL,
        "openai_project_recommendation": "AI Bridge Visual Review",
    }


def kit_root() -> Path:
    return Path(__file__).resolve().parents[1]


def copy_file(src: Path, dst: Path, *, force: bool, actions: list[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force:
        actions.append(f"SKIP existing file: {dst}")
        return
    existed = dst.exists()
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    actions.append(f"COPY {'overwrite' if existed else 'create'}: {dst}")


def write_rendered_file(src: Path, dst: Path, replacements: dict[str, str], *, force: bool, actions: list[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and not force:
        actions.append(f"SKIP existing file: {dst}")
        return
    text = src.read_text(encoding="utf-8")
    for key, value in replacements.items():
        text = text.replace(key, value)
    existed = dst.exists()
    dst.write_text(text, encoding="utf-8")
    actions.append(f"COPY {'overwrite' if existed else 'create'}: {dst}")


def install_visual_review(target: Path, *, force: bool = False, bridge_kit_ref: str | None = None) -> list[str]:
    target = target.resolve()
    source = kit_root() / "templates" / "visual_review"
    if not source.exists():
        raise VisualReviewError("visual review templates are missing from the Bridge Kit installation")
    actions: list[str] = []
    pip_spec = bridge_kit_pip_spec(bridge_kit_ref)
    copy_file(source / "README.md", target / "docs" / "AI_BRIDGE_VISUAL_REVIEW.md", force=force, actions=actions)
    write_rendered_file(
        source / "github-actions" / "visual-review.yml",
        target / ".github" / "workflows" / "ai-bridge-visual-review.yml",
        {"__AI_BRIDGE_KIT_PIP_SPEC__": pip_spec},
        force=force,
        actions=actions,
    )
    copy_file(
        source / "visual_inputs.template.json",
        target / "docs" / "visual_inputs.template.json",
        force=force,
        actions=actions,
    )
    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-bridge visual-review")
    sub = parser.add_subparsers(dest="command")
    install_cmd = sub.add_parser("install")
    install_cmd.add_argument("--target", type=Path, default=Path.cwd())
    install_cmd.add_argument("--force", action="store_true")
    install_cmd.add_argument("--bridge-kit-ref")
    preflight_cmd = sub.add_parser("preflight")
    preflight_cmd.add_argument("--target", type=Path, default=Path.cwd())
    preflight_cmd.add_argument("--repo")
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("--target", type=Path, default=Path.cwd())
    run_cmd.add_argument("--manifest", type=Path, required=True)
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
            actions = install_visual_review(args.target, force=args.force, bridge_kit_ref=args.bridge_kit_ref)
        except VisualReviewError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for action in actions:
            print(action)
        return 0
    if args.command == "preflight":
        print(canonical_json(preflight(args.target, repo=args.repo), pretty=True), end="")
        return 0
    if args.command == "run":
        try:
            artifact = run_visual_review(args.target, args.manifest, args.output, model=args.model, timeout=args.timeout)
        except VisualReviewError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(canonical_json(artifact, pretty=True), end="")
        return 0
    if args.command == "validate":
        errors = validate_visual_review_payload(load_json(args.path))
        if errors:
            for error in errors:
                print(f"ERROR {error}")
            return 1
        print("Visual Review validation passed.")
        return 0
    if args.command == "writeback-needed":
        try:
            needed = visual_evidence_commit_needed(args.target, args.output)
        except (VisualReviewError, subprocess.CalledProcessError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if needed:
            print("Visual review evidence changes staged.")
            return 1
        print("No visual review evidence changes.")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
