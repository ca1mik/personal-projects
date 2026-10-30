"""
Модуль добавлен распознавания и анализа изображений.
- Извлечение EXIF данных (дата, геолокация)
- Анализ содержимого через Ollama vision
- Поиск по описанию и ключевым словам
"""

from pathlib import Path
from typing import Optional
import json
from datetime import datetime

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def extract_exif_data(image_path: Path) -> dict:
    """
    Извлекает EXIF данные из изображения
    """
    if not PIL_AVAILABLE:
        return {}
    
    try:
        image = Image.open(image_path)
        exif = image._getexif() if hasattr(image, '_getexif') else None
        
        if not exif:
            return {}
        
        data = {}
        for tag_id, value in exif.items():
            tag_name = TAGS.get(tag_id, tag_id)
            try:
                # Пропускаем очень большие данные
                if isinstance(value, bytes) and len(value) > 1000:
                    continue
                data[tag_name] = str(value)[:100]
            except Exception:
                pass
        
        return data
    except Exception:
        return {}


async def analyze_image_ollama(image_path: Path, query: str = "") -> tuple[bool, str]:
    """
    Анализирует изображение через Ollama vision
    Требует модели с поддержкой vision (например llava:7b или similar)
    """
    try:
        from src.tools.ollama_agent import test_ollama_available
        import requests
        
        if not test_ollama_available():
            return False, "Ollama недоступна"
        
        if not image_path.exists():
            return False, "Файл не найден"
        
        # Читаем изображение в base64
        import base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Определяем расширение
        suffix = image_path.suffix.lower()
        if suffix in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif suffix in [".png"]:
            media_type = "image/png"
        elif suffix in [".webp"]:
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"
        
        # Запрос к Ollama vision
        prompt = query or f"Опиши в деталях что ты видишь на этом фото. Кто на нём? Что происходит? Какие объекты?"
        
        payload = {
            "model": "llava:7b",  # или другая vision модель
            "prompt": prompt,
            "images": [image_data],
            "stream": False
        }
        
        try:
            resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
            if resp.status_code != 200:
                return False, f"Ollama ошибка: {resp.status_code}"
            
            result = resp.json()
            response_text = result.get("response", "")
            return True, response_text.strip()
        except requests.exceptions.RequestException as e:
            return False, f"Ошибка подключения: {str(e)[:100]}"
        except Exception as e:
            return False, f"Ошибка Ollama: {str(e)[:100]}"
    
    except Exception as e:
        return False, f"Ошибка анализа: {str(e)[:100]}"


def get_image_keywords(image_path: Path) -> list[str]:
    """
    Извлекает ключевые слова из имени и EXIF
    """
    keywords = []
    
    # Из имени файла
    name_without_ext = image_path.stem.lower()
    # Разбиваем на слова по _, -, пробелу
    import re
    words = re.split(r'[_\-\s]+', name_without_ext)
    keywords.extend([w for w in words if len(w) > 2])
    
    # Из EXIF
    exif = extract_exif_data(image_path)
    if exif.get("DateTime"):
        keywords.append(exif["DateTime"][:10])  # дата
    
    return list(set(keywords))


def find_images_by_description(search_dir: Path, description: str, max_results: int = 10) -> list[dict]:
    """
    Ищет фото по описанию (сначала по имени, потом по EXIF, опционально по анализу Ollama)
    """
    from pathlib import Path
    import os
    
    PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
    EXCLUDED_DIRS = {"$RECYCLE.BIN", "System Volume Information", ".git", "__pycache__"}
    
    results = []
    description_lower = description.lower()
    
    try:
        for root, dirs, files in os.walk(search_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            
            for filename in files:
                if Path(filename).suffix.lower() not in PHOTO_EXTENSIONS:
                    continue
                
                filepath = Path(root) / filename
                keywords = get_image_keywords(filepath)
                
                # Простой поиск по ключевым словам
                if any(desc_word in keywords for desc_word in description_lower.split()):
                    results.append({
                        "path": str(filepath),
                        "name": filename,
                        "keywords": keywords,
                        "score": 100
                    })
                    if len(results) >= max_results:
                        return results
        
        # Если мало результатов, ищем по простому совпадению имени
        if len(results) < max_results // 2:
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                
                for filename in files:
                    if Path(filename).suffix.lower() not in PHOTO_EXTENSIONS:
                        continue
                    
                    if description_lower in filename.lower():
                        filepath = Path(root) / filename
                        if not any(r["path"] == str(filepath) for r in results):
                            results.append({
                                "path": str(filepath),
                                "name": filename,
                                "keywords": get_image_keywords(filepath),
                                "score": 50
                            })
                            if len(results) >= max_results:
                                return results
    
    except Exception as e:
        pass
    
    return results

