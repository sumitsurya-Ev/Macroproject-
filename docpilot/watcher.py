"""
watcher.py — Background Folder Watcher for Windows.
Monitors the 'incoming/' folder in real time.
Automatically detects when a PDF arrives, extracts text, classifies it,
and routes it:
  - If Confidence >= 85%: Auto-filed to filed/<Category>/
  - If Confidence < 85%: Moved to uploads/ and queued for human review on Web UI.
"""

import os
import time
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from extractor import extract_text, is_pdf
from classifier import classify
from filer import file_document, get_destination_folder, ensure_folders
from database import init_db, insert_document

INCOMING_FOLDER = "incoming"
UPLOADS_FOLDER  = "uploads"

class DocumentArrivalHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        filepath = event.src_path
        filename = os.path.basename(filepath)

        if not is_pdf(filename):
            return

        print(f"\n[DocPilot Watcher] 📥 New document intercepted: {filename}")

        # Wait briefly to ensure file write is complete
        time.sleep(1.0)

        # Retry logic for reading if file is still locked by OS
        text = ""
        for attempt in range(5):
            try:
                text = extract_text(filepath)
                if text or attempt == 4:
                    break
            except Exception:
                time.sleep(0.5)

        # Classify document
        result = classify(text)
        doc_type   = result["type"]
        confidence = result["confidence"]
        status     = result["status"]
        pct        = round(confidence * 100, 1)

        print(f"[DocPilot Watcher] 🧠 AI Classified as: {doc_type} (Confidence: {pct}%)")

        dest_display = os.path.basename(get_destination_folder(doc_type))

        if status == "filed":
            # Auto-file directly
            dest_path = file_document(filepath, doc_type)
            print(f"[DocPilot Watcher] ✅ Auto-filed to: {dest_path}")
        else:
            # Low confidence: move to uploads for web review queue
            os.makedirs(UPLOADS_FOLDER, exist_ok=True)
            temp_dest = os.path.join(UPLOADS_FOLDER, filename)
            
            # If name collision, adjust
            if os.path.exists(temp_dest):
                base, ext = os.path.splitext(filename)
                temp_dest = os.path.join(UPLOADS_FOLDER, f"{base}_{int(time.time())}{ext}")
            
            os.rename(filepath, temp_dest)
            print(f"[DocPilot Watcher] ⚠️ Low confidence (<85%). Sent to Web Review Queue: {temp_dest}")

        # Record in database
        insert_document(
            filename=filename,
            doc_type=doc_type,
            confidence=confidence,
            destination=dest_display,
            status=status
        )
        print(f"[DocPilot Watcher] 💾 Audit record saved to docpilot.db\n")

def start_watching():
    os.makedirs(INCOMING_FOLDER, exist_ok=True)
    os.makedirs(UPLOADS_FOLDER, exist_ok=True)
    ensure_folders()
    init_db()

    event_handler = DocumentArrivalHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INCOMING_FOLDER, recursive=False)
    observer.start()

    print("=" * 65)
    print("  🚀 DocPilot Intelligent Folder Watcher Active")
    print(f"  Watching folder: ./{INCOMING_FOLDER}/")
    print("  Auto-filing threshold: >= 85% confidence")
    print("  Press Ctrl+C to stop.")
    print("=" * 65)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[DocPilot Watcher] Stopped.")
    observer.join()

if __name__ == "__main__":
    start_watching()
