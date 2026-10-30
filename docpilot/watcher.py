"""
watcher.py — DocPilot Multi-Folder Background Watcher v2.

Monitors multiple folders simultaneously (Downloads, Desktop, Documents, WhatsApp,
and any user-configured paths) in real time.

NON-DESTRUCTIVE: Always COPIES intercepted files — originals are never deleted
from Downloads or WhatsApp.

Pipeline per intercepted file:
  1. Wait for write to finish
  2. Hash check for deduplication
  3. Extract text
  4. AI classify
  5. Confidence >= 85% AND folder exists  → auto-file
     Confidence >= 85% AND new folder     → pending_approval (UI notification)
     Confidence < 85%                    → needs_review queue
"""

import os
import sys
import time
import shutil
import hashlib

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from extractor     import extract_text, is_pdf
from ai_classifier import ai_classify
from filer         import file_document, get_destination_folder, ensure_folders, folder_exists
from database      import (
    init_db, insert_document, check_duplicate,
    get_watcher_folders, add_watcher_folder,
)

UPLOADS_FOLDER = "uploads"
SUPPORTED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}   # PDF + images

# ── Default Windows folders to suggest (added automatically on first run) ──────
def _get_default_watch_paths():
    username = os.environ.get("USERNAME") or os.environ.get("USER", "")
    paths = []
    for folder in ["Downloads", "Desktop", "Documents"]:
        p = f"C:\\Users\\{username}\\{folder}"
        if os.path.isdir(p):
            paths.append((p, folder))
    # WhatsApp Desktop cache
    wa = f"C:\\Users\\{username}\\AppData\\Local\\Packages\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\\LocalCache\\Roaming\\WhatsApp\\Media"
    if os.path.isdir(wa):
        paths.append((wa, "WhatsApp Media"))
    return paths


def _wait_for_file(filepath, timeout=10):
    """Wait until the file is fully written (size stabilizes)."""
    prev_size = -1
    deadline  = time.time() + timeout
    while time.time() < deadline:
        try:
            size = os.path.getsize(filepath)
        except OSError:
            time.sleep(0.5)
            continue
        if size == prev_size and size > 0:
            return True
        prev_size = size
        time.sleep(0.8)
    return False


class DocPilotHandler(FileSystemEventHandler):
    """Handles file creation events from any watched folder."""

    def __init__(self, watch_label=""):
        self.watch_label = watch_label

    def on_created(self, event):
        if event.is_directory:
            return
        filepath = event.src_path
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in SUPPORTED_EXTS:
            return
        self._process(filepath)

    def on_moved(self, event):
        """Catches files moved/dropped into the watched folder."""
        if event.is_directory:
            return
        ext = os.path.splitext(event.dest_path)[1].lower()
        if ext not in SUPPORTED_EXTS:
            return
        self._process(event.dest_path)

    def _process(self, filepath):
        filename = os.path.basename(filepath)
        print(f"\n[DocPilot] Intercepted from {self.watch_label}: {filename}")

        # Wait for file write to finish
        if not _wait_for_file(filepath):
            print(f"[DocPilot] Timed out waiting for {filename} — skipping.")
            return

        # ── Hash for deduplication ──
        try:
            with open(filepath, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        except OSError as e:
            print(f"[DocPilot] Cannot read {filename}: {e}")
            return

        if check_duplicate(file_hash):
            print(f"[DocPilot] Duplicate skipped: {filename}")
            return

        # ── NON-DESTRUCTIVE: Copy to uploads/, leave original intact ──
        os.makedirs(UPLOADS_FOLDER, exist_ok=True)
        dest_copy = os.path.join(UPLOADS_FOLDER, filename)
        if os.path.exists(dest_copy):
            base, ext2 = os.path.splitext(filename)
            dest_copy = os.path.join(UPLOADS_FOLDER, f"{base}_{int(time.time())}{ext2}")
        try:
            shutil.copy2(filepath, dest_copy)
        except Exception as e:
            print(f"[DocPilot] Copy failed: {e}")
            return

        # ── Extract & classify ──
        text   = extract_text(dest_copy)
        result = ai_classify(text, original_filename=filename)

        doc_type   = result["type"]
        confidence = result["confidence"]
        smart_name = result.get("suggested_filename") or os.path.splitext(filename)[0]

        # ── Route decision ──
        is_new = not folder_exists(doc_type)
        dest   = get_destination_folder(doc_type)   # creates dir if needed
        dest_display = os.path.basename(dest)

        if result["status"] == "filed" and not is_new:
            # High confidence + existing folder → auto-file immediately
            file_document(dest_copy, doc_type)
            status = "filed"
            print(f"[DocPilot] Auto-filed: {filename} → {dest_display}/")
        elif result["status"] == "filed" and is_new:
            # High confidence BUT brand-new folder → ask user on dashboard
            status = "pending_approval"
            print(f"[DocPilot] Pending approval: {filename} → wants to create {dest_display}/")
        else:
            # Low confidence → review queue
            status = "needs_review"
            print(f"[DocPilot] Review needed: {filename} ({confidence*100:.0f}%)")

        insert_document(
            filename      = filename,
            doc_type      = doc_type,
            confidence    = confidence,
            destination   = dest_display,
            status        = status,
            reasoning     = result.get("reasoning", ""),
            entities      = result.get("entities", {}),
            suggested_name= smart_name,
            provider      = result.get("provider", "keyword"),
            file_hash     = file_hash,
            source_path   = dest_copy,
        )
        print(f"[DocPilot] Done: {filename} — {status}")


# ─────────────────────────────────────────────────────────────────────────────
# Main watcher runner
# ─────────────────────────────────────────────────────────────────────────────
def run_watcher():
    ensure_folders()
    init_db()

    # Seed default watch folders into DB if table is empty
    existing = [r["folder_path"] for r in get_watcher_folders()]
    if not existing:
        print("[DocPilot] First run — seeding default watch folders...")
        for path, label in _get_default_watch_paths():
            add_watcher_folder(path, label)
            print(f"  + {label}: {path}")

    # Load enabled watch folders from DB
    watch_rows = get_watcher_folders()
    enabled    = [r for r in watch_rows if r["enabled"]]

    if not enabled:
        print("[DocPilot] No enabled watch folders. Configure them in Settings → Watched Folders.")
        print("[DocPilot] Falling back to local 'incoming/' folder.")
        # Fallback: watch local incoming/ folder
        os.makedirs("incoming", exist_ok=True)
        enabled = [{"folder_path": os.path.abspath("incoming"), "label": "incoming/"}]

    observer = Observer()
    for row in enabled:
        path  = row["folder_path"]
        label = row["label"] or os.path.basename(path)
        if not os.path.isdir(path):
            print(f"[DocPilot] Skipping (not found): {path}")
            continue
        handler = DocPilotHandler(watch_label=label)
        observer.schedule(handler, path=path, recursive=False)
        print(f"[DocPilot] Watching: {label} ({path})")

    observer.start()
    print(f"\n[DocPilot] Watcher running — monitoring {len(enabled)} folder(s)")
    print("[DocPilot] Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    print("[DocPilot] Watcher stopped.")


if __name__ == "__main__":
    run_watcher()
