"""
Regression and Accessibility Compliance Test Suite
Tests for WCAG 2.2 Level AA and PDF/UA-1 (ISO 14289-1) compliance.
"""

import os
import sys
import json
import unittest
from pathlib import Path

# Set stdout/stderr encoding safely
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import fitz
import pikepdf
from main import PDFTaggingPipeline
from pdf_accessibility_validator import PDFAccessibilityValidator, AccessibilityCheckResult


class TestPDFAccessibilityCompliance(unittest.TestCase):
    """Automated test cases verifying all accessibility requirements."""

    INPUT_PDF = "input.pdf"
    OUTPUT_PDF = "test_output_accessible.pdf"

    @classmethod
    def setUpClass(cls):
        """Run the tagging pipeline once on input.pdf before testing."""
        assert os.path.exists(cls.INPUT_PDF), f"Test input PDF '{cls.INPUT_PDF}' must exist"
        pipeline = PDFTaggingPipeline(use_api=False)
        cls.metadata = pipeline.process_pdf(cls.INPUT_PDF, cls.OUTPUT_PDF)
        
        cls.validator = PDFAccessibilityValidator(cls.OUTPUT_PDF)
        cls.audit_report = cls.validator.validate()

    @classmethod
    def tearDownClass(cls):
        """Cleanup test artifacts if desired (we keep OUTPUT_PDF for audit inspection)."""
        pass

    def test_overall_audit_passed(self):
        """Verify that automated accessibility audit achieves 100% pass rate."""
        stats = self.audit_report["statistics"]
        self.assertEqual(stats["failed"], 0, f"Accessibility audit had {stats['failed']} failures")
        self.assertEqual(self.audit_report["automated_status"], "PASS_AUTOMATED")
        self.assertEqual(stats["automated_compliance_rate_pct"], 100.0)

    def test_document_catalog_and_marked_info(self):
        """Verify /MarkInfo /Marked is true and /Lang is specified."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            self.assertIn("/MarkInfo", pdf.Root)
            self.assertTrue(bool(pdf.Root.MarkInfo.Marked))
            self.assertIn("/Lang", pdf.Root)
            self.assertEqual(str(pdf.Root.Lang).strip("()"), "en-US")

    def test_viewer_preferences_display_doc_title(self):
        """Verify /ViewerPreferences /DisplayDocTitle is true (WCAG 2.4.2)."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            self.assertIn("/ViewerPreferences", pdf.Root)
            self.assertTrue(bool(pdf.Root.ViewerPreferences.DisplayDocTitle))

    def test_document_title_and_pdfua_xmp(self):
        """Verify Title metadata and PDF/UA-1 XMP schema identifier."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            self.assertIn("/Title", pdf.docinfo)
            title = str(pdf.docinfo["/Title"]).strip("()")
            self.assertIn("Accessible PDF Demo Document", title)

            self.assertIn("/Metadata", pdf.Root)
            xmp = pdf.Root.Metadata.read_bytes().decode('utf-8')
            self.assertIn("pdfuaid:part", xmp)
            self.assertIn("<pdfuaid:part>1</pdfuaid:part>", xmp)
            self.assertIn("http://www.aiim.org/pdfua/ns/id/", xmp)

    def test_logical_structure_tree_root(self):
        """Verify /StructTreeRoot, /Document root element, and /ParentTree."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            self.assertIn("/StructTreeRoot", pdf.Root)
            str_root = pdf.Root.StructTreeRoot
            self.assertIn("/K", str_root)
            self.assertIn("/ParentTree", str_root)
            
            # Check root Document element
            doc_k = str_root.K
            self.assertTrue(len(doc_k) > 0)
            doc_elem = doc_k[0]
            self.assertEqual(str(doc_elem.get("/S", "")).strip("/"), "Document")

    def test_headings_hierarchy(self):
        """Verify H1 exists and headings follow logical hierarchy without skipping levels."""
        headings = []
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            def collect_headings(node):
                if isinstance(node, pikepdf.Dictionary):
                    tag = str(node.get("/S", "")).strip("/")
                    if tag in ["H1", "H2", "H3", "H4", "H5", "H6"]:
                        headings.append({
                            "tag": tag,
                            "level": int(tag[1]),
                            "text": str(node.get("/ActualText", "")).strip()
                        })
                    if "/K" in node:
                        k = node["/K"]
                        if isinstance(k, pikepdf.Array):
                            for c in k: collect_headings(c)
                        elif isinstance(k, pikepdf.Dictionary):
                            collect_headings(k)
                elif isinstance(node, pikepdf.Array):
                    for c in node: collect_headings(c)
            
            collect_headings(pdf.Root.StructTreeRoot)

        self.assertTrue(len(headings) > 0)
        # Check exactly one H1
        h1s = [h for h in headings if h["level"] == 1]
        self.assertEqual(len(h1s), 1)
        self.assertEqual(h1s[0]["text"], "Accessible PDF Demo Document")

        # Check no illegal level jumps
        prev_level = 1
        for h in headings[1:]:
            self.assertLessEqual(h["level"], prev_level + 1, f"Illegal jump from H{prev_level} to H{h['level']}")
            prev_level = h["level"]

        # Check all 5 major sections are present as H2 (including Images)
        h2_texts = [h["text"] for h in headings if h["level"] == 2]
        self.assertIn("Lists", h2_texts)
        self.assertIn("Artifacts", h2_texts)
        self.assertIn("Tables", h2_texts)
        self.assertIn("Images", h2_texts)
        self.assertIn("Links", h2_texts)

        # Check sub-sections and titles are properly tagged as headings (not flat body text)
        all_heading_texts = [h["text"] for h in headings]
        self.assertIn("Photos of Sunsets", all_heading_texts)
        self.assertIn("List of Canadian Provinces by Population (2014)", all_heading_texts)
        self.assertIn("Some Adobe Creative Cloud Desktop Apps with Descriptions", all_heading_texts)
        self.assertIn("Vehicles Sold by Model and Color", all_heading_texts)
        self.assertIn("Sales Results for 2015", all_heading_texts)

    def test_lists_structure(self):
        """Verify lists are enclosed in <L>, children are <LI>, and no naked <LI> exist."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            naked_li = 0
            list_count = 0
            li_count = 0

            def inspect_lists(node, parent_tag=None):
                nonlocal naked_li, list_count, li_count
                if isinstance(node, pikepdf.Dictionary):
                    tag = str(node.get("/S", "")).strip("/")
                    if tag == "L":
                        list_count += 1
                    elif tag == "LI":
                        li_count += 1
                        if parent_tag != "L":
                            naked_li += 1
                    
                    if "/K" in node:
                        k = node["/K"]
                        if isinstance(k, pikepdf.Array):
                            for c in k: inspect_lists(c, tag)
                        elif isinstance(k, pikepdf.Dictionary):
                            inspect_lists(k, tag)
                elif isinstance(node, pikepdf.Array):
                    for c in node: inspect_lists(c, parent_tag)

            inspect_lists(pdf.Root.StructTreeRoot)
            self.assertGreater(list_count, 0, "Document should contain <L> list elements")
            self.assertGreater(li_count, 0, "Document should contain <LI> list item elements")
            self.assertEqual(naked_li, 0, "No <LI> should exist outside of a parent <L> element")

    def test_tables_structure_and_headers(self):
        """Verify tables contain <TR> rows and <TH> cells with /Scope attribute."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            tables = []

            def find_tables(node):
                if isinstance(node, pikepdf.Dictionary):
                    tag = str(node.get("/S", "")).strip("/")
                    if tag == "Table":
                        tables.append(node)
                    if "/K" in node:
                        k = node["/K"]
                        if isinstance(k, pikepdf.Array):
                            for c in k: find_tables(c)
                        elif isinstance(k, pikepdf.Dictionary):
                            find_tables(k)
                elif isinstance(node, pikepdf.Array):
                    for c in node: find_tables(c)

            find_tables(pdf.Root.StructTreeRoot)
            self.assertEqual(len(tables), 2, "Expected 2 data tables in document")

            for tbl in tables:
                rows = tbl.K
                self.assertGreater(len(rows), 0, "Table must have <TR> children")
                has_th = False
                for row in rows:
                    self.assertEqual(str(row.get("/S", "")).strip("/"), "TR")
                    for cell in row.K:
                        cell_tag = str(cell.get("/S", "")).strip("/")
                        self.assertIn(cell_tag, ["TH", "TD"])
                        if cell_tag == "TH":
                            has_th = True
                            # Check scope attribute
                            self.assertIn("/A", cell)
                            self.assertIn("/Scope", cell.A)
                self.assertTrue(has_th, "Table must have <TH> header cells")

    def test_figures_and_alternative_text(self):
        """Verify all <Figure> elements have non-empty /Alt attributes."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            figures = []

            def find_figures(node):
                if isinstance(node, pikepdf.Dictionary):
                    tag = str(node.get("/S", "")).strip("/")
                    if tag == "Figure":
                        figures.append(node)
                    if "/K" in node:
                        k = node["/K"]
                        if isinstance(k, pikepdf.Array):
                            for c in k: find_figures(c)
                        elif isinstance(k, pikepdf.Dictionary):
                            find_figures(k)
                elif isinstance(node, pikepdf.Array):
                    for c in node: find_figures(c)

            find_figures(pdf.Root.StructTreeRoot)
            self.assertEqual(len(figures), 8, "Expected 8 <Figure> elements for document images")
            for fig in figures:
                self.assertIn("/Alt", fig, "Figure must have /Alt attribute")
                alt_text = str(fig.Alt).strip("()")
                self.assertTrue(len(alt_text) > 5, "Figure /Alt must be non-empty and descriptive")

    def test_links_and_objr(self):
        """Verify links contain /OBJR annotations and valid destination accessible names."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            links = []

            def find_links(node):
                if isinstance(node, pikepdf.Dictionary):
                    tag = str(node.get("/S", "")).strip("/")
                    if tag == "Link":
                        links.append(node)
                    if "/K" in node:
                        k = node["/K"]
                        if isinstance(k, pikepdf.Array):
                            for c in k: find_links(c)
                        elif isinstance(k, pikepdf.Dictionary):
                            find_links(k)
                elif isinstance(node, pikepdf.Array):
                    for c in node: find_links(c)

            find_links(pdf.Root.StructTreeRoot)
            self.assertGreaterEqual(len(links), 1, "Expected at least 1 <Link> element")
            for lnk in links:
                self.assertIn("/Alt", lnk)
                # Check for /OBJR in /K
                has_objr = False
                for item in lnk.K:
                    if isinstance(item, pikepdf.Dictionary) and str(item.get("/Type", "")).strip("/") == "OBJR":
                        has_objr = True
                self.assertTrue(has_objr, "Link must contain /OBJR object reference")

    def test_bookmarks_outlines(self):
        """Verify navigation bookmarks exist and reflect heading hierarchy."""
        with pikepdf.Pdf.open(self.OUTPUT_PDF) as pdf:
            self.assertIn("/Outlines", pdf.Root)
            outlines = pdf.Root.Outlines
            self.assertIn("/First", outlines)
            self.assertIn("/Last", outlines)

    def test_content_integrity_preservation(self):
        """Verify that original text, page count, and dimensions are preserved without corruption."""
        with fitz.open(self.INPUT_PDF) as orig_doc, fitz.open(self.OUTPUT_PDF) as tagged_doc:
            self.assertEqual(len(orig_doc), len(tagged_doc), "Page count must match")
            for pno in range(len(orig_doc)):
                orig_page = orig_doc[pno]
                tagged_page = tagged_doc[pno]
                self.assertEqual(orig_page.rect, tagged_page.rect, f"Page {pno+1} dimensions must match")
                # Text should be selectable on all pages
                self.assertGreater(len(tagged_page.get_text()), 100, f"Page {pno+1} text must be selectable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
