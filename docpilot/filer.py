"""
filer.py — Fully dynamic document filer.

Creates destination folders on-the-fly for ANY document type.
No hardcoded category list — if a new type comes in, a new folder is created automatically.
"""

import os
import re
import shutil

BASE_FILED_DIR = "filed"


def _sanitize_folder_name(name: str) -> str:
    """
    Converts any AI-generated category name into a safe folder name.
    e.g. "Bank Statement" -> "Bank_Statements"
        "Purchase Order"  -> "Purchase_Orders"
        "KYC Document"    -> "KYC_Documents"
        "Invoice"         -> "Invoices"
        "other"           -> "Other"
    """
    # Title-case, strip unsafe chars
    name = name.strip().title()
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = name.replace(' ', '_').replace('-', '_')
    name = re.sub(r'_+', '_', name).strip('_')

    # Pluralize common single-word categories for cleaner folder names
    plurals = {
        'Invoice':       'Invoices',
        'Contract':      'Contracts',
        'Lease':         'Leases',
        'Receipt':       'Receipts',
        'Agreement':     'Agreements',
        'Quotation':     'Quotations',
        'Proposal':      'Proposals',
        'Notice':        'Notices',
        'Report':        'Reports',
        'Statement':     'Statements',
        'Certificate':   'Certificates',
        'Order':         'Orders',
        'Challan':       'Challans',
        'Voucher':       'Vouchers',
        'Payslip':       'Payslips',
        'Slip':          'Slips',
        'Form':          'Forms',
    }
    # Multi-word: pluralize the last word
    parts = name.split('_')
    last  = parts[-1]
    if last in plurals:
        parts[-1] = plurals[last]
        return '_'.join(parts)

    # Already plural or no rule — just return as-is
    if not name.endswith('s') and name not in ('Other', 'Misc', 'Unknown'):
        # gentle pluralization: only for clean single words
        if '_' not in name and len(name) < 20:
            name = name + 's'

    return name


def get_destination_folder(doc_type: str) -> str:
    """
    Returns (and creates) the destination folder for any document type.
    Always works — even for brand new AI-generated categories.
    """
    folder_name = _sanitize_folder_name(doc_type)
    folder_path = os.path.join(BASE_FILED_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def ensure_folders():
    """Creates the base filed/ directory. Individual category folders are created on demand."""
    os.makedirs(BASE_FILED_DIR, exist_ok=True)


def list_all_folders() -> list:
    """Returns a sorted list of all existing category folders inside filed/."""
    if not os.path.isdir(BASE_FILED_DIR):
        return []
    return sorted([
        d for d in os.listdir(BASE_FILED_DIR)
        if os.path.isdir(os.path.join(BASE_FILED_DIR, d))
    ])


def file_document(source_path: str, doc_type: str) -> str:
    """
    Moves a document to the correct folder for its type.
    Creates the folder automatically if it doesn't exist.
    Returns the final destination path.
    """
    dest_folder = get_destination_folder(doc_type)
    filename    = os.path.basename(source_path)
    dest_path   = os.path.join(dest_folder, filename)

    # Handle name collisions
    if os.path.exists(dest_path):
        base, ext = os.path.splitext(filename)
        counter   = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
            counter  += 1

    shutil.move(source_path, dest_path)
    return dest_path


def copy_document(source_path: str, doc_type: str) -> str:
    """
    Copies (instead of moves) — for watcher mode where the source should remain.
    """
    dest_folder = get_destination_folder(doc_type)
    filename    = os.path.basename(source_path)
    dest_path   = os.path.join(dest_folder, filename)

    if os.path.exists(dest_path):
        base, ext = os.path.splitext(filename)
        counter   = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
            counter  += 1

    shutil.copy2(source_path, dest_path)
    return dest_path
