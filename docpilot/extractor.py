"""
extractor.py — Extracts text from documents (PDFs and images).
"""

import os
from pypdf import PdfReader
from PIL import Image

SUPPORTED_EXTENSIONS = (
    '.pdf', '.png', '.jpg', '.jpeg', '.webp',
    '.docx', '.xlsx', '.pptx',
    '.txt', '.csv', '.tsv', '.json', '.zip'
)

def extract_text(filepath: str) -> str:
    """
    Extract text from a document.
    Supports native PDFs, images, Office formats, and text/archive files.
    Returns empty string if file is unreadable.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        try:
            reader = PdfReader(filepath)
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            return "\n".join(pages_text)
        except Exception as e:
            print(f"[Extractor] Could not read PDF {filepath}: {e}")
            return ""

    elif ext in ('.png', '.jpg', '.jpeg', '.webp'):
        try:
            with Image.open(filepath) as img:
                w, h = img.size
                info = [f"Image Document: {os.path.basename(filepath)}", f"Dimensions: {w}x{h}", f"Format: {img.format}"]
                basename = os.path.splitext(os.path.basename(filepath))[0]
                info.append(f"Filename description: {basename.replace('_', ' ').replace('-', ' ')}")
                return " ".join(info)
        except Exception as e:
            print(f"[Extractor] Could not read Image {filepath}: {e}")
            return ""

    elif ext in ('.docx', '.xlsx', '.pptx', '.txt', '.csv', '.tsv', '.json', '.zip'):
        try:
            from docpilot.extract import extract
            return extract(filepath).text
        except Exception as e:
            print(f"[Extractor] Multi-format parse error for {filepath}: {e}")
            return ""

    return ""

def is_pdf(filepath: str) -> bool:
    return filepath.lower().endswith(".pdf")

def is_supported_document(filepath: str) -> bool:
    return filepath.lower().endswith(SUPPORTED_EXTENSIONS)
