from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class DependencyClass(str, Enum):
    HUMAN_ONLY = "HUMAN_ONLY"
    AGENT_RESOLVABLE = "AGENT_RESOLVABLE"
    UNSUPPORTED_WITH_EVIDENCE = "UNSUPPORTED_WITH_EVIDENCE"
    OPTIONAL_NOT_REQUIRED_FOR_CURRENT_CLOSURE = "OPTIONAL_NOT_REQUIRED_FOR_CURRENT_CLOSURE"
    SAFETY_OR_AUTHORITY_BLOCKER = "SAFETY_OR_AUTHORITY_BLOCKER"


class HumanGateState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    HUMAN_BLOCKED_RECOVERABLE = "HUMAN_BLOCKED_RECOVERABLE"
    RESUMED_EXACT_ONCE = "RESUMED_EXACT_ONCE"
    UNSUPPORTED_CLOSED = "UNSUPPORTED_CLOSED"
    SAFETY_OR_AUTHORITY_BLOCKED = "SAFETY_OR_AUTHORITY_BLOCKED"


@dataclass(frozen=True)
class HumanGateRecord:
    dependency_class: DependencyClass
    state: HumanGateState
    goal_id: str
    resume_point: str
    prompt_identity: str
    question: str | None = None
    unsupported_reason: str | None = None
    resume_count: int = 0
    dependent_execution_allowed: bool = False
    used_native_request_user_input: bool = False


NO_REPLY_BOUNDARY_FLAGS = {
    "GOAL_BLOCKED": "YES",
    "GOAL_ACHIEVED": "NO",
    "COMPLETE": "NO",
    "READY_FOR_USER_REVIEW": "NO",
    "DEPENDENT_EXECUTION_BLOCKED": "YES",
}


def classify_dependency(label: str) -> DependencyClass:
    try:
        return DependencyClass(label)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DependencyClass)
        raise ValueError(f"unknown dependency class {label!r}; expected one of: {allowed}") from exc


def open_transcript_gate(
    *,
    dependency_class: DependencyClass,
    goal_id: str,
    resume_point: str,
    prompt_identity: str,
    question: str | None = None,
    unsupported_reason: str | None = None,
) -> HumanGateRecord:
    if dependency_class == DependencyClass.HUMAN_ONLY:
        if not question or "\n" in question.strip():
            raise ValueError("HUMAN_ONLY transcript gate requires one concise plain-text question")
        return HumanGateRecord(
            dependency_class=dependency_class,
            state=HumanGateState.WAITING_FOR_HUMAN,
            goal_id=goal_id,
            resume_point=resume_point,
            prompt_identity=prompt_identity,
            question=question.strip(),
            dependent_execution_allowed=False,
            used_native_request_user_input=False,
        )
    if dependency_class == DependencyClass.AGENT_RESOLVABLE:
        return HumanGateRecord(
            dependency_class=dependency_class,
            state=HumanGateState.NOT_REQUIRED,
            goal_id=goal_id,
            resume_point=resume_point,
            prompt_identity=prompt_identity,
            dependent_execution_allowed=True,
        )
    if dependency_class == DependencyClass.UNSUPPORTED_WITH_EVIDENCE:
        return HumanGateRecord(
            dependency_class=dependency_class,
            state=HumanGateState.UNSUPPORTED_CLOSED,
            goal_id=goal_id,
            resume_point=resume_point,
            prompt_identity=prompt_identity,
            unsupported_reason=unsupported_reason or "unsupported with evidence",
            dependent_execution_allowed=False,
        )
    if dependency_class == DependencyClass.OPTIONAL_NOT_REQUIRED_FOR_CURRENT_CLOSURE:
        return HumanGateRecord(
            dependency_class=dependency_class,
            state=HumanGateState.NOT_REQUIRED,
            goal_id=goal_id,
            resume_point=resume_point,
            prompt_identity=prompt_identity,
            dependent_execution_allowed=True,
        )
    return HumanGateRecord(
        dependency_class=dependency_class,
        state=HumanGateState.SAFETY_OR_AUTHORITY_BLOCKED,
        goal_id=goal_id,
        resume_point=resume_point,
        prompt_identity=prompt_identity,
        dependent_execution_allowed=False,
    )


def mark_no_reply_boundary(record: HumanGateRecord) -> tuple[HumanGateRecord, dict[str, str]]:
    if record.state != HumanGateState.WAITING_FOR_HUMAN:
        raise ValueError("only a waiting HUMAN_ONLY gate can reach the no-reply boundary")
    return (
        replace(record, state=HumanGateState.HUMAN_BLOCKED_RECOVERABLE, dependent_execution_allowed=False),
        dict(NO_REPLY_BOUNDARY_FLAGS),
    )


def resume_after_explicit_answer(
    record: HumanGateRecord,
    *,
    goal_id: str,
    prompt_identity: str,
    answer: str,
) -> HumanGateRecord:
    if record.dependency_class != DependencyClass.HUMAN_ONLY:
        raise ValueError("only HUMAN_ONLY gates can be resumed by a human answer")
    if record.state not in {HumanGateState.WAITING_FOR_HUMAN, HumanGateState.HUMAN_BLOCKED_RECOVERABLE}:
        raise ValueError("gate is not waiting for a human answer")
    if record.resume_count:
        raise ValueError("human answer for this gate has already been consumed")
    if goal_id != record.goal_id or prompt_identity != record.prompt_identity:
        raise ValueError("stale answer does not match the preserved Goal and prompt identity")
    if not answer.strip():
        raise ValueError("empty answer is not an explicit in-scope answer")
    return replace(
        record,
        state=HumanGateState.RESUMED_EXACT_ONCE,
        resume_count=1,
        dependent_execution_allowed=True,
    )
