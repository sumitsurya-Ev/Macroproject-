"""Self-organising: group files nothing matched into candidate NEW folders, and name them."""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

try:
    from .folders import normalize_name
except (ImportError, ValueError):
    from docpilot.folders import normalize_name


def propose_clusters(items, sim_thr: float, min_support: int = 3):
    """items: list of (path, embedding, term_weights).

    Greedy leader clustering by cosine similarity, then name each cluster after the terms
    that are frequent inside it but rare across the other unmatched files.
    -> [{"name", "description", "files"}]
    """
    clusters = []
    for i, (_, v, _) in enumerate(items):
        best, best_s = None, -1.0
        for c in clusters:
            nrm = np.linalg.norm(c["sum"])
            s = float(v @ (c["sum"] / nrm)) if nrm else 0.0
            if s > best_s:
                best, best_s = c, s
        if best is not None and best_s >= sim_thr:
            best["sum"] = best["sum"] + v
            best["members"].append(i)
        else:
            clusters.append({"sum": v.copy(), "members": [i]})

    n = len(items)
    df = Counter()
    for _, _, terms in items:
        df.update(terms.keys())
    out = []
    for c in clusters:
        if len(c["members"]) < min_support:
            continue
        score = Counter()
        for i in c["members"]:
            for t, w in items[i][2].items():
                score[t] += w * math.log((n + 1) / df[t])
        top = [t for t, _ in score.most_common(5)]
        if not top:
            continue
        out.append({
            "name": normalize_name(" ".join(top[:2])),
            "description": "Files about " + ", ".join(top),
            "files": [items[i][0] for i in c["members"]],
        })
    return out
