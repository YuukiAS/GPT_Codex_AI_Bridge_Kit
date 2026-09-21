from __future__ import annotations

import re


LEGACY_TASK_KEY_RE = re.compile(r"^\d+_[A-Za-z0-9]+(?:_[A-Za-z0-9]+){0,2}$")
SEMANTIC_COMPONENT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_TASK_KEY_LENGTH = 96


def is_legacy_task_key(task_key: str) -> bool:
    return bool(LEGACY_TASK_KEY_RE.fullmatch(task_key))


def is_semantic_task_key(task_key: str) -> bool:
    if len(task_key) > MAX_TASK_KEY_LENGTH:
        return False
    if task_key.count("--") != 1:
        return False
    scope, goal = task_key.split("--", 1)
    return bool(SEMANTIC_COMPONENT_RE.fullmatch(scope) and SEMANTIC_COMPONENT_RE.fullmatch(goal))


def is_existing_task_key(task_key: str) -> bool:
    return is_legacy_task_key(task_key) or is_semantic_task_key(task_key)


def new_task_key_error(task_key: str) -> str | None:
    if is_semantic_task_key(task_key):
        return None
    if is_legacy_task_key(task_key):
        return (
            "new Reviewed Handoff task_key must be semantic, not legacy numeric; "
            "use <scope-token>--<goal-token>, for example repo--release-notes"
        )
    return (
        "task_key must be semantic <scope-token>--<goal-token> with lowercase "
        "kebab-case components, exactly one '--', no path separators, and at most "
        f"{MAX_TASK_KEY_LENGTH} characters"
    )


def existing_task_key_error(task_key: str) -> str | None:
    if is_existing_task_key(task_key):
        return None
    return (
        "task_key must be either legacy <id>_<1-3-word_slug> or semantic "
        "<scope-token>--<goal-token>"
    )
