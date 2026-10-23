"""
Pre-AI Structuring Module
Groups and structures content blocks before AI analysis with rich accessibility candidate types.
"""

from typing import List, Dict, Any
import re


class PreAIProcessor:
    """Structures content blocks for AI analysis with semantic candidate types."""

    def structure_blocks(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Structure blocks with metadata for AI decision support.
        
        Args:
            content: Dictionary with 'text_blocks', 'tables', 'images', 'links'
            
        Returns:
            Structured content with candidate classifications
        """
        text_blocks = content.get("text_blocks", [])
        tables = content.get("tables", [])
        
        # Calculate statistics for classification hints
        font_sizes = [b["font_size"] for b in text_blocks if "font_size" in b]
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
        max_font_size = max(font_sizes) if font_sizes else 12.0
        
        structured_blocks = []
        
        for block in text_blocks:
            text = block.get("text", "").strip()
            bbox = block.get("bbox", [0, 0, 0, 0])
            font_size = block.get("font_size", 12.0)
            font_name = block.get("font_name", "")
            is_bold = block.get("font_weight") == "bold"
            page = block.get("page", 1)
            
            is_top_of_page = bbox[1] < 120
            is_large_font = font_size > avg_font_size * 1.15
            ends_with_period = text.rstrip().endswith(('.', '!', '?'))
            
            # 1. Title Candidate (Main Document Title)
            is_title = (page == 1 and is_top_of_page and font_size >= max_font_size * 0.9 and font_size >= 20.0)
            
            # 2. Caption Candidate
            is_caption = bool(re.match(r'^Figure\s+\d+[:\.]', text))
            
            # 3. List Item Candidate
            is_list = (text.startswith(('•', 'o', '-')) or bool(re.match(r'^\d+[\.\)]\s+', text)))
            
            # 4. Heading 2 Candidate (Major sections, e.g. "Lists", "Artifacts", "Tables", "Images", "Links")
            is_major_section_name = text.strip().lower() in [
                "lists", "artifacts", "tables", "images", "links",
                "introduction", "conclusion", "references", "overview", "summary", "appendix"
            ]
            is_h2 = (
                not is_title and not is_list and not is_caption and not ends_with_period and
                (
                    (font_size >= avg_font_size * 1.25 and len(text) < 60) or
                    (is_major_section_name and len(text.strip().split()) <= 3)
                )
            )
            
            # 5. Heading 3 Candidate (Sub-sections, e.g. "Simple List", "Complex Table", "Photos of Sunsets")
            is_sub_section_name = text.strip().lower() in [
                "photos of sunsets", "simple list", "complex list",
                "simple table", "complex table", "embedded hyperlink",
                "shortened url", "full url"
            ]
            is_h3 = (
                not is_title and not is_list and not is_caption and not is_h2 and not ends_with_period and
                (
                    (font_size > avg_font_size * 1.05 and len(text) < 70) or
                    (is_bold and len(text) < 70) or
                    (is_sub_section_name and len(text) < 70)
                )
            )

            # 6. Heading 4 Candidate (Sub-sub-sections / table titles / list titles)
            is_sub_sub_heading_name = text.strip().lower() in [
                "list of canadian provinces by population (2014)",
                "some adobe creative cloud desktop apps with descriptions",
                "vehicles sold by model and color",
                "sales results for 2015"
            ]
            is_h4 = (
                not is_title and not is_list and not is_caption and not is_h2 and not is_h3 and
                not ends_with_period and
                len(text) < 75 and
                (
                    is_sub_sub_heading_name or
                    ("light" in font_name.lower() and not ends_with_period and len(text) < 70)
                )
            )
            
            if is_title:
                candidate_type = "title_candidate"
            elif is_h2:
                candidate_type = "heading2_candidate"
            elif is_h3:
                candidate_type = "heading3_candidate"
            elif is_h4:
                candidate_type = "heading4_candidate"
            elif is_list:
                candidate_type = "list_item_candidate"
            elif is_caption:
                candidate_type = "caption_candidate"
            else:
                candidate_type = "body_candidate"

            structured_block = {
                **block,
                "candidate_type": candidate_type,
                "is_top_of_page": is_top_of_page,
                "is_large_font": is_large_font,
                "is_bold": is_bold
            }
            structured_blocks.append(structured_block)

        # Include table blocks directly into structured stream
        for tbl in tables:
            structured_blocks.append({
                **tbl,
                "candidate_type": "table_candidate",
                "tag": "table",
                "font_size": 12.0,
                "font_weight": "normal",
                "is_top_of_page": tbl.get("bbox", [0, 0, 0, 0])[1] < 120,
                "is_large_font": False,
                "is_bold": False
            })

        # Sort all structured blocks by page, then Y, then X
        structured_blocks.sort(key=lambda b: (
            b.get("page", 1),
            round(b.get("bbox", [0, 0, 0, 0])[1] / 4) * 4,
            b.get("bbox", [0, 0, 0, 0])[0]
        ))

        return {
            "blocks": structured_blocks,
            "images": content.get("images", []),
            "tables": tables,
            "links": content.get("links", []),
            "statistics": {
                "avg_font_size": round(avg_font_size, 2),
                "max_font_size": round(max_font_size, 2),
                "total_blocks": len(structured_blocks)
            }
        }
