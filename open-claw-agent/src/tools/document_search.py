"""
Модуль для поиска и анализа текста в документах.
- PDF: извлечение текста через pdfplumber или PyPDF2
- DOCX: извлечение текста через python-docx
- TXT: прямое чтение
- Полнотекстовый поиск
- Опционально: OCR для отсканированных PDF через pytesseract
"""

from pathlib import Path
from typing import Optional
import re

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False


def extract_text_from_pdf(pdf_path: Path) -> tuple[bool, str]:
    """
    Извлекает текст из PDF файла
    """
    if not PDFPLUMBER_AVAILABLE:
        return False, "pdfplumber не установлен"
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:50]:  # Ограничиваем первыми 50 страницами
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if not text.strip():
            return False, "PDF пуст или не читается"
        
        return True, text
    except Exception as e:
        return False, f"Ошибка PDF: {str(e)[:100]}"


def extract_text_from_docx(docx_path: Path) -> tuple[bool, str]:
    """
    Извлекает текст из DOCX файла
    """
    if not DOCX_AVAILABLE:
        return False, "python-docx не установлен"
    
    try:
        doc = Document(docx_path)
        text = ""
        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"
        
        if not text.strip():
            return False, "DOCX пуст или не читается"
        
        return True, text
    except Exception as e:
        return False, f"Ошибка DOCX: {str(e)[:100]}"


def extract_text_from_txt(txt_path: Path) -> tuple[bool, str]:
    """
    Читает обычный текстовый файл
    """
    try:
        text = txt_path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            return False, "TXT пуст"
        return True, text
    except Exception as e:
        return False, f"Ошибка TXT: {str(e)[:100]}"


def extract_text_from_document(doc_path: Path) -> tuple[bool, str]:
    """
    Распознаёт тип документа и извлекает текст
    """
    if not doc_path.exists():
        return False, "Файл не найден"
    
    suffix = doc_path.suffix.lower()
    
    if suffix == ".pdf":
        return extract_text_from_pdf(doc_path)
    elif suffix == ".docx":
        return extract_text_from_docx(doc_path)
    elif suffix == ".txt":
        return extract_text_from_txt(doc_path)
    else:
        return False, f"Неподдерживаемый формат: {suffix}"


def search_in_document(doc_path: Path, query: str) -> tuple[bool, list[dict]]:
    """
    Ищет совпадения слов в документе
    Возвращает список совпадений с контекстом
    """
    ok, text = extract_text_from_document(doc_path)
    if not ok:
        return False, []
    
    results = []
    lines = text.split("\n")
    query_lower = query.lower()
    
    for line_num, line in enumerate(lines):
        if query_lower in line.lower():
            results.append({
                "line": line_num + 1,
                "text": line.strip()[:200],
                "score": 100
            })
    
    # Если мало результатов, ищем по отдельным словам
    if len(results) < 5:
        query_words = query_lower.split()
        for line_num, line in enumerate(lines):
            line_lower = line.lower()
            matched_words = sum(1 for word in query_words if word in line_lower)
            if matched_words > 0:
                if not any(r["line"] == line_num + 1 for r in results):
                    results.append({
                        "line": line_num + 1,
                        "text": line.strip()[:200],
                        "score": matched_words * 30
                    })
    
    # Сортируем по скору
    results.sort(key=lambda r: r["score"], reverse=True)
    return True, results[:20]  # Вернули макс 20 совпадений


def find_documents_by_content(search_dir: Path, query: str, max_results: int = 10) -> list[dict]:
    """
    Ищет документы по содержимому текста
    """
    from pathlib import Path
    import os
    
    DOC_EXTENSIONS = {".pdf", ".docx", ".txt", ".rtf"}
    EXCLUDED_DIRS = {"$RECYCLE.BIN", "System Volume Information", ".git", "__pycache__"}
    
    results = []
    query_lower = query.lower()
    
    try:
        for root, dirs, files in os.walk(search_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            
            for filename in files:
                if Path(filename).suffix.lower() not in DOC_EXTENSIONS:
                    continue
                
                filepath = Path(root) / filename
                
                try:
                    ok, matches = search_in_document(filepath, query)
                    if ok and matches:
                        # Если нашли совпадения, добавляем документ
                        results.append({
                            "path": str(filepath),
                            "name": filename,
                            "matches_count": len(matches),
                            "preview": matches[0]["text"] if matches else "",
                            "score": sum(m["score"] for m in matches[:3]) / 3
                        })
                        
                        if len(results) >= max_results:
                            return results
                except Exception:
                    continue
    
    except Exception:
        pass
    
    # Сортируем по скору
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]


def get_document_summary(doc_path: Path, max_words: int = 500) -> tuple[bool, str]:
    """
    Выводит первые N слов из документа как краткое описание
    """
    ok, text = extract_text_from_document(doc_path)
    if not ok:
        return False, ok
    
    words = text.split()[:max_words]
    summary = " ".join(words)
    
    if len(words) == max_words:
        summary += "..."
    
    return True, summary

