"""
config.py — DocPilot configuration.

Set your API key as an environment variable before running:

  Windows PowerShell:
    $env:GEMINI_API_KEY = "your-key-here"
    $env:OPENAI_API_KEY = "your-key-here"   (alternative)

  Or create a .env file in the docpilot/ folder:
    GEMINI_API_KEY=your-key-here

Priority: GEMINI_API_KEY → OPENAI_API_KEY → keyword fallback
"""

import os

# ── Try loading a .env file if python-dotenv is installed ──
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── API Keys ──
GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "").strip()

# ── Active provider ──
if GEMINI_API_KEY:
    AI_PROVIDER = "gemini"
elif OPENAI_API_KEY:
    AI_PROVIDER = "openai"
else:
    AI_PROVIDER = "keyword"   # built-in fallback, no API needed

# ── Model choices ──
GEMINI_MODEL = "gemini-1.5-flash"   # free tier: 15 RPM, 1M tokens/min
OPENAI_MODEL = "gpt-4o-mini"        # very cheap: $0.15/1M input tokens

# ── Confidence threshold ──
CONFIDENCE_THRESHOLD = 0.85         # ≥ this → auto-file  |  < this → review queue

# ── Max text sent to AI (keep cost low) ──
MAX_TEXT_CHARS = 4000
