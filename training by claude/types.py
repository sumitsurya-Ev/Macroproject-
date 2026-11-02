from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Doc:
    path: str
    kind: str = "other"          # pdf_text | pdf_scanned | image | image_photo | office | text | archive | other
    text: str = ""
    ocr_conf: float = 1.0        # 1.0 = native text; lower = OCR quality (feeds the confidence penalty)
    source_url: str = ""
    meta: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


@dataclass
class Decision:
    action: str                                  # auto_move | suggest | review | new_folder
    folder: Optional[str] = None
    alt: Optional[str] = None
    confidence: float = 0.0
    signals: dict = field(default_factory=dict)  # signal name -> that signal's top folder
    tier: str = "local"
    new_folder: Optional[dict] = None            # {"name","description"} when a folder should be created
    warnings: list = field(default_factory=list)
