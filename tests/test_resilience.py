"""
Комплексные тесты отказоустойчивости (tests/test_resilience.py).
Проверяют 4 обязательных сценария из методички:
1. Сетевые ошибки / недоступность сервера.
2. Невалидный, обрезанный или мусорный JSON от модели (проверка отката в neutral).
3. Пустой ввод пользователя (пробелы, переводы строк).
4. Таймаут запроса.
А также инвариант ограничения истории (10 сообщений) и контракты FastAPI эндпоинтов.
"""
import pytest
from unittest.mock import patch
import requests
from fastapi.testclient import TestClient

from backend.main import app
from backend.parser import parse_model_response, clean_markdown_fences
from backend.prompts import trim_history, build_messages_payload, MIRA_SYSTEM_PROMPT, DEFAULT_EMOTION
from backend.network import (
    send_chat_completion,
    LLMConnectionException,
    LLMTimeoutException,
    LLMResponseException
)

client = TestClient(app)


# ==========================================
# Сценарий 1: Сетевые ошибки и недоступность
# ==========================================
def test_scenario_network_connection_error():
    """Проверка обработки недоступности сервера Ollama/OpenRouter."""
    with patch("backend.network.requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        with pytest.raises(LLMConnectionException) as excinfo:
            send_chat_completion([{"role": "user", "content": "Привет"}], base_url="http://localhost:99999/v1")
        assert "Не удалось подключиться к серверу" in str(excinfo.value)

    # Проверка через REST API эндпоинт FastAPI
    with patch("backend.main.send_chat_completion") as mock_send:
        mock_send.side_effect = LLMConnectionException("Connection refused")
        res = client.post("/api/chat", json={"message": "Привет"})
        assert res.status_code == 503
        assert "Connection refused" in res.json()["detail"]


# ==========================================
# Сценарий 2: Невалидный или мусорный JSON
# ==========================================
def test_scenario_invalid_or_garbage_json():
    """Проверка отката в neutral и спасения текста при сбоях JSON от модели."""
    # 1. Мусорный текст без JSON
    raw_garbage = "Привет! Я просто хочу поболтать, вот мой ответ без всякого формата."
    res = parse_model_response(raw_garbage)
    assert res["emotion"] == DEFAULT_EMOTION
    assert res["fallback_applied"] is True
    assert "Привет!" in res["reply"]

    # 2. Markdown блок с валидным JSON
    fenced_json = "```json\n{\"emotion\": \"joy\", \"reply\": \"Отличная погода!\"}\n```"
    res = parse_model_response(fenced_json)
    assert res["emotion"] == "joy"
    assert res["reply"] == "Отличная погода!"
    assert res["fallback_applied"] is False

    # 3. Неизвестная/галлюцинированная моделью эмоция
    weird_emotion_json = '{"emotion": "super_mega_excited", "reply": "Ура!"}'
    res = parse_model_response(weird_emotion_json)
    assert res["emotion"] == DEFAULT_EMOTION
    assert res["fallback_applied"] is True
    assert res["reply"] == "Ура!"

    # 4. Обрезанный/незакрытый JSON
    broken_json = '{"emotion": "surprise", "reply": "Ого, я не договори'
    res = parse_model_response(broken_json)
    assert res["emotion"] == DEFAULT_EMOTION
    assert res["fallback_applied"] is True
    assert "Ого, я не договори" in res["reply"]


# ==========================================
# Сценарий 3: Пустой ввод пользователя
# ==========================================
def test_scenario_empty_user_input():
    """Проверка валидации пустого ввода пользователя (пробелы, табуляции)."""
    # Пустая строка
    res1 = client.post("/api/chat", json={"message": ""})
    assert res1.status_code == 400
    assert "не может быть пустой" in res1.json()["detail"]

    # Пробелы и переводы строк
    res2 = client.post("/api/chat", json={"message": "   \n\t  "})
    assert res2.status_code == 400

    # Разбор пустого ответа модели
    res_empty_model = parse_model_response("")
    assert res_empty_model["emotion"] == DEFAULT_EMOTION
    assert res_empty_model["fallback_applied"] is True


# ==========================================
# Сценарий 4: Таймаут
# ==========================================
def test_scenario_timeout():
    """Проверка обработки превышения времени ожидания ответа модели."""
    with patch("backend.network.requests.post") as mock_post:
        mock_post.side_effect = requests.exceptions.Timeout("Read timed out")
        with pytest.raises(LLMTimeoutException) as excinfo:
            send_chat_completion([{"role": "user", "content": "Тяжелый вопрос"}], timeout=1)
        assert "не ответил" in str(excinfo.value)

    # Проверка через REST API эндпоинт FastAPI
    with patch("backend.main.send_chat_completion") as mock_send:
        mock_send.side_effect = LLMTimeoutException("Сервер не ответил за 60 секунд.")
        res = client.post("/api/chat", json={"message": "Привет"})
        assert res.status_code == 504
        assert "не ответил за 60 секунд" in res.json()["detail"]


# ==========================================
# Инвариант: Ограничение истории (10 реплик)
# ==========================================
def test_sliding_history_window():
    """Проверка инварианта ограничения контекстного окна последними 10 репликами."""
    long_history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(25)]
    trimmed = trim_history(long_history, max_length=10)
    assert len(trimmed) == 10
    assert trimmed[0]["content"] == "msg 15"
    assert trimmed[-1]["content"] == "msg 24"

    # Проверка системного промпта
    payload = build_messages_payload(long_history, MIRA_SYSTEM_PROMPT)
    assert len(payload) == 11
    assert payload[0]["role"] == "system"
    assert "Ты - Мира" in payload[0]["content"]


# ==========================================
# Контракты эндпоинтов Health и Config
# ==========================================
def test_health_and_config_endpoints():
    """Проверка служебных эндпоинтов /api/health и /api/config."""
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_config = client.get("/api/config")
    assert res_config.status_code == 200
    data = res_config.json()
    assert "joy" in data["valid_emotions"]
    assert "neutral" in data["valid_emotions"]
    assert data["max_history_length"] == 10
