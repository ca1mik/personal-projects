"""
Speech-to-text модуль.
Преобразует голосовые сообщения в текст.

Поддерживает:
- Google Speech Recognition (через telegram - встроенная функция)
- Lokальное распознавание (если ffmpeg + numpy установлены)
"""

import asyncio
from pathlib import Path
from typing import Optional
import subprocess
import os

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False


async def transcribe_voice(voice_file_path: Path) -> tuple[bool, str]:
    """
    Транскрибирует голосовой файл в текст.
    
    Args:
        voice_file_path: Путь к файлу голоса (.ogg, .wav, etc)
        
    Returns:
        (success: bool, text: str)
    """
    if not SPEECH_RECOGNITION_AVAILABLE:
        return False, "❌ speech_recognition не установлен"
    
    try:
        # Преобразуем .ogg → .wav если нужно
        if voice_file_path.suffix.lower() == ".ogg":
            wav_path = voice_file_path.with_suffix(".wav")
            
            # Находим ffmpeg
            ffmpeg_paths = [
                r"C:\Users\koall\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffmpeg.exe",
                r"C:\ffmpeg\bin\ffmpeg.exe",
                "ffmpeg",
            ]
            
            ffmpeg_exe = None
            for path in ffmpeg_paths:
                if path == "ffmpeg" or os.path.exists(path):
                    ffmpeg_exe = path
                    break
            
            if not ffmpeg_exe:
                return False, "❌ ffmpeg не найден"
            
            # Используем subprocess для конвертации
            try:
                result = subprocess.run(
                    [ffmpeg_exe, "-i", str(voice_file_path), "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(wav_path), "-y"],
                    capture_output=True,
                    timeout=60,
                    text=True
                )
                
                if result.returncode != 0:
                    # ffmpeg не удалось конвертировать
                    error_text = result.stderr[:200] if result.stderr else "unknown error"
                    return False, f"❌ Ошибка конвертации: {error_text}"
                
                # Проверяем что файл создан
                if not wav_path.exists():
                    return False, "❌ WAV файл не создан"
                
                if wav_path.stat().st_size == 0:
                    return False, "❌ WAV файл пуст"
                
                audio_file = wav_path
            except subprocess.TimeoutExpired:
                return False, "❌ Конвертация заняла слишком долго"
            except Exception as e:
                return False, f"❌ Ошибка ffmpeg: {str(e)[:100]}"
        else:
            audio_file = voice_file_path
        
        # Распознавание речи
        try:
            recognizer = sr.Recognizer()
            
            # Читаем файл
            with sr.AudioFile(str(audio_file)) as source:
                # Для длинных файлов пробуем по частям
                audio = recognizer.record(source)
            
            # Google Speech Recognition
            try:
                text = recognizer.recognize_google(audio, language="ru-RU")
                return True, text
            except sr.UnknownValueError:
                return False, "❌ Не смог распознать речь"
            except sr.RequestError as e:
                return False, f"❌ Сервис недоступен: {str(e)[:50]}"
        except Exception as e:
            error = str(e)
            if "AudioFile" in error or "PCM" in error:
                return False, f"❌ Формат аудио не поддерживается: файл может быть повреждён"
            return False, f"❌ Ошибка обработки: {error[:100]}"
            
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)[:100]}"


def is_speech_recognition_available() -> bool:
    """Проверка доступности speech recognition"""
    return SPEECH_RECOGNITION_AVAILABLE
