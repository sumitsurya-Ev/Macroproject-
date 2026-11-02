"""LLM tiers (local Ollama, then cloud Gemini / OpenAI / Grok) with PII masking.

All of these speak the OpenAI-compatible chat API, so one adapter covers every provider:
  Ollama (local) : base_url="http://localhost:11434/v1", api_key="ollama"
  OpenAI         : base_url=None
  Gemini         : base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
  Grok (xAI)     : base_url="https://api.x.ai/v1"
Model names change often, so `model` is always passed in by you.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    from .folders import normalize_name
    from .textutil import canonical
    from .types import Doc
except (ImportError, ValueError):
    from folders import normalize_name
    from textutil import canonical
    from docpilot.types import Doc

_MASKS = [
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[AADHAAR]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"), "[PHONE]"),
    (re.compile(r"\b\d{9,18}\b"), "[NUMBER]"),
]


def mask_pii(text: str) -> str:
    for rx, tag in _MASKS:
        text = rx.sub(tag, text)
    return text


def openai_compatible(model: str, api_key: str, base_url: Optional[str] = None, timeout: float = 20):
    """-> complete(prompt) -> str"""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def complete(prompt: str) -> str:
        r = client.chat.completions.create(
            model=model, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content or ""

    return complete


def build_prompt(snippet: str, filename: str, cands: list[str], descriptions: dict) -> str:
    folders = "\n".join(f"- {c}" + (f": {descriptions[c]}" if c in descriptions else "") for c in cands)
    return (
        "You file documents into folders. Choose the best existing folder, or propose a new one "
        "ONLY if none fits.\n\nExisting folders:\n" + folders +
        f"\n\nFile name: {filename}\nContent (may be truncated):\n\"\"\"\n{snippet}\n\"\"\"\n\n"
        'Reply with JSON only: {"folder": "<existing folder or null>", "confidence": 0.0-1.0, '
        '"is_new": true|false, "new_name": "<1-3 words or null>", "description": "<one sentence>"}'
    )


def parse_response(raw: str):
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
        j["confidence"] = max(0.0, min(1.0, float(j.get("confidence", 0))))
        return j
    except Exception:
        return None


@dataclass
class Verdict:
    dist: dict = field(default_factory=dict)
    confidence: float = 0.0
    is_new: bool = False
    name: str = ""
    description: str = ""


class LLMTier:
    def __init__(self, name: str, complete: Callable[[str], str], cloud: bool, max_chars: int = 1500):
        self.name, self.complete, self.cloud = name, complete, cloud   # name: "llm_local" | "llm_cloud"
        self.max_chars = 800 if cloud else max_chars

    def classify(self, doc: Doc, cands: list[str], descriptions: dict | None = None):
        snippet, fname = doc.text[: self.max_chars], doc.name
        if self.cloud:                                    # opt-in, short and masked only
            snippet, fname = mask_pii(snippet), mask_pii(fname)
        try:
            j = parse_response(self.complete(build_prompt(snippet, fname, cands, descriptions or {})))
        except Exception:
            return None                                   # offline / quota / timeout: caller falls through
        if not j:
            return None
        conf = j["confidence"]
        folder = next((c for c in cands if canonical(c) == canonical(str(j.get("folder") or ""))), None)
        if j.get("is_new") or not folder:
            name = normalize_name(str(j.get("new_name") or j.get("folder") or ""))
            return Verdict(is_new=True, confidence=conf, name=name, description=str(j.get("description", "")))
        rest = (1 - conf) / max(1, len(cands) - 1)
        return Verdict(dist={c: (conf if c == folder else rest) for c in cands}, confidence=conf)
