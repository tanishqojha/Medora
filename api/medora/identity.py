"""Identity resolution (F7, S9). Precision first.

Outcomes:
- auto_merge: only with phone + name + one more strong field (hospital number or birth year), above a strict score.
- review: some evidence, not enough. A person decides.
- apart: keep as separate patients.
Every merge is a patient_merges row with its features, reversible by setting reversed_at.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import jellyfish
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

from medora.config import setting
from medora.hashing import hash_obj

HONORIFICS = {"smt", "shri", "sri", "shrimati", "mr", "mrs", "ms", "miss", "dr", "kumari", "km", "md", "late",
              "श्री", "श्रीमती", "कुमारी", "डॉ"}
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def normalise_phone(raw: Any) -> str | None:
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw).translate(str.maketrans("०१२३४५६७८९", "0123456789")))
    if len(digits) > 10 and digits.startswith(("91", "0")):
        digits = digits[-10:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        return None
    return digits


def to_latin(name: str) -> str:
    """Devanagari to plain Latin letters (ITRANS, simplified) so both scripts compare."""
    if not _DEVANAGARI.search(name):
        return name
    out = []
    for word in name.split():
        s = transliterate(word, sanscript.DEVANAGARI, sanscript.ITRANS)
        for a, b in (("aa", "a"), ("ii", "i"), ("uu", "u"), ("A", "a"), ("I", "i"), ("U", "u"), ("~N", "n"),
                     ("N", "n"), ("M", "n"), (".n", "n"), ("Sh", "sh"), ("R^i", "ri"), (".", "")):
            s = s.replace(a, b)
        # Word-final inherent vowel is not spoken: "राजेश" -> "rajesh", not "rajesha".
        if s.endswith("a") and "क" <= word[-1] <= "ह":
            s = s[:-1]
        out.append(s)
    return " ".join(out)


def normalise_name(raw: Any) -> str:
    if raw is None:
        return ""
    s = unicodedata.normalize("NFC", str(raw)).strip()
    tokens = [t for t in re.split(r"[\s.,]+", s) if t]
    tokens = [t for t in tokens if t.lower().rstrip(".") not in HONORIFICS]
    latin = to_latin(" ".join(tokens)).lower()
    latin = re.sub(r"[^a-z ]", "", latin)
    latin = re.sub(r"(.)\1+", r"\1", latin)  # collapse doubled letters: "sunitaa" ~ "sunita"
    return re.sub(r"\s+", " ", latin).strip()


def phonetic_key(norm_name: str) -> str:
    toks = norm_name.split()
    if not toks:
        return ""
    keep = [toks[0], toks[-1]] if len(toks) > 1 else toks
    return " ".join(jellyfish.metaphone(t) for t in keep)


@dataclass
class Record:
    name: str = ""
    phone: str | None = None
    hospital_number: str | None = None
    sex: str | None = None
    birth_year: int | None = None
    norm_name: str = field(init=False)
    phonetic: str = field(init=False)

    def __post_init__(self) -> None:
        self.norm_name = normalise_name(self.name)
        self.phonetic = phonetic_key(self.norm_name)
        self.phone = normalise_phone(self.phone)
        self.hospital_number = (str(self.hospital_number).strip().upper() or None) if self.hospital_number else None

    def exact_key(self) -> str:
        return hash_obj([self.norm_name, self.phone, self.hospital_number, self.sex, self.birth_year])

    def known_identifiers(self) -> dict[str, list[str]]:
        return {"patient_name": [v for v in [self.name, self.norm_name] if v],
                "phone": [self.phone] if self.phone else [],
                "hospital_number": [self.hospital_number] if self.hospital_number else []}


@dataclass
class Match:
    outcome: str  # auto_merge | review | apart
    score: float
    features: dict[str, Any]


def score(a: Record, b: Record) -> Match:
    f: dict[str, Any] = {
        "phone_match": bool(a.phone and a.phone == b.phone),
        "hospital_number_match": bool(a.hospital_number and a.hospital_number == b.hospital_number),
        "name_similarity": round(jellyfish.jaro_winkler_similarity(a.norm_name, b.norm_name), 4)
        if a.norm_name and b.norm_name else 0.0,
        "phonetic_match": bool(a.phonetic and a.phonetic == b.phonetic),
        "birth_year_match": bool(a.birth_year and b.birth_year and abs(a.birth_year - b.birth_year) <= 1),
        "sex_conflict": bool(a.sex and b.sex and a.sex in "FM" and b.sex in "FM" and a.sex != b.sex),
        "hospital_number_conflict": bool(a.hospital_number and b.hospital_number
                                         and a.hospital_number != b.hospital_number),
    }
    name_ok = f["name_similarity"] >= 0.92 or (f["phonetic_match"] and f["name_similarity"] >= 0.85)
    f["name_match"] = name_ok
    s = (0.35 * f["phone_match"] + 0.25 * f["hospital_number_match"] + 0.25 * f["name_similarity"]
         + 0.10 * f["birth_year_match"] + 0.05 * (not f["sex_conflict"]))
    s = round(s, 4)
    strong = f["phone_match"] and name_ok and (f["hospital_number_match"] or f["birth_year_match"])
    conflict = f["sex_conflict"] or f["hospital_number_conflict"]
    if strong and not conflict and s >= float(setting("identity.auto_merge_min_score")):
        return Match("auto_merge", s, f)
    evidence = f["phone_match"] or f["hospital_number_match"] or name_ok
    if evidence and s >= float(setting("identity.review_min_score")) or (f["hospital_number_match"] and not conflict):
        return Match("review", s, f)
    return Match("apart", s, f)


def best_match(rec: Record, candidates: list[tuple[str, Record]]) -> tuple[str | None, Match]:
    """Pick the strongest candidate. Two auto-merge candidates for different patients go to review."""
    scored = sorted(((pid, score(rec, c)) for pid, c in candidates), key=lambda x: (-x[1].score, x[0]))
    if not scored:
        return None, Match("apart", 0.0, {})
    pid, m = scored[0]
    autos = {p for p, mm in scored if mm.outcome == "auto_merge"}
    if m.outcome == "auto_merge" and len(autos) > 1:
        return pid, Match("review", m.score, {**m.features, "multiple_strong_candidates": len(autos)})
    return pid, m
