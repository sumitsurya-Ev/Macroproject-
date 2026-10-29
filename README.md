# DocPilot — Intelligent Document Intake & Automated Routing System

> **Catching documents at arrival — so critical files never get lost.**

DocPilot is an automated document ingestion, classification, and organization system designed to eliminate manual filing for professionals (chartered accountants, legal practices, real estate firms, and SMEs).

---

## 📂 Repository Structure

```
.
├── docpilot/                                    # Core Software Application
│   ├── app.py                                   # Flask web server & REST API
│   ├── ai_classifier.py                         # Multi-tier AI classification (Gemini -> OpenAI -> Keyword)
│   ├── classifier.py                            # Fast offline rule-based classification engine
│   ├── extractor.py                             # PDF text parsing (pypdf)
│   ├── filer.py                                 # Safe filesystem routing & dynamic folder creation
│   ├── database.py                              # SQLite schema, duplicate detection & audit logs
│   ├── watcher.py                               # Real-time background folder watcher (watchdog)
│   ├── run_production.py                        # Production WSGI server (Waitress)
│   ├── requirements.txt                         # Python dependencies
│   ├── Procfile & render.yaml                   # Cloud deployment configs (Render / Railway / Heroku)
│   ├── Dockerfile & .dockerignore               # Containerized deployment
│   ├── templates/                               # Modern minimal web dashboard UI
│   └── DEPLOYMENT.md                            # Comprehensive deployment instructions
│
├── Project Documentation & Research Reports
│   ├── Problem_Identification_and_Requirement_Analysis.docx
│   ├── System_Design_and_Planning.docx
│   ├── Implementation_and_Development.docx
│   ├── Testing_and_Validation.docx
│   ├── Competitive_Analysis_and_Market_Landscape.docx
│   ├── Modern_AI_File_Classifiers_Analysis.docx
│   ├── Startup_Pitch_Deck_and_Strategy.docx
│   ├── Startup_Pitch_Deck_India_Market.docx
│   ├── DocPilot_Executive_Presentation.pptx
│   └── DocPilot Presentation.pptx
│
└── .gitignore
```

---

## ⚡ Quick Start

### 1. Run Web Dashboard
```bash
cd docpilot
pip install -r requirements.txt
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

### 2. Run Production Server (Local / Office LAN)
```bash
cd docpilot
python run_production.py
```

### 3. Run Real-Time Folder Watcher
```bash
cd docpilot
python watcher.py
```

---

## 🚀 Cloud Deployment
See [docpilot/DEPLOYMENT.md](docpilot/DEPLOYMENT.md) for full instructions on deploying to Render, Docker, or Windows Server.
