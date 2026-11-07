"""Priority list ranking (F11). Schedule facts only, deterministic tiebreak.

Order: unreachable first (nobody has reached them), then most days overdue, then most missed
appointments, then earliest due date, then patient id. No weights, no clinical values.
"""
from __future__ import annotations

from typing import Any

from medora import whitelist


class RankingInputError(ValueError):
    pass


def sort_key(inputs: dict[str, Any]) -> tuple[Any, ...]:
    extra = set(inputs) - whitelist.ranking_inputs()
    if extra:
        raise RankingInputError(f"ranking may only read whitelisted schedule fields, got {sorted(extra)}")
    return (
        0 if inputs["unreachable"] else 1,
        -int(inputs["days_overdue"]),
        -int(inputs["missed_count"]),
        str(inputs["due_by"]),
        str(inputs["patient_id"]),
    )


def rank(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each item must carry `rank_inputs`. Returns a new list with `rank` set from 1."""
    ordered = sorted(items, key=lambda it: sort_key(it["rank_inputs"]))
    return [{**it, "rank": i} for i, it in enumerate(ordered, start=1)]
