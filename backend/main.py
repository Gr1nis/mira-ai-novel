"""
FastAPI сервер визуальной новеллы «Мира» (backend/main.py).
Предоставляет REST API для диалога с эмоциональным ИИ-персонажем
и раздаёт веб-интерфейс из папки frontend.
"""
import os
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.prompts import (
    MIRA_SYSTEM_PROMPT,
    VALID_EMOTIONS,
    DEFAULT_EMOTION,
    build_messages_payload,
    trim_history
)
from backend.network import (
    send_chat_completion,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_API_KEY,
    DEFAULT_TIMEOUT,
    LLMTimeoutException,
    LLMConnectionException,
    LLMResponseException,
    LLMNetworkException,
)
from backend.parser import parse_model_response

app = FastAPI(
    title="Mira Emotional AI Novel API",
    description="Интерактивная визуальная новелла с эмоциональным ИИ-персонажем",
    version="1.0.0"
)

# CORS для локальной разработки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MessageItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="Реплика пользователя (не может быть пустой)")
    history: List[MessageItem] = Field(default_factory=list, description="История диалога")
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = 0.7


class ChatResponse(BaseModel):
    emotion: str
    reply: str
    fallback_applied: bool
    error_detail: Optional[str] = None
    history: List[MessageItem]


@app.get("/api/health")
def health_check():
    """Проверка доступности бэкенда."""
    return {
        "status": "ok",
        "character": "Mira",
        "default_model": DEFAULT_MODEL,
        "default_base_url": DEFAULT_BASE_URL
    }


@app.get("/api/config")
def get_config():
    """Возвращает настройки по умолчанию и поддерживаемые эмоции."""
    return {
        "default_base_url": DEFAULT_BASE_URL,
        "default_model": DEFAULT_MODEL,
        "valid_emotions": sorted(list(VALID_EMOTIONS)),
        "max_history_length": 10,
        "character_name": "Мира",
        "character_desc": "24 года, студентка-художница"
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Основной эндпоинт отправки реплики персонажу.
    1. Валидация пустого ввода.
    2. Добавление реплики в историю.
    3. Ограничение скользящего окна (последние 10 реплик).
    4. Запрос к LLM с системным промптом Миры.
    5. Безопасный парсинг JSON-контракта с fallback в neutral.
    """
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Реплика пользователя не может быть пустой."
        )

    # Формируем историю
    raw_history = [{"role": item.role, "content": item.content} for item in req.history]
    raw_history.append({"role": "user", "content": user_text})
    bounded_history = trim_history(raw_history, max_length=10)

    # Параметры подключения
    base_url = req.base_url.strip() if req.base_url else DEFAULT_BASE_URL
    model = req.model.strip() if req.model else DEFAULT_MODEL
    api_key = req.api_key.strip() if req.api_key else DEFAULT_API_KEY
    temperature = req.temperature if req.temperature is not None else 0.7

    messages_payload = build_messages_payload(bounded_history, MIRA_SYSTEM_PROMPT)

    try:
        raw_llm_response = send_chat_completion(
            messages=messages_payload,
            base_url=base_url,
            model=model,
            api_key=api_key,
            temperature=temperature,
            timeout=DEFAULT_TIMEOUT
        )
    except LLMTimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc)
        )
    except LLMConnectionException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)
        )
    except LLMResponseException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{exc.detail} (HTTP {exc.status_code})"
        )
    except LLMNetworkException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        )

    parsed = parse_model_response(raw_llm_response)
    
    # Добавляем ответ ассистента в историю
    assistant_content = parsed["reply"]
    bounded_history.append({"role": "assistant", "content": assistant_content})

    return ChatResponse(
        emotion=parsed["emotion"],
        reply=parsed["reply"],
        fallback_applied=parsed["fallback_applied"],
        error_detail=parsed["error_detail"],
        history=[MessageItem(**item) for item in bounded_history]
    )


# Монтируем статический фронтенд, если директория существует
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
