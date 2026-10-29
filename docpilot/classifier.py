"""
classifier.py — Keyword-based document classifier.
Returns a dict: { type: str, confidence: float, keywords_matched: list }

Confidence is calculated as:
  matched_keywords / total_keywords_in_category (capped at 1.0)
  then scaled by a base weight per category.

To upgrade to AI later: replace classify(text) with an API call.
"""

import re

CATEGORIES = {
    "Invoice": {
        "weight": 0.90,
        "keywords": [
            "invoice", "bill to", "bill", "amount due", "total amount", "payment due",
            "invoice number", "invoice no", "inv no", "due date", "subtotal",
            "tax invoice", "gst invoice", "gstin", "hsn", "sac", "taxable amount",
            "net amount", "gross amount", "payable", "receipt no", "vendor",
            "purchase order", "p.o", "po number", "item description", "qty", "unit price",
            "line total", "vat", "cgst", "sgst", "igst"
        ]
    },
    "Contract": {
        "weight": 0.90,
        "keywords": [
            "agreement", "contract", "terms and conditions", "parties", "whereas",
            "hereinafter", "obligations", "liabilities", "indemnify", "indemnification",
            "binding", "enforceable", "jurisdiction", "governing law", "dispute resolution",
            "arbitration", "termination", "breach", "warranty", "representations",
            "covenants", "execution", "executed", "witness whereof", "in witness",
            "effective date", "counterparts", "entire agreement", "confidentiality",
            "non-disclosure", "nda", "scope of work", "deliverables", "intellectual property"
        ]
    },
    "Lease": {
        "weight": 0.90,
        "keywords": [
            "lease", "rental agreement", "tenancy", "tenant", "landlord", "lessor",
            "lessee", "rent", "monthly rent", "security deposit", "deposit",
            "premises", "property", "flat", "apartment", "house", "unit",
            "lease period", "lease term", "tenancy period", "notice period",
            "eviction", "possession", "occupation", "maintenance charges",
            "society charges", "leave and licence", "licence fee", "stamp duty",
            "registered", "notarized", "witness"
        ]
    },
    "Receipt": {
        "keywords": [
            "receipt", "payment received", "received from", "cash receipt",
            "acknowledgement of payment", "paid", "amount paid", "payment confirmation",
            "transaction id", "txn id", "reference number", "ref no",
            "mode of payment", "upi", "neft", "rtgs", "cheque", "cash",
            "bank transfer", "thank you for your payment", "payment successful"
        ],
        "weight": 0.85
    }
}

CONFIDENCE_THRESHOLD = 0.85

def extract_keywords_matched(text_lower, keywords):
    matched = []
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text_lower):
            matched.append(kw)
    return matched

def classify(text: str) -> dict:
    """
    Classifies a document based on keyword matching.
    Returns:
        {
            "type": "Invoice" | "Contract" | "Lease" | "Receipt" | "Other",
            "confidence": 0.0 – 1.0,
            "keywords_matched": [...],
            "status": "filed" | "needs_review"
        }
    """
    if not text or not text.strip():
        return {
            "type": "Other",
            "confidence": 0.0,
            "keywords_matched": [],
            "status": "needs_review"
        }

    text_lower = text.lower()
    scores = {}

    for category, config in CATEGORIES.items():
        matched = extract_keywords_matched(text_lower, config["keywords"])
        total   = len(config["keywords"])
        ratio   = len(matched) / total if total > 0 else 0
        # Scale: ratio * weight, then soft-clip to give partial credit
        score   = min(ratio * config["weight"] * 5, config["weight"])
        scores[category] = {"score": score, "matched": matched}

    best_category = max(scores, key=lambda k: scores[k]["score"])
    best_score    = scores[best_category]["score"]
    best_matched  = scores[best_category]["matched"]

    # If best score is below a minimum bar, classify as Other
    if best_score < 0.05 or len(best_matched) < 1:
        return {
            "type": "Other",
            "confidence": round(best_score, 4),
            "keywords_matched": [],
            "status": "needs_review"
        }

    status = "filed" if best_score >= CONFIDENCE_THRESHOLD else "needs_review"

    return {
        "type": best_category,
        "confidence": round(best_score, 4),
        "keywords_matched": best_matched,
        "status": status
    }

def get_all_types():
    return list(CATEGORIES.keys()) + ["Other"]

CONFIDENCE_THRESHOLD_VALUE = CONFIDENCE_THRESHOLD
