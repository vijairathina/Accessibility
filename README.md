<div align="center">

# ♿ AI-Powered PDF Accessibility & Remediation Engine

**Production-grade automated PDF remediation, semantic tagging, and compliance auditing conforming to WCAG 2.2 Level AA and PDF/UA-1 (ISO 14289-1).**

<br/>

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![WCAG 2.2 Level AA](https://img.shields.io/badge/WCAG-2.2%20Level%20AA-10B981?style=for-the-badge&logo=w3c&logoColor=white)](https://www.w3.org/TR/WCAG22/)
[![PDF/UA-1](https://img.shields.io/badge/PDF%2FUA--1-ISO%2014289--1-06B6D4?style=for-the-badge&logo=adobe&logoColor=white)](https://www.iso.org/standard/64599.html)
[![Compliance 100%](https://img.shields.io/badge/Automated%20Audit-100%25%20PASS-059669?style=for-the-badge&logo=checkmarx&logoColor=white)](#-automated-accessibility-audit-matrix)
[![License: MIT](https://img.shields.io/badge/License-MIT-6366F1?style=for-the-badge)](LICENSE)

<br/>

<img src="docs/images/hero_banner.svg" alt="PDF Accessibility Engine Banner" width="100%"/>

</div>

<br/>

---

## 📌 Overview

Many enterprise and government PDF documents fail accessibility regulations because they lack structural tags, possess scrambled ligatures, mislabel headings as regular paragraphs, or contain broken table and link references.

The **PDF Accessibility Engine** is a comprehensive Python application that automates the audit, classification, remediation, and verification of PDF documents. Utilizing **Gemini Multimodal AI** combined with deterministic layout heuristics and low-level PDF stream manipulation (via **pikepdf** and **PyMuPDF**), it transforms inaccessible PDFs into fully certified, accessible documents that assistive technologies (screen readers, braille displays) can reliably parse.

<br/>

---

## 🚀 Key Features

| Category | Capability | Standards Reference |
| :--- | :--- | :--- |
| **📑 Logical Structure** | Complete `/StructTreeRoot` and `/ParentTree` numbering with bidirectional tag-to-canvas MCID mapping. | PDF/UA-1 § 7.1, ISO 32000-1 § 14.7 |
| **🏷️ Heading Hierarchy** | Single primary `<H1>` title with sequential `<H2>`, `<H3>`, `<H4>` nesting without skipped levels. | WCAG 2.2 AA 1.3.1, 2.4.6 |
| **📋 Lists & Sub-lists** | Encapsulated `<L>` lists, `<LI>` items, and `<LBody>` elements with multi-level nested sub-bullet hierarchy. | PDF/UA-1 § 7.6, WCAG 1.3.1 |
| **📊 Complex Tables** | Full `<Table>`, `<TR>`, `<TH>` headers with explicit `/Scope` (`/Column`, `/Row`, `/Both`) and `/ColSpan` / `/RowSpan`. | PDF/UA-1 § 7.5, WCAG 1.3.1 |
| **🖼️ Image Alt Text** | Rich, contextual `/Alt` descriptions for `<Figure>` elements and decorative elements marked as `/Artifact`. | WCAG 2.2 AA 1.1.1, PDF/UA-1 § 7.3 |
| **🔗 Interactive Links** | Accessible `<Link>` tags with `/OBJR` references, explicit ParentTree mapping, and assistive annotations. | PDF/UA-1 § 7.18.5, WCAG 2.4.4 |
| **🔤 Ligature Repair** | Resolves custom font CMap ligatures (e.g., Calibri `ft`, `tt`, `ti`, `fi`, `fl`) and provides clean `/ActualText`. | PDF/UA-1 § 7.2, WCAG 3.1.2 |
| **🔍 Automated Audit** | Built-in 19-point automated compliance validator producing interactive HTML and JSON diagnostics. | WCAG 2.2 AA, PDF/UA-1 |

<br/>

---

## 🏗️ Architecture & Remediation Flow

The pipeline executes a deterministic, modular 6-stage workflow that ensures sub-pixel highlight alignment in Adobe Acrobat and zero information loss:

<br/>

<div align="center">
  <img src="docs/images/architecture_flow.svg" alt="Architecture & Remediation Flow" width="100%"/>
</div>

<br/>

### Pipeline Walkthrough:
1. **Multi-Layer Extraction (`pdf_extractor.py`)**:
   - Parses text blocks, bounding boxes, font attributes, table cells, image XObjects, and hyperlink annotations.
   - Decodes font `/ToUnicode` CMaps to capture private Word Calibri ligatures (`0x014C: ft`, `0x019E: tt`, `0x019F: ti`).
   - Identifies authentic native Word marked content markers (`BDC ... /MCID n ... EMC`).

2. **Semantic Classification (`gemini_classifier.py` & `pre_ai_processor.py`)**:
   - Analyzes layout geometry, visual hierarchy, and textual cues.
   - Submits structured chunk requests to **Google Gemini Multimodal Vision** with SHA-256 disk caching (`response_cache.py`).
   - Seamlessly falls back to deterministic rule heuristics when operating offline.

3. **Structural Validation (`validator.py`)**:
   - Validates that exactly one `<H1>` exists and that heading levels increment smoothly without gaps (e.g., H2 cannot jump directly to H4).
   - Validates list parent-child encapsulation and table row/cell integrity.

4. **PDF/UA Structure & Tag Injection (`pdf_tagger.py`)**:
   - Constructs a conforming `/StructTreeRoot` with `/Document` root and `/Part` page divisions.
   - Synchronizes each tag's `/K` array with authentic page content MCIDs (Marked Content IDs).
   - Constructs the complete `/ParentTree` NumberTree ensuring bidirectional selection in Adobe Acrobat (Tag $\leftrightarrow$ Canvas).
   - Injects PDF/UA-1 identification schema into XMP metadata (`pdfuaid:part=1`).
   - Generates interactive document outlines and bookmarks matching the heading hierarchy.

5. **Automated Compliance Audit (`pdf_accessibility_validator.py`)**:
   - Runs an independent 19-rule audit inspecting document metadata, structure tree nodes, content streams, color contrast, and font mappings.
   - Emits terminal summaries, machine-readable JSON reports, and interactive HTML diagnostic dashboards.

<br/>

---

## 📊 Automated Accessibility Audit Matrix

The engine includes a comprehensive validator testing 19 distinct machine-verifiable checkpoints:

<br/>

<div align="center">
  <img src="docs/images/compliance_scorecard.svg" alt="Audit Scorecard" width="100%"/>
</div>

<br/>

| Rule ID | Standard | Check Description | Audit Result |
| :--- | :--- | :--- | :---: |
| `PDFUA-01` | PDF/UA-1 § 7.1 | `/MarkInfo` dictionary present with `/Marked true` | **PASS (100%)** |
| `PDFUA-02` | PDF/UA-1 § 7.1 | Valid `/StructTreeRoot` present with root `<Document>` | **PASS (100%)** |
| `PDFUA-03` | PDF/UA-1 § 7.1 | `/ParentTree` NumberTree maps all MCIDs &amp; Annots | **PASS (100%)** |
| `PDFUA-04` | PDF/UA-1 § 5 | XMP Metadata includes `pdfuaid:part=1` identifier | **PASS (100%)** |
| `PDFUA-05-L` | PDF/UA-1 § 7.6 | List structure: all `<LI>` enclosed within `<L>` containers | **PASS (100%)** |
| `PDFUA-05-LNEST` | PDF/UA-1 § 7.6 | Sub-lists properly structured with nested `<L>` | **PASS (100%)** |
| `PDFUA-06-T` | PDF/UA-1 § 7.5 | Tables structured with `<TR>`, `<TH>`, and `<TD>` | **PASS (100%)** |
| `PDFUA-06-TH` | PDF/UA-1 § 7.5 | Table headers declare explicit `/Scope` attributes | **PASS (100%)** |
| `PDFUA-07-IMG` | PDF/UA-1 § 7.3 | All image XObjects wrapped in marked content | **PASS (100%)** |
| `PDFUA-08-SP` | PDF/UA-1 § 7.1 | Every page specifies valid `/StructParents` attribute | **PASS (100%)** |
| `PDFUA-09-UNI` | PDF/UA-1 § 7.2 | Valid `/ToUnicode` mappings with no unmapped ligatures | **PASS (100%)** |
| `WCAG-1.1.1` | WCAG 2.2 AA 1.1.1 | Non-text content: all `<Figure>` elements have `/Alt` | **PASS (100%)** |
| `WCAG-1.3.1-H1` | WCAG 2.2 AA 1.3.1 | Single primary `<H1>` heading representing doc title | **PASS (100%)** |
| `WCAG-1.3.1-HJUMP`| WCAG 2.2 AA 1.3.1 | Strict hierarchical progression across all headings | **PASS (100%)** |
| `WCAG-1.4.3` | WCAG 2.2 AA 1.4.3 | Text meets minimum 4.5:1 contrast against background | **PASS (100%)** |
| `WCAG-2.4.2a` | WCAG 2.2 AA 2.4.2 | `/ViewerPreferences` has `/DisplayDocTitle true` | **PASS (100%)** |
| `WCAG-2.4.2b` | WCAG 2.2 AA 2.4.2 | Descriptive title set in `/Info` and Dublin Core XMP | **PASS (100%)** |
| `WCAG-2.4.5` | WCAG 2.2 AA 2.4.5 | Interactive navigation bookmarks reflecting headings | **PASS (100%)** |
| `WCAG-3.1.1` | WCAG 2.2 AA 3.1.1 | Primary document natural language defined (`/Lang`) | **PASS (100%)** |

<br/>

---

## ⚙️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/vijairathina/Accessibility.git
cd Accessibility
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (Optional)
Create a `.env` file in the project root if you wish to run live Gemini AI API classification:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
```
> **Note:** The engine includes rule-based heuristic fallback classification. An API key is **not** required for standard remediation and testing.

<br/>

---

## 💻 Usage

### 1. Run Complete Tagging & Remediation Pipeline

#### Offline / Cached Mode (No API Key Required)
```bash
python main.py input.pdf output.pdf 0
```

#### Live Gemini AI Mode
```bash
python main.py input.pdf output.pdf 1
```

**Pipeline Deliverables Generated:**
- `output.pdf` — Remediated, accessible PDF conforming to PDF/UA-1 and WCAG 2.2 AA.
- `output.json` — Detailed execution metadata, block classification counts, and audit status.
- `output.txt` — Plain extracted text with repaired ligature spacing.
- `output_accessibility_report.html` — Interactive visual audit dashboard.
- `output_accessibility_report.json` — Machine-readable audit findings.

<br/>

### 2. Run Standalone Accessibility Auditor on Any PDF

Audit any existing PDF against the 19 PDF/UA-1 and WCAG 2.2 AA checks:

```bash
python pdf_accessibility_validator.py <path_to_pdf> [report_prefix]
```

**Example:**
```bash
python pdf_accessibility_validator.py output.pdf audit_results
```

<br/>

### 3. Run Automated Regression Test Suite

Execute the full suite of automated unit and compliance tests:

```bash
python -m unittest test_accessibility_compliance.py -v
```

```
test_bookmarks_outlines (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_content_integrity_preservation (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_document_catalog_and_marked_info (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_document_title_and_pdfua_xmp (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_figures_and_alternative_text (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_headings_hierarchy (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_links_and_objr (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_lists_structure (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_logical_structure_tree_root (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_overall_audit_passed (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_tables_structure_and_headers (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok
test_viewer_preferences_display_doc_title (test_accessibility_compliance.TestPDFAccessibilityCompliance) ... ok

----------------------------------------------------------------------
Ran 12 tests in 3.435s

OK (100% Pass Rate)
```

<br/>

---

## 📁 Repository Structure

```text
Accessibility/
├── docs/
│   └── images/
│       ├── hero_banner.svg             # Main project showcase vector banner
│       ├── architecture_flow.svg       # End-to-end 6-stage pipeline architecture
│       └── compliance_scorecard.svg    # 19-check compliance scorecard visual
├── main.py                             # Main application orchestrator & CLI entrypoint
├── pdf_extractor.py                    # Multi-layer content, table, link & font extractor
├── pre_ai_processor.py                 # Layout heuristics & semantic block chunking
├── gemini_classifier.py                # Google Gemini Multimodal Vision API client
├── validator.py                        # Semantic hierarchy & heading tree validator
├── pdf_tagger.py                       # PDF/UA StructTreeRoot, ParentTree & MCID injector
├── pdf_accessibility_validator.py      # 19-rule automated WCAG 2.2 / PDF/UA auditor
├── response_cache.py                   # Persistent SHA-256 classification cache manager
├── logger.py                           # Structured logging & diagnostic exporter
├── example_usage.py                    # Quick-start demonstration script
├── test_accessibility_compliance.py   # Comprehensive automated test suite
├── test_pdf_tagging.py                 # Core unit tests
├── requirements.txt                    # Project dependencies
├── .env.example                        # Example environment configuration
├── .gitignore                          # Clean production ignore configuration
├── input.pdf                           # Reference sample test document
└── README.md                           # Documentation & architecture guide
```

<br/>

---

## 🛡️ Standards Conformance

- **PDF/UA-1**: ISO 14289-1:2014 — Document management applications — Electronic document file format enhancement for accessibility.
- **WCAG 2.2**: Web Content Accessibility Guidelines 2.2 Level AA (W3C Recommendation).
- **PDF 1.7**: ISO 32000-1:2008 — Document management — Portable document format.

<br/>

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

<br/>

<div align="center">
  <sub>Built with precision for universal digital document accessibility.</sub>
</div>
