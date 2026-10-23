"""
AI Response Validation Module
Validates, normalizes, and enforces accessibility rules on classification results.
"""

from typing import List, Dict, Any


class ClassificationValidator:
    """Validates AI and heuristic classification results for PDF accessibility."""

    def __init__(self, min_confidence: float = 0.7):
        """
        Initialize validator.
        
        Args:
            min_confidence: Minimum confidence threshold
        """
        self.min_confidence = min_confidence

    def validate(self, classified_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate and normalize classifications for proper semantic hierarchy.
        
        Rules:
        - Exactly one main document title (H1)
        - Subsequent titles become H2 section headings, not flat body text
        - Preserve H2, H3, lists, tables, figures, and captions
        - Flag low-confidence blocks for human review
        
        Args:
            classified_blocks: List of classified blocks
            
        Returns:
            Validated classifications with full summary
        """
        # Separate title blocks from others
        title_blocks = []
        other_blocks = []

        for b in classified_blocks:
            tag = b.get("tag", "body")
            if tag == "title":
                title_blocks.append(b)
            else:
                other_blocks.append(b)

        # Enforce Rule: Exactly one main H1 title
        if len(title_blocks) > 1:
            # Sort by page (page 1 first), then confidence
            title_blocks.sort(key=lambda x: (x.get("page", 1), -x.get("confidence", 0)))
            main_title = title_blocks[0]
            
            # Convert subsequent titles to heading2 (H2), NOT body
            for b in title_blocks[1:]:
                b["tag"] = "heading2"
                b["original_tag"] = "title"
                b["reason"] = "Secondary title promoted to H2 section heading to maintain hierarchy"
                other_blocks.append(b)
            
            title_blocks = [main_title]

        all_blocks = title_blocks + other_blocks
        unverified = []

        tag_counts = {
            "titles": len(title_blocks),
            "heading2": 0,
            "heading3": 0,
            "heading4": 0,
            "bodies": 0,
            "list_items": 0,
            "tables": 0,
            "figures": 0,
            "captions": 0
        }

        for block in all_blocks:
            tag = block.get("tag", "body")
            
            # Normalize tag names to standard set
            if tag in ["heading2", "h2"]:
                tag_counts["heading2"] += 1
            elif tag in ["heading3", "h3"]:
                tag_counts["heading3"] += 1
            elif tag in ["heading4", "h4"]:
                tag_counts["heading4"] += 1
            elif tag in ["body", "paragraph", "p"]:
                tag_counts["bodies"] += 1
            elif tag in ["list", "list_item", "li"]:
                tag_counts["list_items"] += 1
            elif tag in ["table"]:
                tag_counts["tables"] += 1
            elif tag in ["figure"]:
                tag_counts["figures"] += 1
            elif tag in ["caption"]:
                tag_counts["captions"] += 1

            confidence = block.get("confidence", 0.0)
            if confidence < self.min_confidence:
                block["unverified"] = True
                block["verification_note"] = f"Confidence {confidence:.2f} below threshold {self.min_confidence}"
                unverified.append(block)
            else:
                block["unverified"] = False

        return {
            "validated_blocks": all_blocks,
            "title_count": tag_counts["titles"],
            "heading2_count": tag_counts["heading2"],
            "heading3_count": tag_counts["heading3"],
            "heading4_count": tag_counts["heading4"],
            "body_count": tag_counts["bodies"],
            "list_item_count": tag_counts["list_items"],
            "table_count": tag_counts["tables"],
            "unverified_count": len(unverified),
            "validation_summary": {
                "total_blocks": len(all_blocks),
                "titles": tag_counts["titles"],
                "heading2": tag_counts["heading2"],
                "heading3": tag_counts["heading3"],
                "heading4": tag_counts["heading4"],
                "bodies": tag_counts["bodies"],
                "list_items": tag_counts["list_items"],
                "tables": tag_counts["tables"],
                "figures": tag_counts["figures"],
                "captions": tag_counts["captions"],
                "unverified": len(unverified)
            }
        }
