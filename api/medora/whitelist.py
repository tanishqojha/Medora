"""Loads config/field_whitelist.yaml (two-key). Single place every whitelist check reads from."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from medora.config import load_yaml


@lru_cache
def wl() -> dict[str, Any]:
    return load_yaml("field_whitelist.yaml")


def canonical_fields() -> set[str]:
    return set(wl()["canonical_fields"])


def identifier_fields() -> set[str]:
    return {k for k, v in wl()["canonical_fields"].items() if v["kind"] == "identifier"}


def event_types() -> set[str]:
    return set(wl()["event_types"])


def payload_fields() -> set[str]:
    return set(wl()["event_payload_fields"])


def llm_plain_fields() -> set[str]:
    return set(wl()["llm_fields"]["plain"])


def llm_tokenised_fields() -> set[str]:
    return set(wl()["llm_fields"]["tokenised_only"])


def ranking_inputs() -> set[str]:
    return set(wl()["ranking_inputs"])


def llm_task_inputs(task: str) -> set[str]:
    tasks = wl()["llm_tasks"]
    if task not in tasks:
        raise KeyError(f"LLM task not whitelisted: {task}")
    return set(tasks[task])
