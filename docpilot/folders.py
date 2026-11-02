"""Folder naming and creation policy: reuse before create, normalize, batch, remember refusals."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher

try:
    from .textutil import canonical, content_tokens, filename_tokens
except (ImportError, ValueError):
    from textutil import canonical, content_tokens, filename_tokens

RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
FALLBACK = "Unsorted"


def normalize_name(name: str, max_words: int = 3, max_len: int = 40) -> str:
    """'  invoices_2026: acme/corp ' -> 'Invoices 2026 Acme'. Safe on Windows, macOS and Linux."""
    name = ILLEGAL.sub(" ", name)
    name = re.sub(r"[_\-]+", " ", name)
    words = name.split()[:max_words]
    name = " ".join(w if (w.isupper() and len(w) <= 4) else w.capitalize() for w in words)
    name = name.strip(" .")[:max_len].strip(" .")
    if not name:
        return FALLBACK
    if name.upper() in RESERVED:
        name += " Files"
    return name


def find_existing(name: str, existing: list[str], cutoff: float = 0.85):
    """Fuzzy match so 'Invoice' / 'Invoices' / 'invoices ' never become two folders."""
    want = canonical(name)
    best, best_r = None, 0.0
    for e in existing:
        leaf = canonical(e.replace("\\", "/").split("/")[-1])
        r = 1.0 if leaf == want else SequenceMatcher(None, want, leaf).ratio()
        if r > best_r:
            best, best_r = e, r
    return best if best_r >= cutoff else None


def fallback_name(text: str, filename: str) -> str:
    """No LLM available: name the folder after the most frequent content words."""
    words = Counter(content_tokens(text[:4000]))
    for t in filename_tokens(filename):
        words[t] += 2
    top = [w for w, _ in words.most_common(2)]
    return normalize_name(" ".join(top)) if top else FALLBACK


class FolderPolicy:
    """mode: 'ask' (default) | 'auto' | 'never'.

    - Never creates a folder before `min_support` similar files exist (prevents folder explosion).
    - Asks once per folder, in a batch, not once per file.
    - Remembers refusals and never asks again.
    """

    def __init__(self, mode: str = "ask", min_support: int = 3):
        self.mode, self.min_support = mode, min_support
        self.pending: dict[str, list[str]] = defaultdict(list)
        self.descriptions: dict[str, str] = {}
        self.denied: set[str] = set()

    def propose(self, name: str, description: str, path: str, existing: list[str]):
        """-> (action, folder). action: use_existing | fallback | wait | ask | create"""
        name = normalize_name(name)
        match = find_existing(name, existing)
        if match:
            return "use_existing", match
        key = canonical(name)
        if key in self.denied or self.mode == "never" or name == FALLBACK:
            return "fallback", FALLBACK
        if path not in self.pending[key]:
            self.pending[key].append(path)
        self.descriptions.setdefault(key, description)
        if len(self.pending[key]) < self.min_support:
            return "wait", name
        return ("create" if self.mode == "auto" else "ask"), name

    def pending_batch(self, name: str) -> list[str]:
        return list(self.pending.get(canonical(name), []))

    def resolve(self, name: str, accepted: bool) -> list[str]:
        """Call with the user's answer. Returns the files that were waiting on this folder."""
        key = canonical(name)
        files = self.pending.pop(key, [])
        if not accepted:
            self.denied.add(key)
        return files
