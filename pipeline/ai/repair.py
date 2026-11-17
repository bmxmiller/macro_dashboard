"""Deterministic, wording-only clean-up of an LLM answer BEFORE the fact checker runs.

Models keep tripping the validator on harmless style slips (a leaked snake_case field name). Burning a whole provider attempt on those wastes free-tier quota, so we fix the
slips in code. Rules for this module:

* Advice/prediction words ("guarantee", "will rise") are deliberately NOT rewritten: swapping them
  would hide a prediction instead of rejecting it, so the validator still rejects and retries.
* It never touches digits, units or signs, so it cannot make a wrong number pass.
* The repaired answer still goes through the full validator.
"""
from __future__ import annotations

import re
from typing import Any

from .validate import SKIP_KEYS

# "a level_pct of 5.15" / "the ret_1w_pct of -0.4%" -> "" (the number then follows the metric name)
_FIELD_OF = re.compile(r"\b(?:an?|the)\s+(?:[a-z][a-z0-9]*(?:_[a-z0-9]+)+)\s+of\s+", re.IGNORECASE)
_FIELD = re.compile(r"\s*\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")


def repair_text(text: str) -> str:
    t = _FIELD_OF.sub("", text)
    t = _FIELD.sub("", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def repair(obj: Any) -> Any:
    """A copy of the LLM output with every free-text string cleaned (ids/tags/urls left alone)."""
    if isinstance(obj, str):
        return repair_text(obj)
    if isinstance(obj, dict):
        return {k: (v if k in SKIP_KEYS else repair(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [repair(v) for v in obj]
    return obj
