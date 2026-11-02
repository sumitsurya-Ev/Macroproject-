"""Domain-agnostic learners. None of these know any domain in advance: they learn it from your files.

TermModel   online naive Bayes over each folder's vocabulary (any language, any domain)
ExemplarKNN nearest already-filed files (catches folders with several distinct sub-topics)
NamePrior   cold start: match a file against folder NAMES/descriptions, so a brand-new
            or empty folder works before it has any files in it

Every learner supports unlearning (sign=-1 / remove) so corrections undo the wrong lesson.
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

try:
    from .textutil import content_tokens, filename_tokens, softmax, stem_word
    from .doc_types import Doc
except (ImportError, ValueError):
    from docpilot.textutil import content_tokens, filename_tokens, softmax, stem_word
    from docpilot.doc_types import Doc


def doc_terms(doc: Doc) -> Counter:
    toks = (
        content_tokens(doc.text[:8000])
        + filename_tokens(doc.name) * 2
        + content_tokens(str(doc.meta.get("title", "")))
    )
    return Counter({t: 1 + math.log(n) for t, n in Counter(toks).items()})


# ================================================================= online naive Bayes
class TermModel:
    ALPHA = 0.1

    def __init__(self):
        self.tc: dict[str, dict[str, float]] = {}   # term -> {folder: weight}
        self.ft: dict[str, float] = {}              # folder -> total term weight
        self.nd: Counter = Counter()                # folder -> number of docs

    def add(self, doc: Doc, folder: str, sign: int = 1):
        terms = doc_terms(doc)
        for t, w in terms.items():
            d = self.tc.setdefault(t, {})
            v = d.get(folder, 0.0) + sign * w
            if v > 1e-9:
                d[folder] = v
            else:
                d.pop(folder, None)
            if not d:
                self.tc.pop(t, None)
        self.ft[folder] = max(0.0, self.ft.get(folder, 0.0) + sign * sum(terms.values()))
        self.nd[folder] += sign
        if self.nd[folder] <= 0:
            self.nd.pop(folder, None)
            self.ft.pop(folder, None)

    def scores(self, doc: Doc):
        folders = [f for f, n in self.nd.items() if n > 0]
        if len(folders) < 2:                         # nothing to discriminate between
            return None
        known = {t: w for t, w in doc_terms(doc).items() if t in self.tc}
        if len(known) < 3:                           # an unfamiliar domain: abstain, do not guess
            return None
        use = sorted(known.items(), key=lambda kv: -kv[1])[:150]
        V, a = len(self.tc), self.ALPHA
        ntot = sum(self.nd[f] for f in folders)
        logp = {f: 0.5 * math.log(self.nd[f] / ntot) for f in folders}
        for t, w in use:
            d = self.tc[t]
            for f in folders:
                logp[f] += w * math.log((d.get(f, 0.0) + a) / (self.ft[f] + a * V))
        n = math.sqrt(sum(w for _, w in use))        # length-normalise: NB is overconfident on long docs
        return softmax({f: v / n for f, v in logp.items()})

    def to_json(self):
        return {"tc": self.tc, "ft": self.ft, "nd": dict(self.nd)}

    def load(self, data: dict):
        self.tc = {t: dict(d) for t, d in data.get("tc", {}).items()}
        self.ft = dict(data.get("ft", {}))
        self.nd = Counter(data.get("nd", {}))


# ================================================================= nearest filed files
class ExemplarKNN:
    def __init__(self, min_sim: float, k: int = 5, cap: int = 150):
        self.min_sim, self.k, self.cap = min_sim, k, cap
        self.items: dict[str, list] = {}

    def add(self, folder: str, vec):
        lst = self.items.setdefault(folder, [])
        lst.append(vec)
        if len(lst) > self.cap:
            lst.pop(0)

    def remove(self, folder: str, vec):
        lst = self.items.get(folder)
        if not lst:
            return
        sims = [float(vec @ v) for v in lst]
        i = int(np.argmax(sims))
        if sims[i] > 0.98:
            lst.pop(i)
        if not lst:
            self.items.pop(folder, None)

    def scores(self, vec):
        if len(self.items) < 2:
            return None
        pairs = sorted(((float(vec @ v), f) for f, lst in self.items.items() for v in lst), reverse=True)
        top = pairs[: self.k]
        if not top or top[0][0] < self.min_sim:
            return None
        votes = {f: 0.01 for f in self.items}
        for s, f in top:
            votes[f] += max(0.0, s) ** 2             # closer neighbours count more
        z = sum(votes.values())
        return {f: v / z for f, v in votes.items()}

    def to_json(self):
        return {f: [np.round(v, 4).tolist() for v in lst] for f, lst in self.items.items()}

    def load(self, data: dict):
        self.items = {f: [np.asarray(v, dtype=np.float32) for v in lst] for f, lst in data.items()}


# ================================================================= cold start
class NamePrior:
    """Folders with fewer than `min_n` files are matched by their name + description instead."""

    def __init__(self, embedder, min_n: int = 3):
        self.emb, self.min_n, self._cache = embedder, min_n, {}

    def _vec(self, folder: str, desc: str):
        key = (folder, desc)
        if key not in self._cache:
            label = folder.replace("/", " ").replace("_", " ").replace("-", " ")
            stems = " ".join(stem_word(w) for w in label.lower().split() if w)
            self._cache[key] = self.emb.embed(f"{label} {stems} {desc}".strip())
        return self._cache[key]

    def scores(self, docvec, cands, descriptions: dict, counts, text: str = ""):
        cold = [f for f in cands if counts.get(f, 0) < self.min_n]
        if not cold:
            return None
        sims = {f: float(docvec @ self._vec(f, descriptions.get(f, ""))) for f in cold}
        if text:
            doc_toks = set(text.lower().split())
            for f in cold:
                f_words = set(f.lower().replace("/", " ").replace("_", " ").replace("-", " ").split())
                f_stems = {stem_word(w) for w in f_words}
                if f_words & doc_toks or f_stems & doc_toks:
                    sims[f] = max(sims[f], 0.45)
        if max(sims.values(), default=0.0) < max(self.emb.min_sim, 0.2):
            return None
        warm = [f for f in cands if f not in sims]
        dist = {f: (0.2 / len(warm)) if warm else 0.0 for f in warm}
        for f, p in softmax(sims, 0.1).items():
            dist[f] = 0.8 * p
        return dist
