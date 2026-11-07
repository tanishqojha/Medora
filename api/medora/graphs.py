"""Approval gates (S11): LangGraph interrupt() with a Postgres checkpointer.

One small graph: ask (interrupt, waits for a person) -> apply (writes the decision). The thread id is
"<kind>:<object id>", so a pending approval survives a worker or API restart. Timeouts escalate the
review item; they never approve anything.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from medora.config import database_url


class GateState(TypedDict, total=False):
    kind: str
    hospital_id: str
    object_id: str
    proposal: dict[str, Any]
    decision: dict[str, Any]
    result: dict[str, Any]


# kind -> apply(hospital_id, object_id, proposal, decision) -> result. Registered by the owning modules.
APPLY: dict[str, Callable[[str, str, dict[str, Any], dict[str, Any]], dict[str, Any]]] = {}


def register(kind: str) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    def deco(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        APPLY[kind] = fn
        return fn
    return deco


def _ask(state: GateState) -> GateState:
    decision = interrupt({"kind": state["kind"], "object_id": state["object_id"], "proposal": state["proposal"]})
    return {"decision": decision}


def _apply(state: GateState) -> GateState:
    fn = APPLY[state["kind"]]
    return {"result": fn(state["hospital_id"], state["object_id"], state["proposal"], state["decision"])}


def _builder() -> StateGraph:
    g = StateGraph(GateState)
    g.add_node("ask", _ask)
    g.add_node("apply", _apply)
    g.add_edge(START, "ask")
    g.add_edge("ask", "apply")
    g.add_edge("apply", END)
    return g


@contextmanager
def _graph() -> Iterator[Any]:
    with PostgresSaver.from_conn_string(database_url()) as saver:
        yield _builder().compile(checkpointer=saver)


def thread_id(kind: str, object_id: str) -> str:
    return f"{kind}:{object_id}"


def start(kind: str, hospital_id: str, object_id: str, proposal: dict[str, Any]) -> None:
    """Open a gate. Idempotent: an existing thread is left as it is."""
    cfg = {"configurable": {"thread_id": thread_id(kind, object_id)}}
    with _graph() as g:
        if g.get_state(cfg).values:
            return
        g.invoke({"kind": kind, "hospital_id": hospital_id, "object_id": object_id, "proposal": proposal}, cfg)


def pending(kind: str, object_id: str) -> bool:
    cfg = {"configurable": {"thread_id": thread_id(kind, object_id)}}
    with _graph() as g:
        return tuple(g.get_state(cfg).next) == ("ask",)


def decide(kind: str, hospital_id: str, object_id: str, proposal: dict[str, Any],
           decision: dict[str, Any]) -> dict[str, Any]:
    """Resume a gate with a person's decision. Opens it first if the opener crashed before starting it."""
    cfg = {"configurable": {"thread_id": thread_id(kind, object_id)}}
    with _graph() as g:
        snap = g.get_state(cfg)
        if not snap.values:
            g.invoke({"kind": kind, "hospital_id": hospital_id, "object_id": object_id, "proposal": proposal}, cfg)
            snap = g.get_state(cfg)
        if tuple(snap.next) != ("ask",):
            raise ValueError("this decision was already made")
        out = g.invoke(Command(resume=decision), cfg)
    return dict(out.get("result") or {})
