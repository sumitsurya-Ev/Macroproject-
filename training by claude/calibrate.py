"""Self-tuning thresholds.

Every time the user confirms or corrects a decision (or an evaluation runs on the library),
we log (confidence, was_it_right). The auto-move threshold is then the LOWEST confidence at
which everything above it is still at least `target` precise (default 97%).
So the system measures its own reliability instead of trusting hand-picked numbers.
"""
from __future__ import annotations

import json
from pathlib import Path

BIN = 0.05


class Calibrator:
    def __init__(self, path=None, target: float = 0.97, min_samples: int = 30,
                 auto_default: float = 0.85, suggest_default: float = 0.55, keep: int = 3000):
        self.path = Path(path) if path else None
        self.target, self.min_samples, self.keep = target, min_samples, keep
        self.auto_default, self.suggest_default = auto_default, suggest_default
        self.log: dict[str, tuple[float, bool]] = {}
        if self.path and self.path.exists():
            try:
                for k, c, ok in json.loads(self.path.read_text())["log"]:
                    self.log[k] = (float(c), bool(ok))
            except Exception:
                pass

    def record(self, key: str, conf: float, correct: bool):
        self.log.pop(key, None)
        self.log[key] = (conf, correct)
        while len(self.log) > self.keep:
            self.log.pop(next(iter(self.log)))

    def set_outcome(self, key: str, correct: bool):
        if key in self.log:
            self.log[key] = (self.log[key][0], correct)

    def bulk(self, pairs, prefix: str = "eval"):
        for k in [k for k in self.log if k.startswith(prefix + ":")]:
            del self.log[k]
        for i, (c, ok) in enumerate(pairs):
            self.log[f"{prefix}:{i}"] = (float(c), bool(ok))

    @staticmethod
    def _cut(data, target: float, tol: float, min_n: int, default: float):
        """Walk confidence bins from the top; stop when precision (cumulative or in-bin) drops."""
        bins: dict[int, list] = {}
        for c, ok in data:
            b = bins.setdefault(min(int(c / BIN + 1e-9), int(1 / BIN)), [0, 0])
            b[0] += 1
            b[1] += int(ok)
        n = hit = 0
        best = None
        for idx in sorted(bins, reverse=True):
            bn, bok = bins[idx]
            n, hit = n + bn, hit + bok
            if hit / n < target or (bn >= 5 and bok / bn < target - tol):
                break
            if n >= min_n:
                best = round(idx * BIN, 3)
        return best if best is not None else default

    def thresholds(self):
        """-> (auto, suggest). auto=1.01 means 'never auto-move: precision target not reachable yet'."""
        data = list(self.log.values())
        if len(data) < self.min_samples:
            return self.auto_default, self.suggest_default
        auto = self._cut(data, self.target, 0.07, 10, 1.01)
        auto = min(max(auto, 0.70), 1.01)
        suggest = self._cut(data, 0.80, 0.15, 10, self.suggest_default)
        return auto, min(suggest, auto - 0.05)

    def save(self):
        if self.path:
            self.path.write_text(json.dumps({"log": [[k, c, ok] for k, (c, ok) in self.log.items()]}))
