"""S15: a seeded run reproduces byte-identical output, and the data is labelled synthetic."""
import hashlib
import json

from medora import synth


def _digest(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}


def test_seeded_build_is_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    synth.build(a, n_patients=60, seed=7, photos=1)
    synth.build(b, n_patients=60, seed=7, photos=1)
    assert _digest(a) == _digest(b)
    assert json.loads((a / "meta.json").read_text())["synthetic"] is True


def test_corruptions_are_recorded(tmp_path):
    ds = synth.build(tmp_path, n_patients=300, seed=42, photos=0)
    kinds = {c for r in ds.rows for c in r["corruptions"]}
    assert {"typo", "swap_dm", "phone_format", "duplicate_registration"} <= kinds
