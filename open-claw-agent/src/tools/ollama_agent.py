import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral:7b"  # Быстрая и качественная модель

async def ask_ollama(question: str, model: str = DEFAULT_MODEL) -> str:
    """
    Отправить вопрос в локальную Ollama и получить ответ.
    Returns: (success: bool, response: str)
    """
    payload = {
        "model": model,
        "prompt": question,
        "stream": False,
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("response", "")
        if not result:
            return False, "Empty response from Ollama"
        return True, result.strip()
    except requests.exceptions.ConnectionError:
        return False, "❌ Cannot connect to Ollama at localhost:11434. Is it running?"
    except requests.exceptions.Timeout:
        return False, "❌ Ollama request timed out (>5min)"
    except Exception as e:
        return False, f"❌ Ollama error: {e}"

def test_ollama_available() -> bool:
    """Check if Ollama is reachable"""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        return resp.status_code == 200
    except:
        return False
