"""Extraction router: turn any file into text + a quality score.

Key ideas
- Detect type by magic bytes, never by extension alone.
- Never read a half-downloaded file (partial extensions + size-stability check).
- A PDF text layer is only trusted if it passes a quality check; otherwise OCR it.
- Every stage has a timeout and fails soft: worst case we fall back to filename-only.
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path

try:
    from .doc_types import Doc
except (ImportError, ValueError):
    from docpilot.doc_types import Doc

PARTIAL_EXT = {".crdownload", ".part", ".tmp", ".download", ".opdownload", ".partial"}
MAX_CHARS = 20000
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".html", ".xml", ".rtf"}
OFFICE_EXT = {".docx", ".xlsx", ".pptx"}


# ----------------------------------------------------------------- capture helpers
def is_partial(path) -> bool:
    p = Path(path)
    return p.suffix.lower() in PARTIAL_EXT or p.name.startswith("~$") or p.name.startswith(".")


def wait_until_stable(path, checks: int = 3, interval: float = 1.0, timeout: float = 120) -> bool:
    """True once the file size has not changed for `checks` consecutive polls."""
    last, same, start = None, 0, time.time()
    while time.time() - start < timeout:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size > 0 and size == last:
            same += 1
            if same >= checks:
                try:
                    with open(path, "rb"):
                        return True
                except OSError:      # still locked by the browser
                    same = 0
        else:
            same, last = 0, size
        time.sleep(interval)
    return False


def sniff_type(path) -> str:
    with open(path, "rb") as f:
        head = f.read(16)
    ext = Path(path).suffix.lower()
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith((b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"BM")) or (
        head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    ):
        return "image"
    if head.startswith(b"PK\x03\x04"):
        return "office" if ext in OFFICE_EXT else "archive"
    if head.startswith(b"MZ"):
        return "other"
    if ext in TEXT_EXT:
        return "text"
    return "other"


def source_url(path) -> str:
    """Where the file was downloaded from (a very strong, free signal)."""
    try:
        if sys.platform == "win32":
            urls = []
            with open(str(path) + ":Zone.Identifier", "r", errors="ignore") as f:
                for line in f:
                    if line.startswith(("HostUrl=", "ReferrerUrl=")):
                        urls.append(line.split("=", 1)[1].strip())
            return next((u for u in urls if u.startswith("http")), "")
        if sys.platform == "darwin":
            out = subprocess.run(
                ["mdls", "-raw", "-name", "kMDItemWhereFroms", str(path)],
                capture_output=True, text=True, timeout=5,
            ).stdout
            m = re.search(r"https?://[^\s\",)]+", out)
            return m.group(0) if m else ""
        return os.getxattr(path, "user.xdg.origin.url").decode()
    except Exception:
        return ""


# ----------------------------------------------------------------- quality check
_WORDLIKE = re.compile(r"[A-Za-z]{2,20}|[\u0900-\u097F]{2,20}")
_VOWEL = re.compile(r"[aeiouAEIOU\u0900-\u097F]")


def text_quality(text: str, pages: int) -> float:
    """0..1 share of word-like tokens; 0 if the page has almost no text.

    Scanned PDFs usually have an empty text layer (or garbage like 'l1|]x~').
    Below 50 chars/page or under 0.6 word-like tokens we do not trust the layer.
    """
    if pages <= 0 or len(text.strip()) / pages < 50:
        return 0.0
    toks = text.split()
    if not toks:
        return 0.0
    good = 0
    for t in toks:
        t = t.strip(".,;:()[]{}\"'")
        if _WORDLIKE.fullmatch(t) and (len(t) <= 3 or _VOWEL.search(t)):
            good += 1
    return good / len(toks)


# ----------------------------------------------------------------- OCR
_engine = None
_image_labeler = None   # optional hook: callable(PIL.Image) -> str, e.g. CLIP zero-shot labels


def set_image_labeler(fn):
    global _image_labeler
    _image_labeler = fn


def _get_ocr():
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _engine = RapidOCR()
        except Exception:
            _engine = False
    return _engine or None


def preprocess(img):
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.autocontrast(img)
    if min(img.size) < 1000:                       # small screenshots OCR badly unless upscaled
        s = 1000 / min(img.size)
        img = img.resize((int(img.width * s), int(img.height * s)))
    return img.convert("RGB")


def ocr_image(img):
    """-> (text, mean_confidence 0..1). Empty result if no OCR engine is installed."""
    engine = _get_ocr()
    if engine is None:
        return "", 0.0
    import numpy as np
    result, _ = engine(np.array(preprocess(img)))
    if not result:
        return "", 0.0
    texts = [r[1] for r in result]
    confs = [float(r[2]) for r in result]
    return "\n".join(texts), sum(confs) / len(confs)


# ----------------------------------------------------------------- per-type extractors
def _sample_pages(n: int) -> list[int]:
    return sorted(set(list(range(min(3, n))) + ([n - 1] if n else [])))


def _pdf(doc: Doc):
    import fitz  # PyMuPDF
    d = fitz.open(doc.path)
    if d.needs_pass:
        doc.warnings.append("encrypted_pdf")
        doc.kind, doc.ocr_conf = "pdf_text", 0.3
        return
    n = len(d)
    idx = _sample_pages(n)
    doc.meta["pages"] = n
    doc.meta["title"] = (d.metadata or {}).get("title") or ""
    text = "\n".join(d[i].get_text() for i in idx)
    q = text_quality(text, len(idx))
    doc.meta["text_quality"] = round(q, 2)
    if q >= 0.6:
        doc.kind, doc.text, doc.ocr_conf = "pdf_text", text, 1.0
        return
    doc.kind = "pdf_scanned"
    if not doc.meta.get("allow_ocr", True):
        doc.ocr_conf = 0.3
        return
    parts, confs = [], []
    for i in idx:                                  # first 3 pages + last page is enough to classify
        png = d[i].get_pixmap(dpi=200).tobytes("png")
        from PIL import Image
        t, c = ocr_image(Image.open(io.BytesIO(png)))
        if t:
            parts.append(t)
            confs.append(c)
    doc.text = "\n".join(parts)
    doc.ocr_conf = sum(confs) / len(confs) if confs else 0.0
    if _get_ocr() is None:
        doc.warnings.append("no_ocr_engine")


def _image(doc: Doc):
    from PIL import Image
    img = Image.open(doc.path)
    doc.meta["size"] = img.size
    try:
        exif = img.getexif()
        if exif:
            doc.meta["exif_date"] = str(exif.get(306, ""))
            doc.meta["camera"] = str(exif.get(272, ""))
    except Exception:
        pass
    doc.kind = "image"
    if doc.meta.get("allow_ocr", True):
        doc.text, doc.ocr_conf = ocr_image(img)
        if _get_ocr() is None:
            doc.warnings.append("no_ocr_engine")
    else:
        doc.ocr_conf = 0.3
    if len(doc.text.strip()) < 20:                 # photo / diagram: little or no text
        doc.kind = "image_photo"
        if _image_labeler:
            try:
                doc.text = (doc.text + " " + _image_labeler(img)).strip()
                doc.ocr_conf = max(doc.ocr_conf, 0.6)
            except Exception:
                pass


def _office(doc: Doc):
    ext = Path(doc.path).suffix.lower()
    doc.kind = "office"
    if ext == ".docx":
        import docx
        d = docx.Document(doc.path)
        doc.text = "\n".join(p.text for p in d.paragraphs[:300])
    elif ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(doc.path, read_only=True, data_only=True)
        rows = [f"sheet {ws.title}" for ws in wb.worksheets]
        for ws in wb.worksheets[:3]:
            for row in ws.iter_rows(min_row=1, max_row=30, values_only=True):
                rows.append(" ".join(str(c) for c in row if c is not None))
        doc.text = "\n".join(rows)
    elif ext == ".pptx":
        from pptx import Presentation
        out = []
        for slide in list(Presentation(doc.path).slides)[:15]:
            for sh in slide.shapes:
                if sh.has_text_frame:
                    out.append(sh.text_frame.text)
        doc.text = "\n".join(out)


def _text(doc: Doc):
    doc.kind = "text"
    raw = Path(doc.path).read_text(errors="ignore")[:MAX_CHARS]
    if Path(doc.path).suffix.lower() in {".csv", ".tsv"}:
        raw = "\n".join(" ".join(r) for _, r in zip(range(40), csv.reader(io.StringIO(raw))))
    doc.text = raw


def _archive(doc: Doc):
    doc.kind = "archive"
    with zipfile.ZipFile(doc.path) as z:
        doc.text = " ".join(z.namelist()[:100])
    doc.ocr_conf = 0.5


def _other(doc: Doc):
    doc.kind = "other"
    doc.ocr_conf = 0.3     # filename-only: never auto-move on this alone


_ROUTER = {"pdf": _pdf, "image": _image, "office": _office, "text": _text, "archive": _archive, "other": _other}


def extract(path, timeout: float = 30, allow_ocr: bool = True) -> Doc:
    path = str(path)
    doc = Doc(path=path)
    doc.meta["ext"] = Path(path).suffix.lower()
    doc.meta["allow_ocr"] = allow_ocr
    doc.source_url = source_url(path)
    try:
        fn = _ROUTER[sniff_type(path)]
    except Exception as e:
        doc.warnings.append(f"sniff_error:{type(e).__name__}")
        fn = _other
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(fn, doc)
    try:
        fut.result(timeout=timeout)
    except FutureTimeout:
        doc.warnings.append("timeout")
        doc.ocr_conf = min(doc.ocr_conf, 0.3)
    except Exception as e:                         # corrupt file, missing library, etc.
        doc.warnings.append(f"error:{type(e).__name__}")
        doc.ocr_conf = min(doc.ocr_conf, 0.3)
    finally:
        ex.shutdown(wait=False)
    doc.text = doc.text[:MAX_CHARS]
    if not doc.text.strip():
        doc.ocr_conf = min(doc.ocr_conf, 0.3)
    return doc
