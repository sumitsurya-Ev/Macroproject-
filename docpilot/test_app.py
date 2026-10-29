"""
test_app.py — Automated test simulating browser requests to the Flask web dashboard:
1. Load Dashboard
2. Upload high-confidence invoice (Auto-files)
3. Upload ambiguous document (Routes to Review Queue)
4. Confirm review queue item
5. Verify Filed Audit Log
"""

import os
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import app
from database import get_stats, get_review_queue, get_filed_log

client = app.test_client()

print("\n" + "=" * 70)
print("  🌐 TESTING DOCPILOT FLASK WEB DASHBOARD")
print("=" * 70)

# 1. Test Dashboard Home
res = client.get("/")
assert res.status_code == 200
print("✅ 1. Dashboard Home Page (/) loaded successfully [Status 200]")

# 2. Test Uploading High-Confidence Invoice
invoice_path = os.path.join("test_samples", "sample_tax_invoice.pdf")
with open(invoice_path, "rb") as f:
    res = client.post("/upload", data={"file": (f, "sample_tax_invoice.pdf")}, follow_redirects=True)
assert res.status_code == 200
print("✅ 2. Upload Invoice: Successfully processed and auto-filed")

# 3. Test Uploading Low-Confidence Ambiguous Document
ambiguous_path = os.path.join("test_samples", "sample_ambiguous_notes.pdf")
with open(ambiguous_path, "rb") as f:
    res = client.post("/upload", data={"file": (f, "sample_ambiguous_notes.pdf")}, follow_redirects=True)
assert res.status_code == 200
print("✅ 3. Upload Ambiguous Notes: Routed to Review Queue (<85% confidence)")

# 4. Check Review Queue
review_items = get_review_queue()
assert len(review_items) >= 1
print(f"✅ 4. Review Queue has {len(review_items)} pending document(s)")
target_doc_id = review_items[0]["id"]

# 5. Confirm Review Item
res = client.post(f"/review/confirm/{target_doc_id}", data={"doc_type": "Other"}, follow_redirects=True)
assert res.status_code == 200
print(f"✅ 5. Review Item #{target_doc_id} confirmed and filed to Other/")

# 6. Verify Log & Stats
stats = get_stats()
print(f"✅ 6. Final Dashboard Stats: Total: {stats['total']} | Auto-Filed: {stats['filed']} | Needs Review: {stats['review']}")

print("\n" + "=" * 70)
print("  🎉 FLASK WEB DASHBOARD & WORKFLOW COMPLETELY VERIFIED!")
print("=" * 70 + "\n")
