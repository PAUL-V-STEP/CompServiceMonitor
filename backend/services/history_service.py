"""
История запросов анализа услуг ТО.
"""
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from backend.config import settings
from backend.models.schemas import HistoryItem

logger = logging.getLogger("compservice.history")


class HistoryService:
    def __init__(self):
        logger.info("Инициализация History-сервиса")
        self.history_file = Path(settings.history_file)
        self.max_items = settings.max_history_items
        logger.info("  Файл: %s, лимит: %s", self.history_file.resolve(), self.max_items)
        self._ensure_file_exists()
        logger.info("  Текущих записей: %s", len(self._load_history()))

    def _ensure_file_exists(self):
        if not self.history_file.exists():
            logger.info("Создание пустого файла истории: %s", self.history_file)
            self.history_file.write_text("[]", encoding="utf-8")

    def _load_history(self) -> List[dict]:
        try:
            history = json.loads(self.history_file.read_text(encoding="utf-8"))
            logger.debug("История загружена: %s записей", len(history))
            return history
        except json.JSONDecodeError:
            logger.exception("Повреждён JSON истории, возвращаю пустой список")
            return []
        except FileNotFoundError:
            logger.warning("Файл истории не найден: %s", self.history_file)
            return []

    def _save_history(self, history: List[dict]):
        logger.debug("Сохранение истории: %s записей -> %s", len(history), self.history_file)
        self.history_file.write_text(
            json.dumps(history, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def add_entry(self, request_type: str, request_summary: str, response_summary: str) -> HistoryItem:
        logger.info(
            "Новая запись истории type=%s request=%s response=%s",
            request_type,
            request_summary[:80],
            response_summary[:80],
        )
        history = self._load_history()
        item = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "request_type": request_type,
            "request_summary": request_summary[:200],
            "response_summary": response_summary[:500],
        }
        history.insert(0, item)
        trimmed = history[: self.max_items]
        if len(history) > len(trimmed):
            logger.info("Обрезаны старые записи: %s", len(history) - len(trimmed))
        self._save_history(trimmed)
        logger.info("Запись сохранена id=%s, всего=%s", item["id"], len(trimmed))
        return HistoryItem(**item)

    def get_history(self) -> List[HistoryItem]:
        history = self._load_history()
        logger.info("Чтение истории: %s записей", len(history))
        return [HistoryItem(**item) for item in history]

    def clear_history(self):
        count = len(self._load_history())
        logger.info("Очистка истории, удаляется %s записей", count)
        self._save_history([])


logger.info("Создание глобального экземпляра History-сервиса")
history_service = HistoryService()
