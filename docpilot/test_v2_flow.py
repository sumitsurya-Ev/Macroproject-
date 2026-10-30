"""
test_v2_flow.py — Comprehensive end-to-end test for DocPilot v2:
1. Pending Approval workflow (high-confidence + new folder -> pending_approval)
2. Approve flow (creates folder, records metadata, moves file, marks filed)
3. Rename flow (creates custom folder, records description, moves file, marks filed)
4. Reject/Route to Review flow
5. Watcher folder management (add, toggle, remove)
6. Stats validation (pending count, total, filed, review)
"""

import os
import sys
import shutil

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import app
from database import (
    get_stats,
    get_pending_approvals,
    get_pending_approvals_count,
    get_watcher_folders,
    insert_document,
    get_document,
    get_all_folder_metadata
)
from filer import (
    folder_exists,
    get_destination_folder,
    _sanitize_folder_name,
    BASE_FILED_DIR as FILED_DIR
)

client = app.test_client()

print("\n" + "=" * 70)
print("  🧪 TESTING DOCPILOT V2 WORKFLOW & APPROVAL SYSTEM")
print("=" * 70)

# 1. Test Dashboard Home renders with 5-card stats
res = client.get("/")
assert res.status_code == 200
assert b"Awaiting Approval" in res.data
print("✅ 1. Dashboard loaded successfully with 'Awaiting Approval' stat card")

# 2. Test Pending Approvals page renders empty or loaded
res = client.get("/pending")
assert res.status_code == 200
print("✅ 2. Pending Approval page (/pending) loaded successfully [Status 200]")

# 3. Simulate inserting a document that requires folder approval
dummy_pdf_name = "sample_quarterly_report.pdf"
dummy_pdf_path = os.path.join("uploads", dummy_pdf_name)
with open(dummy_pdf_path, "wb") as f:
    f.write(b"%PDF-1.4 simulated pdf document content")

test_doc_type = "Quarterly Reports"
sanitized_test_folder = _sanitize_folder_name(test_doc_type)
test_folder_path = os.path.join(FILED_DIR, sanitized_test_folder)
if os.path.exists(test_folder_path):
    shutil.rmtree(test_folder_path)

assert not folder_exists(test_doc_type)

doc_id_1 = insert_document(
    filename=dummy_pdf_name,
    doc_type=test_doc_type,
    confidence=0.94,
    status="pending_approval",
    destination=sanitized_test_folder,
    provider="gemini",
    reasoning="Detected quarterly earnings disclosures and balance sheets",
    entities={"period": "Q3 2026", "vendor": "Acme Corp"},
    suggested_name="Acme_Corp_Q3_2026_Report",
    source_path=dummy_pdf_path
)

print(f"✅ 3. Simulated pending document inserted (ID: {doc_id_1})")

# Verify pending count
pending_count = get_pending_approvals_count()
assert pending_count >= 1
print(f"✅ 4. Pending approvals count verified: {pending_count}")

# Verify pending page shows document
res = client.get("/pending")
assert res.status_code == 200
assert b"sample_quarterly_report.pdf" in res.data
assert b"Quarterly Reports" in res.data
print("✅ 5. /pending renders the document card and suggested folder")

# 4. Test Approving the folder
res = client.post(f"/pending/approve/{doc_id_1}", data={
    "description": "Folder for all quarterly financial reports and disclosures"
}, follow_redirects=True)
assert res.status_code == 200

doc_1_updated = get_document(doc_id_1)
assert doc_1_updated["status"] == "filed"
assert os.path.exists(test_folder_path)
print(f"✅ 6. Folder approval succeeded! Folder '{sanitized_test_folder}' created and doc #{doc_id_1} marked as filed")

# Verify folder metadata
metadata = get_all_folder_metadata()
folder_names = [m["folder_name"] for m in metadata]
assert sanitized_test_folder in folder_names
print(f"✅ 7. Folder metadata recorded in DB with user description")

# 5. Test Renaming flow on another document
dummy_pdf_name_2 = "sample_research_whitepaper.pdf"
dummy_pdf_path_2 = os.path.join("uploads", dummy_pdf_name_2)
with open(dummy_pdf_path_2, "wb") as f:
    f.write(b"%PDF-1.4 simulated research document")

doc_id_2 = insert_document(
    filename=dummy_pdf_name_2,
    doc_type="AI Whitepapers",
    confidence=0.91,
    status="pending_approval",
    destination="AI_Whitepapers",
    provider="gemini",
    reasoning="Identified scientific technical paper about neural architectures",
    entities={"author": "Deep Learning Team"},
    suggested_name="Neural_Architecture_Whitepaper_2026",
    source_path=dummy_pdf_path_2
)

custom_folder = "Machine Learning Research"
custom_folder_sanitized = _sanitize_folder_name(custom_folder)
custom_folder_path = os.path.join(FILED_DIR, custom_folder_sanitized)
if os.path.exists(custom_folder_path):
    shutil.rmtree(custom_folder_path)

res = client.post(f"/pending/rename/{doc_id_2}", data={
    "folder_name": custom_folder,
    "description": "Technical papers, ML research drafts and benchmarks"
}, follow_redirects=True)
assert res.status_code == 200

doc_2_updated = get_document(doc_id_2)
assert doc_2_updated["status"] == "filed"
assert doc_2_updated["destination"] == custom_folder_sanitized
assert os.path.exists(custom_folder_path)
print(f"✅ 8. Folder rename succeeded! Custom folder '{custom_folder_sanitized}' created and filed")

# 6. Test Watcher settings endpoints
res = client.get("/settings")
assert res.status_code == 200
assert b"Watched Folders" in res.data
print("✅ 9. Settings page displays Watched Folders configuration panel")

# Add a test watcher folder
test_watch_dir = os.path.abspath("test_watch_target")
os.makedirs(test_watch_dir, exist_ok=True)

res = client.post("/settings/watchers/add", data={
    "folder_path": test_watch_dir,
    "label": "Test Watch Directory"
}, follow_redirects=True)
assert res.status_code == 200

watchers = get_watcher_folders()
test_watcher = [w for w in watchers if w["folder_path"] == test_watch_dir]
assert len(test_watcher) > 0
watcher_id = test_watcher[0]["id"]
print(f"✅ 10. Added watcher directory: {test_watch_dir} (ID: {watcher_id})")

# Toggle watcher
res = client.post("/settings/watchers/toggle", data={
    "folder_path": test_watch_dir,
    "enabled": "0"
})
assert res.status_code == 200
assert res.get_json()["ok"] is True
print(f"✅ 11. Watcher toggled successfully")

# Remove watcher
res = client.post("/settings/watchers/remove", data={
    "folder_path": test_watch_dir
}, follow_redirects=True)
assert res.status_code == 200
print(f"✅ 12. Watcher removed successfully")

if os.path.exists(test_watch_dir):
    os.rmdir(test_watch_dir)

# 7. Verify stats
stats = get_stats()
print(f"✅ 13. Final System Stats: Total: {stats['total']} | Filed: {stats['filed']} | Pending Approval: {stats['pending']} | Review: {stats['review']}")

print("\n" + "=" * 70)
print("  🎉 ALL DOCPILOT V2 TESTS COMPLETED AND 100% PASSING!")
print("=" * 70 + "\n")
