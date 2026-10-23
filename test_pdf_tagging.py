#!/usr/bin/env python3
"""
Test script to verify PDF tagging functionality.
Tests if tags are properly linked to content.
"""

import os
import json
import pikepdf
from typing import Dict, List, Any

def test_pdf_structure(pdf_path: str) -> Dict[str, Any]:
    """
    Test if PDF has proper structure tree and tags.
    """
    results = {
        "has_struct_tree": False,
        "has_marked_flag": False,
        "struct_tree_elements": 0,
        "tag_types": {},
        "errors": []
    }

    try:
        pdf = pikepdf.Pdf.open(pdf_path)

        # Check if structure tree exists
        if "/StructTreeRoot" in pdf.Root:
            results["has_struct_tree"] = True
            struct_tree_root = pdf.Root.StructTreeRoot

            # Count structure elements
            def count_elements(node, depth=0):
                count = 0
                if hasattr(node, 'K') and node.K:
                    for child in node.K:
                        if isinstance(child, pikepdf.Dictionary):
                            if child.get("/Type") == pikepdf.Name("/StructElem"):
                                count += 1
                                tag_type = child.get("/S", "Unknown")
                                tag_str = str(tag_type).strip("/")
                                if tag_str not in results["tag_types"]:
                                    results["tag_types"][tag_str] = 0
                                results["tag_types"][tag_str] += 1

                                # Recursively count children
                                count += count_elements(child, depth + 1)
                return count

            results["struct_tree_elements"] = count_elements(struct_tree_root)

        # Check marked flag
        if "/MarkInfo" in pdf.Root and pdf.Root.MarkInfo.get("/Marked", False):
            results["has_marked_flag"] = True

        pdf.close()

    except Exception as e:
        results["errors"].append(f"Error analyzing PDF: {str(e)}")

    return results

def test_tag_content_linking(pdf_path: str, metadata_path: str) -> Dict[str, Any]:
    """
    Test if tags are properly linked to content.
    """
    results = {
        "metadata_loaded": False,
        "tags_with_bbox": 0,
        "tags_with_alt_text": 0,
        "tags_with_actual_text": 0,
        "linking_analysis": [],
        "recommendations": []
    }

    try:
        # Load metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        results["metadata_loaded"] = True

        tag_metadata = metadata.get("tag_metadata", {}).get("pdf_tags", [])

        for tag in tag_metadata:
            # Check bounding box
            if "bbox" in tag and len(tag["bbox"]) == 4:
                results["tags_with_bbox"] += 1

            # Check alternative text
            if "text" in tag and tag["text"].strip():
                results["tags_with_alt_text"] += 1

            # Analyze linking
            analysis = {
                "block_id": tag["block_id"],
                "tag": tag["pdf_tag"],
                "has_bbox": "bbox" in tag and len(tag["bbox"]) == 4,
                "has_text": bool(tag.get("text", "").strip()),
                "page": tag.get("page", 0)
            }
            results["linking_analysis"].append(analysis)

        # Generate recommendations
        if results["tags_with_bbox"] == 0:
            results["recommendations"].append("Tags missing bounding box information")

        if results["tags_with_alt_text"] == 0:
            results["recommendations"].append("Tags missing alternative text")

        if not results["linking_analysis"]:
            results["recommendations"].append("No tag metadata found")

    except Exception as e:
        results["errors"] = [f"Error analyzing metadata: {str(e)}"]

    return results

def run_comprehensive_test(pdf_path: str, metadata_path: str) -> Dict[str, Any]:
    """
    Run comprehensive test of PDF tagging.
    """
    print(f"Testing PDF: {pdf_path}")
    print(f"Testing metadata: {metadata_path}")
    print("-" * 50)

    # Test PDF structure
    structure_results = test_pdf_structure(pdf_path)
    print("PDF Structure Test:")
    print(f"  Has structure tree: {structure_results['has_struct_tree']}")
    print(f"  Has marked flag: {structure_results['has_marked_flag']}")
    print(f"  Structure elements: {structure_results['struct_tree_elements']}")
    print(f"  Tag types: {structure_results['tag_types']}")
    if structure_results['errors']:
        print(f"  Errors: {structure_results['errors']}")

    print()

    # Test tag content linking
    linking_results = test_tag_content_linking(pdf_path, metadata_path)
    print("Tag Content Linking Test:")
    print(f"  Metadata loaded: {linking_results['metadata_loaded']}")
    print(f"  Tags with bbox: {linking_results['tags_with_bbox']}")
    print(f"  Tags with alt text: {linking_results['tags_with_alt_text']}")
    print(f"  Total tags analyzed: {len(linking_results['linking_analysis'])}")

    if linking_results['recommendations']:
        print("  Recommendations:")
        for rec in linking_results['recommendations']:
            print(f"    - {rec}")

    print()

    # Overall assessment
    success_criteria = [
        structure_results['has_struct_tree'],
        structure_results['has_marked_flag'],
        structure_results['struct_tree_elements'] > 0,
        linking_results['metadata_loaded'],
        linking_results['tags_with_bbox'] > 0,
        linking_results['tags_with_alt_text'] > 0
    ]

    overall_success = all(success_criteria)

    print("Overall Assessment:")
    print(f"  Tagging successful: {overall_success}")

    if not overall_success:
        print("  Failed criteria:")
        criteria_names = [
            "Has structure tree",
            "Has marked flag",
            "Has structure elements",
            "Metadata loaded",
            "Tags have bbox",
            "Tags have alt text"
        ]
        for i, (passed, name) in enumerate(zip(success_criteria, criteria_names)):
            if not passed:
                print(f"    - {name}")

    return {
        "structure_test": structure_results,
        "linking_test": linking_results,
        "overall_success": overall_success
    }

if __name__ == "__main__":
    # Test the most recent output
    pdf_path = "output_input.pdf"
    metadata_path = "output_input.json"

    if not os.path.exists(pdf_path):
        print(f"PDF file not found: {pdf_path}")
        exit(1)

    if not os.path.exists(metadata_path):
        print(f"Metadata file not found: {metadata_path}")
        exit(1)

    results = run_comprehensive_test(pdf_path, metadata_path)

    # Save test results
    with open("tagging_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nTest results saved to: tagging_test_results.json")
