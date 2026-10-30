"""
Smart photo search using metadata and keywords.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image
from PIL.ExifTags import TAGS


def get_photo_metadata(file_path: str) -> dict:
    """Extract metadata from image file."""
    try:
        img = Image.open(file_path)
        exif_data = img._getexif() if hasattr(img, '_getexif') else None
        
        metadata = {
            "path": file_path,
            "size": img.size,
            "format": img.format,
            "created": None,
            "tags": []
        }
        
        if exif_data:
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "DateTime":
                    metadata["created"] = value
                    break
        
        if not metadata["created"]:
            stat = os.stat(file_path)
            metadata["created"] = datetime.fromtimestamp(stat.st_mtime)
        
        return metadata
    except Exception:
        return {"path": file_path, "created": None}


def match_photo_by_description(file_path: str, description: str) -> bool:
    """Check if photo matches description (basic heuristic)."""
    file_lower = file_path.lower()
    desc_lower = description.lower()
    
    # Keywords mapping
    keywords = {
        "девушка": ["girl", "woman", "female", "lady", "portrait"],
        "кот": ["cat", "kitten", "feline"],
        "собака": ["dog", "puppy", "canine"],
        "пейзаж": ["landscape", "nature", "scenery", "outdoor"],
        "природа": ["nature", "tree", "forest", "mountain", "water"],
        "город": ["city", "urban", "street", "building"],
        "море": ["beach", "sea", "ocean", "water"],
        "горы": ["mountain", "peak", "alpine"],
        "лес": ["forest", "tree", "wood"],
    }
    
    # Check if description matches any keywords
    for keyword, related_words in keywords.items():
        if keyword in desc_lower:
            # If we find the keyword, look for related words in filename or path
            if any(word in file_lower for word in related_words):
                return True
    
    # Direct matching
    if any(word in file_lower for word in desc_lower.split()):
        return True
    
    return False
