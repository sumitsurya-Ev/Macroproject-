"""Run:  python tests/test_selflearn.py

Uses made-up domains (gardening, cricket, astronomy) that appear nowhere in the code,
to prove the system learns a domain from the user's own folders.
"""
import random, shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docpilot.calibrate import Calibrator
from docpilot.pipeline import DocPilot
from docpilot.signals import HashingEmbedder

DOMAINS = {
    "Gardening": "soil compost seeds watering pruning mulch fertilizer seedlings greenhouse harvest".split(),
    "Cricket": "wicket innings bowler batsman over runs umpire stumps boundary pitch".split(),
    "Astronomy": "telescope nebula galaxy orbit planet comet eclipse lens stars cosmos".split(),
}
COMMON = "report about notes season weekly summary".split()


def make_text(domain, rng, common=True):
    words = rng.choices(DOMAINS[domain], k=40) + (rng.choices(COMMON, k=6) if common else [])
    rng.shuffle(words)
    return " ".join(words)


def build_library(tmp, domains=("Gardening", "Cricket"), n=10, seed=1):
    rng = random.Random(seed)
    root = Path(tmp) / "Documents"
    for dom in domains:
        (root / dom).mkdir(parents=True)
        for i in range(n):
            (root / dom / f"file{i}.txt").write_text(make_text(dom, rng))
    return root, rng


def test_unseen_domains():
    with tempfile.TemporaryDirectory() as tmp:
        root, rng = build_library(tmp)
        pilot = DocPilot(root, Path(tmp) / "st", embedder=HashingEmbedder())
        print("sync:", pilot.sync())
        new = Path(tmp) / "Downloads"
        new.mkdir()
        for dom in ("Gardening", "Cricket"):
            f = new / f"x_{dom}.txt"
            f.write_text(make_text(dom, rng))
            d = pilot.analyze(f)
            print(dom, "->", d.action, d.folder, d.confidence, d.signals)
            assert d.folder == dom and d.action in ("auto_move", "suggest")


def test_correction_and_manual_move():
    with tempfile.TemporaryDirectory() as tmp:
        root, rng = build_library(tmp)
        pilot = DocPilot(root, Path(tmp) / "st", embedder=HashingEmbedder())
        pilot.sync()
        assert pilot.terms.nd["Cricket"] == 10 and pilot.terms.nd["Gardening"] == 10

        f = Path(tmp) / "a.txt"
        f.write_text(make_text("Gardening", rng))
        dest = pilot.file(f, "Cricket")                          # wrong on purpose
        assert pilot.terms.nd["Cricket"] == 11
        pilot.correct(dest, "Gardening")                         # user fixes it: unlearn + relearn
        assert pilot.terms.nd["Cricket"] == 10 and pilot.terms.nd["Gardening"] == 11

        shutil.move(str(root / "Gardening" / "file0.txt"), str(root / "Cricket" / "file0.txt"))
        stats = pilot.sync()                                     # user reorganised by hand
        print("manual move:", stats)
        assert stats["moved_by_user"] >= 1
        assert pilot.terms.nd["Cricket"] == 11 and pilot.terms.nd["Gardening"] == 10


def test_new_domain_proposes_folder():
    with tempfile.TemporaryDirectory() as tmp:
        root, rng = build_library(tmp)
        pilot = DocPilot(root, Path(tmp) / "st", embedder=HashingEmbedder(), min_support=3)
        pilot.sync()
        new = Path(tmp) / "Downloads"
        new.mkdir()
        files = []
        for i in range(4):
            f = new / f"scan{i}.txt"
            f.write_text(make_text("Astronomy", rng, common=False))    # a domain it has never seen
            d = pilot.analyze(f)
            assert d.action == "review", d                            # it does NOT force a wrong folder
            files.append(str(f))
        props = pilot.propose_new_folders()
        print("proposals:", [(p["name"], p["action"], len(p["files"])) for p in props])
        assert len(props) == 1 and len(props[0]["files"]) == 4 and props[0]["action"] == "ask"
        moved = pilot.create_folder(props[0]["name"], props[0]["description"], props[0]["files"])
        assert len(moved) == 4 and all(Path(m).exists() for m in moved)
        assert (root / props[0]["folder"]).is_dir()


def test_calibrator():
    rng = random.Random(0)
    c = Calibrator(None, target=0.97, min_samples=30)
    assert c.thresholds() == (0.85, 0.55)                        # defaults until it has evidence
    for i in range(100):
        c.record(f"a{i}", rng.uniform(0.9, 1.0), True)
    for i in range(100):
        c.record(f"b{i}", rng.uniform(0.3, 0.7), rng.random() < 0.5)
    auto, sug = c.thresholds()
    print("thresholds:", auto, sug)
    assert 0.85 <= auto <= 0.96 and sug < auto
    noisy = Calibrator(None, target=0.97, min_samples=30)
    for i in range(80):
        noisy.record(f"n{i}", rng.uniform(0.5, 1.0), rng.random() < 0.6)   # never reaches 97%
    assert noisy.thresholds()[0] > 1.0                                      # so: never auto-move


def test_evaluate_and_tune():
    with tempfile.TemporaryDirectory() as tmp:
        root, _ = build_library(tmp, domains=("Gardening", "Cricket", "Astronomy"), n=12)
        pilot = DocPilot(root, Path(tmp) / "st", embedder=HashingEmbedder())
        m = pilot.tune(folds=4)
        print({k: v for k, v in m.items() if k != "pairs"})
        assert m["top1_accuracy"] >= 0.9
        if m["auto_precision"] is not None:
            assert m["auto_precision"] >= 0.95


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
