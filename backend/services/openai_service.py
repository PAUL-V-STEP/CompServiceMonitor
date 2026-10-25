"""
Сервис анализа услуг ТО через ProxyAPI (OpenAI-совместимый API).
"""
import json
import re
import time
import logging
from typing import Optional

import httpx2
from openai import OpenAI, AuthenticationError, APIStatusError, APIConnectionError, APITimeoutError

from backend.config import settings
from backend.models.schemas import ServiceAnalysis, ImageAnalysis
from backend.prompts import (
    TEXT_SYSTEM_PROMPT,
    IMAGE_SYSTEM_PROMPT,
    WEBSITE_SYSTEM_PROMPT,
    USER_TEXT_PREFIX,
    USER_IMAGE_PREFIX,
    USER_WEBSITE_PREFIX,
)

logger = logging.getLogger("compservice.openai")


class OpenAIService:
    """Анализ текстов, изображений и сайтов услуг ТО."""

    def __init__(self):
        logger.info("Инициализация OpenAI-сервиса")
        logger.info("  Base URL: %s", settings.proxy_api_base_url)
        logger.info("  Модель текста: %s", settings.openai_model)
        logger.info("  Модель vision: %s", settings.openai_vision_model)
        key_tail = settings.proxy_api_key[-4:] if settings.proxy_api_key else "НЕ ЗАДАН"
        logger.info("  API ключ: **********...%s готов=%s", key_tail, settings.api_key_ready)
        if not settings.api_key_ready:
            logger.warning("PROXY_API_KEY пустой или это шаблон из env.example — запросы к ProxyAPI дадут 401")

        # IPv4 + раздельный timeout: DNS уже ок, часто зависает именно TLS handshake
        timeout = httpx2.Timeout(120.0, connect=30.0)
        transport = httpx2.HTTPTransport(local_address="0.0.0.0", retries=1)
        http_client = httpx2.Client(
            timeout=timeout,
            transport=transport,
            trust_env=True,
            follow_redirects=True,
        )
        self.client = OpenAI(
            api_key=settings.proxy_api_key,
            base_url=settings.proxy_api_base_url,
            http_client=http_client,
            timeout=timeout,
            max_retries=1,
        )
        self.model = settings.openai_model
        self.vision_model = settings.openai_vision_model
        logger.info("OpenAI-сервис готов")

    def _parse_json_response(self, content: str) -> dict:
        logger.debug("Парсинг JSON, длина ответа: %s", len(content or ""))
        if not content:
            logger.warning("Пустой ответ модели")
            return {}

        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if json_match:
            content = json_match.group(1)
            logger.debug("JSON извлечён из markdown-блока")

        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            content = json_match.group(0)
            logger.debug("JSON-объект найден в тексте")

        try:
            result = json.loads(content)
            logger.debug("JSON разобран, ключи: %s", list(result.keys()))
            return result
        except json.JSONDecodeError:
            logger.exception("Не удалось разобрать JSON. Фрагмент: %s", content[:400])
            return {}

    def _exception_chain(self, exc: BaseException) -> str:
        parts = []
        current: BaseException | None = exc
        seen = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            parts.append(f"{type(current).__name__}: {current}")
            current = current.__cause__
        return " | ".join(parts)

    def _raise_api_error(self, exc: Exception) -> None:
        chain = self._exception_chain(exc)
        logger.error("Цепочка ошибки ProxyAPI: %s", chain)
        if isinstance(exc, AuthenticationError):
            raise RuntimeError(
                "ProxyAPI отклонил ключ (401 Invalid API Key). "
                "Проверьте PROXY_API_KEY в .env и перезапустите сервер."
            ) from exc
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            lowered = chain.lower()
            if "11001" in lowered or "getaddrinfo" in lowered:
                raise RuntimeError(
                    "Не удалось разрешить имя api.proxyapi.ru (DNS, Windows 11001). "
                    "Проверьте интернет, DNS (например 1.1.1.1) и VPN, затем повторите запрос."
                ) from exc
            if "handshake" in lowered:
                raise RuntimeError(
                    "Таймаут TLS-рукопожатия с api.proxyapi.ru. "
                    "DNS работает, но HTTPS режется сетью, VPN или файрволом. "
                    "Проверьте, открывается ли https://proxyapi.ru в браузере."
                ) from exc
            if "timed out" in lowered or "timeout" in lowered:
                raise RuntimeError(
                    "Таймаут соединения с api.proxyapi.ru. "
                    "Хост может быть недоступен из-за сети, файрвола или VPN."
                ) from exc
            raise RuntimeError(
                "Нет соединения с ProxyAPI (api.proxyapi.ru). "
                "Проверьте интернет, DNS и что сайт proxyapi.ru открывается в браузере."
            ) from exc
        if isinstance(exc, APIStatusError):
            raise RuntimeError(f"Ошибка ProxyAPI HTTP {exc.status_code}: {exc.message}") from exc
        raise RuntimeError(f"Ошибка обращения к ProxyAPI: {exc}") from exc

    def _log_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if not usage:
            logger.debug("usage токенов недоступен")
            return
        logger.info(
            "  Токены: prompt=%s completion=%s total=%s",
            getattr(usage, "prompt_tokens", "N/A"),
            getattr(usage, "completion_tokens", "N/A"),
            getattr(usage, "total_tokens", "N/A"),
        )

    def _to_service_analysis(self, data: dict) -> ServiceAnalysis:
        score = data.get("overall_score", 0)
        try:
            score = int(score)
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(10, score))
        result = ServiceAnalysis(
            service_types=data.get("service_types", []) or [],
            equipment_coverage=data.get("equipment_coverage", []) or [],
            sla_and_process=data.get("sla_and_process", []) or [],
            pricing_notes=data.get("pricing_notes", []) or [],
            strengths=data.get("strengths", []) or [],
            gaps=data.get("gaps", []) or data.get("weaknesses", []) or [],
            recommendations=data.get("recommendations", []) or [],
            overall_score=score,
            summary=data.get("summary", "") or "",
        )
        logger.info(
            "  Разбор: услуг=%s техника=%s SLA=%s цены=%s сильные=%s пробелы=%s рекомендации=%s оценка=%s/10",
            len(result.service_types),
            len(result.equipment_coverage),
            len(result.sla_and_process),
            len(result.pricing_notes),
            len(result.strengths),
            len(result.gaps),
            len(result.recommendations),
            result.overall_score,
        )
        return result

    async def analyze_text(self, text: str) -> ServiceAnalysis:
        logger.info("===== АНАЛИЗ ТЕКСТА УСЛУГ ТО =====")
        logger.info("  Длина: %s символов", len(text))
        logger.info("  Превью: %s", text[:120].replace("\n", " "))
        logger.info("  Модель: %s", self.model)

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": TEXT_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{USER_TEXT_PREFIX}{text}"},
                ],
                temperature=0.4,
                max_tokens=2500,
            )
            elapsed = time.time() - start_time
            content = response.choices[0].message.content or ""
            logger.info("  Ответ получен за %.2f с, длина %s", elapsed, len(content))
            self._log_usage(response)
            return self._to_service_analysis(self._parse_json_response(content))
        except Exception as exc:
            logger.error("Ошибка анализа текста за %.2f с: %s", time.time() - start_time, exc)
            self._raise_api_error(exc)

    async def analyze_image(self, image_base64: str, mime_type: str = "image/jpeg") -> ImageAnalysis:
        logger.info("===== АНАЛИЗ ИЗОБРАЖЕНИЯ УСЛУГ ТО =====")
        logger.info("  MIME: %s, base64: %s символов", mime_type, len(image_base64))
        logger.info("  Модель: %s", self.vision_model)

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": IMAGE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER_IMAGE_PREFIX},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                            },
                        ],
                    },
                ],
                temperature=0.4,
                max_tokens=2200,
            )
            elapsed = time.time() - start_time
            content = response.choices[0].message.content or ""
            logger.info("  Ответ Vision за %.2f с, длина %s", elapsed, len(content))
            self._log_usage(response)
            data = self._parse_json_response(content)
            score = data.get("visual_quality_score", 0)
            try:
                score = int(score)
            except (TypeError, ValueError):
                score = 0
            result = ImageAnalysis(
                description=data.get("description", "") or "",
                detected_services=data.get("detected_services", []) or [],
                equipment_shown=data.get("equipment_shown", []) or [],
                communication_quality=data.get("communication_quality", "") or "",
                visual_quality_score=max(0, min(10, score)),
                visual_quality_analysis=data.get("visual_quality_analysis", "") or "",
                recommendations=data.get("recommendations", []) or [],
            )
            logger.info(
                "  Визуал: оценка=%s/10 услуг=%s техника=%s",
                result.visual_quality_score,
                len(result.detected_services),
                len(result.equipment_shown),
            )
            return result
        except Exception as exc:
            logger.error("Ошибка Vision API за %.2f с: %s", time.time() - start_time, exc)
            self._raise_api_error(exc)

    async def analyze_parsed_content(
        self,
        title: Optional[str],
        h1: Optional[str],
        paragraph: Optional[str],
    ) -> ServiceAnalysis:
        logger.info("Анализ извлечённого текста сайта ТО")
        logger.info("  Title: %s", (title or "N/A")[:80])
        logger.info("  H1: %s", (h1 or "N/A")[:80])
        logger.info("  Абзац: %s", (paragraph or "N/A")[:80])

        parts = []
        if title:
            parts.append(f"Заголовок страницы (title): {title}")
        if h1:
            parts.append(f"Главный заголовок (H1): {h1}")
        if paragraph:
            parts.append(f"Первый абзац: {paragraph}")
        combined = "\n\n".join(parts)
        if not combined.strip():
            logger.warning("Пустой контент сайта, анализ невозможен")
            return ServiceAnalysis(summary="Не удалось извлечь описание услуг ТО с сайта")
        return await self.analyze_text(combined)

    async def analyze_website_screenshot(
        self,
        screenshot_base64: str,
        url: str,
        title: Optional[str] = None,
        h1: Optional[str] = None,
        first_paragraph: Optional[str] = None,
    ) -> ServiceAnalysis:
        logger.info("===== АНАЛИЗ САЙТА УСЛУГ ТО =====")
        logger.info("  URL: %s", url)
        logger.info("  Title: %s", (title or "N/A")[:80])
        logger.info("  H1: %s", (h1 or "N/A")[:80])
        logger.info("  Скриншот base64: %s символов", len(screenshot_base64))

        context_parts = [f"URL сайта: {url}"]
        if title:
            context_parts.append(f"Title: {title}")
        if h1:
            context_parts.append(f"H1: {h1}")
        if first_paragraph:
            context_parts.append(f"Текст на странице: {first_paragraph[:400]}")
        context = "\n".join(context_parts)
        logger.debug("Контекст сайта:\n%s", context)

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": WEBSITE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{USER_WEBSITE_PREFIX}{context}"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{screenshot_base64}"},
                            },
                        ],
                    },
                ],
                temperature=0.4,
                max_tokens=3000,
            )
            elapsed = time.time() - start_time
            content = response.choices[0].message.content or ""
            logger.info("  Ответ Vision за %.2f с, длина %s", elapsed, len(content))
            self._log_usage(response)
            return self._to_service_analysis(self._parse_json_response(content))
        except Exception as exc:
            logger.error("Ошибка анализа сайта за %.2f с: %s", time.time() - start_time, exc)
            self._raise_api_error(exc)


logger.info("Создание глобального экземпляра OpenAI-сервиса")
openai_service = OpenAIService()
