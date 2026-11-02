"""Watch Downloads and feed new files into DocPilot.

    python -m docpilot.watch ~/Downloads ~/Documents
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

try:
    from .extract import is_partial, wait_until_stable
    from .pipeline import DocPilot
except (ImportError, ValueError):
    from docpilot.extract import is_partial, wait_until_stable
    from docpilot.pipeline import DocPilot


class DownloadHandler(FileSystemEventHandler):
    def __init__(self, pilot: DocPilot, on_decision):
        self.pilot, self.on_decision = pilot, on_decision
        self._busy, self._lock = set(), threading.Lock()

    def _handle(self, path: str):
        if is_partial(path) or Path(path).is_dir():
            return
        with self._lock:
            if path in self._busy:
                return
            self._busy.add(path)
        threading.Thread(target=self._work, args=(path,), daemon=True).start()

    def _work(self, path: str):
        try:
            if wait_until_stable(path):               # never read a half-downloaded file
                self.on_decision(path, self.pilot.analyze(path))
        finally:
            with self._lock:
                self._busy.discard(path)

    def on_created(self, event):
        self._handle(event.src_path)

    def on_moved(self, event):                        # browsers rename .crdownload -> final name
        self._handle(event.dest_path)


def main():
    downloads, library = sys.argv[1], sys.argv[2]
    pilot = DocPilot(library)
    pilot.sync()                                      # learn from the library as the user organised it
    pilot.tune()                                      # measure real accuracy, set safe thresholds

    def resync():                                     # keep learning from files the user moves by hand
        while True:
            time.sleep(600)
            pilot.sync()

    threading.Thread(target=resync, daemon=True).start()

    def on_decision(path, d):
        if d.action == "auto_move":
            pilot.file(path, d.folder)
            print(f"[moved {d.confidence:.2f}] {Path(path).name} -> {d.folder}   (undo available)")
        elif d.action == "suggest":
            print(f"[suggest {d.confidence:.2f}] {Path(path).name} -> {d.folder} (or {d.alt})")
        elif d.action == "new_folder" or d.new_folder:
            nf = d.new_folder
            print(f"[new folder?] {Path(path).name} -> '{nf['name']}'")
        else:
            print(f"[review] {Path(path).name}")

    obs = Observer()
    obs.schedule(DownloadHandler(pilot, on_decision), downloads, recursive=False)
    obs.start()
    obs.join()


if __name__ == "__main__":
    main()
