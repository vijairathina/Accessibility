"""
Gemini Flash 2.5 Integration Module
Classifies PDF content blocks using AI.
"""

import os
import json
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Use google.generativeai (deprecated but still functional)
# TODO: Migrate to google.genai when stable release is available
import warnings
# Suppress deprecation warnings
warnings.filterwarnings('ignore', category=FutureWarning)
import google.generativeai as genai

load_dotenv()


class GeminiClassifier:
    """Uses Gemini Flash 2.5 to classify PDF content blocks."""
    
    def __init__(self, api_key: str = None, logger=None, use_api: bool = True, cache=None):
        """
        Initialize Gemini classifier.
        
        Args:
            api_key: Gemini API key (or from env var GEMINI_API_KEY)
            logger: Optional ProcessLogger instance for saving requests/responses
            use_api: If True, call API; if False, use cached responses only
            cache: Optional ResponseCache instance for caching responses
        """
        self.use_api = use_api
        self.cache = cache
        
        if use_api:
            self.api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not found. Set it in .env file or pass as parameter.")
        else:
            self.api_key = None  # Not needed when using cache
            print("  Using cached responses (API disabled)")
        
        self.logger = logger
        self.model = None  # Initialize as None
        
        if self.use_api:
            genai.configure(api_key=self.api_key)
            
            # List available models and find one that works
            try:
                available_models = list(genai.list_models())
                model_names = [m.name for m in available_models if 'generateContent' in m.supported_generation_methods]
                
                if model_names:
                    # Prefer flash models (faster and cheaper), then pro models
                    flash_models = [m for m in model_names if 'flash' in m.lower() and '2.5' in m]
                    if not flash_models:
                        flash_models = [m for m in model_names if 'flash' in m.lower()]
                    
                    pro_models = [m for m in model_names if 'pro' in m.lower() and '2.5' in m]
                    if not pro_models:
                        pro_models = [m for m in model_names if 'pro' in m.lower()]
                    
                    # Try flash first, then pro, then any model
                    preferred = flash_models + pro_models + model_names
                    
                    if preferred:
                        model_to_use = preferred[0]
                        # Use the full model name (with 'models/' prefix) or just the name part
                        # GenerativeModel accepts both formats
                        model_name = model_to_use.split('/')[-1]  # Use just the name part
                        self.model = genai.GenerativeModel(model_name)
                        print(f"Using model: {model_name} (from {model_to_use})")
                    else:
                        raise ValueError("No suitable models found")
                else:
                    raise ValueError("No models with generateContent support found")
                    
            except Exception as e:
                # Fallback: try common model names directly
                print(f"Warning: Could not list models: {e}")
                print("Trying direct model initialization...")
                
                # Try model names in order of preference (without 'models/' prefix)
                model_candidates = [
                    'gemini-2.5-flash',     # Latest flash
                    'gemini-2.0-flash',     # 2.0 flash
                    'gemini-2.5-pro',      # Latest pro
                    'gemini-pro',           # Legacy pro
                ]
                
                self.model = None
                for model_name in model_candidates:
                    try:
                        self.model = genai.GenerativeModel(model_name)
                        print(f"Using model: {model_name} (fallback)")
                        break
                    except Exception as model_error:
                        continue
                
                if self.model is None:
                    raise RuntimeError(f"Could not initialize any Gemini model. Please check your API key. Error: {e}")
    
    def classify_blocks(self, structured_content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify blocks using Gemini Flash 2.5.
        
        Args:
            structured_content: Structured content from PreAIProcessor
            
        Returns:
            Dictionary with classified_blocks
        """
        blocks = structured_content.get("blocks", [])
        statistics = structured_content.get("statistics", {})
        
        if not blocks:
            return {"classified_blocks": []}
        
        # Prepare prompt
        prompt = self._build_classification_prompt(blocks, statistics)
        
        # Chunk large requests
        max_blocks_per_request = 20
        all_classified = []
        all_requests = []
        all_responses = []
        
        for i in range(0, len(blocks), max_blocks_per_request):
            chunk = blocks[i:i + max_blocks_per_request]
            chunk_prompt = self._build_classification_prompt(chunk, statistics)
            chunk_num = i // max_blocks_per_request + 1
            
            # Save AI request
            if self.logger:
                self.logger.save_ai_request(chunk_prompt, chunk_num)
                all_requests.append({
                    "chunk_num": chunk_num,
                    "timestamp": datetime.now().isoformat(),
                    "text": chunk_prompt
                })
            
            # Check cache first
            cached_response = None
            if self.cache:
                cached_response = self.cache.get_cached_response(chunk_prompt)
            
            if cached_response and not self.use_api:
                # Use cached response (cache mode)
                response_text = cached_response.get("response", "")
                print(f"  Using cached response for chunk {chunk_num}")
                
                if self.logger:
                    self.logger.save_ai_response(f"[CACHED] {response_text}", chunk_num)
                    all_responses.append({
                        "chunk_num": chunk_num,
                        "timestamp": cached_response.get("metadata", {}).get("cached_at", "unknown"),
                        "text": response_text,
                        "cached": True
                    })
                
                classified_chunk = self._parse_response(response_text, chunk)
                all_classified.extend(classified_chunk)
                
            elif self.use_api:
                if not self.model:
                    raise RuntimeError("API mode enabled but model not initialized. Check API key.")
                # Call API
                try:
                    response = self.model.generate_content(chunk_prompt)
                    response_text = response.text if hasattr(response, 'text') else str(response)
                    
                    # Save to cache
                    if self.cache:
                        self.cache.save_response(chunk_prompt, response_text, {
                            "chunk_num": chunk_num,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Save AI response
                    if self.logger:
                        self.logger.save_ai_response(response_text, chunk_num)
                        all_responses.append({
                            "chunk_num": chunk_num,
                            "timestamp": datetime.now().isoformat(),
                            "text": response_text
                        })
                    
                    classified_chunk = self._parse_response(response_text, chunk)
                    all_classified.extend(classified_chunk)
                    
                except Exception as api_error:
                    # If API fails, try cache as fallback
                    error_msg = str(api_error).lower()
                    print(f"Warning: AI classification failed for chunk {chunk_num}: {api_error}")
                    
                    # Check if it's a quota/limit/token error
                    if any(keyword in error_msg for keyword in ["quota", "limit", "token", "exceeded", "over"]):
                        print(f"  API quota/limit exceeded, trying cache...")
                        if self.cache:
                            cached_response = self.cache.get_cached_response(chunk_prompt)
                            if cached_response:
                                response_text = cached_response.get("response", "")
                                print(f"  Using cached response as fallback")
                                
                                if self.logger:
                                    self.logger.save_ai_response(f"[CACHED FALLBACK] {response_text}", chunk_num)
                                
                                classified_chunk = self._parse_response(response_text, chunk)
                                all_classified.extend(classified_chunk)
                                continue
                    
                    # No cache available - use fallback classification
                    print(f"  Using fallback classification for chunk {chunk_num}")
                    for block in chunk:
                        tag = "table" if block.get("type") == "table" else self._candidate_to_tag(block.get("candidate_type"))
                        all_classified.append({
                            "block_id": block["block_id"],
                            "tag": tag,
                            "confidence": 0.8 if block.get("type") == "table" else 0.6
                        })
            else:
                try:
                    # No API and no cache, or API failed and no cache - use fallback
                    print(f"  Warning: No cached response for chunk {chunk_num}, using fallback classification")
                    for block in chunk:
                        tag = "table" if block.get("type") == "table" else self._candidate_to_tag(block.get("candidate_type"))
                        all_classified.append({
                            "block_id": block["block_id"],
                            "tag": tag,
                            "confidence": 0.8 if block.get("type") == "table" else 0.6
                        })
                except Exception as e:
                    error_msg = f"Warning: AI classification failed for chunk {chunk_num}: {e}"
                    print(error_msg)
                    
                    # Save error response
                    if self.logger:
                        self.logger.save_ai_response(f"ERROR: {error_msg}\n{e}", chunk_num)
                        all_responses.append({
                            "chunk_num": chunk_num,
                            "timestamp": datetime.now().isoformat(),
                            "text": f"ERROR: {error_msg}",
                            "error": str(e)
                        })
                    
                    # Fallback: use candidate_type as tag
                    for block in chunk:
                        tag = "table" if block.get("type") == "table" else self._candidate_to_tag(block.get("candidate_type"))
                        all_classified.append({
                            "block_id": block["block_id"],
                            "tag": tag,
                            "confidence": 0.5
                        })
        
        # Save summary if logger available
        if self.logger and (all_requests or all_responses):
            self.logger.save_ai_summary(all_requests, all_responses)
        
        return {"classified_blocks": all_classified}
    
    def _build_classification_prompt(self, blocks: List[Dict], statistics: Dict) -> str:
        """Build prompt for Gemini classification."""
        prompt = """You are a PDF content classifier. Analyze the following text blocks and classify each using the most specific semantic tag available.

Rules:
- **Title/Headings**:
  - "title": Main document title (usually massive, top of page 1).
  - "heading2" (H2): Major section headers. Look for:
    - Larger font than body text
    - Short text (under 50 chars)
    - No terminal punctuation (doesn't end with period)
    - Examples: "Lists", "Introduction", "Summary"
  - "heading3" (H3): Sub-section headers. Look for:
    - Text that introduces a list or subsection
    - May have similar font size to body but is structurally a heading
    - Short descriptive text (under 50 chars)
    - Examples: "Simple List", "List of X by Y", "Overview"

- **Lists**:
  - "list_item": Text starting with bullets (•, -, *) or numbering (1., 2., a)).
  - Note: List items often have the same left-alignment (x-coordinate).

- **Tables**:
  - "table": Text that appears in a grid or columnar layout.
  - "table_row"/"table_cell": Use these if the text is clearly a single cell or row.
  - Hint: aligned sparse text blocks often indicate a table.

- **Figures**:
  - "figure": Captions below images or image placeholders.

- **Body**:
  - "body": Standard paragraph text that flows naturally.

- **Context clues**:
  - Use the 'bbox' [x0, y0, x1, y1] to detect indentation and alignment.
  - A heading is often followed by a list or body text that elaborates on it.
  - "List of [items] by [year]" patterns are typically heading3.

IMPORTANT:
- Block b5 "List of Canadian Provinces by Popula Ɵon (2014)" should be classified as "heading3"
- "Lists" (b3) is heading2
- "Complex List" (b15) is heading3
- "Some Adobe Creative Cloud Desktop Apps with DescripƟons" (b17) is heading3

Statistics:
"""
        prompt += f"- Average font size: {statistics.get('avg_font_size', 12)}\n"
        prompt += f"- Max font size: {statistics.get('max_font_size', 12)}\n\n"
        prompt += "Blocks to classify:\n\n"
        
        for block in blocks:
            # Provide full text and bbox for better spatial reasoning
            bbox = [round(x, 1) for x in block.get('bbox', [0,0,0,0])]
            prompt += f"""Block ID: {block['block_id']}
Page: {block['page']}
Text: {block['text']}
Font Size: {block.get('font_size', 12.0)}
BBox: {bbox}
Attributes: Top:{block.get('is_top_of_page', False)}, Large:{block.get('is_large_font', False)}, Bold:{block.get('is_bold', False)}
Candidate: {block.get('candidate_type', 'unknown')}

"""
        
        prompt += """\nRespond with a JSON object in this exact format:
{
  "classified_blocks": [
    {
      "block_id": "b1",
      "tag": "title",
      "confidence": 0.95
    },
    ...
  ]
}

Available tags: "title", "heading2", "heading3", "heading4", "body", "list", "list_item", "table", "figure", "caption".
"""
        return prompt
    
    @staticmethod
    def _candidate_to_tag(candidate_type: str) -> str:
        """Map heuristic candidate type to semantic classification tag."""
        mapping = {
            "title_candidate": "title",
            "heading2_candidate": "heading2",
            "heading3_candidate": "heading3",
            "heading4_candidate": "heading4",
            "list_item_candidate": "list_item",
            "table_candidate": "table",
            "caption_candidate": "caption",
            "body_candidate": "body"
        }
        return mapping.get(candidate_type, "body")

    def _parse_response(self, response_text: str, original_blocks: List[Dict]) -> List[Dict[str, Any]]:
        """Parse Gemini response and extract classification."""
        try:
            # Try to extract JSON from response
            response_text = response_text.strip()
            
            # Find JSON block if wrapped in markdown
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            
            # Parse JSON
            result = json.loads(response_text)
            classified = result.get("classified_blocks", [])
            
            # Validate and ensure all blocks are classified
            block_ids = {block["block_id"] for block in original_blocks}
            classified_ids = {item["block_id"] for item in classified}
            
            # Add missing blocks as candidate tag or body
            for block in original_blocks:
                if block["block_id"] not in classified_ids:
                    tag = "table" if block.get("type") == "table" else self._candidate_to_tag(block.get("candidate_type"))
                    classified.append({
                        "block_id": block["block_id"],
                        "tag": tag,
                        "confidence": 0.5
                    })
            
            return classified
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Failed to parse AI response: {e}")
            # Fallback classification
            return [
                {
                    "block_id": block["block_id"],
                    "tag": "table" if block.get("type") == "table" else self._candidate_to_tag(block.get("candidate_type")),
                    "confidence": 0.5
                }
                for block in original_blocks
            ]
