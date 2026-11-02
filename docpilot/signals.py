"""Independent scorers. Each returns {folder: probability}, or None to abstain.

Abstaining matters: a signal with no evidence must not vote.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

import numpy as np

try:
    from .textutil import STOP, canonical, filename_tokens, softmax, stem_word, tokens
    from .doc_types import Doc
except (ImportError, ValueError):
    from docpilot.textutil import STOP, canonical, filename_tokens, softmax, stem_word, tokens
    from docpilot.doc_types import Doc


# ================================================================= A. rules
def _r(pattern: str, weight: float, ignore_case: bool = True):
    return re.compile(pattern, re.I if ignore_case else 0), weight


RULES = {
    "Finance": [
        _r(r"\b(tax invoice|invoice no|invoice number|bill of supply|receipt)\b", 2),
        _r(r"\bGSTIN\b", 2, False),
        _r(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", 3, False),   # GSTIN number
        _r(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", 1.5, False),                       # IFSC
        _r(r"\b(bank statement|account statement|total due|amount payable|upi|neft|rtgs|emi)\b", 2),
        _r(r"\b(income tax|itr|form 16|gst return)\b", 2),
    ],
    "Identity": [
        _r(r"\b(aadhaar|aadhar|uidai)\b", 3),
        _r(r"permanent account number", 3),
        _r(r"\b[A-Z]{5}\d{4}[A-Z]\b", 1, False),                           # PAN (weak: appears on invoices too)
        _r(r"\b(passport|driving licen[cs]e|voter id|election commission)\b", 3),
    ],
    "Education": [
        _r(r"\b(marksheet|mark sheet|transcript|semester|syllabus|lecture|university|exam)\b", 2),
        _r(r"\b(course|chapter|question paper|admit card|enrolment|enrollment)\b", 1.5),
    ],
    "Work": [
        _r(r"\b(offer letter|salary slip|payslip|experience letter|resume|curriculum vitae|appraisal)\b", 3),
        _r(r"\b(meeting minutes|project plan|statement of work|sprint)\b", 2),
    ],
    "Medical": [
        _r(r"\b(prescription|diagnosis|lab report|pathology|discharge summary|patient|hospital|mg)\b", 2),
        _r(r"\b(blood test|x-ray|mri|vaccination|insurance claim)\b", 2),
    ],
    "Travel": [
        _r(r"\b(boarding pass|pnr|e-ticket|itinerary|booking id|check-in|visa)\b", 2.5),
        _r(r"\b(irctc|flight|hotel booking)\b", 2),
    ],
    "Legal": [
        _r(r"\b(agreement|affidavit|power of attorney|notary|stamp paper|lease|rental agreement)\b", 2.5),
        _r(r"\b(hereinafter|whereas|jurisdiction|indemnif\w+)\b", 2),
    ],
    "Invoices": [
        _r(r"\b(tax invoice|invoice no|invoice number|bill to|bill of supply|inv no|taxable amount)\b", 3),
        _r(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", 3, False),
        _r(r"\b(amount due|total amount|payment due|cgst|sgst|igst)\b", 2),
    ],
    "Receipts": [
        _r(r"\b(receipt|payment receipt|received from|cash receipt|acknowledgement of payment)\b", 3),
        _r(r"\b(amount paid|transaction id|receipt no|paid)\b", 2),
    ],
    "Contracts": [
        _r(r"\b(agreement|contract|parties|whereas|hereinafter|obligations|liabilities|non-disclosure|nda)\b", 3),
        _r(r"\b(governing law|dispute resolution|in witness whereof|confidentiality)\b", 2),
    ],
    "Leases": [
        _r(r"\b(lease|rental agreement|tenancy|tenant|landlord|lessor|lessee|monthly rent|security deposit)\b", 3),
        _r(r"\b(leave and licence|licence fee|premises|possession|tenancy period)\b", 2),
    ],
    "Assignments": [
        _r(r"\b(assignment|assignments|homework|coursework|problem set|lab report|submission|term paper|project submission|problem \d+)\b", 3.5),
        _r(r"\b(student name|roll no|course|instructor|professor|department of)\b", 2.0),
    ],
    "Certificates": [
        _r(r"\b(certificate|certified that|completion certificate|achievement|degree)\b", 3),
    ],
    "Reports": [
        _r(r"\b(quarterly report|annual report|audit report|project report|status report)\b", 3),
    ],
}

CATEGORY_SYNONYMS = {
    "finance": {"invoices", "invoice", "receipts", "receipt", "bills", "bill", "finance", "tax", "banking"},
    "legal": {"contracts", "contract", "leases", "lease", "agreements", "agreement", "nda", "legal", "notices"},
    "education": {"lectures", "lecture", "education", "courses", "certificates", "study"},
    "assignments": {"assignment", "assignments", "homework", "coursework", "problem set", "submission", "term paper", "lab report", "study"},
    "work": {"work", "jobs", "payslips", "payslip", "projects", "project", "resumes", "resume"},
    "medical": {"medical", "health", "prescriptions", "prescription", "reports", "report"},
    "travel": {"travel", "tickets", "ticket", "itinerary", "boarding"},
    "identity": {"identity", "kyc", "aadhaar", "pan", "passports"},
}

DOMAIN_HINTS = {
    "bank": "Finance", "hdfc": "Finance", "icici": "Finance", "sbi": "Finance", "paytm": "Finance",
    "incometax": "Finance", "gst.gov": "Finance",
    "irctc": "Travel", "makemytrip": "Travel", "goibibo": "Travel", "airindia": "Travel",
    "coursera": "Education", "udemy": "Education", "nptel": "Education", "swayam": "Education",
    "naukri": "Work", "linkedin": "Work",
    "uidai": "Identity", "digilocker": "Identity", "passportindia": "Identity",
    "practo": "Medical", "pharmeasy": "Medical",
}


def rule_scorer(doc: Doc, cands: list[str]):
    hay = doc.text[:6000] + "\n" + doc.name
    cat = {}
    for c, pats in RULES.items():
        s = sum(w for p, w in pats if p.search(hay))
        if s:
            cat[c] = s
    host = (urlparse(doc.source_url).hostname or "") if doc.source_url else ""
    for key, c in DOMAIN_HINTS.items():
        if key in host:
            cat[c] = cat.get(c, 0) + 2.5
    if not cat or max(cat.values()) < 2:
        return None
    sc = {}
    for f in cands:
        comps = [canonical(x) for x in f.replace("\\", "/").split("/")]
        hit = 0.0
        for c, v in cat.items():
            can_c = canonical(c)
            if can_c in comps:
                hit = max(hit, v)
            syns = CATEGORY_SYNONYMS.get(can_c, set())
            if any(comp in syns for comp in comps):
                hit = max(hit, v * 0.95)
        # Direct folder name and stem match in document text or filename
        folder_clean = canonical(f.split("/")[-1])
        folder_stem = stem_word(folder_clean)
        if folder_clean and len(folder_clean) >= 3 and (re.search(r'\b' + re.escape(folder_clean) + r'\b', hay.lower()) or (len(folder_stem) >= 3 and re.search(r'\b' + re.escape(folder_stem) + r'\b', hay.lower()))):
            hit = max(hit, 4.0)
        if hit > 0:
            sc[f] = hit + (0.05 * len(comps))   # tie-break: prefer the specific subfolder over its parent
    if max(sc.values(), default=0) < 2:
        return None
    return softmax(sc)


# ================================================================= B. embeddings
class HashingEmbedder:
    """Zero-dependency fallback (signed feature hashing of words + bigrams). Works fully offline."""
    name, dim, min_sim = "hash512", 512, 0.12

    def embed(self, text: str):
        v = np.zeros(self.dim, dtype=np.float32)
        toks = [t for t in tokens(text)[:3000] if t not in STOP]
        cnt = Counter(toks + [f"{a} {b}" for a, b in zip(toks, toks[1:])])
        for f, c in cnt.items():
            h = int.from_bytes(hashlib.md5(f.encode()).digest()[:4], "little")
            v[h % self.dim] += (1 if (h >> 16) & 1 else -1) * (1 + math.log(c))
        n = np.linalg.norm(v)
        return v / n if n else v


class FastEmbedder:
    """Small multilingual ONNX model via fastembed (handles Hindi + English)."""
    min_sim = 0.35

    def __init__(self, model: str):
        from fastembed import TextEmbedding
        self.m = TextEmbedding(model_name=model)
        self.name = "fastembed:" + model
        self.dim = len(next(iter(self.m.embed(["x"]))))

    def embed(self, text: str):
        v = np.asarray(next(iter(self.m.embed([text[:4000] or "empty"]))), dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n else v


def get_embedder(model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
    try:
        return FastEmbedder(model)
    except Exception:
        return HashingEmbedder()


class CentroidIndex:
    """One running-average vector per folder. This is the 'training': it is just filing history."""

    def __init__(self, min_sim: float):
        self.min_sim = min_sim
        self.sum: dict[str, np.ndarray] = {}
        self.n: Counter = Counter()

    def add(self, folder: str, vec):
        self.sum[folder] = self.sum.get(folder, 0) + vec
        self.n[folder] += 1

    def remove(self, folder: str, vec):
        """Unlearn one file (used when the user corrects a wrong filing)."""
        if folder not in self.sum:
            return
        self.sum[folder] = self.sum[folder] - vec
        self.n[folder] -= 1
        if self.n[folder] <= 0:
            self.sum.pop(folder, None)
            self.n.pop(folder, None)

    def scores(self, vec, T: float = 0.05):
        if not self.sum:
            return None
        sims = {}
        for f, s in self.sum.items():
            nrm = np.linalg.norm(s)
            sims[f] = float(vec @ (s / nrm)) if nrm else 0.0
        self.last_best = max(sims.values())
        if self.last_best < self.min_sim:      # looks like nothing we have: possible new folder
            return None
        return softmax(sims, T)

    def to_json(self):
        return {f: {"sum": s.tolist(), "n": self.n[f]} for f, s in self.sum.items()}

    def load(self, data: dict):
        for f, d in data.items():
            self.sum[f] = np.asarray(d["sum"], dtype=np.float32)
            self.n[f] = d["n"]


# ================================================================= C. habit prior
class HabitPrior:
    """'Files from this domain / with this filename pattern usually go here.'"""

    def __init__(self):
        self.counts: dict[str, Counter] = defaultdict(Counter)

    @staticmethod
    def features(doc: Doc) -> list[str]:
        feats = []
        if doc.source_url:
            host = urlparse(doc.source_url).hostname
            if host:
                feats.append("dom:" + host.removeprefix("www."))
        feats += ["tok:" + t for t in filename_tokens(doc.name)]
        feats.append("ext:" + doc.meta.get("ext", ""))
        return feats

    def update(self, doc: Doc, folder: str):
        for f in self.features(doc):
            self.counts[f][folder] += 1

    def remove(self, doc: Doc, folder: str):
        for f in self.features(doc):
            c = self.counts.get(f)
            if c and c.get(folder, 0) > 0:
                c[folder] -= 1
                if c[folder] <= 0:
                    del c[folder]

    def score(self, doc: Doc, cands: list[str]):
        dist, wsum = Counter(), 0.0
        for f in self.features(doc):
            c = self.counts.get(f)
            if not c or f.startswith("ext:"):
                continue
            total = sum(c.values())
            if total < 2:
                continue
            w = math.log(1 + total)
            for folder, k in c.items():
                dist[folder] += w * k / total
            wsum += w
        if not wsum:                           # extension alone is never evidence
            return None
        return {f: dist.get(f, 0.0) / wsum + 0.01 for f in cands}

    def to_json(self):
        return {k: dict(v) for k, v in self.counts.items()}

    def load(self, data: dict):
        for k, v in data.items():
            self.counts[k] = Counter(v)
