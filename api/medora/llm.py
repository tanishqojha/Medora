"""The single gate for every LLM and ASR call (F5, S10, S23, Rules 4).

- Inputs must use whitelisted keys for the task and carry no raw identifier, checked before any network call.
- Prompts live in prompts/<name>.md with a version. No inline prompt strings.
- Temperature 0, JSON output validated against a schema, unknown fields dropped.
- Record/replay: live mode records responses, replay mode serves recordings only and fails loudly on a miss.
- Any failure raises LLMUnavailable. Callers route to a human (fail closed).
"""
from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from medora import whitelist
from medora.config import ROOT, env, setting
from medora.hashing import canonical, sha256
from medora.pii import contains_raw_identifier

log = logging.getLogger("medora.llm")
PROMPTS = ROOT / "prompts"
RECORDINGS = ROOT / "recordings"


class LLMUnavailable(RuntimeError):
    """Provider missing, errored, timed out, replay miss or invalid output. Route to a human."""


class PayloadRejected(ValueError):
    """The request would have sent non-whitelisted data or a raw identifier. Never sent."""


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    task: str
    body: str
    schema: dict[str, Any]


def load_prompt(name: str) -> Prompt:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    meta = dict(line.split(":", 1) for line in front.strip().splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    schema = json.loads((PROMPTS / f"{name}.schema.json").read_text(encoding="utf-8"))
    return Prompt(name=name, version=meta["version"], task=meta["task"], body=body.strip(), schema=schema)


def mode() -> str:
    return env("MEDORA_LLM_MODE", "live")


def check_payload(task: str, inputs: dict[str, Any], known: dict[str, list[str]] | None = None) -> None:
    allowed = whitelist.llm_task_inputs(task)
    extra = set(inputs) - allowed
    if extra:
        raise PayloadRejected(f"task {task} may not send {sorted(extra)}")
    text_inputs = {k: v for k, v in inputs.items() if k != "image_crop"}
    if contains_raw_identifier(canonical(text_inputs), known):
        raise PayloadRejected("payload contains a raw identifier")


def _drop_unknown(data: Any, schema: dict[str, Any]) -> Any:
    if schema.get("type") == "object" and isinstance(data, dict):
        props = schema.get("properties", {})
        return {k: _drop_unknown(v, props[k]) for k, v in data.items() if k in props}
    if schema.get("type") == "array" and isinstance(data, list) and "items" in schema:
        return [_drop_unknown(x, schema["items"]) for x in data]
    return data


def _recording_path(key: str) -> Path:
    return RECORDINGS / f"{key}.json"


def _client(base_url_var: str, key_var: str) -> Any:
    from openai import OpenAI

    key = env(key_var) or env("LLM_API_KEY")
    base = env(base_url_var) or env("LLM_BASE_URL")
    if not key or not base:
        raise LLMUnavailable("no LLM provider configured")
    return OpenAI(api_key=key, base_url=base, timeout=float(setting("llm.timeout_seconds")), max_retries=1)


def call(prompt_name: str, inputs: dict[str, Any], known: dict[str, list[str]] | None = None,
         model_var: str = "LLM_MODEL") -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (validated_output, meta). meta has prompt_version, model, replay, tokens, latency_ms."""
    p = load_prompt(prompt_name)
    check_payload(p.task, inputs, known)
    model = env(model_var) or env("LLM_MODEL")
    image = inputs.get("image_crop")
    text_inputs = {k: v for k, v in inputs.items() if k != "image_crop"}
    key = sha256(canonical({"prompt": p.name, "v": p.version, "in": text_inputs,
                            "img": sha256(image) if image else None}))
    meta: dict[str, Any] = {"prompt": p.name, "prompt_version": p.version, "model": model, "replay": False,
                            "input_hash": key[:16]}
    started = time.monotonic()
    raw: str
    if mode() == "replay":
        path = _recording_path(key)
        if not path.exists():
            log.error("replay miss", extra=meta)
            raise LLMUnavailable(f"replay mode: no recording for {p.name} {key[:12]}")
        rec = json.loads(path.read_text(encoding="utf-8"))
        raw, meta["replay"], meta["model"] = rec["response"], True, rec["model"]
    else:
        if not model:
            raise LLMUnavailable("no model configured")
        content: Any = p.body.replace("{{inputs}}", canonical(text_inputs))
        if image:
            content = [{"type": "text", "text": content},
                       {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()}}]
        try:
            # Vision may use its own provider (VISION_BASE_URL / VISION_API_KEY); unset falls back to LLM_*.
            prefix = "VISION" if model_var == "VISION_MODEL" else "LLM"
            resp = _client(f"{prefix}_BASE_URL", f"{prefix}_API_KEY").chat.completions.create(
                model=model, temperature=0, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": "Reply with one JSON object only."},
                          {"role": "user", "content": content}],
            )
        except LLMUnavailable:
            raise
        except Exception as e:
            log.error("llm call failed", extra={**meta, "error": type(e).__name__})
            raise LLMUnavailable(f"provider error: {type(e).__name__}") from e
        raw = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        meta["tokens_in"] = getattr(usage, "prompt_tokens", None)
        meta["tokens_out"] = getattr(usage, "completion_tokens", None)
        RECORDINGS.mkdir(exist_ok=True)
        _recording_path(key).write_text(json.dumps(
            {"prompt": p.name, "prompt_version": p.version, "model": model, "response": raw}, ensure_ascii=False),
            encoding="utf-8")
    meta["latency_ms"] = int((time.monotonic() - started) * 1000)
    try:
        data = _drop_unknown(json.loads(raw), p.schema)
        jsonschema.validate(data, p.schema)
    except (json.JSONDecodeError, jsonschema.ValidationError) as e:
        log.error("llm output invalid", extra={**meta, "error": type(e).__name__})
        raise LLMUnavailable("output failed schema validation") from e
    log.info("llm call", extra=meta)
    return data, meta


def transcribe(audio: bytes, filename: str, language: str | None = None) -> tuple[str, dict[str, Any]]:
    """ASR via an OpenAI-compatible /audio/transcriptions endpoint. Same record/replay rules."""
    model = env("ASR_MODEL")
    key = sha256(canonical({"asr": model, "audio": sha256(audio), "lang": language}))
    meta: dict[str, Any] = {"prompt": "asr", "model": model, "replay": False, "input_hash": key[:16]}
    path = _recording_path(key)
    if mode() == "replay":
        if not path.exists():
            raise LLMUnavailable("replay mode: no ASR recording")
        rec = json.loads(path.read_text(encoding="utf-8"))
        meta["replay"] = True
        return rec["response"], meta
    if not model:
        raise LLMUnavailable("no ASR model configured")
    started = time.monotonic()
    try:
        kwargs: dict[str, Any] = {"model": model, "file": (filename, audio), "temperature": 0}
        if language:
            kwargs["language"] = language
        text = _client("ASR_BASE_URL", "ASR_API_KEY").audio.transcriptions.create(**kwargs).text
    except LLMUnavailable:
        raise
    except Exception as e:
        log.error("asr failed", extra={**meta, "error": type(e).__name__})
        raise LLMUnavailable(f"ASR error: {type(e).__name__}") from e
    meta["latency_ms"] = int((time.monotonic() - started) * 1000)
    RECORDINGS.mkdir(exist_ok=True)
    path.write_text(json.dumps({"prompt": "asr", "model": model, "response": text}, ensure_ascii=False),
                    encoding="utf-8")
    log.info("asr call", extra=meta)
    return text, meta
