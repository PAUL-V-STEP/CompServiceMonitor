"""
Запуск анализатора услуг ТО компьютерной техники.
"""
import uvicorn
import logging
from backend.config import settings, logger

logging.getLogger("compservice").setLevel(logging.DEBUG)

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("ТО КОМПЬЮТЕРНОЙ ТЕХНИКИ — AI-анализ услуг")
    print("=" * 60)
    print()
    print(f"Веб-интерфейс:  http://localhost:{settings.api_port}")
    print(f"Документация:   http://localhost:{settings.api_port}/docs")
    print(f"ReDoc:          http://localhost:{settings.api_port}/redoc")
    print()
    print(f"Модель текста:  {settings.openai_model}")
    print(f"Модель vision:  {settings.openai_vision_model}")
    print(f"API ключ:       {'настроен' if settings.api_key_ready else 'НЕ ЗАДАН или шаблон из env.example'}")
    print(f"Лог-файл:       {settings.log_file}")
    print()
    logger.info("Старт uvicorn host=%s port=%s", settings.api_host, settings.api_port)
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
