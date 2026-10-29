"""
run_production.py — Production WSGI server for DocPilot using Waitress.
Safe for multi-threaded production deployment on Windows and Linux.
"""

import os
from waitress import serve
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    threads = int(os.environ.get("THREADS", 6))
    
    print("=" * 60)
    print(f"🚀 DocPilot Production Server Running on http://{host}:{port}")
    print(f"⚙️  WSGI: Waitress (Threads: {threads})")
    print("=" * 60)
    
    serve(app, host=host, port=port, threads=threads)
