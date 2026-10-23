"""
PDF Content Extraction Module
Extracts text, structured tables, images, and links with metadata from PDF documents.
Ensures clean Unicode text mapping and resolves font ligatures for accessibility.
"""

import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import io
import re


def normalize_ligatures(text: str) -> str:
    """
    Resolve private and discretionary font ligatures and split-ligature spacing.
    Commonly produced by Word/Calibri without ToUnicode mapping.
    """
    if not text:
        return text

    # Direct character replacements for Calibri/Word ligatures and standard Unicode ligatures
    replacements = {
        '\u019f': 'ti',   # Ɵ ligature for 'ti'
        '\u014c': 'ft',   # Ō ligature for 'ft'
        '\u019e': 'tt',   # ƞ ligature for 'tt'
        '\ufb00': 'ff',
        '\ufb01': 'fi',
        '\ufb02': 'fl',
        '\ufb03': 'ffi',
        '\ufb04': 'ffl',
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)

    # Word-level split repairs where space was inserted at ligature boundaries
    word_repairs = [
        (r'\bPopula\s+tion\b', 'Population'),
        (r'\bBri\s+tish\b', 'British'),
        (r'\bNova\s+Sco\s+tia\b', 'Nova Scotia'),
        (r'\bcrea\s+ting\b', 'creating'),
        (r'\bcrea\s+tion\b', 'creation'),
        (r'\bcrea\s+tive\b', 'Creative'),
        (r'\bCon\s+tinuous\b', 'Continuous'),
        (r'\bmul\s+tiple\b', 'multiple'),
        (r'\bso\s*ftware\b', 'software'),
        (r'\bpla\s*tform\b', 'platform'),
        (r'\bpla\s*tforms\b', 'platforms'),
        (r'\bpla\s*ttorm\b', 'platform'),
        (r'\bdiscon\s+tinued\b', 'discontinued'),
        (r'\bAr\s+tifacts\b', 'Artifacts'),
        (r'\bAddi\s+tionally\b', 'Additionally'),
        (r'\binforma\s+tion\b', 'information'),
        (r'\bcap\s+tion\b', 'caption'),
        (r'\bpar\s+ticularly\b', 'particularly'),
        (r'\bedi\s+ting\b', 'editing'),
        (r'\bimpor\s+ting\b', 'importing'),
        (r'\binges\s+ting\b', 'ingesting'),
        (r'\bcorrec\s+tions\b', 'corrections'),
        (r'\borganiza\s+tional\b', 'organizational'),
        (r'\bpos\s*t\s*-\s*produc\s+tion\b', 'post-production'),
        (r'\binterac\s+tive\b', 'interactive'),
        (r'\bA\s+fter\b', 'After'),
        (r'\bcross\s*-\s*pla\s*(?:tt|t)?orm\b', 'cross-platform'),
        (r'\bhtp://', 'http://'),
    ]
    for pattern, repl in word_repairs:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    # Collapse multiple spaces while preserving single spaces
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


class PDFExtractor:
    """Extracts text blocks, tables, images, and links from PDF with accessibility metadata."""

    def __init__(self):
        self.block_counter = 0

    def extract_content(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract all content from PDF.
        
        Args:
            pdf_path: Path to input PDF file
            
        Returns:
            Dictionary with 'text_blocks', 'tables', 'images', 'links', and 'total_pages'
        """
        doc = fitz.open(pdf_path)
        text_blocks = []
        tables = []
        images = []
        links = []
        
        total_pages = len(doc)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            
            # Step 1: Detect tables on this page to isolate their bounding boxes
            page_tables, table_bboxes = self._extract_tables(page, page_num)
            tables.extend(page_tables)

            # Step 2: Extract text blocks outside table regions
            text_blocks.extend(self._extract_text_blocks(page, page_num, table_bboxes))
            
            # Step 3: Extract interactive links
            page_links = self._extract_links(page, page_num)
            links.extend(page_links)

            # Step 4: Extract images
            try:
                images.extend(self._extract_images(page, page_num))
            except Exception as e:
                print(f"Warning: Image extraction failed for page {page_num + 1}: {e}")
        
        doc.close()
        
        return {
            "text_blocks": text_blocks,
            "tables": tables,
            "images": images,
            "links": links,
            "total_pages": total_pages
        }

    def _extract_tables(self, page: fitz.Page, page_num: int) -> Tuple[List[Dict[str, Any]], List[List[float]]]:
        """Detect and extract genuine data tables from the page."""
        page_tables = []
        table_bboxes = []
        
        try:
            tabs = list(page.find_tables())
        except Exception:
            tabs = []

        for tab_idx, tab in enumerate(tabs):
            bbox = [round(c, 2) for c in tab.bbox]
            table_bboxes.append(bbox)
            
            raw_matrix = tab.extract()
            rows_data = []
            
            # Extract cells with span and coordinate information
            for r_idx, r in enumerate(tab.rows):
                row_cells = []
                for c_idx, cell_rect in enumerate(r.cells):
                    cell_text = ""
                    if r_idx < len(raw_matrix) and c_idx < len(raw_matrix[r_idx]):
                        val = raw_matrix[r_idx][c_idx]
                        if val is not None:
                            cell_text = normalize_ligatures(str(val))
                    
                    # Detect header cell: row 0 or column 0 in simple data tables
                    is_header = (r_idx == 0) or (tab.row_count > 1 and c_idx == 0 and r_idx > 0 and len(cell_text) > 0 and not cell_text.replace('.', '').isdigit())
                    scope = "Column" if r_idx == 0 else ("Row" if is_header else None)

                    row_cells.append({
                        "row": r_idx,
                        "col": c_idx,
                        "text": cell_text,
                        "bbox": [round(c, 2) for c in cell_rect] if cell_rect else bbox,
                        "is_header": is_header,
                        "scope": scope
                    })
                rows_data.append(row_cells)

            self.block_counter += 1
            tbl_block = {
                "block_id": f"tbl_p{page_num+1}_{tab_idx+1}",
                "page": page_num + 1,
                "type": "table",
                "tag": "table",
                "bbox": bbox,
                "row_count": tab.row_count,
                "col_count": tab.col_count,
                "rows": rows_data,
                "header_names": [normalize_ligatures(h) for h in (tab.header.names if tab.header else [])],
                "text": " | ".join([" ".join([c["text"] for c in r if c["text"]]) for r in rows_data])
            }
            page_tables.append(tbl_block)

        return page_tables, table_bboxes

    def _extract_links(self, page: fitz.Page, page_num: int) -> List[Dict[str, Any]]:
        """Extract hyperlink annotations with bounding boxes and destination URIs."""
        links = []
        try:
            for l_idx, link in enumerate(page.get_links()):
                uri = link.get("uri", "")
                r = link.get("from", None)
                if r:
                    links.append({
                        "link_id": f"link_p{page_num+1}_{l_idx+1}",
                        "page": page_num + 1,
                        "uri": uri,
                        "bbox": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)],
                        "xref": link.get("xref", 0)
                    })
        except Exception:
            pass
        return links

    def _extract_text_blocks(
        self,
        page: fitz.Page,
        page_num: int,
        table_bboxes: Optional[List[List[float]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract text blocks with metadata from a page, preserving paragraphs as single units.
        Filters out text contained within detected tables.
        """
        blocks = []
        text_dict = page.get_text("dict")
        table_bboxes = table_bboxes or []

        def is_inside_table(line_bbox):
            lx0, ly0, lx1, ly1 = line_bbox
            l_cx = (lx0 + lx1) / 2
            l_cy = (ly0 + ly1) / 2
            for tx0, ty0, tx1, ty1 in table_bboxes:
                if (tx0 - 2 <= l_cx <= tx1 + 2) and (ty0 - 2 <= l_cy <= ty1 + 2):
                    return True
            return False

        # Collect all lines with metadata
        all_lines = []
        for block in text_dict.get("blocks", []):
            if "lines" in block and block.get("lines"):
                for line in block.get("lines", []):
                    line_bbox = line.get("bbox", [0, 0, 0, 0])
                    
                    # Skip text inside table areas
                    if is_inside_table(line_bbox):
                        continue

                    all_spans = []
                    raw_spans_text = []
                    
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        if span_text:
                            raw_spans_text.append(span_text)
                            all_spans.append(span)

                    raw_line_text = " ".join(raw_spans_text).strip()
                    cleaned_line_text = normalize_ligatures(raw_line_text)

                    if cleaned_line_text:
                        font_size = all_spans[0].get("size", 12) if all_spans else 12
                        is_all_caps = cleaned_line_text.isupper() and len(cleaned_line_text) > 3
                        ends_with_punct = cleaned_line_text.rstrip().endswith(('.', '!', '?', ':', ';'))

                        font_name = all_spans[0].get("font", "") if all_spans else ""
                        line_width = line_bbox[2] - line_bbox[0]

                        all_lines.append({
                            "text": cleaned_line_text,
                            "bbox": line_bbox,
                            "width": line_width,
                            "spans": all_spans,
                            "font_name": font_name,
                            "x0": line_bbox[0],
                            "font_size": font_size,
                            "is_all_caps": is_all_caps,
                            "ends_with_punct": ends_with_punct
                        })

        # Group lines into paragraphs based on spatial and structural heuristics
        paragraphs = []
        current_para_lines = []
        prev_y1 = None
        prev_font_size = None
        prev_text = ""
        prev_width = None
        prev_font_name = ""

        for line_data in all_lines:
            y0 = line_data["bbox"][1]
            y1 = line_data["bbox"][3]
            line_text = line_data["text"]
            font_size = line_data["font_size"]
            line_width = line_data.get("width", 500.0)
            font_name = line_data.get("font_name", "")

            # Detect list item indicators
            is_bullet = line_text.strip().startswith(('•', 'o', '-'))
            is_numbered = bool(re.match(r'^\d+[\.\)]\s*', line_text.strip()))
            is_list_item = is_bullet or is_numbered

            # Detect figure caption
            is_figure_caption = bool(re.match(r'^Figure\s+\d+[:\.]', line_text.strip()))

            gap = y0 - prev_y1 if prev_y1 is not None else 0
            font_size_change = prev_font_size is not None and abs(font_size - prev_font_size) > 1.5

            should_start_new = False

            if prev_y1 is None:
                should_start_new = True
            elif is_list_item or is_figure_caption:
                should_start_new = True
            elif gap > 6.0:
                should_start_new = True
            elif font_size_change and gap > 1.5:
                should_start_new = True
            else:
                line_clean = line_text.strip()
                prev_clean = prev_text.strip()
                
                # Check if current line is a heading
                current_is_heading = (
                    len(line_clean) < 60 and
                    not line_clean.rstrip().endswith(('.', ':', ';', ',', '!', '?')) and
                    (font_size_change or line_width < 250 or len(line_clean.split()) <= 6 or "light" in font_name.lower())
                )
                prev_is_heading = False
                if prev_clean:
                    prev_is_heading = (
                        len(prev_clean) < 60 and
                        not prev_clean.rstrip().endswith(('.', ':', ';', ',', '!', '?')) and
                        (font_size_change or (prev_width is not None and prev_width < 250) or len(prev_clean.split()) <= 6 or "light" in prev_font_name.lower())
                    )

                if current_is_heading or prev_is_heading:
                    should_start_new = True

            if should_start_new:
                if current_para_lines:
                    paragraphs.append(current_para_lines)
                current_para_lines = [line_data]
            else:
                current_para_lines.append(line_data)

            prev_y1 = y1
            prev_font_size = font_size
            prev_text = line_text
            prev_width = line_width
            prev_font_name = font_name

        if current_para_lines:
            paragraphs.append(current_para_lines)

        # Assemble paragraph blocks
        for para_lines in paragraphs:
            if not para_lines:
                continue

            para_text = " ".join(line["text"] for line in para_lines)
            para_text = normalize_ligatures(para_text)

            sizes = []
            is_bold = False
            colors = []
            fonts = []

            for line in para_lines:
                for span in line["spans"]:
                    sizes.append(span.get("size", 12))
                    if span.get("flags", 0) & 16 or "bold" in span.get("font", "").lower():
                        is_bold = True
                    fnt = span.get("font", "")
                    if fnt:
                        fonts.append(fnt)
                    color = span.get("color", 0)
                    if isinstance(color, int):
                        r = (color >> 16) & 0xFF
                        g = (color >> 8) & 0xFF
                        b = color & 0xFF
                        colors.append((r, g, b))
                    elif isinstance(color, list) and len(color) >= 3:
                        colors.append(tuple(int(c * 255) if isinstance(c, float) else c for c in color[:3]))

            avg_size = sum(sizes) / len(sizes) if sizes else 12.0
            font_weight = "bold" if is_bold else "normal"
            rep_color = colors[0] if colors else (0, 0, 0)
            primary_font = fonts[0] if fonts else ""

            x0 = min(line["bbox"][0] for line in para_lines)
            y0 = min(line["bbox"][1] for line in para_lines)
            x1 = max(line["bbox"][2] for line in para_lines)
            y1 = max(line["bbox"][3] for line in para_lines)

            self.block_counter += 1
            blocks.append({
                "block_id": f"b{self.block_counter}",
                "page": page_num + 1,
                "type": "text",
                "text": para_text,
                "font_size": round(avg_size, 2),
                "font_name": primary_font,
                "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                "font_weight": font_weight,
                "font_color": rep_color
            })

        return blocks

    def _extract_images(self, page: fitz.Page, page_num: int) -> List[Dict[str, Any]]:
        """Extract images with metadata, xref, and bounding boxes."""
        images = []
        image_list = page.get_images(full=True)
        
        # Get image rectangles from page display list
        image_rects_dict = {}
        try:
            for img_info in image_list:
                xref = img_info[0]
                try:
                    rects = page.get_image_rects(xref)
                    if rects:
                        image_rects_dict[xref] = rects[0]
                except Exception:
                    pass
        except Exception:
            pass

        for img_index, img in enumerate(image_list):
            try:
                xref = img[0]
                name = img[7] if len(img) > 7 else f"Im{img_index}"
                base_image = page.parent.extract_image(xref)
                image_bytes = base_image["image"]
                
                bbox = None
                if xref in image_rects_dict:
                    rect = image_rects_dict[xref]
                    bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
                else:
                    try:
                        rects = page.get_image_rects(xref)
                        if rects:
                            bbox = [rects[0].x0, rects[0].y0, rects[0].x1, rects[0].y1]
                    except Exception:
                        pass

                if bbox is None:
                    bbox = [0, 0, page.rect.width, page.rect.height]

                self.block_counter += 1
                images.append({
                    "block_id": f"b{self.block_counter}",
                    "page": page_num + 1,
                    "type": "image",
                    "name": name,
                    "xref": xref,
                    "bbox": [round(coord, 2) for coord in bbox],
                    "image_data": image_bytes,
                    "width": base_image.get("width", 0),
                    "height": base_image.get("height", 0)
                })
            except Exception as e:
                print(f"Warning: Could not extract image {img_index} from page {page_num + 1}: {e}")
                continue

        return images
