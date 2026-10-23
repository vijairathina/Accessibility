"""
Response Cache Module
Caches AI responses to avoid repeated API calls.
"""

import json
import hashlib
import os
from pathlib import Path
from typing import Dict, Any, Optional


class ResponseCache:
    """Manages caching of AI responses."""
    
    def __init__(self, cache_dir: str = "ai_cache"):
        """
        Initialize cache.
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_key(self, prompt: str) -> str:
        """Generate cache key from prompt."""
        return hashlib.md5(prompt.encode('utf-8')).hexdigest()
    
    def get_cached_response(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a prompt.
        
        Args:
            prompt: The prompt text
            
        Returns:
            Cached response dict or None if not found
        """
        cache_key = self._get_cache_key(prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not read cache file: {e}")
                return None
        return None
    
    def save_response(self, prompt: str, response: str, metadata: Dict[str, Any] = None):
        """
        Save response to cache.
        
        Args:
            prompt: The prompt text
            response: The AI response text
            metadata: Additional metadata to store
        """
        cache_key = self._get_cache_key(prompt)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        cache_data = {
            "prompt": prompt,
            "response": response,
            "metadata": metadata or {},
            "cached_at": __import__("datetime").datetime.now().isoformat()
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")
