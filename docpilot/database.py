import sqlite3, os, json

DB_PATH = "docpilot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Core documents table ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            filename         TEXT    NOT NULL,
            doc_type         TEXT    NOT NULL,
            confidence       REAL    NOT NULL,
            destination      TEXT    NOT NULL,
            status           TEXT    NOT NULL,
            reasoning        TEXT    DEFAULT '',
            entities         TEXT    DEFAULT '{}',
            suggested_name   TEXT    DEFAULT '',
            provider         TEXT    DEFAULT 'keyword',
            file_hash        TEXT    DEFAULT '',
            source_path      TEXT    DEFAULT '',
            uploaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Folder metadata table ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS folder_metadata (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_name  TEXT UNIQUE NOT NULL,
            description  TEXT DEFAULT '',
            auto_created INTEGER DEFAULT 0,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Watcher config table ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS watcher_config (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_path TEXT UNIQUE NOT NULL,
            label       TEXT DEFAULT '',
            enabled     INTEGER DEFAULT 1,
            added_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Migrate older DB schemas (backward compatible) ──
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(documents)").fetchall()]
    new_cols = [
        ("reasoning",      "TEXT DEFAULT ''"),
        ("entities",       "TEXT DEFAULT '{}'"),
        ("suggested_name", "TEXT DEFAULT ''"),
        ("provider",       "TEXT DEFAULT 'keyword'"),
        ("file_hash",      "TEXT DEFAULT ''"),
        ("source_path",    "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in new_cols:
        if col_name not in existing_cols:
            c.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_def}")

    conn.commit()
    conn.close()


# ── Document CRUD ──────────────────────────────────────────────────────────────

def insert_document(filename, doc_type, confidence, destination, status,
                    reasoning="", entities=None, suggested_name="",
                    provider="keyword", file_hash="", source_path=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO documents
           (filename, doc_type, confidence, destination, status,
            reasoning, entities, suggested_name, provider, file_hash, source_path)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            filename, doc_type, round(confidence, 4), destination, status,
            reasoning,
            json.dumps(entities or {}),
            suggested_name or "",
            provider,
            file_hash or "",
            source_path or "",
        )
    )
    conn.commit()
    doc_id = c.lastrowid
    conn.close()
    return doc_id

def get_document(doc_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    return row

def get_review_queue():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents WHERE status='needs_review' ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    return rows

def get_pending_approvals():
    """Documents where AI is confident but needs permission to create a NEW folder."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents WHERE status='pending_approval' ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    return rows

def get_pending_approvals_count():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE status='pending_approval'"
    ).fetchone()[0]
    conn.close()
    return count

def get_filed_log():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents WHERE status='filed' ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    return rows

def get_all_documents():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM documents ORDER BY uploaded_at DESC"
    ).fetchall()
    conn.close()
    return rows

def update_document_status(doc_id, new_type, new_destination, new_status):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE documents SET doc_type=?, destination=?, status=? WHERE id=?",
        (new_type, new_destination, new_status, doc_id)
    )
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    total    = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    filed    = c.execute("SELECT COUNT(*) FROM documents WHERE status='filed'").fetchone()[0]
    review   = c.execute("SELECT COUNT(*) FROM documents WHERE status='needs_review'").fetchone()[0]
    pending  = c.execute("SELECT COUNT(*) FROM documents WHERE status='pending_approval'").fetchone()[0]
    avg_conf = c.execute("SELECT AVG(confidence) FROM documents WHERE status='filed'").fetchone()[0] or 0
    conn.close()
    return {
        "total": total,
        "filed": filed,
        "review": review,
        "pending": pending,
        "avg_confidence": round(avg_conf * 100, 1)
    }

def check_duplicate(file_hash: str) -> bool:
    """Returns True if this file hash already exists in the database."""
    if not file_hash:
        return False
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id FROM documents WHERE file_hash=? LIMIT 1", (file_hash,)
    ).fetchone()
    conn.close()
    return row is not None


# ── Folder Metadata ────────────────────────────────────────────────────────────

def register_folder(folder_name, description="", auto_created=False):
    """Register a folder in folder_metadata (idempotent — ignores if exists)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR IGNORE INTO folder_metadata (folder_name, description, auto_created)
           VALUES (?,?,?)""",
        (folder_name, description, 1 if auto_created else 0)
    )
    conn.commit()
    conn.close()

def get_all_folder_metadata():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM folder_metadata ORDER BY folder_name"
    ).fetchall()
    conn.close()
    return rows

def update_folder_description(folder_name, description):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE folder_metadata SET description=? WHERE folder_name=?",
        (description, folder_name)
    )
    conn.commit()
    conn.close()


# ── Watcher Config ─────────────────────────────────────────────────────────────

def get_watcher_folders():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM watcher_config ORDER BY label").fetchall()
    conn.close()
    return rows

def add_watcher_folder(folder_path, label=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO watcher_config (folder_path, label, enabled) VALUES (?,?,1)",
        (folder_path, label or os.path.basename(folder_path))
    )
    conn.commit()
    conn.close()

def toggle_watcher_folder(folder_path, enabled: bool):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE watcher_config SET enabled=? WHERE folder_path=?",
        (1 if enabled else 0, folder_path)
    )
    conn.commit()
    conn.close()

def remove_watcher_folder(folder_path):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM watcher_config WHERE folder_path=?", (folder_path,))
    conn.commit()
    conn.close()
