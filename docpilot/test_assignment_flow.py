"""
test_assignment_flow.py — Test assignment classification and filing into user-created folders.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, docpilot_engine
import database
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


class TestAssignmentFlow(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.test_filename = "test_ai_assignment_submission.pdf"
        self.test_pdf_path = os.path.join(os.path.dirname(__file__), self.test_filename)

        c = canvas.Canvas(self.test_pdf_path, pagesize=letter)
        c.drawString(100, 750, "UNIVERSITY DEPARTMENT OF COMPUTER SCIENCE")
        c.drawString(100, 720, "Course: CS 501 - Advanced Machine Learning")
        c.drawString(100, 690, "Student Name: Rahul Sharma (Roll No: CS2026-042)")
        c.drawString(100, 660, "Assignment Title: Assignment 2 - Deep Neural Network Optimization")
        c.drawString(100, 630, "Submission Date: 2026-10-24")
        c.drawString(100, 600, "Problem 1: Derive the backpropagation equations for a 3-layer MLP.")
        c.drawString(100, 570, "Problem 2: Compare Adam vs SGD with momentum on gradient descent.")
        c.save()

    def tearDown(self):
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

    def test_assignment_files_into_assignments_folder(self):
        with open(self.test_pdf_path, "rb") as f:
            res = self.client.post("/upload?json=1", data={"file": (f, self.test_filename)})

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        print("Upload Result:", data)

        self.assertEqual(data.get("destination"), "Assignments", f"Expected destination Assignments, got: {data.get('destination')}")
        self.assertGreaterEqual(data.get("confidence", 0), 85, f"Expected confidence >= 85%, got: {data.get('confidence')}%")
        self.assertEqual(data.get("status"), "filed", f"Expected status filed, got: {data.get('status')}")


if __name__ == "__main__":
    unittest.main()
