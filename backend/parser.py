"""
Слой разбора ответа модели (backend/parser.py).
Очистка Markdown-блоков, безопасный парсинг JSON, валидация полей
и гарантированный fallback в neutral при любых непредвиденных ошибках.
"""
import re
import json
from typing import Dict, Any, Tuple
from backend.prompts import VALID_EMOTIONS, DEFAULT_EMOTION


def clean_markdown_fences(raw_text: str) -> str:
    """Удаляет markdown-разметку ```json ... ``` или ``` ... ```."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    
    # Удаляем тройные кавычки с префиксом json или без
    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fenced_match:
        return fenced_match.group(1).strip()
    
    # Если кавычки не закрыты или одинарные
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json_object(text: str) -> str:
    """Находит первое включение JSON-объекта {...} в строке."""
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start : brace_end + 1]
    return text


def parse_model_response(raw_response: str) -> Dict[str, Any]:
    """
    Разбирает сырой текст ответа модели в структурированный контракт:
    {
        "emotion": "joy" | "sadness" | "anger" | "fear" | "disgust" | "surprise" | "neutral",
        "reply": str,
        "fallback_applied": bool,
        "error_detail": str | None
    }
    
    При ЛЮБОМ сбое автоматически переключается в neutral и спасает текст реплики.
    """
    if not raw_response or not raw_response.strip():
        return {
            "emotion": DEFAULT_EMOTION,
            "reply": "...",
            "fallback_applied": True,
            "error_detail": "Пустой ответ от модели"
        }

    cleaned = clean_markdown_fences(raw_response)
    json_candidate = extract_json_object(cleaned)

    try:
        data = json.loads(json_candidate)
        if not isinstance(data, dict):
            raise ValueError(f"Ожидался JSON-объект (dict), получено: {type(data).__name__}")
        
        reply = str(data.get("reply", "")).strip()
        raw_emotion = str(data.get("emotion", "")).strip().lower()

        # Если reply пустой внутри валидного json
        if not reply:
            reply = cleaned

        # Валидация эмоции
        if raw_emotion in VALID_EMOTIONS:
            emotion = raw_emotion
            fallback = False
            error = None
        else:
            emotion = DEFAULT_EMOTION
            fallback = True
            error = f"Неизвестная эмоция '{raw_emotion}', применён fallback в '{DEFAULT_EMOTION}'"

        return {
            "emotion": emotion,
            "reply": reply,
            "fallback_applied": fallback,
            "error_detail": error
        }

    except Exception as exc:
        # Модель вернула простой текст вместо JSON или поврежденный JSON
        # Спасаем очищенный текст как реплику, выставляем neutral
        salvaged_text = cleaned if cleaned else raw_response.strip()
        return {
            "emotion": DEFAULT_EMOTION,
            "reply": salvaged_text,
            "fallback_applied": True,
            "error_detail": f"Ошибка парсинга JSON ({type(exc).__name__}: {str(exc)}), текст спасён с эмоцией '{DEFAULT_EMOTION}'"
        }
