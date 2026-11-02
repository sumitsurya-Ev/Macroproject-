# DocPilot v3 — Complete Execution Plan

**Product decisions confirmed:**
- Local-first. All data stays on your machine.
- Image support required. OCR pipeline included.
- Search by description is a core feature, not an afterthought.

---

## What This Plan Builds

When finished, DocPilot will:

1. Run silently in the background on Windows startup, watching your Downloads,
   Desktop, and WhatsApp folders without any terminal window open.
2. Process PDF files whether they are native text or scanned images.
3. Process image files (JPG, PNG, WEBP) dropped into watched folders — for
   example, a photo of a receipt shared over WhatsApp.
4. Let you find any filed document by typing a description, not just a filename.
   "That HDFC invoice from October" will return the right document even if the
   file was saved as `downloaded_file_443.pdf`.

---

## Phase 0 — Foundation (must complete before anything else)

These are corrections to live bugs, not new features.

---

### 0.1 — Path Anchoring

**What the problem is:**
Every path in the system — the database file, the uploads folder, the filed
folder — is written as a bare name like `"docpilot.db"` or `"uploads"`.
Python resolves these relative to whichever directory the process was started
from. When you run the app by double-clicking a file, or via Windows autostart,
the starting directory is not the docpilot folder, so the app creates a new
empty database somewhere else and appears to have lost all your data.

**What changes:**
One constant, `BASE_DIR`, is added to `config.py`. It is derived from the
location of `config.py` itself, which never changes:

```
BASE_DIR = /path/to/e:/Macro project/docpilot/   (always, regardless of CWD)
```

Then:
```
database.py  — DB_PATH       becomes BASE_DIR/docpilot.db
app.py       — UPLOAD_FOLDER becomes BASE_DIR/uploads
filer.py     — BASE_FILED_DIR becomes BASE_DIR/filed
watcher.py   — UPLOADS_FOLDER becomes BASE_DIR/uploads
```

Five file edits, no logic changes. Tests re-run afterward to confirm nothing
broke.

---

### 0.2 — Image Mis-Filing Fix

**What the problem is:**
`watcher.py` accepts `.jpg`, `.png`, `.webp` files. When one arrives,
it copies it to the uploads folder and calls `extract_text()`. That function
calls PyPDF's `PdfReader` on a JPEG, which throws an error that is silently
caught, returning an empty string. The empty string is classified as `Other`
at 0% confidence and inserted into the review queue. Every WhatsApp image
currently pollutes the review queue with useless entries.

**What changes:**
Before Phase 2A (OCR) ships, the fix is a guard at the start of `_process()`:

```
If file is an image (.jpg/.png/.webp):
    If OCR is installed → proceed to OCR extraction (Phase 2A)
    If OCR is NOT installed → skip this file cleanly, log the reason, do not insert
    
If file is a PDF:
    Attempt pypdf extraction
    If pypdf returns < 50 characters → file is scanned → route to OCR (Phase 2A)
    If Phase 2A not installed → insert with status=needs_ocr, do not classify
```

This stops the garbage from entering the database. Once Phase 2A is installed,
all deferred `needs_ocr` documents are reprocessed automatically.

---

### 0.3 — Minimum Authentication

**What the problem is:**
Every route on the Render-hosted URL is publicly accessible. Anyone with the
link can upload files, read your document log, and see extracted content from
everything you have filed.

**What changes:**
A `users` table is added to the database. On first startup, if the table is
empty, the app redirects every page to a setup screen that asks for a password.
After that:

- The web UI requires a session cookie, set after entering the password.
- The `/api/*` routes require a `X-DocPilot-Token` header.
- The token is shown once in Settings and can be regenerated.
- Session duration: 30 days by default, configurable.

The password is stored as a bcrypt hash. The plaintext is never stored anywhere.

This is the minimum before the live URL is safe to share or use for real
documents.

---

### 0.4 — Health Endpoint

A single endpoint `/api/health` that returns the current system state:

```json
{
  "status": "ok",
  "version": "3.0.0",
  "ocr_available": false,
  "db_connected": true,
  "ai_provider": "gemini",
  "watcher_active": false,
  "pending_ocr": 0
}
```

Used by the browser extension (Phase 3) to confirm the local server is running
before sending anything, and useful for debugging.

---

## Phase 2A — OCR Pipeline (image support + scanned PDF support)

**What this enables:**
- Photos of receipts from WhatsApp: processed correctly
- Scanned bank statements: processed correctly
- Camera photos of documents: processed correctly

**Prerequisite — Tesseract installation:**
Tesseract is the OCR engine. It is not a Python package; it is a separate
program that must be installed once:

```
winget install UB-Mannheim.TesseractOCR
```

This requires administrator rights and takes about 2 minutes. After that,
all OCR functionality works offline with no API key.

---

### How the OCR pipeline works, step by step

**Step 1 — Detect whether text extraction is possible:**

```
File arrives (PDF or image)
  │
  ├─ If PDF:
  │    Try pypdf → if result has ≥ 50 characters → use that text (fast path)
  │    If result < 50 characters → file is scanned → go to Step 2
  │
  └─ If image (JPG/PNG/WEBP):
       Go directly to Step 2
```

**Step 2 — OCR preprocessing:**

Raw images and scanned PDFs are often imperfect: tilted, too dark, too light,
or noisy. Before feeding to Tesseract, each page image goes through three
quick fixes using OpenCV (a image processing library):

```
Convert to grayscale          (removes color noise)
Apply Otsu thresholding       (makes text black, background white, removes shadows)
Confirm 300 DPI rendering     (Tesseract accuracy drops sharply below 300 DPI)
```

This preprocessing step alone improves Tesseract's accuracy from roughly 70%
to 90%+ on typical document scans.

**Step 3 — Extract text:**

```
PDF pages → convert each page to 300 DPI image → preprocess → Tesseract → text
Image file → preprocess → Tesseract → text
```

**Step 4 — Feed extracted text into the existing classification pipeline:**

The OCR output goes to exactly the same classifier that text-based PDFs use.
No other changes needed. The classifier does not know or care how the text
was obtained.

---

### New file: `ocr_engine.py`

```
ocr_engine.py
  is_ocr_available()          → bool: checks if Tesseract is on PATH
  extract_text_from_image()   → str: runs Tesseract on an image file
  extract_text_from_scanned_pdf() → str: converts pages, runs Tesseract on each
```

`extractor.py` is updated to call `ocr_engine.py` when pypdf returns too little
text.

---

### What happens to `needs_ocr` documents after installation

When Phase 2A is installed and Tesseract is confirmed present, a one-time
migration runs at startup:

```
For each document where status = 'needs_ocr':
    Re-extract text using OCR
    Re-classify
    Update status to filed / pending_approval / needs_review accordingly
```

This means no documents are permanently stuck. Installing Tesseract later
processes everything that was deferred.

---

## Phase 2B — Structural Classifier Rewrite

**What the problem is:**
The current keyword classifier (`classifier.py:99`) uses this formula:

```python
score = min(ratio * weight * 5, weight)
# ratio = matched_keywords / total_keywords
```

An Invoice with 20 keywords that matches 3 scores: `3/20 * 0.90 * 5 = 0.68`,
which sends it to the review queue even though it has a GSTIN and a tax invoice
header — clear structural evidence.

**What changes:**
Two-stage approach.

**Stage 1 — Structural flags (replaces score multipliers):**

A set of high-precision regex patterns detect definitive signals. Each signal
narrows the candidate category. Signals do not produce scores; they produce
a shortlist:

```
GSTIN pattern found             → candidate set: [Invoice, Purchase Order, Tax Return]
"Account Statement" header      → candidate set: [Bank Statement]
"salary" + "earnings" found     → candidate set: [Salary Slip]
"Tenant" + "Landlord" found     → candidate set: [Lease]
"hereinafter" + "parties"       → candidate set: [Contract]
"ITR" + "assessment year"       → candidate set: [Tax Return]
"Aadhaar" or "PAN CARD" header  → candidate set: [KYC Document]
```

If the shortlist has exactly one candidate → that is the document type.
Score it only against its own category keywords (much higher scores result).

If the shortlist has 2–3 candidates → score all of them, take the highest.

If no signals fire → fall back to full keyword scoring across all categories
(current behavior, as a last resort).

**Stage 2 — AI enrichment (only for ambiguous cases):**

When Stage 1 produces a shortlist with 2+ candidates whose scores are within
15% of each other, and an API key is set, the AI is called with the shortlist
provided in the prompt. This costs one API call per genuinely ambiguous
document, rather than one per document.

When no API key is set, the highest-scored candidate from Stage 1 is used,
with a confidence penalty applied to reflect the ambiguity.

---

## Phase S — Search and Retrieval

This is the feature the user specifically asked for. The design objective is
that a user who cannot remember the filename, the date, or the exact type of
document should be able to describe it in plain language and find it reliably.

---

### What "search by description" actually means technically

When a user types "that HDFC invoice from October", the system needs to:

1. Understand that "HDFC" is a vendor name or bank name.
2. Understand that "October" is a date filter.
3. Understand that "invoice" is a document type.
4. Return documents that match any combination of these signals.

The approach uses three layers working together, all offline:

---

### Layer 1 — SQLite FTS5 Full-Text Search

FTS5 is a built-in SQLite extension for full-text search. It is already
available in the Python 3.11 SQLite bundled here (confirmed: version 3.45.1).

A virtual table indexes selected document fields:

```sql
CREATE VIRTUAL TABLE docs_fts USING fts5(
    filename,
    suggested_name,
    doc_type,
    vendor,
    amount,
    date,
    reference_no,
    reasoning,
    full_text,          -- full OCR/pypdf extracted text, stored separately
    content='documents',
    content_rowid='id'
);
```

This means a search for "HDFC bank statement" finds all documents where those
words appear in any of those fields.

**What FTS5 provides:**
- Prefix matching: "inv" matches "Invoice", "INV-0042"
- Phrase search: `"tax invoice"` matches exactly that phrase
- Field-specific search: `vendor:Acme` matches only the vendor field
- Ranking by relevance (BM25 algorithm, built in)
- Case-insensitive

**Current limitation — extracted text is not stored:**
Right now the database stores only metadata (type, confidence, entities).
The full extracted text is discarded after classification. For search to work
on document content, extracted text must be stored. A new column `full_text`
is added to the `documents` table and the FTS index.

---

### Layer 2 — Query Understanding

Before hitting FTS5, the search query is parsed to extract structured signals:

**Date patterns:**

| User types | Parsed as |
|---|---|
| "October" / "october 2026" | month=10, year=2026 |
| "last month" | month = current - 1 |
| "Q3" / "quarter 3" | months = July-September |
| "2024-2025" | financial year filter |

**Amount patterns:**

| User types | Parsed as |
|---|---|
| "45000" / "45,000" | amount_approx = 45000 |
| "1.5 lakh" / "1 lakh 50" | amount_approx = 150000 |
| "around 50k" | amount_range = 40000–60000 |

**Type hints:**

| User types | Applied as filter |
|---|---|
| "invoice" / "bill" | doc_type = Invoice |
| "rent" / "tenancy" | doc_type = Lease |
| "salary" / "payslip" | doc_type = Salary Slip |
| "bank statement" / "account" | doc_type = Bank Statement |

These patterns are implemented as a local Python parser — no API call needed.

**What happens with the parsed output:**
Structured signals become SQL WHERE clauses applied before or alongside FTS5.
Remaining unstructured words become the FTS5 query. Both results are merged
and ranked.

---

### Layer 3 — AI-Assisted Query Expansion (when API key is set)

For queries that the local parser cannot decode — for example, "that contract
about the office maintenance in Andheri" — the AI is given the query and the
list of document types as context, and returns a structured interpretation:

```json
{
  "doc_type": "Contract",
  "keywords": ["office maintenance", "Andheri"],
  "date_range": null,
  "vendor": null
}
```

This feeds back into Layer 1 and 2. The AI does not need to see document
content; it only interprets the user's query. This is cheap: one short API
call per search, and only when the local parser produces no useful signals.

---

### What the search page looks like

URL: `/search`

Layout:
```
[ Search bar — "Describe the document you are looking for..." ]

Filters (collapsible sidebar):
  Document Type: [All] [Invoice] [Contract] [Lease] [Receipt] ...
  Date Filed: [Any] [Today] [This week] [This month] [Custom]
  Status: [Filed only] [All including review queue]

Results (card per document):

  ┌─────────────────────────────────────────────────────────────┐
  │  Invoice                                       96%           │
  │  2026-10-15_HDFC_Invoice_INV-0422.pdf                       │
  │                                                             │
  │  Vendor: HDFC Bank    Amount: Rs. 12,400    Date: 15 Oct    │
  │  Filed in: Invoices/                                        │
  │                                                             │
  │  "...payment due for account maintenance charges GSTIN      │
  │   27AAPCA1538Q1ZG total amount 12,400..."                   │
  │                                         [Open Folder]       │
  └─────────────────────────────────────────────────────────────┘
```

The text snippet shown under each result has the matched query terms
highlighted. This tells the user exactly why that result was returned.

**Keyboard navigation:**
- Typing in the search bar triggers live results (debounced, 300ms after
  last keystroke — no submit button needed)
- Arrow keys navigate between results
- Enter opens the top result's folder

---

### How existing documents get indexed

Documents inserted before Phase S existed will not have `full_text` stored.
At Phase S startup, a one-time backfill runs:

```
For each filed document:
    If full_text column is empty:
        Re-extract text from the file at source_path (if file still exists)
        Update the full_text column
        Update the FTS index
```

Documents whose source files no longer exist cannot be backfilled for full-text
search, but they remain searchable by all metadata fields (type, vendor, amount,
suggested name, date).

---

### API endpoint for search

`GET /search?q=HDFC+invoice+october&type=Invoice&limit=20`

Returns JSON (for the live-search JavaScript) or renders the full search page
(for direct navigation). The same endpoint handles both, distinguished by the
`Accept` header.

```json
{
  "query": "HDFC invoice october",
  "parsed": { "doc_type": "Invoice", "vendor_hint": "HDFC", "month": 10 },
  "count": 3,
  "results": [
    {
      "id": 47,
      "filename": "downloaded_file_443.pdf",
      "suggested_name": "2026-10-15_HDFC_Invoice_INV-0422",
      "doc_type": "Invoice",
      "confidence": 0.96,
      "vendor": "HDFC Bank",
      "amount": "Rs. 12,400",
      "date": "2026-10-15",
      "destination": "Invoices",
      "snippet": "...payment due for account maintenance charges...",
      "match_score": 18.4
    }
  ]
}
```

---

## Phase 1 — Background Service and System Tray

Builds on the corrected foundation from Phase 0. Not scheduled until Phase 2A
has been verified working end-to-end.

**What this adds:**
- DocPilot starts automatically on Windows login (no terminal window needed)
- A small icon appears in the system tray (bottom-right of taskbar)
- Right-clicking the icon: Open Dashboard / Pause Watching / Quit
- A Windows notification (toast) appears within 2–3 seconds of any file being
  processed, showing what was filed and where

**One confirmed limitation:**
Windows toast notifications cannot contain interactive buttons (Approve /
Rename) reliably across Windows 10/11 versions. Toasts are informational only.
Approving a new folder still requires opening the dashboard. The toast includes
a direct link.

**New files:**
- `docpilot_tray.py` — entry point that starts Flask, watcher, and tray icon
  in coordinated threads
- `setup_autostart.py` — registers the startup entry via `winreg`, handles path
  quoting correctly for paths with spaces

---

## Phase 3 — Browser Extension (simplified)

Connects the Chrome/Edge download event directly to DocPilot, removing the
need for the watchdog folder approach for browser downloads.

**How it works:**
The extension listens for any download completing in Chrome. When a PDF or
image finishes downloading, it sends the absolute file path to
`http://127.0.0.1:5000/api/download-hook` with a bearer token. DocPilot
processes the file the same way the watcher would, without needing to watch
the Downloads folder at all.

**No native messaging.** Under Chrome Manifest V3, the extension can POST
directly to localhost using `host_permissions`. No registry entries, no host
manifest, no `.bat` wrapper. Installation is: open `chrome://extensions`,
enable Developer Mode, click Load Unpacked, select the extension folder.

**Extension folder contents:**
```
docpilot_extension/
  manifest.json       (MV3, permissions: downloads, host_permissions: localhost)
  background.js       (service worker: hooks download completion)
  popup/
    popup.html        (small status popup: last file processed, link to dashboard)
    popup.js
  icons/
    icon16.png  icon48.png  icon128.png
```

---

## Execution Sequence Summary

```
Phase 0 — path fix, image mis-filing fix, auth
    |
    +-- verified with: python test_app.py + python test_v2_flow.py pass
    |
Phase 2A — Tesseract install, ocr_engine.py, extractor.py update
    |
    +-- verified with: test a scanned PDF and a JPEG, both classified correctly
    |
Phase 2B — structural_signals.py, classifier rewrite, confidence formula
    |
    +-- verified with: existing test_pipeline.py still 100% pass rate
    |
Phase S — full_text column, FTS5 index, query parser, /search route, search.html
    |
    +-- verified with: search for "Acme vendor Q3 report" returns correct doc
    |
Phase 1 — docpilot_tray.py, autostart registration, toast notifications
    |
    +-- verified with: reboot, confirm tray icon present, drop file in Downloads
    |
Phase 3 — browser extension, /api/download-hook, popup UI
    |
    +-- verified with: download a PDF in Chrome, confirm it appears in dashboard
```

---

## What Needs Your Approval Before Execution Starts

One prerequisite that requires action on your side:

**Tesseract installation (for Phase 2A):**
Run this in a terminal with administrator rights:

```
winget install UB-Mannheim.TesseractOCR
```

This takes about 2 minutes. Without it, Phase 2A cannot be verified end-to-end.
You do not need to do this before Phase 0 — Phase 0 can start immediately.

**Confirm and I will start Phase 0 immediately.**
