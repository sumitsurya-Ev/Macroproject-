"""Run:  python tests/test_core.py   (no pytest needed)"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docpilot.extract import is_partial, text_quality
from docpilot.folders import FolderPolicy, find_existing, normalize_name
from docpilot.fusion import Weights, confidence, fuse
from docpilot.llm import mask_pii, parse_response
from docpilot.pipeline import DocPilot
from docpilot.signals import HashingEmbedder


def test_helpers():
    assert is_partial("a.pdf.crdownload") and not is_partial("a.pdf")
    assert text_quality("", 3) == 0.0
    assert text_quality("l1| ]x~ qq# 9@ " * 40, 1) < 0.6
    assert text_quality("This is a normal invoice with amount payable and tax details. " * 10, 1) >= 0.6
    assert normalize_name("  invoices_2026: acme/corp extra ") == "Invoices 2026 Acme"
    assert normalize_name("CON") == "Con Files" or normalize_name("con").endswith("Files")
    assert find_existing("Invoice", ["Finance/Invoices", "Travel"]) == "Finance/Invoices"
    assert "[PAN]" in mask_pii("pan ABCDE1234F") and "[AADHAAR]" in mask_pii("1234 5678 9012")
    assert parse_response('sure {"folder":"X","confidence":0.9}')["confidence"] == 0.9


def test_policy():
    p = FolderPolicy(mode="ask", min_support=3)
    assert p.propose("Rent Receipts", "", "a", [])[0] == "wait"
    assert p.propose("Rent Receipts", "", "b", [])[0] == "wait"
    assert p.propose("rent receipt", "", "c", [])[0] == "ask"          # batched, fuzzy-same name
    assert len(p.pending_batch("Rent Receipts")) == 3
    p.resolve("Rent Receipts", accepted=False)
    assert p.propose("Rent Receipts", "", "d", [])[0] == "fallback"    # never asks twice


def test_fusion():
    s = {"rules": {"A": 0.9, "B": 0.1}, "embed": {"A": 0.8, "B": 0.2}}
    top, _, conf = confidence(fuse(s, Weights()), s, 1.0)
    assert top == "A" and conf > 0.6
    _, _, c1 = confidence(fuse({"rules": {"A": 0.99, "B": 0.01}}, Weights()), {"rules": {"A": 0.99, "B": 0.01}}, 1.0)
    assert c1 < 0.85                                                   # one signal never auto-moves
    _, _, c2 = confidence(fuse(s, Weights()), s, 0.0)
    assert c2 < conf                                                   # bad OCR lowers confidence


def test_pipeline():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Documents"
        inv = root / "Finance" / "Invoices"
        edu = root / "Education" / "Lectures"
        inv.mkdir(parents=True)
        edu.mkdir(parents=True)
        for i in range(3):
            (inv / f"bill{i}.txt").write_text(
                "Tax Invoice No 10%d GSTIN 27ABCDE1234F1Z5 total due amount payable GST rupees" % i)
            (edu / f"notes{i}.txt").write_text(
                "Lecture %d semester syllabus assignment physics chapter exam university course" % i)
        pilot = DocPilot(root, Path(tmp) / "state", embedder=HashingEmbedder())
        pilot.scan_existing()

        new = Path(tmp) / "Downloads"
        new.mkdir()
        f = new / "invoice_acme.txt"
        f.write_text("Invoice number 77 total due amount payable GSTIN 29ABCDE1234F1Z9 GST")
        d = pilot.analyze(f)
        print("decision:", d.action, d.folder, d.confidence, d.signals)
        assert d.folder == "Finance/Invoices", d
        assert d.action in ("auto_move", "suggest")

        g = new / "physics_lecture.txt"
        g.write_text("Lecture on semester physics syllabus chapter assignment exam course university")
        assert pilot.analyze(g).folder == "Education/Lectures"

        dest = pilot.file(f, "Finance/Invoices")
        assert dest.exists() and not f.exists()
        assert pilot.undo_last() == str(f) and f.exists()              # one-click undo works

        junk = new / "zzz.bin"
        junk.write_bytes(b"\x00\x01\x02")
        assert pilot.analyze(junk).action == "review"                  # never auto-moves unknown files


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
