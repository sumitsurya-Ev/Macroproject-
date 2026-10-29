"""
app.py — DocPilot Flask application (AI-powered).
"""

import os
import json
import hashlib
import sqlite3

from flask import Flask, request, render_template, redirect, url_for, flash

from database     import (init_db, insert_document, get_document, get_review_queue,
                           get_filed_log, get_all_documents, update_document_status,
                           get_stats, check_duplicate)
from extractor    import extract_text, is_pdf
from ai_classifier import ai_classify, get_provider_status, get_all_known_types
from filer        import file_document, get_destination_folder, ensure_folders, list_all_folders

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "docpilot-secret-local-2026")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ensure_folders()
init_db()


# ── Context processor: inject globals into every template ──
@app.context_processor
def inject_globals():
    try:
        conn = sqlite3.connect("docpilot.db")
        count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status='needs_review'"
        ).fetchone()[0]
        conn.close()
    except Exception:
        count = 0
    return dict(
        review_count=count,
        ai_status=get_provider_status(),
        all_folders=list_all_folders()
    )


# ── Category breakdown ──
def get_category_breakdown():
    conn = sqlite3.connect("docpilot.db")
    rows = conn.execute(
        """SELECT doc_type, COUNT(*) as cnt FROM documents
           WHERE status='filed' GROUP BY doc_type ORDER BY cnt DESC"""
    ).fetchall()
    total = sum(r[1] for r in rows) or 1
    conn.close()
    return [(r[0], r[1], round(r[1]/total*100, 1)) for r in rows]


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@app.route("/")
def index():
    stats              = get_stats()
    recent             = get_all_documents()[:8]
    category_breakdown = get_category_breakdown()
    return render_template("index.html",
                           stats=stats,
                           recent=recent,
                           category_breakdown=category_breakdown)


# ─────────────────────────────────────────────
# UPLOAD PAGE
# ─────────────────────────────────────────────
@app.route("/upload-page")
def upload_page():
    return render_template("upload.html")


# ─────────────────────────────────────────────
# UPLOAD & PROCESS (main pipeline)
# ─────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("upload_page"))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("upload_page"))

    if not is_pdf(file.filename):
        flash("Only PDF files are supported right now.", "error")
        return redirect(url_for("upload_page"))

    # ── Save temporarily ──
    save_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(save_path)

    # ── Duplicate detection ──
    with open(save_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    if check_duplicate(file_hash):
        os.remove(save_path)
        flash(f"Duplicate: '{file.filename}' has already been processed and filed.", "error")
        return redirect(url_for("upload_page"))

    # ── Extract text ──
    text = extract_text(save_path)

    # ── AI Classification ──
    result = ai_classify(text, original_filename=file.filename)

    # ── Determine smart filename ──
    orig_ext       = ".pdf"
    smart_name     = result.get("suggested_filename") or os.path.splitext(file.filename)[0]
    final_filename = smart_name + orig_ext

    dest_folder  = get_destination_folder(result["type"])
    dest_display = os.path.basename(dest_folder)

    # ── File or hold for review ──
    if result["status"] == "filed":
        # Rename file on disk before filing
        renamed_path = os.path.join(UPLOAD_FOLDER, final_filename)
        if save_path != renamed_path and not os.path.exists(renamed_path):
            os.rename(save_path, renamed_path)
            save_path = renamed_path
        file_document(save_path, result["type"])
        stored_filename = final_filename
    else:
        stored_filename = file.filename   # keep original name in uploads for review

    # ── Save to DB ──
    doc_id = insert_document(
        filename      = stored_filename,
        doc_type      = result["type"],
        confidence    = result["confidence"],
        destination   = dest_display,
        status        = result["status"],
        reasoning     = result.get("reasoning", ""),
        entities      = result.get("entities", {}),
        suggested_name= smart_name,
        provider      = result.get("provider", "keyword"),
        file_hash     = file_hash
    )

    return redirect(url_for("result", doc_id=doc_id))


# ─────────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────────
@app.route("/result/<int:doc_id>")
def result(doc_id):
    doc = get_document(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("index"))

    # Parse entities JSON for template
    try:
        entities = json.loads(doc["entities"]) if doc["entities"] else {}
    except Exception:
        entities = {}

    return render_template("result.html", doc=doc, entities=entities)


# ─────────────────────────────────────────────
# REVIEW QUEUE
# ─────────────────────────────────────────────
@app.route("/review")
def review():
    items     = get_review_queue()
    doc_types = get_all_known_types()
    # Parse entities for each item
    parsed = []
    for item in items:
        try:
            ent = json.loads(item["entities"]) if item["entities"] else {}
        except Exception:
            ent = {}
        parsed.append((item, ent))
    return render_template("review_queue.html", items=parsed, doc_types=doc_types)


@app.route("/review/confirm/<int:doc_id>", methods=["POST"])
def confirm_review(doc_id):
    new_type = request.form.get("doc_type", "").strip()
    custom   = request.form.get("custom_type", "").strip()
    if custom:
        new_type = custom   # user typed their own category

    if not new_type:
        flash("Please select or type a document category.", "error")
        return redirect(url_for("review"))

    new_destination = os.path.basename(get_destination_folder(new_type))
    doc = get_document(doc_id)
    if doc:
        upload_path = os.path.join(UPLOAD_FOLDER, doc["filename"])
        if os.path.exists(upload_path):
            file_document(upload_path, new_type)

    update_document_status(doc_id, new_type, new_destination, "filed")
    flash(f"Filed to {new_destination}/.", "success")
    return redirect(url_for("review"))


# ─────────────────────────────────────────────
# FOLDER VIEW (per-folder document list)
# ─────────────────────────────────────────────
@app.route("/folder/<folder_name>")
def folder_view(folder_name):
    conn = sqlite3.connect("docpilot.db")
    conn.row_factory = sqlite3.Row
    docs = conn.execute(
        "SELECT * FROM documents WHERE destination=? AND status='filed' ORDER BY uploaded_at DESC",
        (folder_name,)
    ).fetchall()
    conn.close()
    folder_path    = os.path.join("filed", folder_name)
    physical_files = sorted(os.listdir(folder_path)) if os.path.isdir(folder_path) else []
    return render_template("folder_view.html",
                           folder_name=folder_name,
                           docs=docs,
                           physical_files=physical_files)


# ─────────────────────────────────────────────
# OPEN FOLDER IN EXPLORER (Windows helper)
# ─────────────────────────────────────────────
@app.route("/open-folder/<folder_name>")
def open_folder(folder_name):
    import subprocess
    # Sanitise: only letters, digits, spaces, underscores, hyphens
    safe = "".join(c for c in folder_name if c.isalnum() or c in (" ", "_", "-"))
    folder_path = os.path.abspath(os.path.join("filed", safe))
    if os.path.isdir(folder_path):
        subprocess.Popen(["explorer", folder_path])
    from flask import jsonify
    return jsonify({"ok": True, "path": folder_path})


# ─────────────────────────────────────────────
# FILED LOG
# ─────────────────────────────────────────────
@app.route("/log")
def log():
    docs = get_filed_log()
    return render_template("filed_log.html", docs=docs)



# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────
@app.route("/settings")
def settings():
    import config
    # Mask keys — only show last 6 chars if set
    def mask(key):
        return ("•" * (len(key) - 6) + key[-6:]) if len(key) > 6 else ("•" * len(key))
    current_gemini = mask(config.GEMINI_API_KEY) if config.GEMINI_API_KEY else ""
    current_openai = mask(config.OPENAI_API_KEY) if config.OPENAI_API_KEY else ""
    return render_template("settings.html",
                           current_gemini=current_gemini,
                           current_openai=current_openai)


@app.route("/settings/save", methods=["POST"])
def settings_save():
    gemini_key = request.form.get("gemini_key", "").strip()
    openai_key = request.form.get("openai_key", "").strip()

    # Skip masked placeholder values (e.g. •••di8GMg)
    def is_masked(val):
        return "•" in val

    existing_gemini = os.environ.get("GEMINI_API_KEY", "")
    existing_openai = os.environ.get("OPENAI_API_KEY", "")

    final_gemini = existing_gemini if is_masked(gemini_key) else (gemini_key or existing_gemini)
    final_openai = existing_openai if is_masked(openai_key) else (openai_key or existing_openai)

    env_lines = []
    if final_gemini:
        env_lines.append(f"GEMINI_API_KEY={final_gemini}")
    if final_openai:
        env_lines.append(f"OPENAI_API_KEY={final_openai}")

    if env_lines:
        # Write to .env file with explicit UTF-8 so it persists safely across restarts
        with open(".env", "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")

        # Apply immediately to current process environment
        import importlib
        if final_gemini:
            os.environ["GEMINI_API_KEY"] = final_gemini
        if final_openai:
            os.environ["OPENAI_API_KEY"] = final_openai

        # Reload config and ai_classifier with new env
        import config as cfg_mod, ai_classifier as ai_mod
        importlib.reload(cfg_mod)
        importlib.reload(ai_mod)

        flash("API key saved. AI engine is now active.", "success")
    else:
        flash("No changes made.", "error")

    return redirect(url_for("settings"))


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


