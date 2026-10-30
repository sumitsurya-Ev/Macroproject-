"""
app.py — DocPilot Flask application (AI-powered, v2).
"""

import os
import json
import hashlib
import sqlite3
import shutil

from flask import Flask, request, render_template, redirect, url_for, flash, jsonify

from database import (
    init_db, insert_document, get_document, get_review_queue,
    get_filed_log, get_all_documents, update_document_status,
    get_stats, check_duplicate, get_pending_approvals,
    get_pending_approvals_count, register_folder, get_all_folder_metadata,
    update_folder_description, get_watcher_folders, add_watcher_folder,
    toggle_watcher_folder, remove_watcher_folder,
)
from extractor    import extract_text, is_pdf
from ai_classifier import ai_classify, get_provider_status, get_all_known_types
from filer        import (
    file_document, get_destination_folder, ensure_folders,
    list_all_folders, folder_exists,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "docpilot-secret-local-2026")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ensure_folders()
init_db()


# ── Context processor: inject globals into every template ──────────────────────
@app.context_processor
def inject_globals():
    try:
        conn = sqlite3.connect("docpilot.db")
        review_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status='needs_review'"
        ).fetchone()[0]
        pending_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status='pending_approval'"
        ).fetchone()[0]
        conn.close()
    except Exception:
        review_count = 0
        pending_count = 0
    return dict(
        review_count=review_count,
        pending_count=pending_count,
        ai_status=get_provider_status(),
        all_folders=list_all_folders(),
    )


# ── Category breakdown ─────────────────────────────────────────────────────────
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

    # ── Smart filename ──
    orig_ext       = ".pdf"
    smart_name     = result.get("suggested_filename") or os.path.splitext(file.filename)[0]
    final_filename = smart_name + orig_ext

    # ── Decide: auto-file, pending approval, or review ──
    doc_type       = result["type"]
    confidence     = result["confidence"]
    dest_folder    = get_destination_folder(doc_type)   # creates folder if new
    dest_display   = os.path.basename(dest_folder)
    is_new_folder  = not folder_exists(doc_type)        # was this folder brand-new?

    if result["status"] == "filed" and is_new_folder:
        # High confidence but brand new folder → ask user permission
        filing_status = "pending_approval"
        stored_filename = file.filename
    elif result["status"] == "filed":
        # High confidence + known folder → auto-file
        filing_status = "filed"
        renamed_path = os.path.join(UPLOAD_FOLDER, final_filename)
        if save_path != renamed_path and not os.path.exists(renamed_path):
            os.rename(save_path, renamed_path)
            save_path = renamed_path
        file_document(save_path, doc_type)
        stored_filename = final_filename
    else:
        # Low confidence → review queue
        filing_status = "needs_review"
        stored_filename = file.filename

    # ── Save to DB ──
    doc_id = insert_document(
        filename      = stored_filename,
        doc_type      = doc_type,
        confidence    = confidence,
        destination   = dest_display,
        status        = filing_status,
        reasoning     = result.get("reasoning", ""),
        entities      = result.get("entities", {}),
        suggested_name= smart_name,
        provider      = result.get("provider", "keyword"),
        file_hash     = file_hash,
        source_path   = save_path,
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
        new_type = custom

    if not new_type:
        flash("Please select or type a document category.", "error")
        return redirect(url_for("review"))

    new_destination = os.path.basename(get_destination_folder(new_type))
    register_folder(new_destination)
    doc = get_document(doc_id)
    if doc:
        upload_path = os.path.join(UPLOAD_FOLDER, doc["filename"])
        if os.path.exists(upload_path):
            file_document(upload_path, new_type)

    update_document_status(doc_id, new_type, new_destination, "filed")
    flash(f"Filed to {new_destination}/.", "success")
    return redirect(url_for("review"))


# ─────────────────────────────────────────────
# PENDING APPROVAL (new folder needs permission)
# ─────────────────────────────────────────────
@app.route("/pending")
def pending():
    items  = get_pending_approvals()
    parsed = []
    for item in items:
        try:
            ent = json.loads(item["entities"]) if item["entities"] else {}
        except Exception:
            ent = {}
        parsed.append((item, ent))
    return render_template("pending_approval.html", items=parsed)


@app.route("/pending/approve/<int:doc_id>", methods=["POST"])
def approve_folder(doc_id):
    """User says YES — create the folder and file the document."""
    doc = get_document(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("pending"))

    doc_type    = doc["doc_type"]
    dest_folder = get_destination_folder(doc_type)   # creates the folder
    dest_name   = os.path.basename(dest_folder)
    description = request.form.get("description", "").strip()

    # Register folder in metadata
    register_folder(dest_name, description=description, auto_created=True)

    # Move file from uploads/ to filed/
    src = doc["source_path"] or os.path.join(UPLOAD_FOLDER, doc["filename"])
    if os.path.exists(src):
        file_document(src, doc_type)
    else:
        # File might be in uploads under original name
        alt_src = os.path.join(UPLOAD_FOLDER, doc["filename"])
        if os.path.exists(alt_src):
            file_document(alt_src, doc_type)

    update_document_status(doc_id, doc_type, dest_name, "filed")
    flash(f"New folder '{dest_name}' created and document filed.", "success")
    return redirect(url_for("pending"))


@app.route("/pending/rename/<int:doc_id>", methods=["POST"])
def rename_folder(doc_id):
    """User says NO and provides their own folder name."""
    doc = get_document(doc_id)
    if not doc:
        flash("Document not found.", "error")
        return redirect(url_for("pending"))

    custom_folder = request.form.get("folder_name", "").strip()
    description   = request.form.get("description", "").strip()

    if not custom_folder:
        flash("Please enter a folder name.", "error")
        return redirect(url_for("pending"))

    dest_folder = get_destination_folder(custom_folder)
    dest_name   = os.path.basename(dest_folder)

    register_folder(dest_name, description=description, auto_created=True)

    src = doc["source_path"] or os.path.join(UPLOAD_FOLDER, doc["filename"])
    if os.path.exists(src):
        file_document(src, custom_folder)
    else:
        alt_src = os.path.join(UPLOAD_FOLDER, doc["filename"])
        if os.path.exists(alt_src):
            file_document(alt_src, custom_folder)

    update_document_status(doc_id, custom_folder, dest_name, "filed")
    flash(f"Filed to '{dest_name}/' as requested.", "success")
    return redirect(url_for("pending"))


@app.route("/pending/reject/<int:doc_id>", methods=["POST"])
def reject_document(doc_id):
    """User says NO and doesn't want to file right now — move to review queue."""
    update_document_status(doc_id, "", "", "needs_review")
    flash("Document moved to Review Queue.", "error")
    return redirect(url_for("pending"))


# ─────────────────────────────────────────────
# API: live approval count for badge refresh
# ─────────────────────────────────────────────
@app.route("/api/approvals/count")
def api_approvals_count():
    return jsonify({
        "pending": get_pending_approvals_count(),
        "review":  len(get_review_queue()),
    })


# ─────────────────────────────────────────────
# FOLDER VIEW
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

    # Get folder description if available
    conn2 = sqlite3.connect("docpilot.db")
    conn2.row_factory = sqlite3.Row
    meta = conn2.execute(
        "SELECT * FROM folder_metadata WHERE folder_name=?", (folder_name,)
    ).fetchone()
    conn2.close()

    return render_template("folder_view.html",
                           folder_name=folder_name,
                           docs=docs,
                           physical_files=physical_files,
                           meta=meta)


# ─────────────────────────────────────────────
# OPEN FOLDER IN EXPLORER (Windows helper)
# ─────────────────────────────────────────────
@app.route("/open-folder/<folder_name>")
def open_folder(folder_name):
    import subprocess
    safe = "".join(c for c in folder_name if c.isalnum() or c in (" ", "_", "-"))
    folder_path = os.path.abspath(os.path.join("filed", safe))
    if os.path.isdir(folder_path):
        subprocess.Popen(["explorer", folder_path])
    return jsonify({"ok": True, "path": folder_path})


# ─────────────────────────────────────────────
# FILED LOG
# ─────────────────────────────────────────────
@app.route("/log")
def log():
    docs = get_filed_log()
    return render_template("filed_log.html", docs=docs)


# ─────────────────────────────────────────────
# SETTINGS — API Keys
# ─────────────────────────────────────────────
@app.route("/settings")
def settings():
    import config
    def mask(key):
        return ("•" * (len(key) - 6) + key[-6:]) if len(key) > 6 else ("•" * len(key))
    current_gemini = mask(config.GEMINI_API_KEY) if config.GEMINI_API_KEY else ""
    current_openai = mask(config.OPENAI_API_KEY) if config.OPENAI_API_KEY else ""

    # Watched folders
    watcher_folders = get_watcher_folders()
    # Suggest default Windows folders
    username = os.environ.get("USERNAME") or os.environ.get("USER", "")
    default_watches = []
    for path, label in [
        (f"C:\\Users\\{username}\\Downloads", "Downloads"),
        (f"C:\\Users\\{username}\\Desktop",   "Desktop"),
        (f"C:\\Users\\{username}\\Documents", "Documents"),
    ]:
        if os.path.isdir(path):
            default_watches.append({"path": path, "label": label})

    return render_template("settings.html",
                           current_gemini=current_gemini,
                           current_openai=current_openai,
                           watcher_folders=watcher_folders,
                           default_watches=default_watches)


@app.route("/settings/save", methods=["POST"])
def settings_save():
    gemini_key = request.form.get("gemini_key", "").strip()
    openai_key = request.form.get("openai_key", "").strip()

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
        with open(".env", "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
        import importlib
        if final_gemini:
            os.environ["GEMINI_API_KEY"] = final_gemini
        if final_openai:
            os.environ["OPENAI_API_KEY"] = final_openai
        import config as cfg_mod, ai_classifier as ai_mod
        importlib.reload(cfg_mod)
        importlib.reload(ai_mod)
        flash("API key saved. AI engine is now active.", "success")
    else:
        flash("No changes made.", "error")

    return redirect(url_for("settings"))


# ─────────────────────────────────────────────
# SETTINGS — Watched Folders
# ─────────────────────────────────────────────
@app.route("/settings/watchers/add", methods=["POST"])
def add_watcher():
    path  = request.form.get("folder_path", "").strip()
    label = request.form.get("label", "").strip()
    if path and os.path.isdir(path):
        add_watcher_folder(path, label)
        flash(f"Now watching: {path}", "success")
    else:
        flash("Folder path not found. Please enter a valid Windows path.", "error")
    return redirect(url_for("settings"))


@app.route("/settings/watchers/remove", methods=["POST"])
def remove_watcher():
    path = request.form.get("folder_path", "").strip()
    remove_watcher_folder(path)
    flash("Stopped watching that folder.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/watchers/toggle", methods=["POST"])
def toggle_watcher():
    path    = request.form.get("folder_path", "").strip()
    enabled = request.form.get("enabled", "1") == "1"
    toggle_watcher_folder(path, enabled)
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# CREATE FOLDER (user-initiated, no document required)
# ─────────────────────────────────────────────
@app.route("/folders/create", methods=["POST"])
def create_folder():
    """User creates a custom filing folder from the UI."""
    folder_name = request.form.get("folder_name", "").strip()
    description = request.form.get("description", "").strip()

    if not folder_name:
        flash("Please enter a folder name.", "error")
        return redirect(request.referrer or url_for("settings"))

    from filer import _sanitize_folder_name
    safe_name = _sanitize_folder_name(folder_name)

    dest_folder = os.path.join("filed", safe_name)
    os.makedirs(dest_folder, exist_ok=True)

    register_folder(safe_name, description=description, auto_created=False)
    flash(f"Folder '{safe_name}' created successfully.", "success")
    return redirect(url_for("folder_view", folder_name=safe_name))


# ─────────────────────────────────────────────
# FOLDER DESCRIPTION update
# ─────────────────────────────────────────────
@app.route("/folder/<folder_name>/describe", methods=["POST"])
def describe_folder(folder_name):
    desc = request.form.get("description", "").strip()
    update_folder_description(folder_name, desc)
    flash("Folder description saved.", "success")
    return redirect(url_for("folder_view", folder_name=folder_name))


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
