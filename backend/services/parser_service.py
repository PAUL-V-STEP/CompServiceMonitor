"""
Парсинг одной страницы через headless Chrome: контент, скриншот и внутренние ссылки.
"""
import base64
import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from backend.config import settings

logger = logging.getLogger("compservice.parser")

BLOCKED_URL_PATTERNS = [
    "*google-analytics.com*",
    "*googletagmanager.com*",
    "*googleadservices.com*",
    "*doubleclick.net*",
    "*mc.yandex.ru*",
    "*mc.yandex.com*",
    "*metrika.yandex*",
    "*yandex.ru/metrika*",
    "*facebook.net*",
    "*facebook.com/tr*",
    "*vk.com/rtrg*",
    "*hotjar.com*",
    "*tawk.to*",
    "*jivosite.com*",
    "*bitrix24.ru*",
    "*bitrix.info*",
    "*calltouch.ru*",
    "*roistat.com*",
    "*mindbox.ru*",
    "*carrotquest.io*",
    "*usedesk.ru*",
]

SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".zip",
    ".doc", ".docx", ".xls", ".xlsx", ".mp4", ".mp3", ".css", ".js",
)

COLLECT_LINKS_JS = """
const origin = location.origin;
const items = [];
const seen = new Set();
const skip = ['.pdf','.jpg','.jpeg','.png','.gif','.webp','.svg','.zip','.doc','.docx','.xls','.xlsx','.mp4','.mp3'];
for (const a of document.querySelectorAll('a[href]')) {
  try {
    const u = new URL(a.href, location.href);
    if (u.origin !== origin) continue;
    if (u.protocol !== 'http:' && u.protocol !== 'https:') continue;
    const path = u.pathname.toLowerCase();
    if (skip.some((ext) => path.endsWith(ext))) continue;
    u.hash = '';
    let href = u.toString();
    if (href.endsWith('/') && u.pathname !== '/') href = href.slice(0, -1);
    if (seen.has(href)) continue;
    seen.add(href);
    const title = (a.innerText || a.getAttribute('title') || a.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
    items.push({url: href, title: title});
  } catch (e) {}
}
return items.slice(0, 80);
"""


@dataclass
class PageParseResult:
    title: Optional[str] = None
    h1: Optional[str] = None
    first_paragraph: Optional[str] = None
    screenshot: Optional[bytes] = None
    error: Optional[str] = None
    links: List[Dict[str, str]] = field(default_factory=list)


class ParserService:
    def __init__(self):
        logger.info("Инициализация Parser сервиса, timeout=%s с", settings.parser_timeout)
        self.timeout = settings.parser_timeout
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._driver_path: Optional[str] = None

    def _chrome_driver_path(self) -> str:
        if not self._driver_path:
            self._driver_path = ChromeDriverManager().install()
            logger.info("ChromeDriver: %s", self._driver_path)
        return self._driver_path

    def _create_driver(self) -> webdriver.Chrome:
        logger.info("Создание Chrome драйвера")
        start_time = time.time()
        options = Options()
        options.page_load_strategy = "eager"
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={settings.parser_user_agent}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-background-networking")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        service = Service(self._chrome_driver_path())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(self.timeout)
        driver.set_script_timeout(self.timeout)
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": BLOCKED_URL_PATTERNS})
        except Exception:
            logger.warning("CDP блокировка URL недоступна")
        logger.info("Chrome драйвер создан за %.2f с", time.time() - start_time)
        return driver

    def _extract_content(self, driver: webdriver.Chrome):
        title = driver.title or None
        if title:
            logger.info("Title: %s", title[:80])
        h1 = None
        try:
            h1_element = driver.find_element(By.TAG_NAME, "h1")
            h1 = h1_element.text.strip() or None
            logger.info("H1: %s", (h1 or "N/A")[:80])
        except Exception:
            logger.debug("H1 не найден")
        first_paragraph = None
        try:
            for p in driver.find_elements(By.TAG_NAME, "p"):
                text = (p.text or "").strip()
                if len(text) > 50:
                    first_paragraph = text[:500]
                    break
        except Exception:
            logger.debug("Абзацы не найдены")
        return title, h1, first_paragraph

    def _extract_links(self, driver: webdriver.Chrome, page_url: str) -> List[Dict[str, str]]:
        try:
            raw = driver.execute_script(COLLECT_LINKS_JS) or []
        except Exception:
            logger.warning("Не удалось собрать ссылки скриптом")
            raw = []
        page_norm = page_url.rstrip("/")
        links = []
        seen = {page_norm, page_norm + "/"}
        for item in raw:
            url = (item.get("url") or "").rstrip("/")
            if not url or url in seen:
                continue
            path = urlparse(url).path.lower()
            if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
                continue
            seen.add(url)
            links.append({"url": url, "title": (item.get("title") or "").strip()})
        logger.info("Собрано внутренних ссылок: %s", len(links))
        return links

    def _capture_page(self, driver: webdriver.Chrome, page_url: str) -> PageParseResult:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1.0)
        title, h1, first_paragraph = self._extract_content(driver)
        links = self._extract_links(driver, page_url)
        screenshot_bytes = driver.get_screenshot_as_png()
        logger.info("Скриншот: %.1f KB, ссылок: %s", len(screenshot_bytes) / 1024, len(links))
        return PageParseResult(
            title=title,
            h1=h1,
            first_paragraph=first_paragraph,
            screenshot=screenshot_bytes,
            links=links,
        )

    def _parse_sync(self, url: str) -> PageParseResult:
        logger.info("Парсинг: %s", url)
        driver = None
        total_start = time.time()
        try:
            driver = self._create_driver()
            page_start = time.time()
            try:
                driver.get(url)
                logger.info("document.ready (eager) за %.2f с", time.time() - page_start)
            except TimeoutException:
                logger.warning("Таймаут renderer на %s — снимаем DOM и ссылки как есть", url)
            result = self._capture_page(driver, url)
            if not result.title and not result.first_paragraph and not result.screenshot:
                return PageParseResult(error="Страница открылась, но контент не извлечён")
            logger.info("Парсинг завершён за %.2f с, ссылок=%s", time.time() - total_start, len(result.links))
            return result
        except TimeoutException:
            logger.warning("TIMEOUT парсинга url=%s", url)
            return PageParseResult(error="Превышено время ожидания загрузки страницы")
        except WebDriverException as e:
            error_msg = str(e)
            logger.error("WebDriver ошибка url=%s: %s", url, error_msg[:300])
            if "net::ERR_NAME_NOT_RESOLVED" in error_msg:
                return PageParseResult(error="Не удалось найти сайт по указанному адресу")
            if "net::ERR_CONNECTION_REFUSED" in error_msg:
                return PageParseResult(error="Соединение отклонено сервером")
            if "net::ERR_CONNECTION_TIMED_OUT" in error_msg:
                return PageParseResult(error="Превышено время ожидания соединения")
            return PageParseResult(error=f"Ошибка браузера: {error_msg[:200]}")
        except Exception as e:
            logger.exception("Неизвестная ошибка парсинга url=%s", url)
            return PageParseResult(error=f"Ошибка при загрузке страницы: {str(e)[:200]}")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning("Ошибка при закрытии драйвера: %s", e)

    async def parse_url(self, url: str) -> PageParseResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._parse_sync, url)

    def screenshot_to_base64(self, screenshot_bytes: bytes) -> str:
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def close(self):
        self._executor.shutdown(wait=False)


logger.info("Создание глобального экземпляра Parser сервиса")
parser_service = ParserService()
