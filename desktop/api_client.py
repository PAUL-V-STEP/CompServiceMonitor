"""
API клиент desktop-приложения анализа услуг ТО.
"""
import logging
import time
from typing import Dict, Any

import requests

logger = logging.getLogger("compservice.desktop.api")


class APIClient:
    """Клиент для работы с API backend."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.timeout = 120
        logger.info("APIClient base_url=%s timeout=%s", base_url, self.timeout)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("timeout", self.timeout)
        logger.info("HTTP %s %s", method, url)
        started = time.time()
        try:
            response = requests.request(method, url, **kwargs)
            elapsed = time.time() - started
            logger.info("HTTP %s %s -> %s за %.2f с", method, endpoint, response.status_code, elapsed)
            response.raise_for_status()
            data = response.json()
            logger.debug("Ответ keys=%s", list(data.keys()) if isinstance(data, dict) else type(data))
            return data
        except requests.exceptions.ConnectionError:
            logger.exception("Нет соединения с backend %s", url)
            return {"success": False, "error": "Не удалось подключиться к серверу. Убедитесь, что backend запущен."}
        except requests.exceptions.Timeout:
            logger.exception("Timeout %s %s", method, url)
            return {"success": False, "error": "Превышено время ожидания ответа от сервера."}
        except requests.exceptions.HTTPError as e:
            logger.exception("HTTP ошибка %s", e)
            return {"success": False, "error": f"HTTP ошибка: {e}"}
        except Exception as e:
            logger.exception("Неизвестная ошибка API")
            return {"success": False, "error": str(e)}
    
    def check_health(self) -> bool:
        """Проверить доступность сервера"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Анализ описания услуг ТО."""
        logger.info("analyze_text len=%s", len(text))
        return self._request(
            "POST",
            "/analyze_text",
            json={"text": text}
        )
    
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Анализ визуала услуг ТО."""
        logger.info("analyze_image path=%s", image_path)
        try:
            with open(image_path, 'rb') as f:
                files = {'file': (image_path.split('/')[-1], f, 'image/jpeg')}
                return self._request("POST", "/analyze_image", files=files)
        except FileNotFoundError:
            return {"success": False, "error": "Файл не найден"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def analyze_image_bytes(self, image_bytes: bytes, filename: str = "image.jpg") -> Dict[str, Any]:
        """Анализ изображения из bytes"""
        files = {'file': (filename, image_bytes, 'image/jpeg')}
        return self._request("POST", "/analyze_image", files=files)
    
    def parse_demo(self, url: str) -> Dict[str, Any]:
        """Парсинг и анализ сайта"""
        return self._request(
            "POST",
            "/parse_demo",
            json={"url": url}
        )
    
    def get_history(self) -> Dict[str, Any]:
        """Получить историю запросов"""
        return self._request("GET", "/history")
    
    def clear_history(self) -> Dict[str, Any]:
        """Очистить историю"""
        return self._request("DELETE", "/history")

    def get_parsed_sites(self) -> Dict[str, Any]:
        return self._request("GET", "/parsed_sites")

    def delete_parsed_site(self, site_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/parsed_sites/{site_id}")

    def clear_parsed_sites(self) -> Dict[str, Any]:
        return self._request("DELETE", "/parsed_sites")


# Глобальный экземпляр
api_client = APIClient()

