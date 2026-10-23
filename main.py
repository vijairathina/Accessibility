"""
Main Application Orchestrator
End-to-end accessible PDF tagging and validation pipeline.
Conforms to WCAG 2.2 Level AA and PDF/UA-1 (ISO 14289-1).
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Configure Windows console encoding safely
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from pdf_extractor import PDFExtractor
from pre_ai_processor import PreAIProcessor
from gemini_classifier import GeminiClassifier
from validator import ClassificationValidator
from pdf_tagger import PDFTagger
from logger import ProcessLogger
from pdf_accessibility_validator import run_audit


class PDFTaggingPipeline:
    """Orchestrates the complete accessible PDF tagging and verification workflow."""
    
    def __init__(self, gemini_api_key: str = None, use_api: bool = True):
        """
        Initialize pipeline.
        
        Args:
            gemini_api_key: Optional Gemini API key (otherwise from env)
            use_api: If True, call API; if False, use cached responses
        """
        self.extractor = PDFExtractor()
        self.pre_processor = PreAIProcessor()
        self.validator = ClassificationValidator(min_confidence=0.7)
        self.tagger = PDFTagger()
        self.logger = None  # Initialized in process_pdf
        self._gemini_api_key = gemini_api_key
        self.use_api = use_api
    
    def process_pdf(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """
        Process PDF through complete accessibility pipeline.
        
        Args:
            input_path: Input PDF file path
            output_path: Output tagged accessible PDF file path
            
        Returns:
            Processing and accessibility results dictionary
        """
        print(f"Processing PDF: {input_path}")
        
        # Initialize process logger
        self.logger = ProcessLogger(output_path)
        print(f"Log folder: {self.logger.get_log_folder()}")
        
        # Get API key for classifier
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key and hasattr(self, '_gemini_api_key'):
            api_key = self._gemini_api_key
        
        # Initialize classifier with logger and cache
        from response_cache import ResponseCache
        cache = ResponseCache()
        self.classifier = GeminiClassifier(
            api_key=api_key,
            logger=self.logger, 
            use_api=self.use_api,
            cache=cache
        )
        
        try:
            # Step 1: Extract content
            print("Step 1: Extracting content with table and link recognition...")
            content = self.extractor.extract_content(input_path)
            print(f"  Extracted {len(content['text_blocks'])} text blocks, "
                  f"{len(content.get('tables', []))} tables, "
                  f"{len(content.get('images', []))} images, and "
                  f"{len(content.get('links', []))} links")

            # Save extracted text as plain text file immediately
            extracted_text_path = Path(output_path).with_suffix('.txt')
            with open(extracted_text_path, 'w', encoding='utf-8') as f:
                f.write(f"Extracted Text from: {input_path}\n")
                f.write(f"Processing Time: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")

                for i, block in enumerate(content['text_blocks'], 1):
                    f.write(f"\n--- Block {i} (ID: {block.get('block_id', 'N/A')}) ---\n")
                    f.write(f"Page: {block.get('page', 'N/A')}\n")
                    f.write(f"Font Size: {block.get('font_size', 'N/A')}\n")
                    f.write(f"Font Weight: {block.get('font_weight', 'N/A')}\n")
                    f.write(f"Font Color: {block.get('font_color', 'N/A')}\n")
                    f.write(f"Bounding Box: {block.get('bbox', [])}\n")
                    f.write(f"Text:\n{block.get('text', '')}\n")
                    f.write("-" * 80 + "\n")

                if content.get('tables'):
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("Extracted Tables:\n")
                    for tbl in content['tables']:
                        f.write(f"\nTable ID: {tbl['block_id']} on Page {tbl['page']}\n")
                        f.write(f"Dimensions: {tbl['row_count']} rows x {tbl['col_count']} columns\n")
                        f.write(f"Text Preview: {tbl['text']}\n")
                        f.write("-" * 80 + "\n")

            print(f"Step 1.5: Saved clean extracted text to {extracted_text_path}")

            # Save extracted text and images to logs
            self.logger.save_extracted_text(content['text_blocks'], content['images'], input_path)
            self.logger.save_extracted_images(content['images'], input_path)
            
            # Step 2: Pre-AI structuring
            print("Step 2: Structuring content and determining candidate hierarchy...")
            structured = self.pre_processor.structure_blocks(content)
            print(f"  Structured {structured['statistics']['total_blocks']} blocks")
            
            # Step 3: AI classification
            print("Step 3: Semantic classification (Gemini / Cache / Heuristics)...")
            classified = self.classifier.classify_blocks(structured)
            print(f"  Classified {len(classified['classified_blocks'])} blocks")
            
            # Step 4: Validation
            print("Step 4: Validating accessibility semantic hierarchy...")
            validated = self.validator.validate(classified['classified_blocks'])
            summary = validated['validation_summary']
            print(f"  Validated: {summary['titles']} title (H1), "
                  f"{summary.get('heading2', 0)} H2s, "
                  f"{summary.get('heading3', 0)} H3s, "
                  f"{summary.get('list_items', 0)} list items, "
                  f"{summary.get('tables', 0)} tables, "
                  f"{summary['bodies']} paragraphs, "
                  f"{summary['unverified']} unverified")
            
            # Merge validated blocks with original block metadata
            original_blocks_dict = {block['block_id']: block for block in structured['blocks']}
            enriched_blocks = []
            for validated_block in validated['validated_blocks']:
                block_id = validated_block['block_id']
                original_block = original_blocks_dict.get(block_id, {})
                enriched_block = {
                    **original_block,
                    **validated_block
                }
                enriched_blocks.append(enriched_block)
            
            # Step 5: Tag injection
            print("Step 5: Injecting PDF/UA-1 structure tree, ParentTree, metadata, and outlines...")
            tag_metadata = self.tagger.inject_tags(
                input_path,
                enriched_blocks,
                output_path,
                images=content.get('images', []),
                links=content.get('links', [])
            )
            print(f"  Injected {tag_metadata['total_tags']} accessible structure tags")
            
            # Step 6: Automated Accessibility Audit
            print("Step 6: Performing comprehensive automated accessibility audit...")
            audit_report = run_audit(output_path)
            
            # Step 7: Save metadata
            metadata_path = Path(output_path).with_suffix('.json')
            metadata = {
                "input_pdf": input_path,
                "output_pdf": output_path,
                "processing_summary": {
                    "total_blocks": structured['statistics']['total_blocks'],
                    "tables": len(content.get('tables', [])),
                    "images": len(content.get('images', [])),
                    "links": len(content.get('links', [])),
                    "pages": content['total_pages']
                },
                "classification": validated['validation_summary'],
                "tag_metadata": tag_metadata,
                "accessibility_audit": {
                    "automated_status": audit_report["automated_status"],
                    "compliance_rate": audit_report["statistics"]["automated_compliance_rate_pct"],
                    "passed": audit_report["statistics"]["passed"],
                    "failed": audit_report["statistics"]["failed"],
                    "warnings": audit_report["statistics"]["warnings"],
                    "report_json": f"{Path(output_path).with_suffix('')}_accessibility_report.json",
                    "report_html": f"{Path(output_path).with_suffix('')}_accessibility_report.html"
                }
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            print(f"Step 7: Saved execution metadata to {metadata_path}")
            print(f"\n[OK] Processing and accessibility remediation complete!")
            print(f"  Output PDF: {output_path}")
            print(f"  Metadata: {metadata_path}")
            print(f"  Extracted Text: {extracted_text_path}")
            print(f"  Audit Report (HTML): {metadata['accessibility_audit']['report_html']}")
            print(f"  Log folder: {self.logger.get_log_folder()}")

            return metadata
            
        except Exception as e:
            print(f"\n[ERROR] Error during processing: {e}")
            import traceback
            traceback.print_exc()
            print("Returning original PDF as fallback...")
            
            import shutil
            try:
                shutil.copy2(input_path, output_path)
                print(f"Original PDF copied to {output_path}")
            except Exception as copy_error:
                print(f"Failed to copy original PDF: {copy_error}")
            
            raise


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: python main.py <input.pdf> <output.pdf> [use_api]")
        print("\nArguments:")
        print("  input.pdf   - Input PDF file")
        print("  output.pdf  - Output PDF file")
        print("  use_api     - 0 = use cached responses (skip API calls)")
        print("                1 = call API (default)")
        print("\nExample:")
        print("  python main.py input.pdf output_accessible.pdf 0  # Use cache/heuristics")
        print("  python main.py input.pdf output_accessible.pdf 1  # Call API")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    use_api = 1
    if len(sys.argv) >= 4:
        try:
            use_api = int(sys.argv[3])
            if use_api not in [0, 1]:
                print(f"Warning: Invalid use_api value '{sys.argv[3]}'. Using default (1)")
                use_api = 1
        except ValueError:
            print(f"Warning: Invalid use_api value '{sys.argv[3]}'. Using default (1)")
            use_api = 1
    
    if not os.path.exists(input_path):
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    api_key = None
    if use_api == 1:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("Note: GEMINI_API_KEY not set. Falling back to cached responses / local heuristics.")
            use_api = 0
    else:
        print("Mode: Using cached responses and heuristics (API calls disabled)")
    
    pipeline = PDFTaggingPipeline(gemini_api_key=api_key, use_api=use_api == 1)
    try:
        pipeline.process_pdf(input_path, output_path)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
