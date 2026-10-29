"""
test_pipeline.py — Tests text extraction, classification, and confidence scoring
across all generated test PDFs.
"""

import os
import sys

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from extractor import extract_text
from classifier import classify

TEST_DIR = "test_samples"

files = [
    ("sample_tax_invoice.pdf", "Invoice", True),
    ("sample_rental_lease.pdf", "Lease", True),
    ("sample_nda_contract.pdf", "Contract", True),
    ("sample_payment_receipt.pdf", "Receipt", True),
    ("sample_ambiguous_notes.pdf", "Other", False), # Expected < 85% confidence -> needs_review
]

print("\n" + "=" * 75)
print("  🧪 DOCPILOT END-TO-END PIPELINE TEST")
print("=" * 75)

all_passed = True

for filename, expected_type, expected_auto_file in files:
    filepath = os.path.join(TEST_DIR, filename)
    text = extract_text(filepath)
    res = classify(text)
    
    detected_type = res["type"]
    confidence    = res["confidence"]
    status        = res["status"]
    pct           = round(confidence * 100, 1)
    
    type_ok   = (detected_type == expected_type)
    action_ok = (status == "filed") if expected_auto_file else (status == "needs_review")
    test_ok   = type_ok and action_ok
    
    if not test_ok:
        all_passed = False
        
    status_icon = "✅ PASS" if test_ok else "❌ FAIL"
    action_label = "Auto-Filed (>=85%)" if status == "filed" else "Needs Review (<85%)"
    
    print(f"\n{status_icon} | File: {filename}")
    print(f"      Expected Type: {expected_type}  --> Detected: {detected_type}")
    print(f"      Confidence:    {pct}%           --> Action:   {action_label}")
    print(f"      Matched Words: {res['keywords_matched'][:6]}")

print("\n" + "=" * 75)
if all_passed:
    print("  🎉 ALL 5 TEST CASES PASSED WITH 100% INTENDED BEHAVIOR!")
else:
    print("  ⚠️ Some tests did not match expectations.")
print("=" * 75 + "\n")
