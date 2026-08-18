from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MIN_EXTERNAL_GPT_WAIT_SECONDS = 2 * 60 * 60
EXTERNAL_GPT_ROLES = {"PLANNER", "REVIEWER", "CRITIC", "FINAL_CRITIC", "FINAL CRITIC"}


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def parse_wait_timestamp(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def external_owner(current: dict[str, Any], *, state_owner_map: dict[str, str] | None = None) -> str | None:
    for key in ("state_owner", "owner_role", "target_role"):
        owner = _upper(current.get(key)).replace("_", " ")
        if owner in EXTERNAL_GPT_ROLES:
            return owner.title()

    state = _upper(current.get("state"))
    if state_owner_map and state in state_owner_map:
        return state_owner_map[state]
    fallback_state_roles = {
        "NEEDS_GPT_PLANNER": "Planner",
        "READY_FOR_GPT_REVIEW": "Reviewer",
        "READY_FOR_PLANNER_REVIEW": "Planner",
        "WAITING_FOR_EXTERNAL_GPT": "Planner",
        "CONTRACT_REVIEW_REQUIRED": "Critic",
        "READY_FOR_CRITIC_FINAL_AUDIT": "Final Critic",
    }
    if state in fallback_state_roles:
        return fallback_state_roles[state]

    next_action = _upper(current.get("next_action"))
    action_role_map = {
        "FINAL_CRITIC": "Final Critic",
        "FINAL CRITIC": "Final Critic",
        "GPT_REVIEW": "Reviewer",
        "GPT_PLANNER": "Planner",
        "REVIEWER": "Reviewer",
        "PLANNER": "Planner",
        "CRITIC": "Critic",
    }
    for marker, role in action_role_map.items():
        if marker in next_action:
            return role
    return None


def wait_started_at(current: dict[str, Any]) -> datetime | None:
    for key in ("external_wait_started_at", "wait_started_at", "implementation_published_at", "published_at"):
        parsed = parse_wait_timestamp(current.get(key))
        if parsed is not None:
            return parsed
    return None


def build_wait_status(
    current: dict[str, Any],
    *,
    current_identity: str | None,
    latest_decision_identity: str | None = None,
    latest_decision_path: str | None = None,
    latest_decision: str | None = None,
    state_owner_map: dict[str, str] | None = None,
    external_failure_evidence: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    owner = external_owner(current, state_owner_map=state_owner_map)
    if owner is None:
        return {
            "operational_status": "not_external_gpt_wait",
            "external_owner": None,
            "may_block": False,
        }

    failures = [item for item in (external_failure_evidence or []) if str(item).strip()]
    if failures:
        return {
            "operational_status": "external_review_blocked",
            "external_owner": owner,
            "may_block": True,
            "failure_evidence": failures,
            "recovery_action_required": True,
        }

    current_id = str(current_identity or "").strip() or None
    decision_id = str(latest_decision_identity or "").strip() or None
    fresh = bool(current_id and decision_id and current_id == decision_id)
    stale = bool(current_id and decision_id and current_id != decision_id)

    started_at = wait_started_at(current)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    elapsed_seconds: int | None = None
    remaining_seconds: int | None = None
    within_minimum_grace: bool | None = None
    if started_at is not None:
        elapsed_seconds = max(0, int((now - started_at).total_seconds()))
        remaining_seconds = max(0, MIN_EXTERNAL_GPT_WAIT_SECONDS - elapsed_seconds)
        within_minimum_grace = elapsed_seconds < MIN_EXTERNAL_GPT_WAIT_SECONDS

    return {
        "operational_status": "fresh_external_decision" if fresh else "waiting_external_review",
        "external_owner": owner,
        "current_identity": current_id,
        "latest_decision_identity": decision_id,
        "latest_decision": latest_decision,
        "latest_decision_path": latest_decision_path,
        "fresh_decision": fresh,
        "stale_decision": stale,
        "min_wait_seconds": MIN_EXTERNAL_GPT_WAIT_SECONDS,
        "elapsed_wait_seconds": elapsed_seconds,
        "remaining_min_wait_seconds": remaining_seconds,
        "within_minimum_grace": within_minimum_grace,
        "may_block": False,
        "blocker_required_evidence": [
            "external automation disabled, deleted, expired, or unauthenticated",
            "workflow installation or schema is invalid",
            "review artifact required for the external role is missing or inaccessible because of a concrete service failure",
            "repository state is contradictory or user/product/scientific input is required",
            "a workflow-defined hard deadline has passed",
        ],
    }
