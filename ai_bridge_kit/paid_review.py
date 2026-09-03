from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable, Iterator


BUDGET_SCHEMA = "AI_BRIDGE_PAID_REVIEW_BUDGET_V1"
RECEIPT_SCHEMA = "AI_BRIDGE_PAID_REVIEW_RECEIPT_V1"
INPUT_TOKENS_URL = "https://api.openai.com/v1/responses/input_tokens"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_MAX_PAID_CALLS = 2
DEFAULT_CAMPAIGN_RESERVED_COST_HARD_CEILING_USD = Decimal("0.50")
DEFAULT_PER_CALL_WORST_CASE_CEILING_USD = Decimal("0.25")
DEFAULT_AUTOMATIC_PAID_RETRIES = 0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_SERVICE_TIER = "default"
DEFAULT_REASONING_EFFORT = "low"
LONG_CONTEXT_INPUT_TOKEN_THRESHOLD = 272_000
INPUT_TOKEN_COUNT_SUPPORTED_FIELDS = (
    "conversation",
    "input",
    "instructions",
    "model",
    "parallel_tool_calls",
    "personality",
    "previous_response_id",
    "reasoning",
    "text",
    "tool_choice",
    "tools",
    "truncation",
)
TERRA_PRICING_REVIEWED_ON = "2026-09-03"
TERRA_INPUT_USD_PER_1M = Decimal("2")
TERRA_CACHED_INPUT_USD_PER_1M = Decimal("0.20")
TERRA_CACHE_WRITE_INPUT_USD_PER_1M = Decimal("2.50")
TERRA_WORST_CASE_INPUT_USD_PER_1M = TERRA_CACHE_WRITE_INPUT_USD_PER_1M
TERRA_OUTPUT_USD_PER_1M = Decimal("12")
ZERO_RETRY_BILLING_ERROR_CODES = {
    "credit_balance_exhausted",
    "project_spend_limit_exceeded",
    "organization_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
}


class PaidReviewBudgetError(ValueError):
    pass


def canonical_json(payload: Any, *, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _decimal_from_json(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise PaidReviewBudgetError("paid review budget contains invalid decimal value") from exc


def default_contract() -> dict[str, Any]:
    return {
        "model": DEFAULT_MODEL,
        "max_paid_calls": DEFAULT_MAX_PAID_CALLS,
        "campaign_reserved_cost_hard_ceiling_usd": _money(DEFAULT_CAMPAIGN_RESERVED_COST_HARD_CEILING_USD),
        "per_call_worst_case_ceiling_usd": _money(DEFAULT_PER_CALL_WORST_CASE_CEILING_USD),
        "automatic_paid_retries": DEFAULT_AUTOMATIC_PAID_RETRIES,
        "pricing": {
            "model": DEFAULT_MODEL,
            "reviewed_on": TERRA_PRICING_REVIEWED_ON,
            "normal_input_usd_per_1m": _money(TERRA_INPUT_USD_PER_1M),
            "cached_input_usd_per_1m": _money(TERRA_CACHED_INPUT_USD_PER_1M),
            "cache_write_usd_per_1m": _money(TERRA_CACHE_WRITE_INPUT_USD_PER_1M),
            "worst_case_standard_input_usd_per_1m": _money(TERRA_WORST_CASE_INPUT_USD_PER_1M),
            "input_usd_per_1m_tokens": _money(TERRA_INPUT_USD_PER_1M),
            "cached_input_usd_per_1m_tokens": _money(TERRA_CACHED_INPUT_USD_PER_1M),
            "cache_write_input_usd_per_1m_tokens": _money(TERRA_CACHE_WRITE_INPUT_USD_PER_1M),
            "worst_case_input_usd_per_1m_tokens": _money(TERRA_WORST_CASE_INPUT_USD_PER_1M),
            "output_usd_per_1m_tokens": _money(TERRA_OUTPUT_USD_PER_1M),
            "output_usd_per_1m": _money(TERRA_OUTPUT_USD_PER_1M),
            "long_context_threshold": LONG_CONTEXT_INPUT_TOKEN_THRESHOLD,
            "runtime_uses_worst_case_input_price": True,
        },
    }


def validate_model_pricing(model: str) -> dict[str, Any]:
    if model != DEFAULT_MODEL:
        raise PaidReviewBudgetError("paid review model/pricing mismatch; only gpt-5.6-terra has reviewed pricing")
    return default_contract()["pricing"]


def pricing_identity() -> dict[str, Any]:
    return {
        "model": DEFAULT_MODEL,
        "reviewed_on": TERRA_PRICING_REVIEWED_ON,
        "normal_input_usd_per_1m": _money(TERRA_INPUT_USD_PER_1M),
        "cached_input_usd_per_1m": _money(TERRA_CACHED_INPUT_USD_PER_1M),
        "cache_write_usd_per_1m": _money(TERRA_CACHE_WRITE_INPUT_USD_PER_1M),
        "output_usd_per_1m": _money(TERRA_OUTPUT_USD_PER_1M),
        "long_context_threshold": LONG_CONTEXT_INPUT_TOKEN_THRESHOLD,
    }


def request_safety_fields() -> dict[str, Any]:
    return {
        "service_tier": DEFAULT_SERVICE_TIER,
        "reasoning": {"effort": DEFAULT_REASONING_EFFORT},
        "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        "tools": [],
        "prompt_cache_options": {"mode": "explicit"},
    }


def campaign_identity_from_manifest(manifest: dict[str, Any]) -> str:
    raw = manifest.get("paid_review_campaign_id") or manifest.get("campaign_id") or manifest.get("task_key")
    identity = str(raw or "").strip()
    if not identity:
        raise PaidReviewBudgetError("paid review campaign identity is required")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", identity):
        raise PaidReviewBudgetError("paid review campaign identity must be a safe task/campaign token")
    return identity


def budget_state_path(target: Path, campaign_identity: str) -> Path:
    return target.resolve() / "results" / campaign_identity / "paid_review_budget.json"


def _lock_path(state_path: Path) -> Path:
    return state_path.with_suffix(".lock")


def _sum_reserved_cost(reservations: list[dict[str, Any]]) -> Decimal:
    return sum((_decimal_from_json(item.get("worst_case_reserved_cost_usd", "0")) for item in reservations), Decimal("0"))


def _sum_actual_cost(reservations: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0")
    for item in reservations:
        if item.get("accounting_status") != "ACCOUNTING_VERIFIED":
            continue
        actual = item.get("actual_model_cost_usd")
        if actual is not None:
            total += _decimal_from_json(actual)
    return total


@contextmanager
def locked_budget(state_path: Path) -> Iterator[None]:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(state_path)
    lock_handle = lock_path.open("a+", encoding="utf-8")
    try:
        import fcntl

        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()


def load_budget_state(state_path: Path, *, campaign_identity: str) -> dict[str, Any]:
    if not state_path.exists():
        return {
            "schema": BUDGET_SCHEMA,
            "campaign_identity": campaign_identity,
            "contract": default_contract(),
            "reservations": [],
            "cumulative_reserved_worst_case_cost_usd": "0.000000",
            "cumulative_actual_model_cost_usd": "0.000000",
        }
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PaidReviewBudgetError("paid review budget state is unreadable") from exc
    if payload.get("schema") != BUDGET_SCHEMA:
        raise PaidReviewBudgetError("paid review budget state schema mismatch")
    if payload.get("campaign_identity") != campaign_identity:
        raise PaidReviewBudgetError("paid review budget campaign identity mismatch")
    if payload.get("contract") != default_contract():
        raise PaidReviewBudgetError("paid review budget contract mismatch")
    reservations = payload.get("reservations")
    if not isinstance(reservations, list):
        raise PaidReviewBudgetError("paid review budget reservations must be a list")
    payload.setdefault("cumulative_reserved_worst_case_cost_usd", _money(_sum_reserved_cost(reservations)))
    payload.setdefault("cumulative_actual_model_cost_usd", _money(_sum_actual_cost(reservations)))
    return payload


def write_budget_state(state_path: Path, payload: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp = state_path.with_name(state_path.name + ".tmp")
    temp.write_text(canonical_json(payload, pretty=True), encoding="utf-8")
    temp.replace(state_path)


def extract_input_tokens(token_payload: dict[str, Any]) -> int:
    candidates = [
        token_payload.get("input_tokens"),
        token_payload.get("tokens"),
        token_payload.get("total_tokens"),
    ]
    usage = token_payload.get("usage")
    if isinstance(usage, dict):
        candidates.extend([usage.get("input_tokens"), usage.get("total_tokens")])
    for value in candidates:
        if type(value) is int and value >= 0:
            return value
    raise PaidReviewBudgetError("Responses input-token preflight did not return input_tokens")


def input_token_count_payload(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Return the provider-compatible token-count projection of a Responses request."""
    if "model" not in request_payload:
        raise PaidReviewBudgetError("paid review input-token preflight requires request model")
    if "input" not in request_payload and "conversation" not in request_payload:
        raise PaidReviewBudgetError("paid review input-token preflight requires request input or conversation")
    canonical_payload = json.loads(canonical_json(request_payload))
    return {
        key: canonical_payload[key]
        for key in INPUT_TOKEN_COUNT_SUPPORTED_FIELDS
        if key in canonical_payload
    }


def count_input_tokens(
    request_payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float = 60.0,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not api_key:
        raise PaidReviewBudgetError("OpenAI API key is not available for paid review token preflight")
    body = canonical_json(input_token_count_payload(request_payload)).encode("utf-8")
    request = urllib.request.Request(
        INPUT_TOKENS_URL,
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
        code = extract_openai_error_code(exc)
        suffix = f" ({code}; zero paid retry)" if code in ZERO_RETRY_BILLING_ERROR_CODES else (f" ({code})" if code else "")
        raise PaidReviewBudgetError(f"OpenAI paid review input-token preflight failed closed: HTTP {exc.code}{suffix}") from exc
    except Exception as exc:
        raise PaidReviewBudgetError(f"OpenAI paid review input-token preflight failed closed: {exc.__class__.__name__}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise PaidReviewBudgetError("OpenAI paid review input-token preflight returned malformed JSON") from exc
    input_tokens = extract_input_tokens(payload)
    return {
        "endpoint": "/v1/responses/input_tokens",
        "input_tokens": input_tokens,
        "raw_response": payload,
    }


def calculate_worst_case_cost(input_tokens: int, max_output_tokens: int) -> Decimal:
    if type(input_tokens) is not int or input_tokens < 0:
        raise PaidReviewBudgetError("paid review input_tokens must be a non-negative integer")
    if input_tokens > LONG_CONTEXT_INPUT_TOKEN_THRESHOLD:
        raise PaidReviewBudgetError("paid review unsupported long-context pricing boundary: input_tokens > 272000")
    if type(max_output_tokens) is not int or max_output_tokens <= 0:
        raise PaidReviewBudgetError("paid review max_output_tokens must be a positive integer")
    input_cost = Decimal(input_tokens) * TERRA_WORST_CASE_INPUT_USD_PER_1M / Decimal(1_000_000)
    output_cost = Decimal(max_output_tokens) * TERRA_OUTPUT_USD_PER_1M / Decimal(1_000_000)
    return input_cost + output_cost


def _required_nonnegative_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if type(value) is int and value >= 0:
        return value
    raise PaidReviewBudgetError(f"paid review accounting malformed required usage field: {key}")


def _optional_nonnegative_int(payload: dict[str, Any], key: str) -> int:
    if key not in payload:
        return 0
    value = payload.get(key)
    if type(value) is int and value >= 0:
        return value
    raise PaidReviewBudgetError(f"paid review accounting malformed optional usage field: {key}")


def _has_unknown_positive_detail(details: dict[str, Any], allowed: set[str]) -> bool:
    for key, value in details.items():
        if key in allowed:
            continue
        if value is not None and value != 0:
            return True
    return False


def normalize_actual_usage(response_payload: dict[str, Any], *, expected_model: str, expected_service_tier: str) -> dict[str, Any]:
    response_id = response_payload.get("id")
    response_model = response_payload.get("model")
    response_service_tier = response_payload.get("service_tier")
    if not isinstance(response_id, str) or not response_id.strip():
        raise PaidReviewBudgetError("paid review accounting malformed response_id")
    if response_model != expected_model:
        raise PaidReviewBudgetError("paid review accounting wrong response model")
    if response_service_tier != expected_service_tier:
        raise PaidReviewBudgetError("paid review accounting unexpected service tier")
    usage = response_payload.get("usage")
    if not isinstance(usage, dict):
        raise PaidReviewBudgetError("paid review accounting malformed usage")
    input_tokens = _required_nonnegative_int(usage, "input_tokens")
    output_tokens = _required_nonnegative_int(usage, "output_tokens")
    input_details = usage.get("input_tokens_details")
    if input_details is None:
        input_details = {}
    if not isinstance(input_details, dict):
        raise PaidReviewBudgetError("paid review accounting malformed input_tokens_details")
    output_details = usage.get("output_tokens_details")
    if output_details is None:
        output_details = {}
    if not isinstance(output_details, dict):
        raise PaidReviewBudgetError("paid review accounting malformed output_tokens_details")
    cached_tokens = _optional_nonnegative_int(input_details, "cached_tokens")
    cache_write_tokens = _optional_nonnegative_int(input_details, "cache_write_tokens")
    reasoning_tokens = _optional_nonnegative_int(output_details, "reasoning_tokens")
    regular_input_tokens = input_tokens - cached_tokens - cache_write_tokens
    if regular_input_tokens < 0:
        raise PaidReviewBudgetError("paid review accounting negative token decomposition")
    if input_tokens > LONG_CONTEXT_INPUT_TOKEN_THRESHOLD:
        raise PaidReviewBudgetError("paid review accounting unsupported long-context pricing boundary")
    if _has_unknown_positive_detail(input_details, {"cached_tokens", "cache_write_tokens"}):
        raise PaidReviewBudgetError("paid review accounting unknown input token category")
    if _has_unknown_positive_detail(output_details, {"reasoning_tokens"}):
        raise PaidReviewBudgetError("paid review accounting unknown output token category")
    return {
        "response_id": response_id,
        "response_model": response_model,
        "response_service_tier": response_service_tier,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "cache_write_tokens": cache_write_tokens,
        "regular_input_tokens": regular_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


def calculate_actual_model_cost_from_tokens(tokens: dict[str, int]) -> Decimal:
    cost = (
        Decimal(tokens["regular_input_tokens"]) * TERRA_INPUT_USD_PER_1M
        + Decimal(tokens["cached_input_tokens"]) * TERRA_CACHED_INPUT_USD_PER_1M
        + Decimal(tokens["cache_write_tokens"]) * TERRA_CACHE_WRITE_INPUT_USD_PER_1M
        + Decimal(tokens["output_tokens"]) * TERRA_OUTPUT_USD_PER_1M
    ) / Decimal(1_000_000)
    return cost


def verified_actual_accounting(response_payload: dict[str, Any], *, expected_model: str, expected_service_tier: str) -> dict[str, Any]:
    tokens = normalize_actual_usage(response_payload, expected_model=expected_model, expected_service_tier=expected_service_tier)
    cost = calculate_actual_model_cost_from_tokens(tokens)
    return {
        "accounting_status": "ACCOUNTING_VERIFIED",
        "actual_model_cost_usd": _money(cost),
        "actual_response_usage": tokens,
    }


def unverified_actual_accounting(reason: str, response_payload: dict[str, Any]) -> dict[str, Any]:
    response_id = response_payload.get("id")
    response_model = response_payload.get("model")
    response_service_tier = response_payload.get("service_tier")
    return {
        "accounting_status": "ACCOUNTING_UNVERIFIED",
        "accounting_unverified_reason": reason,
        "response_id": response_id if isinstance(response_id, str) else None,
        "response_model": response_model if isinstance(response_model, str) else None,
        "response_service_tier": response_service_tier if isinstance(response_service_tier, str) else None,
        "actual_response_usage": None,
        "actual_model_cost_usd": None,
    }


def request_sha256(request_payload: dict[str, Any]) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(request_payload).encode("utf-8")).hexdigest()


def _matching_reusable_zero_billing_reservation(
    reservations: list[dict[str, Any]],
    *,
    review_type: str,
    model: str,
    request_hash: str,
) -> dict[str, Any] | None:
    for item in reservations:
        if item.get("accounting_status") != "ZERO_BILLING_FAILURE" and item.get("actual_cost_status") != "ZERO_BILLING_FAILURE":
            continue
        if item.get("review_type") != review_type:
            continue
        if item.get("model") != model:
            continue
        if item.get("request_sha256") != request_hash:
            continue
        return item
    return None


def reserve_paid_review_call(
    *,
    target: Path,
    campaign_identity: str,
    review_type: str,
    model: str,
    request_payload: dict[str, Any],
    input_token_preflight: dict[str, Any],
) -> dict[str, Any]:
    pricing = validate_model_pricing(model)
    max_output_tokens = request_payload.get("max_output_tokens")
    if type(max_output_tokens) is not int or max_output_tokens <= 0:
        raise PaidReviewBudgetError("paid review request must include bounded max_output_tokens")
    input_tokens = input_token_preflight.get("input_tokens")
    if type(input_tokens) is not int:
        raise PaidReviewBudgetError("paid review input-token preflight input_tokens must be an integer")
    worst_case_cost = calculate_worst_case_cost(input_tokens, max_output_tokens)
    if worst_case_cost > DEFAULT_PER_CALL_WORST_CASE_CEILING_USD:
        raise PaidReviewBudgetError("paid review per-call worst-case cost exceeds USD 0.25")
    request_hash = request_sha256(request_payload)
    state_path = budget_state_path(target, campaign_identity)
    with locked_budget(state_path):
        state = load_budget_state(state_path, campaign_identity=campaign_identity)
        reservations = state["reservations"]
        if any(item.get("accounting_status") == "ACCOUNTING_UNVERIFIED" or item.get("actual_cost_status") == "ACCOUNTING_UNVERIFIED" for item in reservations):
            raise PaidReviewBudgetError("paid review accounting is unverified; refusing next paid request")
        reusable = _matching_reusable_zero_billing_reservation(
            reservations,
            review_type=review_type,
            model=model,
            request_hash=request_hash,
        )
        if reusable is not None:
            return {
                "state_path": state_path,
                "reservation": reusable,
                "reservations": reservations,
                "contract": default_contract(),
                "reused_zero_billing_reservation": True,
            }
        if len(reservations) >= DEFAULT_MAX_PAID_CALLS:
            raise PaidReviewBudgetError("paid review campaign call limit exhausted")
        current_reserved = _sum_reserved_cost(reservations)
        cumulative = current_reserved + worst_case_cost
        if cumulative > DEFAULT_CAMPAIGN_RESERVED_COST_HARD_CEILING_USD:
            raise PaidReviewBudgetError("paid review campaign reserved-cost hard ceiling exceeds USD 0.50")
        call_number = len(reservations) + 1
        reservation = {
            "reservation_id": f"{campaign_identity}-{call_number}-{request_hash[:12]}",
            "call_number": call_number,
            "review_type": review_type,
            "reserved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": model,
            "pricing": pricing,
            "request_sha256": request_hash,
            "input_token_preflight": input_token_preflight,
            "max_output_tokens": max_output_tokens,
            "worst_case_reserved_cost_usd": _money(worst_case_cost),
            "cumulative_reserved_cost_usd": _money(cumulative),
            "cumulative_reserved_worst_case_cost_usd": _money(cumulative),
            "service_tier": request_payload.get("service_tier"),
            "automatic_paid_retries": DEFAULT_AUTOMATIC_PAID_RETRIES,
        }
        reservations.append(reservation)
        state["cumulative_reserved_worst_case_cost_usd"] = _money(cumulative)
        state["cumulative_actual_model_cost_usd"] = _money(_sum_actual_cost(reservations))
        write_budget_state(state_path, state)
    return {
        "state_path": state_path,
        "reservation": reservation,
        "reservations": reservations,
        "contract": default_contract(),
    }


def record_actual_usage(
    *,
    target: Path,
    campaign_identity: str,
    reservation_id: str,
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    state_path = budget_state_path(target, campaign_identity)
    with locked_budget(state_path):
        state = load_budget_state(state_path, campaign_identity=campaign_identity)
        for item in state["reservations"]:
            if item.get("reservation_id") == reservation_id:
                try:
                    accounting = verified_actual_accounting(
                        response_payload,
                        expected_model=DEFAULT_MODEL,
                        expected_service_tier=DEFAULT_SERVICE_TIER,
                    )
                except PaidReviewBudgetError as exc:
                    accounting = unverified_actual_accounting(str(exc), response_payload)
                item.update(accounting)
                item["actual_cost_status"] = item["accounting_status"]
                actual_usage = item.get("actual_response_usage")
                if isinstance(actual_usage, dict):
                    item["response_id"] = actual_usage.get("response_id")
                    item["response_model"] = actual_usage.get("response_model")
                    item["response_service_tier"] = actual_usage.get("response_service_tier")
                state["cumulative_reserved_worst_case_cost_usd"] = _money(_sum_reserved_cost(state["reservations"]))
                state["cumulative_actual_model_cost_usd"] = _money(_sum_actual_cost(state["reservations"]))
                write_budget_state(state_path, state)
                return {
                    "state_path": state_path,
                    "reservation": item,
                    "reservations": state["reservations"],
                    "contract": default_contract(),
                }
    raise PaidReviewBudgetError("paid review reservation id not found for actual usage accounting")


def record_zero_billing_failure(
    *,
    target: Path,
    campaign_identity: str,
    reservation_id: str,
    error_code: str,
    http_status: int | str,
) -> None:
    if error_code not in ZERO_RETRY_BILLING_ERROR_CODES:
        raise PaidReviewBudgetError("paid review zero-billing failure requires a reviewed billing error code")
    state_path = budget_state_path(target, campaign_identity)
    with locked_budget(state_path):
        state = load_budget_state(state_path, campaign_identity=campaign_identity)
        for item in state["reservations"]:
            if item.get("reservation_id") == reservation_id:
                item["actual_cost_status"] = "ZERO_BILLING_FAILURE"
                item["accounting_status"] = "ZERO_BILLING_FAILURE"
                item["actual_model_cost_usd"] = "0.000000"
                item["actual_response_usage"] = {
                    "input_tokens": 0,
                    "regular_input_tokens": 0,
                    "cached_input_tokens": 0,
                    "cache_write_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                }
                item["actual_cost_tokens"] = item["actual_response_usage"]
                item["failure"] = {
                    "failure_class": "ZERO_BILLING_FAILURE",
                    "http_status": str(http_status),
                    "openai_error_code": error_code,
                    "automatic_paid_retry": False,
                    "reservation_preserved": True,
                    "retry_requires_explicit_human_resume": True,
                }
                state["cumulative_actual_model_cost_usd"] = _money(_sum_actual_cost(state["reservations"]))
                write_budget_state(state_path, state)
                return
    raise PaidReviewBudgetError("paid review reservation id not found for failure accounting")


def receipt_from_reservation(
    *,
    campaign_identity: str,
    review_type: str,
    model: str,
    reservation_bundle: dict[str, Any],
    response_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reservation = reservation_bundle["reservation"]
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "campaign_identity": campaign_identity,
        "reservation_id": reservation["reservation_id"],
        "call_number": reservation["call_number"],
        "review_type": review_type,
        "model": model,
        "model_identity": model,
        "service_tier": reservation.get("service_tier") or DEFAULT_SERVICE_TIER,
        "response_id": reservation.get("response_id"),
        "contract": reservation_bundle["contract"],
        "pricing_identity": pricing_identity(),
        "input_token_preflight": reservation["input_token_preflight"],
        "exact_input_token_preflight": reservation["input_token_preflight"],
        "max_output_tokens": reservation["max_output_tokens"],
        "call_reservation": reservation,
        "call_reservations": reservation_bundle["reservations"],
        "worst_case_reserved_cost_usd": reservation["worst_case_reserved_cost_usd"],
        "cumulative_reserved_worst_case_cost_usd": reservation.get(
            "cumulative_reserved_worst_case_cost_usd",
            reservation.get("cumulative_reserved_cost_usd"),
        ),
        "cumulative_reserved_cost_usd": reservation["cumulative_reserved_cost_usd"],
        "actual_response_usage": reservation.get("actual_response_usage"),
        "actual_model_cost_usd": reservation.get("actual_model_cost_usd"),
        "cumulative_actual_model_cost_usd": _money(_sum_actual_cost(reservation_bundle["reservations"])),
        "accounting_status": reservation.get("accounting_status"),
    }
    if reservation.get("accounting_unverified_reason"):
        receipt["accounting_unverified_reason"] = reservation["accounting_unverified_reason"]
    if response_payload and receipt["response_id"] is None and isinstance(response_payload.get("id"), str):
        receipt["response_id"] = response_payload["id"]
    return receipt


def persist_reservation_to_git_if_requested(
    target: Path,
    state_path: Path,
    *,
    message: str = "Reserve AI Bridge paid review budget",
) -> None:
    if os.environ.get("AI_BRIDGE_PAID_REVIEW_GIT_RESERVE") != "1":
        return
    if os.environ.get("GITHUB_REF_TYPE") != "branch" or not os.environ.get("GITHUB_REF_NAME"):
        raise PaidReviewBudgetError("paid review reservation writeback requires a branch ref")
    rel = state_path.resolve().relative_to(target.resolve()).as_posix()
    commands = [
        ["git", "config", "user.name", "github-actions[bot]"],
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        ["git", "add", "--", rel],
        ["git", "diff", "--cached", "--quiet", "--", rel],
        ["git", "commit", "-m", message],
        ["git", "push", "origin", f"HEAD:{os.environ['GITHUB_REF_NAME']}"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=target, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if command[:4] == ["git", "diff", "--cached", "--quiet"]:
            if result.returncode == 0:
                return
            if result.returncode == 1:
                continue
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            message = detail[-1] if detail else "git reservation writeback failed"
            raise PaidReviewBudgetError(f"paid review reservation writeback failed closed: {message}")


def extract_openai_error_code(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read()
    except Exception:
        raw = b""
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else {}
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return error["code"]
    return ""


def billing_error_suffix_from_http_error(exc: urllib.error.HTTPError) -> str:
    code = extract_openai_error_code(exc)
    if code in ZERO_RETRY_BILLING_ERROR_CODES:
        return f" ({code}; zero paid retry)"
    return f" ({code})" if code else ""


def zero_billing_error_code_from_message(message: str) -> str:
    for code in ZERO_RETRY_BILLING_ERROR_CODES:
        if code in message:
            return code
    return ""
