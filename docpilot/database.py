import sqlite3, os, json

DB_PATH = "docpilot.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
            uploaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migrate older DB schemas that are missing new columns
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(documents)").fetchall()]
    new_cols = [
        ("reasoning",      "TEXT DEFAULT ''"),
        ("entities",       "TEXT DEFAULT '{}'"),
        ("suggested_name", "TEXT DEFAULT ''"),
        ("provider",       "TEXT DEFAULT 'keyword'"),
        ("file_hash",      "TEXT DEFAULT ''"),
    ]
    for col_name, col_def in new_cols:
        if col_name not in existing_cols:
            c.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_def}")
    conn.commit()
    conn.close()

def insert_document(filename, doc_type, confidence, destination, status,
                    reasoning="", entities=None, suggested_name="",
                    provider="keyword", file_hash=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO documents
           (filename, doc_type, confidence, destination, status,
            reasoning, entities, suggested_name, provider, file_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            filename, doc_type, round(confidence, 4), destination, status,
            reasoning,
            json.dumps(entities or {}),
            suggested_name or "",
            provider,
            file_hash or ""
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
    avg_conf = c.execute("SELECT AVG(confidence) FROM documents WHERE status='filed'").fetchone()[0] or 0
    conn.close()
    return {
        "total": total,
        "filed": filed,
        "review": review,
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
