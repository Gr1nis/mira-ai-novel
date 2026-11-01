"""
Сетевой слой взаимодействия с языковой моделью (backend/network.py).
Поддерживает любой OpenAI-совместимый API (Ollama, LM Studio, OpenRouter, Groq).
Корректно обрабатывает таймауты, обрывы сети, HTTP-статусы и отсутствие соединения.
"""
import os
import requests
from typing import List, Dict, Any, Optional

DEFAULT_BASE_URL = os.environ.get("AI_BASE_URL", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("AI_MODEL", "qwen2.5:3b")
DEFAULT_API_KEY = os.environ.get("AI_API_KEY", "ollama")
DEFAULT_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "60"))


class LLMNetworkException(Exception):
    """Базовое исключение сетевого слоя LLM."""
    pass


class LLMTimeoutException(LLMNetworkException):
    """Исключение при превышении лимита ожидания ответа модели."""
    pass


class LLMConnectionException(LLMNetworkException):
    """Исключение при невозможности установить соединение с сервером."""
    pass


class LLMResponseException(LLMNetworkException):
    """Исключение при ошибочном HTTP-статусе от сервера."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"Ошибка API ({status_code}): {detail}")
        self.status_code = status_code
        self.detail = detail


def send_chat_completion(
    messages: List[Dict[str, str]],
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    api_key: str = DEFAULT_API_KEY,
    temperature: float = 0.7,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Отправляет POST-запрос на /chat/completions и возвращает сырой текст ответа модели.
    
    :param messages: Список сообщений с ролями [{"role": "system"|"user"|"assistant", "content": "..."}]
    :param base_url: Базовый URL API (например, http://localhost:11434/v1)
    :param model: Имя модели (например, qwen2.5:3b, llama3.2:3b)
    :param api_key: Токен авторизации (для Ollama - любое непустое слово)
    :param temperature: Температура генерации (0.0 - 1.0)
    :param timeout: Таймаут запроса в секундах
    :return: Сырой строковый контент из choices[0].message.content
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "Bearer ollama",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        
        choices = data.get("choices", [])
        if not choices:
            raise LLMResponseException(response.status_code, "Пустой список 'choices' в ответе сервера")
        
        message = choices[0].get("message", {})
        content = message.get("content", "")
        return content

    except requests.exceptions.Timeout as exc:
        raise LLMTimeoutException(f"Сервер не ответил за {timeout} секунд. Возможно, модель слишком нагружена.") from exc
    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
        raise LLMConnectionException(
            f"Не удалось подключиться к серверу по адресу {base_url}. Убедитесь, что служба Ollama запущена."
        ) from exc
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 500
        text = exc.response.text if exc.response is not None else str(exc)
        raise LLMResponseException(status, text) from exc
    except Exception as exc:
        raise LLMNetworkException(f"Непредвиденная сетевая ошибка: {str(exc)}") from exc
