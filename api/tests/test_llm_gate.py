"""F5 AC: no non-whitelisted field and no raw identifier ever appears in an LLM request payload."""
import json
from types import SimpleNamespace

import pytest

from medora import llm
from medora.pii import Tokeniser, signature

KNOWN = {"patient_name": ["Sunita Devi", "सुनीता देवी"], "phone": ["9820144521"], "hospital_number": ["PT-63219"]}


class FakeClient:
    sent: list = []

    def __init__(self, reply):
        self.reply = reply
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        FakeClient.sent.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))], usage=None)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    FakeClient.sent = []
    monkeypatch.setattr(llm, "RECORDINGS", tmp_path)
    monkeypatch.setenv("MEDORA_LLM_MODE", "live")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    def install(reply):
        monkeypatch.setattr(llm, "_client", lambda *a: FakeClient(reply))
    return install


def test_rejects_non_whitelisted_key(fake):
    fake('{"reason_code":"cost","confidence":0.9}')
    with pytest.raises(llm.PayloadRejected):
        llm.call("reason_code_v1", {"text_tokenised": "x", "allowed_codes": ["cost"], "diagnosis": "ca colon"})
    assert FakeClient.sent == []


def test_rejects_raw_phone_and_known_name(fake):
    fake('{"reason_code":"cost","confidence":0.9}')
    with pytest.raises(llm.PayloadRejected):
        llm.call("reason_code_v1", {"text_tokenised": "call 98201 44521", "allowed_codes": ["cost"]})
    with pytest.raises(llm.PayloadRejected):
        llm.call("reason_code_v1", {"text_tokenised": "Sunita Devi said cost", "allowed_codes": ["cost"]}, KNOWN)
    assert FakeClient.sent == []


def test_tokenised_text_passes_and_payload_is_clean(fake):
    fake('{"reason_code":"cost","confidence":0.9}')
    t = Tokeniser()
    text = t.tokenise("Spoke to Sunita Devi on 9820144521, PT-63219. सुनीता देवी said bus fare is too much.", KNOWN)
    out, meta = llm.call("reason_code_v1", {"text_tokenised": text, "allowed_codes": ["cost", "other"]}, KNOWN)
    assert out == {"reason_code": "cost", "confidence": 0.9}
    payload = json.dumps(FakeClient.sent[0]["messages"], ensure_ascii=False)
    for raw in ["Sunita", "सुनीता", "9820144521", "PT-63219"]:
        assert raw not in payload
    assert FakeClient.sent[0]["temperature"] == 0
    assert meta["prompt_version"] == "reason_code_v1"


def test_mapping_sample_is_shape_only(fake):
    fake('{"columns":[{"header":"Mobile","field":"phone","confidence":0.95}],"date_convention_guess":"unknown"}')
    sample = [[signature(v) for v in ["Sunita Devi", "9820144521", "03/04/2026", "PT-63219"]]]
    llm.call("mapping_v1",
             {"headers": ["Name", "Mobile", "Date", "MRN"], "sample_rows": sample, "target_fields": ["phone"]}, KNOWN)
    payload = json.dumps(FakeClient.sent[0]["messages"])
    assert "Sunita" not in payload and "9820144521" not in payload and "PT-63219" not in payload


def test_unknown_fields_dropped_and_invalid_output_fails_closed(fake):
    fake('{"reason_code":"cost","confidence":0.9,"advice":"take rest"}')
    out, _ = llm.call("reason_code_v1", {"text_tokenised": "x", "allowed_codes": ["cost"]})
    assert "advice" not in out
    fake('{"reason_code":"new_code_made_up","confidence":0.9}')
    with pytest.raises(llm.LLMUnavailable):
        llm.call("reason_code_v1", {"text_tokenised": "y", "allowed_codes": ["cost"]})
    fake("not json")
    with pytest.raises(llm.LLMUnavailable):
        llm.call("reason_code_v1", {"text_tokenised": "z", "allowed_codes": ["cost"]})


def test_provider_error_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "RECORDINGS", tmp_path)
    monkeypatch.setenv("MEDORA_LLM_MODE", "live")
    monkeypatch.setenv("LLM_MODEL", "m")

    def boom(*a):
        raise TimeoutError
    monkeypatch.setattr(llm, "_client", lambda *a: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=boom))))
    with pytest.raises(llm.LLMUnavailable):
        llm.call("reason_code_v1", {"text_tokenised": "x", "allowed_codes": ["cost"]})


def test_no_key_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "RECORDINGS", tmp_path)
    monkeypatch.setenv("MEDORA_LLM_MODE", "live")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", "")
    with pytest.raises(llm.LLMUnavailable):
        llm.call("reason_code_v1", {"text_tokenised": "x", "allowed_codes": ["cost"]})


def test_record_then_replay(fake, monkeypatch):
    fake('{"reason_code":"distance","confidence":0.8}')
    inputs = {"text_tokenised": "too far", "allowed_codes": ["distance"]}
    live, _ = llm.call("reason_code_v1", inputs)
    monkeypatch.setenv("MEDORA_LLM_MODE", "replay")
    replayed, meta = llm.call("reason_code_v1", inputs)
    assert replayed == live and meta["replay"] is True
    with pytest.raises(llm.LLMUnavailable):
        llm.call("reason_code_v1", {"text_tokenised": "never recorded", "allowed_codes": ["distance"]})


def test_vision_uses_its_own_provider_vars(fake, monkeypatch):
    used = []
    monkeypatch.setattr(llm, "_client", lambda *a: used.append(a) or FakeClient('{"reason_code":"cost","confidence":0.9}'))
    llm.call("reason_code_v1", {"text_tokenised": "x", "allowed_codes": ["cost"]})
    with pytest.raises(llm.LLMUnavailable):  # reply shape is wrong for vision; we only check which provider was asked
        llm.call("vision_extract_v1", {"image_crop": b"x", "fields": ["event_date"], "page_hint": "p"},
                 model_var="VISION_MODEL")
    assert used == [("LLM_BASE_URL", "LLM_API_KEY"), ("VISION_BASE_URL", "VISION_API_KEY")]
