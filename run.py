"""
Точка входа запуска визуальной новеллы «Мира».
Запуск: python run.py
"""
import os
import sys
import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    
    print("=" * 60)
    print("  🎭 Визуальная новелла «Мира» — Эмоциональный ИИ")
    print("=" * 60)
    print(f"  • Локальный адрес: http://{host}:{port}")
    print(f"  • API документация Swagger: http://{host}:{port}/docs")
    print(f"  • Базовый URL модели: {os.environ.get('AI_BASE_URL', 'http://localhost:11434/v1')}")
    print(f"  • Имя модели: {os.environ.get('AI_MODEL', 'qwen2.5:3b')}")
    print("=" * 60)
    print("Нажмите Ctrl+C для завершения работы сервера.\n")
    
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
