"""
extractor.py — Extracts text from PDF files using pypdf.
"""

import os
from pypdf import PdfReader

def extract_text(filepath: str) -> str:
    """
    Extract all text from a PDF file.
    Returns empty string if file is unreadable or has no extractable text.
    """
    try:
        reader = PdfReader(filepath)
        pages_text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
        return "\n".join(pages_text)
    except Exception as e:
        print(f"[Extractor] Could not read {filepath}: {e}")
        return ""

def is_pdf(filepath: str) -> bool:
    return filepath.lower().endswith(".pdf")
