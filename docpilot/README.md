# DocPilot — Intelligent Document Intake & Automated Routing System

> **Catching documents at arrival — so critical files never get lost.**

---

## 🚀 Quick Start on Windows

You have two ways to run DocPilot:

### Option 1: Web Dashboard (Interactive UI)
Double-click `run_dashboard.bat` or run:
```bash
python app.py
```
Then open your browser at **`http://127.0.0.1:5000`**

* **Upload:** Drag and drop any PDF (Invoice, Contract, Lease, Receipt).
* **Auto-File:** If confidence is $\ge 85\%$, the file is automatically moved into `filed/<Category>/`.
* **Review Queue:** If confidence is $< 85\%$, it is sent to `/review` for one-click human verification.
* **Audit Log:** View `/log` to see a full history of all processed files.

---

### Option 2: Automatic Background Watcher
Double-click `run_watcher.bat` or run:
```bash
python watcher.py
```
* Monitors the `./incoming/` folder in real time.
* Drop any PDF into `incoming/` — DocPilot immediately intercepts it, classifies it, moves it to the appropriate `filed/` directory, and logs it in `docpilot.db`.

---

## 📁 Project Architecture & Components

```
e:/Macro project/docpilot/
├── app.py                  # Flask Web Dashboard & API routes
├── classifier.py           # Keyword & confidence scoring engine (swappable for AI)
├── extractor.py            # PDF text extraction using pypdf
├── filer.py                # Safe filesystem file moving, folder creation & conflict resolution
├── database.py             # SQLite data access layer (schema, audit logs, stats)
├── watcher.py              # Real-time folder monitor using watchdog
├── docpilot.db             # SQLite database storing file records & audit logs
│
├── templates/              # Modern, responsive Jinja2 templates
│   ├── base.html           # Base layout, navbar, alert flashes & drag-drop logic
│   ├── index.html          # Stats cards, upload box, recent activity
│   ├── result.html         # Document classification breakdown & details
│   ├── review_queue.html   # Human-in-the-loop review & override interface
│   └── filed_log.html      # Searchable audit log of all filed documents
│
├── test_samples/           # 5 sample PDFs generated with reportlab
│   ├── sample_tax_invoice.pdf
│   ├── sample_rental_lease.pdf
│   ├── sample_nda_contract.pdf
│   ├── sample_payment_receipt.pdf
│   └── sample_ambiguous_notes.pdf
│
├── test_pipeline.py        # Automated verification script testing all 5 sample PDFs
├── test_app.py             # End-to-end integration test verifying all web routes
├── run_dashboard.bat       # 1-click Windows launcher for Web Dashboard
└── run_watcher.bat         # 1-click Windows launcher for Folder Watcher
```

---

## 🧪 Running Verification Tests

Run the test suite anytime:
```bash
# Test classification & confidence scoring on sample PDFs:
python test_pipeline.py

# Test Flask Web Dashboard routes end-to-end:
python test_app.py
```

---

## 🔮 Next Upgrade: Multimodal AI
To switch from keyword classification to multimodal AI (Claude or OpenAI API), simply update `classify(text)` in `classifier.py` to return the same structured dictionary:
```python
{
    "type": "Invoice",
    "confidence": 0.95,
    "keywords_matched": ["tax invoice", "gstin"],
    "status": "filed"  # or "needs_review"
}
```
All other components (confidence thresholding, folder routing, review queue, database) remain completely unchanged!
