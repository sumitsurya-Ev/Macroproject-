"""Text normalization, tokenization, stopword lists, and scoring utilities."""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", 
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", 
    "by", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from", 
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", 
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more", 
    "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", 
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", 
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then", 
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", 
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", 
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
    # common Indian English and Hindi transliteration stops
    "ka", "ki", "ke", "hai", "ko", "se", "aur", "ya", "par", "me", "mein", "tha", "thi", "the"
}


def stem_word(w: str) -> str:
    """Normalize English word to singular/stem form."""
    w = w.lower()
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es") and not w.endswith("ses") and not w.endswith("xes"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def tokens(text: str) -> list[str]:
    """Extract lowercase alphanumeric tokens, supporting Latin and Devanagari."""
    raw = re.findall(r"[a-z0-9\u0900-\u097f]+", text.lower())
    # Return both original and stemmed variants so hashing matches both singular and plural
    out = []
    for t in raw:
        out.append(t)
        st = stem_word(t)
        if st != t:
            out.append(st)
    return out


def canonical(s: str) -> str:
    """Canonicalize a folder or label string into a clean lowercase stemmed form."""
    s = s.lower().replace("\\", "/").strip()
    s = re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", s).strip()
    words = [stem_word(w) for w in s.split()]
    return " ".join(words)


def filename_tokens(name: str) -> list[str]:
    """Tokenize filename, stripping extension and splitting camelCase and delimiters."""
    name = re.sub(r"\.[a-zA-Z0-9]+$", "", name)
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    raw = re.split(r"[\s_\.\-]+", name.lower())
    return [w for w in raw if len(w) >= 2 and w not in STOP]


def content_tokens(text: str) -> list[str]:
    """Extract meaningful content tokens of length >= 3 not in STOP."""
    return [t for t in tokens(text) if len(t) >= 3 and t not in STOP]


def softmax(d: dict[str, float], T: float = 1.0) -> dict[str, float]:
    """Numerically stable softmax over a dictionary of scores."""
    if not d:
        return {}
    m = max(d.values())
    exp = {k: math.exp((v - m) / max(0.0001, T)) for k, v in d.items()}
    tot = sum(exp.values()) or 1.0
    return {k: v / tot for k, v in exp.items()}
