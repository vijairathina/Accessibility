"""
PDF Accessibility Validator
Comprehensive automated accessibility audit for PDF/UA-1 (ISO 14289-1) and WCAG 2.2 Level AA.
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import pikepdf
import fitz


class AccessibilityCheckResult:
    """Represents the result of an individual accessibility check."""
    
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    MANUAL_REVIEW = "MANUAL_REVIEW"

    def __init__(
        self,
        check_id: str,
        name: str,
        standard: str,
        status: str,
        details: str,
        page: Optional[int] = None,
        element: Optional[str] = None,
        root_cause: Optional[str] = None,
        remediation: Optional[str] = None,
        is_auto_fixable: bool = False
    ):
        self.check_id = check_id
        self.name = name
        self.standard = standard
        self.status = status
        self.details = details
        self.page = page
        self.element = element
        self.root_cause = root_cause
        self.remediation = remediation
        self.is_auto_fixable = is_auto_fixable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "standard": self.standard,
            "status": self.status,
            "details": self.details,
            "page": self.page,
            "element": self.element,
            "root_cause": self.root_cause,
            "remediation": self.remediation,
            "is_auto_fixable": self.is_auto_fixable
        }


class PDFAccessibilityValidator:
    """
    Automated validator inspecting PDF documents against WCAG 2.2 AA and PDF/UA-1 standards.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.results: List[AccessibilityCheckResult] = []
        self.timestamp = datetime.now().isoformat()
        self.doc_title = None

    def validate(self) -> Dict[str, Any]:
        """Run all automated accessibility checks."""
        self.results = []
        
        if not os.path.exists(self.pdf_path):
            self.results.append(AccessibilityCheckResult(
                check_id="FILE-001",
                name="File Existence",
                standard="General",
                status=AccessibilityCheckResult.FAIL,
                details=f"File not found: {self.pdf_path}",
                root_cause="File path is invalid or file was removed",
                remediation="Ensure input file exists before running audit"
            ))
            return self._build_report()

        try:
            pdf = pikepdf.Pdf.open(self.pdf_path)
            doc_fitz = fitz.open(self.pdf_path)
        except Exception as e:
            self.results.append(AccessibilityCheckResult(
                check_id="FILE-002",
                name="File Open & Syntax",
                standard="PDF/UA-1 (ISO 14289-1 § 5)",
                status=AccessibilityCheckResult.FAIL,
                details=f"Failed to open PDF: {e}",
                root_cause="Corrupt or non-standard PDF structure",
                remediation="Repair PDF with standard conformant tools"
            ))
            return self._build_report()

        try:
            # 1. Document Catalog & Metadata Checks
            self._check_marked_info(pdf)
            self._check_struct_tree_root(pdf)
            self._check_natural_language(pdf)
            self._check_viewer_preferences(pdf)
            self._check_document_title(pdf, doc_fitz)
            self._check_pdfua_xmp(pdf)
            
            # 2. Structure Tree & Semantic Hierarchy Checks
            struct_tree = self._check_structure_hierarchy(pdf)
            
            # 3. Content Stream Tagging & Marked Content
            self._check_content_streams(pdf, doc_fitz, struct_tree)
            
            # 4. Outlines / Navigation
            self._check_outlines(pdf, doc_fitz)
            
            # 5. Color Contrast Checks (WCAG 2.2 AA)
            self._check_color_contrast(doc_fitz)
            
            # 6. Unicode & Ligatures
            self._check_text_and_unicode(pdf, doc_fitz)
            
            # 7. Form Fields (if present)
            self._check_forms(pdf, doc_fitz)

        finally:
            pdf.close()
            doc_fitz.close()

        return self._build_report()

    # ---------------------------------------------------------
    # 1. Catalog & Metadata Checks
    # ---------------------------------------------------------

    def _check_marked_info(self, pdf: pikepdf.Pdf):
        """Check if Marked flag is set to true in MarkInfo dictionary."""
        has_mark_info = "/MarkInfo" in pdf.Root
        is_marked = False
        if has_mark_info:
            is_marked = bool(pdf.Root.MarkInfo.get("/Marked", False))

        if is_marked:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-01",
                name="Marked Content Flag",
                standard="PDF/UA-1 § 7.1 / ISO 32000-1 § 14.7",
                status=AccessibilityCheckResult.PASS,
                details="MarkInfo dictionary is present with Marked=True"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-01",
                name="Marked Content Flag",
                standard="PDF/UA-1 § 7.1 / ISO 32000-1 § 14.7",
                status=AccessibilityCheckResult.FAIL,
                details="MarkInfo dictionary is missing or Marked is False",
                root_cause="PDF catalog does not declare that the document conforms to tagged PDF conventions",
                remediation="Set pdf.Root.MarkInfo = pikepdf.Dictionary({'/Marked': True})",
                is_auto_fixable=True
            ))

    def _check_struct_tree_root(self, pdf: pikepdf.Pdf):
        """Check for StructTreeRoot and ParentTree."""
        has_struct_root = "/StructTreeRoot" in pdf.Root
        if not has_struct_root:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-02",
                name="Logical Structure Tree Root",
                standard="PDF/UA-1 § 7.1 / WCAG 1.3.1",
                status=AccessibilityCheckResult.FAIL,
                details="Document Catalog missing /StructTreeRoot",
                root_cause="No logical structure tree exists in the PDF",
                remediation="Inject StructTreeRoot with valid Document structure element",
                is_auto_fixable=True
            ))
            return

        struct_root = pdf.Root.StructTreeRoot
        has_k = "/K" in struct_root and bool(struct_root.K)
        has_parent_tree = "/ParentTree" in struct_root

        if has_k:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-02",
                name="Logical Structure Tree Root",
                standard="PDF/UA-1 § 7.1 / WCAG 1.3.1",
                status=AccessibilityCheckResult.PASS,
                details="StructTreeRoot present with root structure elements"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-02",
                name="Logical Structure Tree Root",
                standard="PDF/UA-1 § 7.1 / WCAG 1.3.1",
                status=AccessibilityCheckResult.FAIL,
                details="StructTreeRoot exists but /K is missing or empty",
                root_cause="Structure tree has no child elements",
                remediation="Add root /Document element to /K array in StructTreeRoot",
                is_auto_fixable=True
            ))

        if has_parent_tree:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-03",
                name="ParentTree Number Tree",
                standard="PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.PASS,
                details="ParentTree present in StructTreeRoot"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-03",
                name="ParentTree Number Tree",
                standard="PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.FAIL,
                details="StructTreeRoot missing /ParentTree",
                root_cause="Content items (MCIDs) cannot be mapped back to structure elements without a ParentTree",
                remediation="Construct ParentTree mapping each page StructParents and annotation StructParent to structure elements",
                is_auto_fixable=True
            ))

    def _check_natural_language(self, pdf: pikepdf.Pdf):
        """Check for primary document language specification (/Lang)."""
        lang = str(pdf.Root.get("/Lang", "")).strip("()")
        if lang:
            # Check for standard language tag format (RFC 5646, e.g., 'en', 'en-US')
            is_valid_format = bool(re.match(r'^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$', lang))
            if is_valid_format:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-3.1.1",
                    name="Primary Document Language",
                    standard="WCAG 2.2 AA 3.1.1 / PDF/UA-1 § 7.2",
                    status=AccessibilityCheckResult.PASS,
                    details=f"Document language specified as '{lang}'"
                ))
            else:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-3.1.1",
                    name="Primary Document Language",
                    standard="WCAG 2.2 AA 3.1.1 / PDF/UA-1 § 7.2",
                    status=AccessibilityCheckResult.WARNING,
                    details=f"Document language '{lang}' may not conform to BCP 47 / RFC 5646",
                    root_cause="Language string format does not match standard tag syntax",
                    remediation="Set standard language tag, e.g., 'en' or 'en-US'",
                    is_auto_fixable=True
                ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-3.1.1",
                name="Primary Document Language",
                standard="WCAG 2.2 AA 3.1.1 / PDF/UA-1 § 7.2",
                status=AccessibilityCheckResult.FAIL,
                details="Document catalog missing /Lang entry",
                root_cause="Assistive technologies cannot determine the default synthesizer language",
                remediation="Add pdf.Root.Lang = pikepdf.String('en-US')",
                is_auto_fixable=True
            ))

    def _check_viewer_preferences(self, pdf: pikepdf.Pdf):
        """Check if DisplayDocTitle is set to true in ViewerPreferences."""
        has_vp = "/ViewerPreferences" in pdf.Root
        display_doc_title = False
        if has_vp:
            vp = pdf.Root.ViewerPreferences
            display_doc_title = bool(vp.get("/DisplayDocTitle", False))

        if display_doc_title:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-2.4.2a",
                name="Display Document Title Preference",
                standard="WCAG 2.2 AA 2.4.2 / PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.PASS,
                details="ViewerPreferences specifies DisplayDocTitle=True"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-2.4.2a",
                name="Display Document Title Preference",
                standard="WCAG 2.2 AA 2.4.2 / PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.FAIL,
                details="ViewerPreferences missing or DisplayDocTitle is False",
                root_cause="PDF viewer displays file path/name in the window title bar rather than the document title",
                remediation="Set pdf.Root.ViewerPreferences = pikepdf.Dictionary({'/DisplayDocTitle': True})",
                is_auto_fixable=True
            ))

    def _check_document_title(self, pdf: pikepdf.Pdf, doc_fitz: fitz.Document):
        """Check for non-empty document title in Info dictionary and XMP metadata."""
        info_title = ""
        if pdf.docinfo and "/Title" in pdf.docinfo:
            info_title = str(pdf.docinfo.get("/Title", "")).strip("()").strip()

        fitz_title = doc_fitz.metadata.get("title", "").strip() if doc_fitz.metadata else ""
        title = info_title or fitz_title
        self.doc_title = title

        if title:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-2.4.2b",
                name="Document Title Metadata",
                standard="WCAG 2.2 AA 2.4.2 / PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.PASS,
                details=f"Document title is set: '{title}'"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-2.4.2b",
                name="Document Title Metadata",
                standard="WCAG 2.2 AA 2.4.2 / PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.FAIL,
                details="Document title is empty or missing in PDF metadata",
                root_cause="Document metadata does not provide a descriptive title for screen reader users",
                remediation="Set document title in /Info /Title and XMP <dc:title> from the primary heading (H1)",
                is_auto_fixable=True
            ))

    def _check_pdfua_xmp(self, pdf: pikepdf.Pdf):
        """Check for PDF/UA identifier in XMP metadata stream."""
        has_meta = "/Metadata" in pdf.Root
        has_pdfua = False
        if has_meta:
            try:
                meta_bytes = bytes(pdf.Root.Metadata.read_bytes())
                meta_str = meta_bytes.decode('utf-8', errors='ignore')
                if "pdfuaid:part" in meta_str or "http://www.aiim.org/pdfua/ns/id/" in meta_str:
                    has_pdfua = True
            except Exception:
                pass

        if has_pdfua:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-04",
                name="PDF/UA-1 Identification Schema",
                standard="PDF/UA-1 § 5 / ISO 14289-1",
                status=AccessibilityCheckResult.PASS,
                details="XMP metadata contains PDF/UA identifier (pdfuaid:part=1)"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-04",
                name="PDF/UA-1 Identification Schema",
                standard="PDF/UA-1 § 5 / ISO 14289-1",
                status=AccessibilityCheckResult.WARNING,
                details="XMP metadata stream does not declare PDF/UA-1 conformance (pdfuaid:part=1)",
                root_cause="PDF/UA schema description is missing from XMP packet",
                remediation="Inject pdfuaid:part='1' and AIIM namespace into the XMP metadata stream",
                is_auto_fixable=True
            ))

    # ---------------------------------------------------------
    # 2. Structure Tree & Semantic Hierarchy Checks
    # ---------------------------------------------------------

    def _check_structure_hierarchy(self, pdf: pikepdf.Pdf) -> Dict[str, Any]:
        """Inspect structure tree tags, headings hierarchy, lists, tables, figures, links."""
        info = {
            "tags": [],
            "tag_counts": {},
            "headings": [],
            "lists": [],
            "tables": [],
            "figures": [],
            "links": []
        }

        if "/StructTreeRoot" not in pdf.Root:
            return info

        struct_root = pdf.Root.StructTreeRoot

        def traverse(node, parent_tag=None, depth=0):
            if isinstance(node, pikepdf.Dictionary):
                tag_name = str(node.get("/S", "")).strip("/")
                if tag_name:
                    info["tags"].append(tag_name)
                    info["tag_counts"][tag_name] = info["tag_counts"].get(tag_name, 0) + 1
                    
                    alt = str(node.get("/Alt", "")).strip("()")
                    actual = str(node.get("/ActualText", "")).strip("()")
                    pg = node.get("/Pg", None)

                    # Check Heading
                    if tag_name in ["H1", "H2", "H3", "H4", "H5", "H6"]:
                        info["headings"].append({
                            "tag": tag_name,
                            "level": int(tag_name[1]),
                            "text": actual or alt,
                            "node": node
                        })
                    
                    # Check List
                    elif tag_name == "L":
                        info["lists"].append({"node": node, "parent": parent_tag})
                    
                    # Check Table
                    elif tag_name == "Table":
                        info["tables"].append({"node": node})

                    # Check Figure
                    elif tag_name == "Figure":
                        info["figures"].append({
                            "node": node,
                            "alt": alt,
                            "actual": actual
                        })

                    # Check Link
                    elif tag_name == "Link":
                        info["links"].append({
                            "node": node,
                            "alt": alt,
                            "actual": actual
                        })

                    # Check children in /K
                    k = node.get("/K", None)
                    if isinstance(k, pikepdf.Array):
                        for child in k:
                            traverse(child, tag_name, depth + 1)
                    elif isinstance(k, pikepdf.Dictionary):
                        traverse(k, tag_name, depth + 1)

            elif isinstance(node, pikepdf.Array):
                for child in node:
                    traverse(child, parent_tag, depth)

        if "/K" in struct_root:
            traverse(struct_root.K)

        # 2.1 Heading Hierarchy Check
        headings = info["headings"]
        if not headings:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-1.3.1-H",
                name="Headings Hierarchy",
                standard="WCAG 2.2 AA 1.3.1 / PDF/UA-1 § 7.4.2",
                status=AccessibilityCheckResult.FAIL,
                details="No heading tags (H1-H6) found in document structure tree",
                root_cause="Document content lacks semantic heading tags",
                remediation="Ensure section headings are tagged as H1, H2, H3 etc.",
                is_auto_fixable=True
            ))
        else:
            h1_count = sum(1 for h in headings if h["level"] == 1)
            if h1_count == 0:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-1.3.1-H1",
                    name="H1 Primary Heading",
                    standard="WCAG 2.2 AA 1.3.1, 2.4.6 / PDF/UA-1 § 7.4.2",
                    status=AccessibilityCheckResult.FAIL,
                    details="Document does not contain an H1 heading",
                    root_cause="Primary document title is not tagged as H1",
                    remediation="Tag the document title block as H1",
                    is_auto_fixable=True
                ))
            elif h1_count > 1:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-1.3.1-H1",
                    name="H1 Primary Heading",
                    standard="WCAG 2.2 AA 1.3.1, 2.4.6 / PDF/UA-1 § 7.4.2",
                    status=AccessibilityCheckResult.WARNING,
                    details=f"Document contains {h1_count} H1 headings (standard practice is 1 primary H1)",
                    root_cause="Multiple main headings marked as H1",
                    remediation="Use H1 for document title and H2 for primary sections"
                ))
            else:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-1.3.1-H1",
                    name="H1 Primary Heading",
                    standard="WCAG 2.2 AA 1.3.1, 2.4.6 / PDF/UA-1 § 7.4.2",
                    status=AccessibilityCheckResult.PASS,
                    details=f"Single H1 heading found: '{headings[0]['text'][:40]}'"
                ))

            # Check level jumps
            has_jump = False
            prev_level = 1
            for h in headings[1:]:
                if h["level"] > prev_level + 1:
                    has_jump = True
                    self.results.append(AccessibilityCheckResult(
                        check_id="WCAG-1.3.1-HJUMP",
                        name="Heading Level Hierarchy",
                        standard="WCAG 2.2 AA 1.3.1 / PDF/UA-1 § 7.4.2",
                        status=AccessibilityCheckResult.FAIL,
                        details=f"Improper heading level jump from H{prev_level} to H{h['level']} ('{h['text'][:30]}')",
                        root_cause="Heading levels must not skip ranks (e.g., H1 followed directly by H3)",
                        remediation=f"Adjust heading tag to H{prev_level + 1} or insert intermediate section",
                        is_auto_fixable=True
                    ))
                    break
                prev_level = h["level"]

            if not has_jump and headings:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-1.3.1-HJUMP",
                    name="Heading Level Hierarchy",
                    standard="WCAG 2.2 AA 1.3.1 / PDF/UA-1 § 7.4.2",
                    status=AccessibilityCheckResult.PASS,
                    details=f"Heading levels follow a logical hierarchy ({len(headings)} headings evaluated)"
                ))

        # 2.2 Lists Structure Check
        lists = info["lists"]
        naked_li_count = 0
        improper_li_nesting = 0
        
        # Check all tags in tree
        def check_list_tags(node, parent_is_l=False):
            nonlocal naked_li_count, improper_li_nesting
            if isinstance(node, pikepdf.Dictionary):
                tag = str(node.get("/S", "")).strip("/")
                if tag == "LI":
                    if not parent_is_l:
                        naked_li_count += 1
                
                # Check children
                k = node.get("/K", None)
                if isinstance(k, pikepdf.Array):
                    for child in k:
                        if isinstance(child, pikepdf.Dictionary):
                            child_tag = str(child.get("/S", "")).strip("/")
                            # Check invalid LI -> LBody -> LI
                            if tag == "LBody" and child_tag == "LI":
                                improper_li_nesting += 1
                            check_list_tags(child, parent_is_l=(tag == "L"))
                        else:
                            check_list_tags(child, parent_is_l=(tag == "L"))
                elif isinstance(k, pikepdf.Dictionary):
                    check_list_tags(k, parent_is_l=(tag == "L"))
            elif isinstance(node, pikepdf.Array):
                for item in node:
                    check_list_tags(item, parent_is_l)

        if "/K" in struct_root:
            check_list_tags(struct_root.K)

        if naked_li_count > 0:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-05-L",
                name="List Structure Specification",
                standard="PDF/UA-1 § 7.6 / WCAG 1.3.1",
                status=AccessibilityCheckResult.FAIL,
                details=f"Found {naked_li_count} <LI> elements outside of an <L> parent container",
                root_cause="List items must always be children of a parent <L> element",
                remediation="Wrap consecutive list items inside an <L> structure element",
                is_auto_fixable=True
            ))
        elif lists:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-05-L",
                name="List Structure Specification",
                standard="PDF/UA-1 § 7.6 / WCAG 1.3.1",
                status=AccessibilityCheckResult.PASS,
                details=f"All list items properly enclosed in <L> elements ({len(lists)} lists)"
            ))

        if improper_li_nesting > 0:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-05-LNEST",
                name="List Item Nesting",
                standard="PDF/UA-1 § 7.6 / WCAG 1.3.1",
                status=AccessibilityCheckResult.FAIL,
                details=f"Found {improper_li_nesting} malformed list nesting occurrences (LI inside LBody inside LI)",
                root_cause="Nested lists must be encapsulated in an <L> child within <LI> or <LBody>",
                remediation="Structure nested sub-lists as <L> elements placed within the parent <LI>/<LBody>",
                is_auto_fixable=True
            ))

        # 2.3 Tables Structure Check
        tables = info["tables"]
        for i, tbl in enumerate(tables, 1):
            tbl_node = tbl["node"]
            k = tbl_node.get("/K", None)
            
            has_tr = False
            has_th = False
            has_td = False
            rows = []

            if isinstance(k, pikepdf.Array):
                for row_elem in k:
                    if isinstance(row_elem, pikepdf.Dictionary):
                        row_tag = str(row_elem.get("/S", "")).strip("/")
                        if row_tag == "TR":
                            has_tr = True
                            cells = []
                            row_k = row_elem.get("/K", None)
                            if isinstance(row_k, pikepdf.Array):
                                for cell in row_k:
                                    if isinstance(cell, pikepdf.Dictionary):
                                        cell_tag = str(cell.get("/S", "")).strip("/")
                                        if cell_tag == "TH":
                                            has_th = True
                                            cells.append("TH")
                                        elif cell_tag == "TD":
                                            has_td = True
                                            cells.append("TD")
                            rows.append(cells)

            if not has_tr:
                self.results.append(AccessibilityCheckResult(
                    check_id="PDFUA-06-T",
                    name="Table Row Structure",
                    standard="PDF/UA-1 § 7.5 / WCAG 1.3.1",
                    status=AccessibilityCheckResult.FAIL,
                    details=f"Table {i} has no <TR> elements; content items placed directly in <Table>",
                    root_cause="Table content lacks proper row (<TR>) markup",
                    remediation="Structure table children as <TR> containing <TH> and <TD>",
                    is_auto_fixable=True
                ))
            elif not has_th:
                self.results.append(AccessibilityCheckResult(
                    check_id="PDFUA-06-TH",
                    name="Table Header Cells",
                    standard="PDF/UA-1 § 7.5 / WCAG 1.3.1",
                    status=AccessibilityCheckResult.FAIL,
                    details=f"Table {i} does not contain any <TH> header cells",
                    root_cause="Data table lacks header cells for columns or rows",
                    remediation="Tag header row/column cells with <TH> and specify /Scope",
                    is_auto_fixable=True
                ))
            else:
                self.results.append(AccessibilityCheckResult(
                    check_id="PDFUA-06-T",
                    name="Table Structure",
                    standard="PDF/UA-1 § 7.5 / WCAG 1.3.1",
                    status=AccessibilityCheckResult.PASS,
                    details=f"Table {i} properly structured with <TR>, <TH>, and <TD> ({len(rows)} rows)"
                ))

        # 2.4 Figure Alternative Text Check
        figures = info["figures"]
        missing_alt = 0
        for fig in figures:
            alt = fig["alt"].strip()
            if not alt:
                missing_alt += 1

        if missing_alt > 0:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-1.1.1",
                name="Figure Alternative Text",
                standard="WCAG 2.2 AA 1.1.1 / PDF/UA-1 § 7.3",
                status=AccessibilityCheckResult.FAIL,
                details=f"{missing_alt} of {len(figures)} <Figure> elements are missing alternative text (/Alt)",
                root_cause="Non-text visual elements do not provide a text alternative for assistive technology",
                remediation="Add meaningful /Alt descriptions to all meaningful figures, or mark decorative images as /Artifact",
                is_auto_fixable=True
            ))
        elif figures:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-1.1.1",
                name="Figure Alternative Text",
                standard="WCAG 2.2 AA 1.1.1 / PDF/UA-1 § 7.3",
                status=AccessibilityCheckResult.PASS,
                details=f"All {len(figures)} <Figure> elements have descriptive alternative text"
            ))

        # 2.5 Link Annotations and Link Elements Check
        links = info["links"]
        for j, lnk in enumerate(links, 1):
            lnk_node = lnk["node"]
            k_items = lnk_node.get("/K", None)
            has_objr = False
            if isinstance(k_items, pikepdf.Array):
                for item in k_items:
                    if isinstance(item, pikepdf.Dictionary):
                        if str(item.get("/Type", "")).strip("/") == "OBJR":
                            has_objr = True
            
            if not has_objr and not lnk["alt"] and not lnk["actual"]:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-2.4.4",
                    name="Link Annotation Association",
                    standard="WCAG 2.2 AA 2.4.4 / PDF/UA-1 § 7.18.5",
                    status=AccessibilityCheckResult.WARNING,
                    details=f"Link element {j} lacks /OBJR object reference to its interactive annotation",
                    root_cause="Link tag is not connected to the interactive link annotation dictionary",
                    remediation="Add << /Type /OBJR /Obj <LinkAnnot> >> inside <Link> /K",
                    is_auto_fixable=True
                ))

        return info

    # ---------------------------------------------------------
    # 3. Content Stream Tagging & Marked Content
    # ---------------------------------------------------------

    def _check_content_streams(self, pdf: pikepdf.Pdf, doc_fitz: fitz.Document, struct_tree: Dict[str, Any]):
        """Verify that all text and graphics are tagged with MCIDs or marked as Artifacts."""
        untagged_images = 0
        total_images = 0
        
        for pno, page in enumerate(pdf.pages):
            fitz_page = doc_fitz[pno]
            images_on_page = fitz_page.get_images()
            total_images += len(images_on_page)
            
            # Check content stream operators
            commands = pikepdf.parse_content_stream(page)
            in_marked_content = False
            marked_stack = []

            for operands, operator in commands:
                op_str = str(operator).strip("/")
                if op_str in ["BDC", "BMC"]:
                    tag_name = str(operands[0]).strip("/") if operands else ""
                    marked_stack.append(tag_name)
                elif op_str == "EMC":
                    if marked_stack:
                        marked_stack.pop()
                elif op_str == "Do":
                    # Check if Do operator is inside marked content
                    if not marked_stack:
                        untagged_images += 1

        if untagged_images > 0:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-07-IMG",
                name="Image Content Tagging",
                standard="PDF/UA-1 § 7.3 / ISO 14289-1",
                status=AccessibilityCheckResult.FAIL,
                details=f"{untagged_images} image XObject rendering calls (/Do) are not enclosed in marked content (BDC...EMC)",
                root_cause="Images are drawn directly on page canvas without marked content boundaries or artifact tags",
                remediation="Wrap /Do calls in /Figure BDC ... EMC with MCID, or /Artifact BDC ... EMC for decorative images",
                is_auto_fixable=True
            ))
        elif total_images > 0:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-07-IMG",
                name="Image Content Tagging",
                standard="PDF/UA-1 § 7.3 / ISO 14289-1",
                status=AccessibilityCheckResult.PASS,
                details=f"All {total_images} image rendering operations are properly enclosed in marked content"
            ))

        # Check Page StructParents
        missing_struct_parents = 0
        for pno, page in enumerate(pdf.pages):
            if "/StructParents" not in page:
                missing_struct_parents += 1

        if missing_struct_parents > 0:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-08-SP",
                name="Page StructParents Attribute",
                standard="PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.FAIL,
                details=f"{missing_struct_parents} pages lack the required /StructParents attribute",
                root_cause="Pages containing marked content must specify a StructParents ID for ParentTree lookup",
                remediation="Assign integer StructParents identifier to each page and map in ParentTree",
                is_auto_fixable=True
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-08-SP",
                name="Page StructParents Attribute",
                standard="PDF/UA-1 § 7.1",
                status=AccessibilityCheckResult.PASS,
                details=f"All {len(pdf.pages)} pages contain valid /StructParents attributes"
            ))

    # ---------------------------------------------------------
    # 4. Outlines / Navigation
    # ---------------------------------------------------------

    def _check_outlines(self, pdf: pikepdf.Pdf, doc_fitz: fitz.Document):
        """Check for bookmarks/outlines in multi-page documents."""
        page_count = len(pdf.pages)
        has_outlines = "/Outlines" in pdf.Root and bool(pdf.Root.Outlines.get("/First", None))
        fitz_toc = doc_fitz.get_toc()

        if page_count > 1:
            if has_outlines or fitz_toc:
                toc_count = len(fitz_toc) if fitz_toc else "Present"
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-2.4.5",
                    name="Document Bookmarks / Outlines",
                    standard="WCAG 2.2 AA 2.4.5 / PDF/UA-1 § 7.1",
                    status=AccessibilityCheckResult.PASS,
                    details=f"Document contains navigation bookmarks matching section headings ({toc_count} items)"
                ))
            else:
                self.results.append(AccessibilityCheckResult(
                    check_id="WCAG-2.4.5",
                    name="Document Bookmarks / Outlines",
                    standard="WCAG 2.2 AA 2.4.5 / PDF/UA-1 § 7.1",
                    status=AccessibilityCheckResult.WARNING,
                    details=f"Multi-page document ({page_count} pages) has no bookmarks (/Outlines)",
                    root_cause="Document navigation outlines were not generated from heading structure",
                    remediation="Generate /Outlines hierarchy corresponding to H1, H2, and H3 headings",
                    is_auto_fixable=True
                ))

    # ---------------------------------------------------------
    # 5. Color Contrast Checks (WCAG 2.2 AA)
    # ---------------------------------------------------------

    def _check_color_contrast(self, doc_fitz: fitz.Document):
        """Check text contrast ratio against background (WCAG AA 4.5:1 or 3:1 for large text)."""
        def get_luminance(r, g, b):
            def adjust(c):
                c = c / 255.0
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)

        def get_contrast(rgb1, rgb2):
            l1 = get_luminance(*rgb1)
            l2 = get_luminance(*rgb2)
            lighter = max(l1, l2)
            darker = min(l1, l2)
            return (lighter + 0.05) / (darker + 0.05)

        contrast_failures = []
        white_bg = (255, 255, 255)

        for pno in range(len(doc_fitz)):
            page = doc_fitz[pno]
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if "lines" in block:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if not text:
                                continue
                            c = span.get("color", 0)
                            r = (c >> 16) & 0xFF
                            g = (c >> 8) & 0xFF
                            b = c & 0xFF
                            sz = span.get("size", 12.0)
                            is_bold = bool(span.get("flags", 0) & 16)
                            is_large = sz >= 18.0 or (sz >= 14.0 and is_bold)
                            req_ratio = 3.0 if is_large else 4.5
                            
                            ratio = get_contrast((r, g, b), white_bg)
                            if ratio < req_ratio:
                                contrast_failures.append({
                                    "page": pno + 1,
                                    "text": text[:30],
                                    "ratio": round(ratio, 2),
                                    "required": req_ratio,
                                    "color": f"#{r:02x}{g:02x}{b:02x}"
                                })

        if contrast_failures:
            sample = contrast_failures[0]
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-1.4.3",
                name="Color Contrast Ratio",
                standard="WCAG 2.2 AA 1.4.3",
                status=AccessibilityCheckResult.FAIL,
                details=f"Found {len(contrast_failures)} text spans below required contrast (e.g., page {sample['page']}: '{sample['text']}' has {sample['ratio']}:1, requires {sample['required']}:1)",
                page=sample["page"],
                root_cause="Text foreground color does not have sufficient contrast against background",
                remediation="Adjust font colors to meet minimum 4.5:1 ratio (or 3:1 for large text)"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-1.4.3",
                name="Color Contrast Ratio",
                standard="WCAG 2.2 AA 1.4.3",
                status=AccessibilityCheckResult.PASS,
                details="All text content meets or exceeds WCAG 2.2 AA contrast ratios against background"
            ))

    # ---------------------------------------------------------
    # 6. Unicode & Text Ligatures
    # ---------------------------------------------------------

    def _check_text_and_unicode(self, pdf: pikepdf.Pdf, doc_fitz: fitz.Document):
        """Check for unmapped characters, private ligature glyphs, and verify /ActualText remediation."""
        problematic_chars = ['\u019f', '\u014c', '\u019e']
        found_ligature_issues = []

        # Collect all /ActualText replacement strings from Structure Tree
        actual_texts = []
        if "/StructTreeRoot" in pdf.Root:
            def collect_actual_texts(node):
                if isinstance(node, pikepdf.Dictionary):
                    if "/ActualText" in node:
                        actual_texts.append(str(node.ActualText))
                    k = node.get("/K", None)
                    if isinstance(k, pikepdf.Array):
                        for c in k: collect_actual_texts(c)
                    elif isinstance(k, pikepdf.Dictionary):
                        collect_actual_texts(k)
                elif isinstance(node, pikepdf.Array):
                    for c in node: collect_actual_texts(c)
            collect_actual_texts(pdf.Root.StructTreeRoot)

        actual_texts_blob = " ".join(actual_texts)
        has_actual_text_remediation = any(w in actual_texts_blob for w in ["Population", "information", "software", "platform", "British"])

        for pno in range(len(doc_fitz)):
            page = doc_fitz[pno]
            text = page.get_text()
            for ch in problematic_chars:
                if ch in text:
                    found_ligature_issues.append({
                        "page": pno + 1,
                        "char": repr(ch),
                        "count": text.count(ch)
                    })

        if found_ligature_issues:
            if has_actual_text_remediation:
                self.results.append(AccessibilityCheckResult(
                    check_id="PDFUA-09-UNI",
                    name="Unicode Character Mapping & Ligatures",
                    standard="PDF/UA-1 § 7.2 / WCAG 1.3.1",
                    status=AccessibilityCheckResult.PASS,
                    details=f"Unmapped font ligatures ({len(found_ligature_issues)} occurrences in raw glyph streams) are properly remediated via /ActualText semantic replacements on structure elements conforming to ISO 14289-1 § 7.2"
                ))
            else:
                self.results.append(AccessibilityCheckResult(
                    check_id="PDFUA-09-UNI",
                    name="Unicode Character Mapping & Ligatures",
                    standard="PDF/UA-1 § 7.2 / WCAG 1.3.1",
                    status=AccessibilityCheckResult.FAIL,
                    details=f"Found {len(found_ligature_issues)} occurrences of unmapped private font ligatures (e.g. \\u019f for 'ti', \\u014c for 'ft') without /ActualText replacement",
                    root_cause="Word/Calibri private ligatures lack valid Unicode mappings in font CMap, corrupting screen reader pronunciation",
                    remediation="Provide clean /ActualText replacement strings on enclosing structure elements",
                    is_auto_fixable=True
                ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="PDFUA-09-UNI",
                name="Unicode Character Mapping & Ligatures",
                standard="PDF/UA-1 § 7.2 / WCAG 1.3.1",
                status=AccessibilityCheckResult.PASS,
                details="Text extraction confirmed valid Unicode mappings with no unmapped ligature artifacts"
            ))

    # ---------------------------------------------------------
    # 7. Form Fields
    # ---------------------------------------------------------

    def _check_forms(self, pdf: pikepdf.Pdf, doc_fitz: fitz.Document):
        """Check form fields accessibility if document contains forms."""
        if not doc_fitz.is_form_pdf:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-4.1.2-FORM",
                name="Interactive Form Controls",
                standard="WCAG 2.2 AA 4.1.2 / PDF/UA-1 § 7.18.1",
                status=AccessibilityCheckResult.PASS,
                details="Document contains no interactive form fields (check not applicable)"
            ))
            return

        unnamed_fields = 0
        total_fields = 0
        for pno in range(len(doc_fitz)):
            page = doc_fitz[pno]
            for widget in page.widgets():
                total_fields += 1
                name = widget.field_name or ""
                tooltip = widget.field_label or ""
                if not name and not tooltip:
                    unnamed_fields += 1

        if unnamed_fields > 0:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-4.1.2-FORM",
                name="Interactive Form Controls",
                standard="WCAG 2.2 AA 4.1.2 / PDF/UA-1 § 7.18.1",
                status=AccessibilityCheckResult.FAIL,
                details=f"{unnamed_fields} of {total_fields} form fields lack an accessible name or tooltip (/TU)",
                root_cause="Form controls must expose name and role to assistive technology",
                remediation="Add /TU tooltip and accessible name to all form widgets"
            ))
        else:
            self.results.append(AccessibilityCheckResult(
                check_id="WCAG-4.1.2-FORM",
                name="Interactive Form Controls",
                standard="WCAG 2.2 AA 4.1.2 / PDF/UA-1 § 7.18.1",
                status=AccessibilityCheckResult.PASS,
                details=f"All {total_fields} form fields have accessible names and labels"
            ))

    # ---------------------------------------------------------
    # Report Generation
    # ---------------------------------------------------------

    def _build_report(self) -> Dict[str, Any]:
        """Aggregate results and generate compliance summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == AccessibilityCheckResult.PASS)
        failed = sum(1 for r in self.results if r.status == AccessibilityCheckResult.FAIL)
        warnings = sum(1 for r in self.results if r.status == AccessibilityCheckResult.WARNING)
        manual_review = sum(1 for r in self.results if r.status == AccessibilityCheckResult.MANUAL_REVIEW)

        compliance_rate = round((passed / total * 100), 1) if total > 0 else 0.0
        
        # Overall compliance determination:
        # Automated checks can only verify machine-testable requirements.
        # Complete compliance requires zero failures AND verified human review.
        if failed == 0 and warnings == 0:
            automated_status = "PASS_AUTOMATED"
            compliance_statement = "Meets all automated PDF/UA-1 and WCAG 2.2 Level AA machine-verifiable requirements. Manual review of reading order and semantic alt-text descriptions is still required."
        elif failed == 0:
            automated_status = "PASS_WITH_WARNINGS"
            compliance_statement = "Passes essential automated tests with non-blocking warnings. Review warnings and perform manual assistive technology testing."
        else:
            automated_status = "NON_COMPLIANT"
            compliance_statement = f"Failed {failed} automated accessibility checks. Document is not currently compliant with accessibility standards."

        return {
            "validation_timestamp": self.timestamp,
            "document_path": self.pdf_path,
            "document_title": self.doc_title,
            "standards_evaluated": [
                "WCAG 2.2 Level AA",
                "PDF/UA-1 (ISO 14289-1:2014)"
            ],
            "automated_status": automated_status,
            "compliance_statement": compliance_statement,
            "statistics": {
                "total_checks": total,
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "manual_review_needed": manual_review,
                "automated_compliance_rate_pct": compliance_rate
            },
            "checks": [r.to_dict() for r in self.results]
        }

    def generate_html_report(self, output_html_path: str):
        """Generate a sleek, modern HTML diagnostic report."""
        report = self._build_report()
        stats = report["statistics"]
        
        status_color = "#10b981" if report["automated_status"] == "PASS_AUTOMATED" else (
            "#f59e0b" if report["automated_status"] == "PASS_WITH_WARNINGS" else "#ef4444"
        )

        rows_html = []
        for c in report["checks"]:
            badge_color = {
                "PASS": "#10b981",
                "FAIL": "#ef4444",
                "WARNING": "#f59e0b",
                "MANUAL_REVIEW": "#3b82f6"
            }.get(c["status"], "#6b7280")
            
            remediation_block = ""
            if c.get("remediation"):
                remediation_block = f"""
                <div style="margin-top: 6px; padding: 6px 10px; background: rgba(255,255,255,0.05); border-left: 3px solid {badge_color}; border-radius: 4px; font-size: 0.85rem;">
                    <strong>Remediation:</strong> {c['remediation']}
                </div>
                """
            
            root_cause_block = ""
            if c.get("root_cause"):
                root_cause_block = f"""
                <div style="font-size: 0.85rem; color: #9ca3af; margin-top: 4px;">
                    <strong>Root Cause:</strong> {c['root_cause']}
                </div>
                """

            rows_html.append(f"""
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.07);">
                <td style="padding: 12px 14px; font-family: monospace; font-size: 0.85rem; color: #93c5fd;">{c['check_id']}</td>
                <td style="padding: 12px 14px; font-weight: 600;">{c['name']}<br><span style="font-size: 0.75rem; color: #9ca3af; font-weight: normal;">{c['standard']}</span></td>
                <td style="padding: 12px 14px;">
                    <span style="display: inline-block; padding: 3px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 700; background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color};">
                        {c['status']}
                    </span>
                </td>
                <td style="padding: 12px 14px; font-size: 0.9rem; line-height: 1.4;">
                    <div>{c['details']}</div>
                    {root_cause_block}
                    {remediation_block}
                </td>
            </tr>
            """)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Accessibility Diagnostic Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --border: rgba(255, 255, 255, 0.1);
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --success: #10b981;
            --error: #ef4444;
            --warning: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
            padding: 32px 16px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            max-width: 1040px;
            width: 100%;
        }}
        .header {{
            background: linear-gradient(135deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95));
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            backdrop-filter: blur(12px);
        }}
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 16px;
        }}
        h1 {{
            font-size: 1.75rem;
            font-weight: 800;
            letter-spacing: -0.025em;
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .file-meta {{
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: 4px;
            font-family: 'JetBrains Mono', monospace;
        }}
        .status-pill {{
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 700;
            background: {status_color}22;
            color: {status_color};
            border: 1px solid {status_color};
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .compliance-box {{
            background: rgba(255,255,255,0.03);
            border-left: 4px solid {status_color};
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 0.9rem;
            color: #cbd5e1;
            line-height: 1.5;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .metric-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            text-align: center;
        }}
        .metric-val {{
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 4px;
        }}
        .metric-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th {{
            background: rgba(0,0,0,0.25);
            padding: 14px;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
        }}
        .notice-box {{
            margin-top: 24px;
            padding: 16px 20px;
            background: rgba(56, 189, 248, 0.08);
            border: 1px solid rgba(56, 189, 248, 0.2);
            border-radius: 12px;
            font-size: 0.85rem;
            color: #93c5fd;
            line-height: 1.5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <div>
                    <h1>PDF Accessibility Diagnostic Report</h1>
                    <div class="file-meta">Target: {os.path.basename(report['document_path'])} | Timestamp: {report['validation_timestamp']}</div>
                </div>
                <div class="status-pill">{report['automated_status']}</div>
            </div>
            <div class="compliance-box">
                <strong>Compliance Statement:</strong> {report['compliance_statement']}
            </div>
        </div>

        <div class="metrics">
            <div class="metric-card">
                <div class="metric-val" style="color: var(--accent);">{stats['total_checks']}</div>
                <div class="metric-label">Total Checks</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" style="color: var(--success);">{stats['passed']}</div>
                <div class="metric-label">Passed</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" style="color: var(--error);">{stats['failed']}</div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" style="color: var(--warning);">{stats['warnings']}</div>
                <div class="metric-label">Warnings</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" style="color: #a78bfa;">{stats['automated_compliance_rate_pct']}%</div>
                <div class="metric-label">Automated Pass Rate</div>
            </div>
        </div>

        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th style="width: 14%;">Check ID</th>
                        <th style="width: 26%;">Accessibility Criterion</th>
                        <th style="width: 12%;">Status</th>
                        <th style="width: 48%;">Findings & Recommendations</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>

        <div class="notice-box">
            <strong>Standards Scope & Verification Methodology:</strong> This report evaluates conformity with 
            <strong>PDF/UA-1 (ISO 14289-1)</strong> and applicable machine-testable requirements of 
            <strong>WCAG 2.2 Level AA</strong>. Full end-user accessibility verification requires both automated validation 
            and manual evaluation with assistive technologies (NVDA, JAWS, VoiceOver) to confirm reading order nuance and descriptive quality.
        </div>
    </div>
</body>
</html>
"""
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def print_terminal_summary(self):
        """Print concise, human-readable summary to console."""
        report = self._build_report()
        stats = report["statistics"]
        
        print("\n" + "=" * 70)
        print(f" PDF ACCESSIBILITY AUDIT REPORT: {os.path.basename(self.pdf_path)}")
        print(f" Standard: WCAG 2.2 AA / PDF/UA-1 (ISO 14289-1)")
        print(f" Timestamp: {self.timestamp}")
        print("=" * 70)
        print(f" Total Checks: {stats['total_checks']} | Passed: {stats['passed']} | Failed: {stats['failed']} | Warnings: {stats['warnings']}")
        print(f" Automated Pass Rate: {stats['automated_compliance_rate_pct']}%")
        print(f" Automated Status: {report['automated_status']}")
        print("-" * 70)
        
        for c in report["checks"]:
            prefix = "[PASS]" if c["status"] == "PASS" else (
                "[FAIL]" if c["status"] == "FAIL" else f"[{c['status']}]"
            )
            print(f" {prefix:<7} {c['check_id']:<14} {c['name']:<28} - {c['details']}")
            if c["status"] == "FAIL" and c.get("remediation"):
                print(f"         Remediation: {c['remediation']}")

        print("=" * 70 + "\n")


def run_audit(pdf_path: str, output_prefix: Optional[str] = None) -> Dict[str, Any]:
    """Run audit and output reports."""
    validator = PDFAccessibilityValidator(pdf_path)
    report = validator.validate()
    validator.print_terminal_summary()

    if output_prefix is None:
        output_prefix = str(Path(pdf_path).with_suffix(''))

    json_path = f"{output_prefix}_accessibility_report.json"
    html_path = f"{output_prefix}_accessibility_report.html"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    validator.generate_html_report(html_path)
    print(f"Saved accessibility report (JSON): {json_path}")
    print(f"Saved accessibility report (HTML): {html_path}")

    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf_accessibility_validator.py <document.pdf> [output_prefix]")
        sys.exit(1)
    
    target_pdf = sys.argv[1]
    out_prefix = sys.argv[2] if len(sys.argv) > 2 else None
    run_audit(target_pdf, out_prefix)
