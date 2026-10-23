"""
Logging Module
Handles all logging operations for the PDF tagging process.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import logging


class ProcessLogger:
    """Manages logging for PDF processing pipeline."""
    
    def __init__(self, base_output_path: str):
        """
        Initialize logger with output path.
        
        Args:
            base_output_path: Base path for output files (used to create log folder)
        """
        # Create log folder based on output file name
        output_path = Path(base_output_path)
        log_folder_name = f"{output_path.stem}_logs"
        self.log_folder = output_path.parent / log_folder_name
        self.log_folder.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.text_folder = self.log_folder / "extracted_text"
        self.image_folder = self.log_folder / "extracted_images"
        self.ai_folder = self.log_folder / "ai_requests_responses"
        
        for folder in [self.text_folder, self.image_folder, self.ai_folder]:
            folder.mkdir(exist_ok=True)
        
        # Setup logging
        log_file = self.log_folder / "process.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"Log folder created: {self.log_folder}")
    
    def save_extracted_text(self, text_blocks: List[Dict[str, Any]], 
                           images: List[Dict[str, Any]], pdf_name: str):
        """
        Save extracted text to files.
        
        Args:
            text_blocks: List of text blocks with metadata
            images: List of image blocks
            pdf_name: Name of the source PDF
        """
        # Save all text blocks to JSON
        text_json_path = self.text_folder / f"{Path(pdf_name).stem}_text_blocks.json"
        with open(text_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "extraction_time": datetime.now().isoformat(),
                "source_pdf": pdf_name,
                "text_blocks": text_blocks,
                "total_blocks": len(text_blocks)
            }, f, indent=2, ensure_ascii=False)
        
        # Save plain text content
        text_txt_path = self.text_folder / f"{Path(pdf_name).stem}_extracted_text.txt"
        with open(text_txt_path, 'w', encoding='utf-8') as f:
            f.write(f"Extracted Text from: {pdf_name}\n")
            f.write(f"Extraction Time: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, block in enumerate(text_blocks, 1):
                f.write(f"\n--- Block {i} (ID: {block.get('block_id', 'N/A')}) ---\n")
                f.write(f"Page: {block.get('page', 'N/A')}\n")
                f.write(f"Font Size: {block.get('font_size', 'N/A')}\n")
                f.write(f"Font Weight: {block.get('font_weight', 'N/A')}\n")
                f.write(f"Bounding Box: {block.get('bbox', [])}\n")
                f.write(f"Text:\n{block.get('text', '')}\n")
                f.write("-" * 80 + "\n")
        
        self.logger.info(f"Saved extracted text: {text_txt_path}")
        self.logger.info(f"Saved text blocks JSON: {text_json_path}")
    
    def save_extracted_images(self, images: List[Dict[str, Any]], pdf_name: str):
        """
        Save extracted images to files.
        
        Args:
            images: List of image blocks with image_data
            pdf_name: Name of the source PDF
        """
        saved_count = 0
        for img in images:
            try:
                block_id = img.get("block_id", "unknown")
                page_num = img.get("page", 0)
                image_data = img.get("image_data")
                
                if image_data:
                    # Determine image format from data
                    ext = "png"  # Default
                    if image_data.startswith(b'\xff\xd8'):
                        ext = "jpg"
                    elif image_data.startswith(b'\x89PNG'):
                        ext = "png"
                    
                    image_filename = f"{Path(pdf_name).stem}_page{page_num}_{block_id}.{ext}"
                    image_path = self.image_folder / image_filename
                    
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    
                    saved_count += 1
                    self.logger.info(f"Saved image: {image_filename}")
            except Exception as e:
                self.logger.warning(f"Failed to save image {block_id}: {e}")
        
        self.logger.info(f"Saved {saved_count} images out of {len(images)} total")
    
    def save_ai_request(self, request_text: str, chunk_num: int, timestamp: str = None):
        """
        Save AI request text to log file.
        
        Args:
            request_text: The prompt/request sent to AI
            chunk_num: Chunk number (for multiple requests)
            timestamp: Optional timestamp (auto-generated if not provided)
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        request_file = self.ai_folder / f"ai_request_chunk_{chunk_num:03d}.txt"
        with open(request_file, 'w', encoding='utf-8') as f:
            f.write(f"AI Request - Chunk {chunk_num}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 80 + "\n\n")
            f.write(request_text)
        
        self.logger.info(f"Saved AI request: {request_file.name}")
    
    def save_ai_response(self, response_text: str, chunk_num: int, timestamp: str = None):
        """
        Save AI response text to log file.
        
        Args:
            response_text: The response received from AI
            chunk_num: Chunk number (for multiple requests)
            timestamp: Optional timestamp (auto-generated if not provided)
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        response_file = self.ai_folder / f"ai_response_chunk_{chunk_num:03d}.txt"
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(f"AI Response - Chunk {chunk_num}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 80 + "\n\n")
            f.write(response_text)
        
        self.logger.info(f"Saved AI response: {response_file.name}")
    
    def save_ai_summary(self, all_requests: List[Dict], all_responses: List[Dict]):
        """
        Save summary of all AI requests and responses.
        
        Args:
            all_requests: List of request dictionaries with chunk_num and text
            all_responses: List of response dictionaries with chunk_num and text
        """
        summary_file = self.ai_folder / "ai_summary.json"
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_chunks": len(all_requests),
            "requests": all_requests,
            "responses": all_responses
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved AI summary: {summary_file.name}")
    
    def get_log_folder(self) -> Path:
        """Get the log folder path."""
        return self.log_folder
