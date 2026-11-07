"""Symptom tripwire (F14). Two-key file. Recall over precision: on any doubt, route to a person.

It never decides what a symptom means. It only answers: does a person need to see this text?
Config (keywords, routes, refusal copy) lives in config/tripwire.yaml and needs clinician approval.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import jellyfish

from medora.config import load_yaml

_LATIN_WORD = re.compile(r"[a-z']+")


@dataclass
class TripResult:
    routed: bool
    route: str | None = None                     # nurse | clinician
    categories: list[str] = field(default_factory=list)
    matched: list[dict[str, str]] = field(default_factory=list)
    reason: str = ""
    refusal: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"routed": self.routed, "route": self.route, "categories": self.categories, "matched": self.matched,
                "reason": self.reason, "refusal": self.refusal}


def _cfg() -> dict[str, Any]:
    return load_yaml("tripwire.yaml")


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFC", text).lower()
    t = t.replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", t).strip()


def _match_latin(term: str, text: str, tokens: list[str]) -> bool:
    if re.search(r"(?<![a-z])" + re.escape(term) + r"(?![a-z])", text):
        return True
    if " " not in term and len(term) >= 5:  # one typo tolerated on longer single words: "bleding", "vomitting"
        return any(abs(len(t) - len(term)) <= 2 and jellyfish.damerau_levenshtein_distance(t, term) <= 1
                   for t in tokens)
    return False


def check(text: str | None) -> TripResult:
    if not text or not text.strip():
        return TripResult(False, reason="empty")
    cfg = _cfg()
    t = _norm(text)
    tokens = _LATIN_WORD.findall(t)
    hits: list[dict[str, str]] = []
    cats: list[str] = []
    for cat, langs in cfg["keywords"].items():
        for lang, terms in langs.items():
            for term in terms:
                term_n = _norm(str(term))
                ok = (term_n in t) if lang == "hi_deva" else _match_latin(term_n, t, tokens)
                if ok:
                    hits.append({"category": cat, "term": term_n})
                    if cat not in cats:
                        cats.append(cat)
    if not cats:
        for lang, terms in cfg["doubt_markers"].items():
            for term in terms:
                term_n = _norm(str(term))
                if (term_n in t) if lang == "hi_deva" else _match_latin(term_n, t, tokens):
                    hits.append({"category": "doubt", "term": term_n})
        if hits:
            cats = ["doubt"]
    if not cats:
        return TripResult(False, reason="no symptom or medical language found")
    routes = cfg["routes"]
    # Clinician outranks nurse when both apply; doubt goes to the nurse.
    route = "clinician" if any(routes.get(c) == "clinician" for c in cats) else "nurse"
    refusal = cfg["refusal_text"] if "medical_question" in cats else None
    return TripResult(True, route, cats, hits, reason=f"matched {', '.join(cats)}", refusal=refusal)
