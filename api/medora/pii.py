"""Tokenisation before any LLM call (F5, Rules 2.4). The token map never leaves this process.

Three layers, strongest first:
1. Known identifiers for the record at hand (names, phones, hospital numbers) are replaced exactly.
2. Regex recognisers for Indian phone numbers, hospital numbers and long digit runs.
3. Presidio (spaCy small model) for PERSON and PHONE_NUMBER in Latin-script text.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

log = logging.getLogger("medora.pii")

PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
HOSPNO_RE = re.compile(r"\b(?:[A-Z]{2,5}[-/]?\d{4,}|\d{6,})\b")
LONG_DIGITS_RE = re.compile(r"\d{7,}")
TOKEN_RE = re.compile(r"<(?:NAME|PHONE|ID|PERSON)_\d+>")


@lru_cache
def _analyzer() -> Any:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]})
    return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])


@dataclass
class Tokeniser:
    """One per LLM request. `mapping` is token -> original value and stays local."""
    mapping: dict[str, str] = field(default_factory=dict)
    _counter: dict[str, int] = field(default_factory=dict)

    def _token(self, kind: str, value: str) -> str:
        for tok, v in self.mapping.items():
            if v == value and tok.startswith(f"<{kind}_"):
                return tok
        n = self._counter.get(kind, 0) + 1
        self._counter[kind] = n
        tok = f"<{kind}_{n}>"
        self.mapping[tok] = value
        return tok

    def tokenise(self, text: str, known: dict[str, list[str]] | None = None, use_presidio: bool = True) -> str:
        for kind, values in (known or {}).items():
            label = {"patient_name": "NAME", "phone": "PHONE", "hospital_number": "ID"}.get(kind, "ID")
            for v in sorted((v for v in values if v and len(v) >= 2), key=len, reverse=True):
                tok = self._token(label, v)
                text = re.compile(re.escape(v), re.IGNORECASE).sub(tok, text)
        text = PHONE_RE.sub(lambda m: self._token("PHONE", m.group(0)), text)
        text = HOSPNO_RE.sub(lambda m: self._token("ID", m.group(0)), text)
        if use_presidio and text.strip():
            text = self._presidio(text)
        return text

    def _presidio(self, text: str) -> str:
        try:
            results = _analyzer().analyze(text=text, language="en", entities=["PERSON", "PHONE_NUMBER"])
        except Exception as e:  # fail closed: if Presidio breaks, the caller must not send
            log.error("presidio failed", extra={"error": type(e).__name__})
            raise
        for r in sorted(results, key=lambda r: r.start, reverse=True):
            span = text[r.start:r.end]
            if TOKEN_RE.fullmatch(span):
                continue
            kind = "PERSON" if r.entity_type == "PERSON" else "PHONE"
            text = text[:r.start] + self._token(kind, span) + text[r.end:]
        return text

    def detokenise(self, text: str) -> str:
        for tok, v in self.mapping.items():
            text = text.replace(tok, v)
        return text


def signature(value: object) -> str:
    """Shape of a cell without its content. Used for the masked mapping sample (F3)."""
    if value is None:
        return "<EMPTY>"
    s = str(value).strip()
    if not s:
        return "<EMPTY>"
    if PHONE_RE.fullmatch(s):
        return "<PHONE>"
    if re.fullmatch(r"[\d०-९]{1,2}[-/.][\d०-९]{1,2}[-/.][\d०-९]{2,4}", s):
        return "<DATE d/m/y or m/d/y>"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", s):
        return "<DATE iso>"
    if re.fullmatch(r"\d+(\.\d+)?", s):
        n = float(s)
        if 20000 <= n <= 80000:
            return "<NUMBER maybe excel date>"
        return f"<NUMBER {len(s.split('.')[0])} digits>"
    if HOSPNO_RE.fullmatch(s):
        return "<ID>"
    if re.search(r"[ऀ-ॿ]", s):
        return f"<TEXT devanagari {len(s.split())} words>"
    words = s.split()
    caps = all(w[:1].isupper() for w in words if w[:1].isalpha())
    return f"<TEXT {len(words)} words{' capitalised' if caps else ''}>"


def contains_raw_identifier(text: str, known: dict[str, list[str]] | None = None) -> bool:
    """Gate check used by llm.call: true if a phone, id or known identifier is still visible."""
    stripped = TOKEN_RE.sub("", text)
    if PHONE_RE.search(stripped) or LONG_DIGITS_RE.search(stripped):
        return True
    for values in (known or {}).values():
        for v in values:
            if v and len(v) >= 3 and v.lower() in stripped.lower():
                return True
    return False
