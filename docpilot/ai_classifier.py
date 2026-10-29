"""
ai_classifier.py — Multimodal AI document classifier.

AI is NOT restricted to a fixed set of categories.
It returns the most accurate document type for any file,
and DocPilot creates the correct folder automatically.

Provider priority: GEMINI_API_KEY → OPENAI_API_KEY → keyword fallback
"""

import json
import re
from config import (
    AI_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY,
    GEMINI_MODEL, OPENAI_MODEL, MAX_TEXT_CHARS, CONFIDENCE_THRESHOLD
)

# ── Prompt: AI is free to return ANY document type ──────────────────────────
SYSTEM_PROMPT = """You are DocPilot, an expert document classification AI for Indian professionals.

Given extracted PDF text, return ONLY a valid JSON object (no markdown, no text outside JSON):

{
  "type": "<Most accurate document category — see rules below>",
  "confidence": <float 0.00 to 1.00>,
  "reasoning": "<One sentence explaining your decision>",
  "entities": {
    "vendor":         "<Company or person who issued the document, or null>",
    "client":         "<Recipient or counterparty, or null>",
    "amount":         "<Total monetary amount with currency symbol, or null>",
    "date":           "<Primary document date YYYY-MM-DD, or null>",
    "reference_no":   "<Invoice / receipt / case / order / ref number, or null>",
    "gstin":          "<15-char GSTIN if present, or null>",
    "pan":            "<10-char PAN if present, or null>",
    "due_date":       "<Payment or expiry deadline YYYY-MM-DD, or null>",
    "period":         "<Financial period, quarter, or month, or null>"
  },
  "suggested_filename": "<Smart descriptive filename without extension, e.g. 2026-09-28_Acme_Invoice_INV-042>"
}

TYPE CLASSIFICATION RULES — choose the most specific and accurate type:
- "Invoice"          : Tax invoices, GST bills, vendor bills, pro-forma invoices, e-invoices
- "Receipt"          : Payment receipts, UPI/NEFT/RTGS confirmations, cash receipts, acknowledgements
- "Contract"         : Service agreements, NDAs, employment contracts, MOU, consulting agreements, SOW
- "Lease"            : Rental agreements, tenancy agreements, leave & licence, property leases
- "Purchase Order"   : PO documents, work orders, supply orders
- "Quotation"        : Price quotations, estimates, tender bids, proposals
- "Bank Statement"   : Bank account statements, passbook extracts, account summaries
- "Salary Slip"      : Pay slips, salary statements, payroll documents, Form 16
- "Delivery Challan" : Challan, e-way bill, packing list, dispatch note
- "Legal Notice"     : Court summons, legal notice, vakalatnama, FIR copy, court order
- "Insurance Policy" : Insurance certificates, policy documents, premium receipts
- "KYC Document"     : Aadhaar, PAN card copy, voter ID, passport copy, address proof
- "Tax Return"       : ITR forms, GST returns (GSTR-1, GSTR-3B), TDS returns
- "Credit Note"      : Credit notes, debit notes, return memos
- "Certificate"      : Academic certificates, completion certificates, registration certificates
- "Meeting Minutes"  : MOM, agenda, meeting notes, board resolutions
- "Other"            : Anything that does not clearly match the above categories

CONFIDENCE GUIDELINES:
- 0.95+  : Multiple specific markers clearly match (e.g. GSTIN + "Tax Invoice" + line items)
- 0.85-0.94 : Primary markers present, minor ambiguity
- 0.70-0.84 : Likely match but document is sparse or unusual
- Below 0.70 : Genuinely unclear

IMPORTANT: Always pick the MOST SPECIFIC type. Only use "Other" when truly nothing else fits.
Extract every entity you can find in the text.
"""


def _build_prompt(text: str) -> str:
    return f"Classify this document and extract all entities:\n\n---\n{text[:MAX_TEXT_CHARS]}\n---"


# ── Gemini ───────────────────────────────────────────────────────────────────
def _classify_gemini(text: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=600,
        )
    )
    response = model.generate_content(_build_prompt(text))
    return json.loads(response.text)


# ── OpenAI ───────────────────────────────────────────────────────────────────
def _classify_openai(text: str) -> dict:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        max_tokens=600,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_prompt(text)}
        ]
    )
    return json.loads(response.choices[0].message.content)


# ── Keyword fallback (extended — 15+ categories) ─────────────────────────────
def _classify_keyword(text: str) -> dict:
    """
    Extended keyword classifier with 15+ categories.
    Used when no AI API key is set.
    """
    text_lower = text.lower()

    KEYWORD_CATEGORIES = {
        "Invoice": {
            "w": 0.90,
            "k": ["tax invoice","invoice number","invoice no","inv no","bill to",
                  "amount due","payment due","subtotal","total amount","gstin",
                  "hsn","sac","cgst","sgst","igst","taxable amount","vendor",
                  "purchase order","line total","unit price"]
        },
        "Receipt": {
            "w": 0.88,
            "k": ["receipt","payment received","received from","cash receipt",
                  "amount paid","paid","payment confirmation","transaction id",
                  "txn id","upi","neft","rtgs","reference number","payment successful",
                  "thank you for your payment","acknowledgement of payment"]
        },
        "Contract": {
            "w": 0.88,
            "k": ["agreement","contract","whereas","parties","hereinafter",
                  "obligations","liabilities","indemnify","arbitration","termination",
                  "breach","jurisdiction","entire agreement","non-disclosure","nda",
                  "scope of work","deliverables","intellectual property","covenants",
                  "in witness whereof","executed"]
        },
        "Lease": {
            "w": 0.88,
            "k": ["lease","rental agreement","tenancy","tenant","landlord",
                  "lessor","lessee","rent","monthly rent","security deposit",
                  "premises","tenancy period","notice period","eviction",
                  "leave and licence","licence fee","stamp duty"]
        },
        "Purchase Order": {
            "w": 0.87,
            "k": ["purchase order","p.o.","po number","order number","work order",
                  "supply order","ordered by","deliver to","order date","order total",
                  "please supply","supply of goods"]
        },
        "Quotation": {
            "w": 0.85,
            "k": ["quotation","quote","estimate","proposal","tender","bid",
                  "valid until","quoted price","quote no","our ref",
                  "please find attached our quotation","rate per unit"]
        },
        "Bank Statement": {
            "w": 0.87,
            "k": ["account statement","bank statement","account number","ifsc",
                  "opening balance","closing balance","debit","credit",
                  "transaction date","account holder","passbook","account summary"]
        },
        "Salary Slip": {
            "w": 0.87,
            "k": ["salary slip","pay slip","payslip","gross salary","net salary",
                  "basic pay","hra","da","pf","professional tax","tds deducted",
                  "employee code","employee id","month of","in hand salary",
                  "earnings","deductions","form 16"]
        },
        "Delivery Challan": {
            "w": 0.85,
            "k": ["delivery challan","challan no","e-way bill","eway bill",
                  "packing list","dispatch note","goods dispatched","consignee",
                  "consignor","vehicle number","quantity dispatched"]
        },
        "Legal Notice": {
            "w": 0.85,
            "k": ["legal notice","court notice","summons","fir","vakalatnama",
                  "court order","high court","district court","arbitration notice",
                  "cause of action","plaintiff","defendant","advocate","counsel"]
        },
        "Insurance Policy": {
            "w": 0.85,
            "k": ["insurance policy","policy number","insured","insurer","premium",
                  "sum assured","policy period","coverage","claim","nominee",
                  "insurance certificate","irda","irdai"]
        },
        "KYC Document": {
            "w": 0.85,
            "k": ["aadhaar","pan card","voter id","passport","driving licence",
                  "address proof","identity proof","kyc","know your customer",
                  "date of birth","unique identification","uidai"]
        },
        "Tax Return": {
            "w": 0.85,
            "k": ["itr","income tax return","gstr","gst return","form 26as",
                  "tds return","assessment year","previous year","total income",
                  "tax payable","refund due","e-filing"]
        },
        "Credit Note": {
            "w": 0.85,
            "k": ["credit note","debit note","return memo","goods return",
                  "credit note no","cn no","adjustment note","reversal"]
        },
        "Certificate": {
            "w": 0.83,
            "k": ["certificate","this is to certify","certified that","completion",
                  "registration certificate","incorporation","udyam","msme certificate",
                  "iso certificate","authorized signatory certifies"]
        },
        "Meeting Minutes": {
            "w": 0.82,
            "k": ["minutes of meeting","mom","agenda","attendees","meeting held",
                  "action items","discussed","resolved","next meeting",
                  "board resolution","committee meeting"]
        },
    }

    scores = {}
    for cat, cfg in KEYWORD_CATEGORIES.items():
        matched = [k for k in cfg["k"] if re.search(r'\b' + re.escape(k) + r'\b', text_lower)]
        ratio   = len(matched) / len(cfg["k"])
        score   = min(ratio * cfg["w"] * 5, cfg["w"])
        scores[cat] = {"score": score, "matched": matched}

    best     = max(scores, key=lambda k: scores[k]["score"])
    b_score  = scores[best]["score"]
    b_match  = scores[best]["matched"]

    if b_score < 0.05 or len(b_match) < 1:
        return {
            "type": "Other", "confidence": 0.0,
            "reasoning": "No recognizable document keywords found.",
            "entities": {k: None for k in ["vendor","client","amount","date",
                                            "reference_no","gstin","pan","due_date","period"]},
            "suggested_filename": None
        }

    return {
        "type":       best,
        "confidence": round(b_score, 4),
        "reasoning":  f"Matched keywords: {', '.join(b_match[:5])}",
        "entities":   {k: None for k in ["vendor","client","amount","date",
                                          "reference_no","gstin","pan","due_date","period"]},
        "suggested_filename": None
    }


# ── Public entry point ───────────────────────────────────────────────────────
def ai_classify(text: str, original_filename: str = "") -> dict:
    """
    Classify a document. Returns a normalized result dict.
    Falls back gracefully on any API error.
    """
    raw      = {}
    provider = AI_PROVIDER

    try:
        if provider == "gemini":
            raw = _classify_gemini(text)
        elif provider == "openai":
            raw = _classify_openai(text)
        else:
            raw = _classify_keyword(text)
    except Exception as exc:
        print(f"[AI] {provider} failed: {exc} — falling back to keyword classifier.")
        raw      = _classify_keyword(text)
        provider = "keyword"

    # ── Normalize ──
    doc_type   = str(raw.get("type", "Other")).strip() or "Other"
    confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
    status     = "filed" if confidence >= CONFIDENCE_THRESHOLD else "needs_review"

    # ── Smart filename ──
    suggested = raw.get("suggested_filename")
    if not suggested:
        suggested = _build_smart_filename(raw.get("entities", {}), doc_type, original_filename)
    if suggested:
        suggested = re.sub(r'[\\/*?:"<>|]', '', suggested).strip()[:120]

    return {
        "type":               doc_type,
        "confidence":         round(confidence, 4),
        "status":             status,
        "reasoning":          raw.get("reasoning", ""),
        "entities":           raw.get("entities", {}),
        "suggested_filename": suggested,
        "provider":           provider,
        "keywords_matched":   [raw.get("reasoning", "")[:80]] if raw.get("reasoning") else [],
    }


def _build_smart_filename(entities: dict, doc_type: str, original: str) -> str:
    parts = []
    if entities.get("date"):
        parts.append(str(entities["date"]))
    vendor = entities.get("vendor") or entities.get("client")
    if vendor:
        clean = re.sub(r'[^a-zA-Z0-9 ]', '', str(vendor)).strip().replace(" ", "_")[:30]
        if clean:
            parts.append(clean)
    parts.append(doc_type.replace(" ", "_"))
    ref = entities.get("reference_no") or entities.get("invoice_number")
    if ref:
        parts.append(re.sub(r'[^a-zA-Z0-9\-]', '', str(ref))[:20])
    if parts:
        return "_".join(filter(None, parts))
    return re.sub(r'\.pdf$', '', original, flags=re.IGNORECASE) or "document"


def get_all_known_types() -> list:
    """
    Returns all document types seen in the DB + standard built-in types.
    Used to populate the Review Queue override dropdown.
    """
    import sqlite3
    builtin = [
        "Invoice", "Receipt", "Contract", "Lease", "Purchase Order",
        "Quotation", "Bank Statement", "Salary Slip", "Delivery Challan",
        "Legal Notice", "Insurance Policy", "KYC Document", "Tax Return",
        "Credit Note", "Certificate", "Meeting Minutes", "Other"
    ]
    try:
        conn  = sqlite3.connect("docpilot.db")
        rows  = conn.execute("SELECT DISTINCT doc_type FROM documents").fetchall()
        conn.close()
        db_types = [r[0] for r in rows if r[0]]
    except Exception:
        db_types = []
    combined = list(dict.fromkeys(builtin + db_types))  # deduplicate, preserve order
    return sorted(combined)


def get_provider_status() -> dict:
    labels = {
        "gemini":  f"Google Gemini ({GEMINI_MODEL})",
        "openai":  f"OpenAI ({OPENAI_MODEL})",
        "keyword": "Keyword Classifier (offline)"
    }
    return {
        "provider": AI_PROVIDER,
        "label":    labels.get(AI_PROVIDER, AI_PROVIDER),
        "active":   AI_PROVIDER != "keyword"
    }
