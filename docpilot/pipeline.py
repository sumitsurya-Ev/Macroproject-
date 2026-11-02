"""DocPilot pipeline: capture -> extract -> signals -> fuse -> (escalate) -> decide -> move/learn.

Self-training loop (no manual training step):
  sync()      learns from the library as the user organised it, and from files the user moves by hand
  file()      learns from every confirmed / auto-moved file
  correct()   unlearns a wrong filing and learns the right one
  evaluate()  hides each file in turn, predicts it, and measures real accuracy
  tune()      turns that measurement into auto-move / suggest thresholds
  propose_new_folders()  clusters files nothing matched and names the folders they should live in
"""
from __future__ import annotations

import functools
import json
import os
import random
import shutil
import tempfile
import threading
import time
from pathlib import Path

try:
    from .calibrate import Calibrator
    from .cluster import propose_clusters
    from .extract import extract, is_partial
    from .folders import FolderPolicy, fallback_name, normalize_name
    from .fusion import Weights, confidence, fuse
    from .learn import ExemplarKNN, NamePrior, TermModel, doc_terms
    from .signals import CentroidIndex, HabitPrior, get_embedder, rule_scorer
    from .textutil import canonical
    from .types import Decision, Doc
except (ImportError, ValueError):
    from docpilot.calibrate import Calibrator
    from docpilot.cluster import propose_clusters
    from docpilot.extract import extract, is_partial
    from docpilot.folders import FolderPolicy, fallback_name, normalize_name
    from docpilot.fusion import Weights, confidence, fuse
    from docpilot.learn import ExemplarKNN, NamePrior, TermModel, doc_terms
    from docpilot.signals import CentroidIndex, HabitPrior, get_embedder, rule_scorer
    from docpilot.textutil import canonical
    from docpilot.types import Decision, Doc

SEED = ["Finance", "Identity", "Education", "Work", "Medical", "Travel", "Legal"]


def _locked(fn):
    @functools.wraps(fn)
    def wrap(self, *a, **k):
        with self.lock:
            return fn(self, *a, **k)
    return wrap


class DocPilot:
    def __init__(self, root, state_dir=".docpilot", embedder=None, tiers=(), offline=False,
                 folder_mode="ask", min_support=3, target_precision=0.97):
        self.root, self.state_dir = Path(root), Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.embedder = embedder or get_embedder()
        self.centroids = CentroidIndex(self.embedder.min_sim)
        self.knn = ExemplarKNN(self.embedder.min_sim)
        self.terms = TermModel()
        self.prior = HabitPrior()
        self.name_prior = NamePrior(self.embedder)
        self.weights = Weights()
        self.cal = Calibrator(self.state_dir / "calibration.json", target=target_precision)
        self.tiers, self.offline = list(tiers), offline
        self.policy = FolderPolicy(folder_mode, min_support)
        self.descriptions: dict[str, str] = {}
        self.seen: dict[str, str] = {}                # file key -> folder it was learned in
        self.review: list[str] = []                   # files nothing matched (feeds new-folder proposals)
        self._pending: dict[str, tuple] = {}          # path -> (doc, scores, decision)
        self._filed: dict[str, tuple] = {}            # dest -> (doc, scores, predicted, confidence)
        self._load()

    # ------------------------------------------------------------ folders
    def existing_folders(self, depth: int = 2) -> list[str]:
        out = []
        for dp, dns, _ in os.walk(self.root):
            rel = Path(dp).relative_to(self.root)
            if len(rel.parts) >= depth:
                dns[:] = []
            dns[:] = [d for d in dns if not d.startswith(".")]
            if rel.parts:
                out.append(rel.as_posix())
        return sorted(out)

    def candidates(self) -> list[str]:
        ex = self.existing_folders()
        keys = {canonical(Path(e).name) for e in ex}
        return ex + [s for s in SEED if canonical(s) not in keys]

    @staticmethod
    def _key(path) -> str:
        return f"{Path(path).name}|{os.path.getsize(path)}"

    def _files_in(self, folder: str):
        d = self.root / folder
        if not d.exists() or not d.is_dir():
            return []
        return [p for p in sorted(d.iterdir()) if p.is_file() and not is_partial(p)]

    # ------------------------------------------------------------ learning
    @staticmethod
    def _embed_text(doc: Doc) -> str:
        return f"{doc.name} {doc.meta.get('title', '')} {doc.text[:6000]}"

    def learn(self, doc: Doc, folder: str, sign: int = 1):
        """sign=+1 learn, sign=-1 unlearn. Updates every learner at once."""
        vec = self.embedder.embed(self._embed_text(doc))
        if sign > 0:
            self.centroids.add(folder, vec)
            self.knn.add(folder, vec)
            self.prior.update(doc, folder)
        else:
            self.centroids.remove(folder, vec)
            self.knn.remove(folder, vec)
            self.prior.remove(doc, folder)
        self.terms.add(doc, folder, sign)

    @_locked
    def sync(self, max_per_folder: int = 200) -> dict:
        """Learn from the library as it is now, including files the user moved by hand.

        A file that appears in a different folder than where we learned it is the strongest
        feedback there is: unlearn the old folder, learn the new one.
        """
        learned = moved = 0
        present = {}
        for folder in self.existing_folders():
            for p in self._files_in(folder)[:max_per_folder]:
                present.setdefault(self._key(p), (p, folder))
        for key, (p, folder) in present.items():
            old = self.seen.get(key)
            if old == folder:
                continue
            doc = extract(p, allow_ocr=False)
            if old is not None:
                self.learn(doc, old, -1)
                moved += 1
            self.learn(doc, folder)
            self.seen[key] = folder
            learned += 1
        self._save()
        return {"learned": learned, "moved_by_user": moved}

    def scan_existing(self, max_per_folder: int = 50):
        return self.sync(max_per_folder)

    # ------------------------------------------------------------ analysis
    @staticmethod
    def _restrict(dist, cands):
        if not dist:
            return None
        cs = set(cands)
        r = {f: p for f, p in dist.items() if f in cs}
        z = sum(r.values())
        return {f: p / z for f, p in r.items()} if r and z > 0 else None

    def _signals(self, doc: Doc, cands: list[str]) -> dict:
        doc_text = self._embed_text(doc)
        vec = self.embedder.embed(doc_text)
        raw = {
            "rules": rule_scorer(doc, cands),
            "embed": self.centroids.scores(vec),
            "terms": self.terms.scores(doc),
            "knn": self.knn.scores(vec),
            "prior": self.prior.score(doc, list(self.centroids.sum) or cands),
            "name": self.name_prior.scores(vec, cands, self.descriptions, self.centroids.n, text=doc_text),
        }
        out = {}
        for name, dist in raw.items():
            d = self._restrict(dist, cands)
            if d:
                out[name] = d
        return out

    def _decide(self, scores: dict, doc: Doc, tier: str, new_folder=None) -> Decision:
        warns = list(doc.warnings)
        if new_folder:
            return Decision("new_folder", None, None, new_folder["confidence"], {}, tier, new_folder, warns)
        if not scores:
            return Decision("review", warnings=warns, tier=tier)
        auto, sug = self.cal.thresholds()
        top, alt, conf = confidence(fuse(scores, self.weights), scores, doc.ocr_conf)
        action = "auto_move" if conf >= auto else "suggest" if conf >= sug else "review"
        if action == "auto_move" and (len(scores) < 2 or doc.ocr_conf < 0.5):
            action = "suggest"                        # one signal, or a file we could barely read
        sig = {k: max(v, key=v.get) for k, v in scores.items() if v}
        return Decision(action, top, alt, round(conf, 3), sig, tier, None, warns)

    def _analyze_doc(self, doc: Doc, cands: list[str], use_tiers: bool = True):
        scores = self._signals(doc, cands)
        d = self._decide(scores, doc, "local")
        if use_tiers:
            for tier in self.tiers:                   # escalate only while not confident
                if d.action == "auto_move":
                    break
                if tier.cloud and self.offline:
                    continue
                v = tier.classify(doc, cands, self.descriptions)
                if v is None:
                    continue
                if v.is_new and v.confidence >= 0.6 and d.confidence < self.cal.thresholds()[1]:
                    nf = {"name": v.name, "description": v.description, "confidence": v.confidence}
                    d = self._decide(scores, doc, tier.name, nf)
                    break
                if v.dist:
                    scores[tier.name] = v.dist
                    d = self._decide(scores, doc, tier.name)
        return d, scores

    @_locked
    def analyze(self, path) -> Decision:
        doc = extract(path)
        d, scores = self._analyze_doc(doc, self.candidates())
        if d.action == "review":
            if not d.new_folder and not scores and doc.text.strip():
                d.new_folder = {"name": fallback_name(doc.text, doc.name), "description": "", "confidence": 0.0}
            if str(path) not in self.review:
                self.review.append(str(path))
        self._pending[str(path)] = (doc, scores, d)
        return d

    # ------------------------------------------------------------ act + learn
    @_locked
    def file(self, path, folder: str):
        """Move (auto-move or user confirm), learn from it, tune weights, log accuracy."""
        path = str(path)
        pend = self._pending.pop(path, None)
        doc, scores, pred, conf = (pend[0], pend[1], pend[2].folder, pend[2].confidence) if pend \
            else (extract(path, allow_ocr=False), {}, None, 0.0)
        if scores:
            self.weights.update(scores, folder)
        dest = self.move(path, folder)
        self.learn(doc, folder)
        self.seen[self._key(dest)] = folder
        self._filed[str(dest)] = (doc, scores, pred, conf)
        if pred is not None:
            self.cal.record(str(dest), conf, pred == folder)
            self.cal.save()
        if path in self.review:
            self.review.remove(path)
        self._save()
        return dest

    @_locked
    def correct(self, dest, right_folder: str):
        """The user says a filed document belongs elsewhere: unlearn the mistake, learn the truth."""
        dest = str(dest)
        info = self._filed.pop(dest, None)
        wrong = Path(dest).parent.relative_to(self.root).as_posix()
        doc = info[0] if info else extract(dest, allow_ocr=False)
        self.learn(doc, wrong, -1)
        self.seen.pop(self._key(dest), None)
        self.cal.set_outcome(dest, False)
        if info and info[1]:
            self.weights.update(info[1], right_folder)
        new = self.move(dest, right_folder)
        self.learn(doc, right_folder)
        self.seen[self._key(new)] = right_folder
        self._filed[str(new)] = (doc, info[1] if info else {}, right_folder, 1.0)
        self.cal.save()
        self._save()
        return new

    def move(self, path, folder: str):
        d = self.root / folder
        d.mkdir(parents=True, exist_ok=True)
        p = Path(path)
        dest, i = d / p.name, 1
        while dest.exists():
            dest = d / f"{p.stem} ({i}){p.suffix}"
            i += 1
        shutil.move(str(p), str(dest))
        with open(self.state_dir / "moves.jsonl", "a") as f:
            f.write(json.dumps({"src": str(p), "dst": str(dest), "t": time.time()}) + "\n")
        return dest

    @_locked
    def undo_last(self):
        log = self.state_dir / "moves.jsonl"
        if not log.exists():
            return None
        lines = log.read_text().splitlines()
        if not lines:
            return None
        m = json.loads(lines.pop())
        info = self._filed.pop(m["dst"], None)
        if info:                                      # undoing a filing is also a lesson
            self.learn(info[0], Path(m["dst"]).parent.relative_to(self.root).as_posix(), -1)
            self.cal.set_outcome(m["dst"], False)
        self.seen.pop(self._key(m["dst"]), None)
        shutil.move(m["dst"], m["src"])
        log.write_text("\n".join(lines) + ("\n" if lines else ""))
        return m["src"]

    # ------------------------------------------------------------ new folders
    def propose_folder(self, path, name: str, description: str = ""):
        """Route a new-folder proposal through the permission policy. -> (action, folder)"""
        action, folder = self.policy.propose(name, description, str(path), self.existing_folders())
        if action == "create":
            self.descriptions[folder] = description
        return action, folder

    @_locked
    def propose_new_folders(self) -> list[dict]:
        """Cluster the files nothing matched; each cluster becomes a named, described folder proposal."""
        items = []
        for p in list(self.review):
            if not os.path.exists(p):
                self.review.remove(p)
                continue
            doc = self._pending[p][0] if p in self._pending else extract(p, allow_ocr=False)
            items.append((p, self.embedder.embed(self._embed_text(doc)), doc_terms(doc)))
        out = []
        for c in propose_clusters(items, self.embedder.min_sim + 0.15, self.policy.min_support):
            action = folder = None
            for p in c["files"]:
                action, folder = self.policy.propose(c["name"], c["description"], p, self.existing_folders())
            out.append({**c, "action": action, "folder": folder})
        return out

    @_locked
    def create_folder(self, name: str, description: str, files: list[str]) -> list[Path]:
        """User approved a proposal: create the folder (with its description) and file the batch."""
        folder = normalize_name(name)
        (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.descriptions[folder] = description
        self.policy.resolve(name, True)
        return [self.file(p, folder) for p in files if os.path.exists(p)]

    @_locked
    def deny_folder(self, name: str):
        self.policy.resolve(name, False)
        self._save()

    # ------------------------------------------------------------ measure + self-tune
    @_locked
    def evaluate(self, folds: int = 5, max_files: int = 600, seed: int = 0, allow_ocr: bool = False):
        """Hold-out test on the user's own library: hide files, predict, compare with where they are."""
        labeled = [(str(p), f) for f in self.existing_folders() for p in self._files_in(f)]
        random.Random(seed).shuffle(labeled)
        labeled = labeled[:max_files]
        if len(labeled) < folds * 2:
            return None
        docs = {p: extract(p, allow_ocr=allow_ocr) for p, _ in labeled}
        cands = self.candidates()
        rows = []                                     # (confidence, correct, n_signals)
        for k in range(folds):
            test = labeled[k::folds]
            held = {p for p, _ in test}
            with tempfile.TemporaryDirectory() as tmp:
                sub = DocPilot(self.root, tmp, embedder=self.embedder, offline=True)
                sub.weights = Weights(dict(self.weights.w))
                for p, f in labeled:
                    if p not in held:
                        sub.learn(docs[p], f)
                for p, f in test:
                    d, sc = sub._analyze_doc(docs[p], cands, use_tiers=False)
                    rows.append((d.confidence, d.folder == f, len(sc)))
        auto, sug = self.cal.thresholds()
        n = len(rows)
        A = [r for r in rows if r[0] >= auto and r[2] >= 2]
        S = [r for r in rows if r not in A and r[0] >= sug]
        prec = lambda xs: round(sum(r[1] for r in xs) / len(xs), 3) if xs else None
        probe = Calibrator(None, target=self.cal.target, min_samples=self.cal.min_samples)
        probe.bulk([(c, ok) for c, ok, _ in rows])
        return {
            "n": n,
            "top1_accuracy": round(sum(r[1] for r in rows) / n, 3),
            "auto_coverage": round(len(A) / n, 3), "auto_precision": prec(A),
            "suggest_precision": prec(S), "review_rate": round((n - len(A) - len(S)) / n, 3),
            "thresholds_now": (auto, sug), "thresholds_proposed": probe.thresholds(),
            "pairs": [(c, ok) for c, ok, _ in rows],
        }

    @_locked
    def tune(self, **kw):
        """Measure on the library, then adopt thresholds that hit the precision target."""
        m = self.evaluate(**kw)
        if m:
            self.cal.bulk(m["pairs"], prefix="eval")
            self.cal.save()
            m["thresholds_now"] = self.cal.thresholds()
        return m

    # ------------------------------------------------------------ state
    def _save(self):
        (self.state_dir / "state.json").write_text(json.dumps({
            "embedder": self.embedder.name,
            "centroids": self.centroids.to_json(),
            "knn": self.knn.to_json(),
            "terms": self.terms.to_json(),
            "prior": self.prior.to_json(),
            "seen": self.seen,
            "review": self.review,
            "weights": self.weights.w,
            "descriptions": self.descriptions,
            "denied": sorted(self.policy.denied),
        }))

    def _load(self):
        f = self.state_dir / "state.json"
        if not f.exists():
            return
        try:
            s = json.loads(f.read_text())
            self.weights = Weights(s.get("weights"))
            self.descriptions = s.get("descriptions", {})
            self.policy.denied = set(s.get("denied", []))
            self.review = list(s.get("review", []))
            if s.get("embedder") == self.embedder.name:   # vectors are only valid for the same model
                self.centroids.load(s.get("centroids", {}))
                self.knn.load(s.get("knn", {}))
                self.terms.load(s.get("terms", {}))
                self.prior.load(s.get("prior", {}))
                self.seen = dict(s.get("seen", {}))
        except Exception:
            pass
