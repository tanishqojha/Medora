import pytest

from medora.ranking import RankingInputError, rank


def item(pid, overdue=0, missed=0, attempts=0, unreachable=False, due="2026-10-01"):
    return {"id": pid, "rank_inputs": {"days_overdue": overdue, "missed_count": missed, "attempts": attempts,
                                       "unreachable": unreachable, "due_by": due, "patient_id": pid}}


def test_order_and_deterministic_tiebreak():
    out = rank([item("c", 2), item("a", 9), item("b", 9), item("u", 0, unreachable=True), item("m", 2, missed=1)])
    assert [x["id"] for x in out] == ["u", "a", "b", "m", "c"]
    assert [x["rank"] for x in out] == [1, 2, 3, 4, 5]


def test_rank_is_stable_under_input_order():
    items = [item("c", 2), item("a", 9), item("b", 9)]
    assert [x["id"] for x in rank(items)] == [x["id"] for x in rank(list(reversed(items)))]


def test_rejects_non_whitelisted_inputs():
    bad = item("x")
    bad["rank_inputs"]["tumour_stage"] = 3
    with pytest.raises(RankingInputError):
        rank([bad])
