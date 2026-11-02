"""Confidence fusion: combine independent signals into one calibrated-ish confidence."""
from __future__ import annotations

import json
import math
from pathlib import Path

AUTO = 0.85       # auto-move (with undo). Tune until auto-move precision >= 97% on your own data.
SUGGEST = 0.55    # one-click confirm. Below this: escalate to LLM tiers, then review queue.

DEFAULT_WEIGHTS = {
    "rules": 1.2, "embed": 1.0, "terms": 1.1, "knn": 0.9, "prior": 0.6, "name": 0.5,
    "llm_local": 1.3, "llm_cloud": 1.5,
}


class Weights:
    """Per-signal trust, learned from user feedback (multiplicative update)."""

    def __init__(self, w: dict | None = None):
        self.w = dict(DEFAULT_WEIGHTS)
        self.w.update(w or {})

    def get(self, sig: str, default: float = 1.0) -> float:
        return self.w.get(sig, default)

    def update(self, scores: dict, correct: str, lr: float = 0.08):
        for sig, dist in scores.items():
            if not dist:
                continue
            top = max(dist, key=dist.get)
            factor = 1 + lr if top == correct else 1 - lr
            self.w[sig] = min(3.0, max(0.2, self.get(sig) * factor))


def fuse(scores: dict, weights: Weights) -> dict:
    """Weighted geometric mean over folders. Signals that abstained are simply not in `scores`."""
    folders = set()
    for d in scores.values():
        if d:
            folders |= set(d)
    if not folders:
        return {}
    n_folders = len(folders)
    neutral = 1.0 / n_folders
    floor = 0.05 / n_folders
    logp = {f: 0.0 for f in folders}
    wsum = {f: 0.0 for f in folders}
    for sig, dist in scores.items():
        if not dist:
            continue
        w = weights.get(sig, 1.0)
        is_exemplar = sig in ("embed", "terms", "knn")
        for f in folders:
            if f in dist:
                logp[f] += w * math.log(dist[f] + 1e-9)
                wsum[f] += w
            else:
                if is_exemplar:
                    logp[f] += w * math.log(neutral)
                    wsum[f] += w
                else:
                    logp[f] += w * math.log(floor + 1e-9)
                    wsum[f] += w
    if not any(wsum.values()):
        return {}
    p = {f: math.exp(logp[f] / max(wsum[f], 1e-9)) for f in folders}
    z = sum(p.values())
    return {f: v / z for f, v in p.items()} if z > 0 else {}


def confidence(p: dict, scores: dict, ocr_conf: float):
    """-> (top_folder, runner_up, confidence 0..1).

    0.5*top probability + 0.3*margin over runner-up + 0.2*share of signals that agree,
    then a penalty for poor OCR. Never auto-move on a single signal.
    """
    if not p:
        return "", None, 0.0
    ranked = sorted(p.items(), key=lambda kv: -kv[1])
    top, p1 = ranked[0]
    alt, p2 = (ranked[1] if len(ranked) > 1 else (None, 0.0))
    eval_scores = [d for d in scores.values() if d and (top in d or len(d) > 1)]
    votes = sum(1 for d in scores.values() if d and max(d, key=d.get) == top)
    agree = votes / max(1, len(eval_scores)) if eval_scores else (votes / max(1, len(scores)))
    conf = 0.5 * p1 + 0.3 * (p1 - p2) + 0.2 * agree
    conf *= 0.5 + 0.5 * max(0.0, min(1.0, ocr_conf))
    if votes < 2 and len(scores) < 2:
        conf = min(conf, AUTO - 0.01)
    return top, alt, min(0.99, max(0.0, conf))


def load_weights(path: Path) -> Weights:
    try:
        return Weights(json.loads(Path(path).read_text()))
    except Exception:
        return Weights()
