"""DocPilot document intelligence and organization package."""
from .calibrate import Calibrator
from .cluster import propose_clusters
from .extract import extract, is_partial, text_quality
from .folders import FALLBACK, FolderPolicy, fallback_name, find_existing, normalize_name
from .fusion import AUTO, SUGGEST, Weights, confidence, fuse
from .learn import ExemplarKNN, NamePrior, TermModel, doc_terms
from .llm import mask_pii, parse_response
from .pipeline import DocPilot
from .signals import CentroidIndex, HabitPrior, HashingEmbedder, get_embedder, rule_scorer
from .textutil import STOP, canonical, content_tokens, filename_tokens, softmax, tokens
from .doc_types import Decision, Doc

__all__ = [
    "Doc",
    "Decision",
    "DocPilot",
    "FolderPolicy",
    "HashingEmbedder",
    "CentroidIndex",
    "HabitPrior",
    "TermModel",
    "ExemplarKNN",
    "NamePrior",
    "Calibrator",
    "propose_clusters",
    "doc_terms",
    "Weights",
    "extract",
    "is_partial",
    "text_quality",
    "normalize_name",
    "find_existing",
    "fallback_name",
    "fuse",
    "confidence",
    "mask_pii",
    "parse_response",
    "get_embedder",
    "rule_scorer",
    "canonical",
    "filename_tokens",
    "content_tokens",
    "tokens",
    "softmax",
    "STOP",
    "AUTO",
    "SUGGEST",
    "FALLBACK",
]
