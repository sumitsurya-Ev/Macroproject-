"""
generate_test_samples.py — Generates realistic sample test PDFs using reportlab.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

TEST_DIR = "test_samples"
os.makedirs(TEST_DIR, exist_ok=True)

def create_invoice_pdf(filepath):
    c = canvas.Canvas(filepath, pagesize=letter)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 750, "TAX INVOICE")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 720, "Invoice Number: INV-2026-0042")
    c.drawString(50, 705, "Invoice Date: 2026-09-28")
    c.drawString(50, 690, "Payment Due Date: 2026-10-15")
    c.drawString(50, 675, "GSTIN: 27AABCU9603R1ZN")
    
    c.drawString(50, 640, "Bill To: Acme Global Technologies Pvt Ltd")
    c.drawString(50, 625, "Vendor: Apex Cloud Solutions")
    c.drawString(50, 610, "Purchase Order: PO-99812")
    
    c.drawString(50, 560, "Item Description                Qty    Unit Price    Line Total")
    c.drawString(50, 545, "------------------------------------------------------------------")
    c.drawString(50, 530, "Cloud Server Hosting (Monthly)    1     Rs 25,000      Rs 25,000")
    c.drawString(50, 515, "Security & Maintenance Package   1     Rs 10,000      Rs 10,000")
    
    c.drawString(50, 470, "Subtotal: Rs 35,000")
    c.drawString(50, 455, "Taxable Amount: Rs 35,000")
    c.drawString(50, 440, "CGST (9%): Rs 3,150")
    c.drawString(50, 425, "SGST (9%): Rs 3,150")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 400, "Total Amount Payable: Rs 41,300")
    c.save()
    print(f"Created: {filepath}")

def create_lease_pdf(filepath):
    c = canvas.Canvas(filepath, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "RESIDENTIAL RENTAL LEASE AGREEMENT")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 715, "This Tenancy and Rental Agreement is made on 2026-09-01 between:")
    c.drawString(50, 695, "Landlord / Lessor: Rajesh Sharma")
    c.drawString(50, 675, "Tenant / Lessee: Amit Verma")
    
    c.drawString(50, 640, "1. Demised Premises: Flat 402, Sunshine Towers, MG Road.")
    c.drawString(50, 620, "2. Lease Term: The tenancy period shall be 11 months.")
    c.drawString(50, 600, "3. Monthly Rent: The Tenant shall pay Rs 32,000 monthly rent on or before the 5th.")
    c.drawString(50, 580, "4. Security Deposit: Refundable deposit of Rs 1,00,000 received by Lessor.")
    c.drawString(50, 560, "5. Maintenance Charges: Society charges payable by Tenant.")
    c.drawString(50, 540, "6. Eviction & Possession: Two months notice period required prior to termination.")
    c.drawString(50, 500, "Witness 1: _______________            Witness 2: _______________")
    c.save()
    print(f"Created: {filepath}")

def create_contract_pdf(filepath):
    c = canvas.Canvas(filepath, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "NON-DISCLOSURE AND SERVICE CONTRACT")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 715, "This Binding Agreement is entered into by and between the Parties:")
    c.drawString(50, 695, "WHEREAS, the parties desire to establish mutual covenants, obligations, and terms.")
    c.drawString(50, 670, "1. Scope of Work: Deliverables and intellectual property ownership.")
    c.drawString(50, 650, "2. Confidentiality: Non-disclosure covenants covering proprietary data.")
    c.drawString(50, 630, "3. Liabilities and Indemnification: Each party shall indemnify the other.")
    c.drawString(50, 610, "4. Termination & Breach: In the event of material breach, written notice is required.")
    c.drawString(50, 590, "5. Dispute Resolution & Arbitration: Governed by the jurisdiction of High Court.")
    c.drawString(50, 550, "IN WITNESS WHEREOF, the parties hereto have executed this Agreement.")
    c.save()
    print(f"Created: {filepath}")

def create_receipt_pdf(filepath):
    c = canvas.Canvas(filepath, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "PAYMENT CONFIRMATION RECEIPT")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 715, "Official Cash Receipt & Acknowledgement of Payment")
    c.drawString(50, 685, "Received from: Priya Nair")
    c.drawString(50, 665, "Receipt No: RCP-8831")
    c.drawString(50, 645, "Amount Paid: Rs 15,000")
    c.drawString(50, 625, "Mode of Payment: UPI / Bank Transfer")
    c.drawString(50, 605, "Transaction ID / Ref No: UPI/2026/8912389")
    c.drawString(50, 585, "Payment Status: Payment Successful - Paid in full")
    c.drawString(50, 550, "Thank you for your payment!")
    c.save()
    print(f"Created: {filepath}")

def create_ambiguous_pdf(filepath):
    c = canvas.Canvas(filepath, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Meeting Agenda and Brainstorming Notes")
    
    c.setFont("Helvetica", 11)
    c.drawString(50, 715, "Discussion topics regarding Q4 team planning:")
    c.drawString(50, 690, "- Team members to coordinate project milestones.")
    c.drawString(50, 670, "- Review quarterly roadmap and feature backlog.")
    c.drawString(50, 650, "- Setup design sprint for upcoming dashboard update.")
    c.drawString(50, 630, "- Next sync scheduled for next Thursday at 3 PM.")
    c.save()
    print(f"Created: {filepath}")

if __name__ == "__main__":
    create_invoice_pdf(os.path.join(TEST_DIR, "sample_tax_invoice.pdf"))
    create_lease_pdf(os.path.join(TEST_DIR, "sample_rental_lease.pdf"))
    create_contract_pdf(os.path.join(TEST_DIR, "sample_nda_contract.pdf"))
    create_receipt_pdf(os.path.join(TEST_DIR, "sample_payment_receipt.pdf"))
    create_ambiguous_pdf(os.path.join(TEST_DIR, "sample_ambiguous_notes.pdf"))
    print("\nAll 5 test sample PDFs successfully generated!")
