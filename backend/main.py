"""
FastAPI: анализ услуг технического обслуживания компьютерной техники.
"""
import base64
import time
import logging
import traceback

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from backend.config import settings, logger as root_logger  # noqa: F401 — инициализация логов
from backend.models.schemas import (
    TextAnalysisRequest,
    TextAnalysisResponse,
    ImageAnalysisResponse,
    ParseDemoRequest,
    ParseDemoResponse,
    ParsedContent,
    HistoryResponse,
    ParsedSitesResponse,
)
from backend.services.openai_service import openai_service
from backend.services.parser_service import parser_service
from backend.services.history_service import history_service
from backend.services.sites_service import sites_service

logger = logging.getLogger("compservice.api")

app = FastAPI(
    title="Анализ услуг ТО компьютерной техники",
    description="AI-ассистент для разбора прайсов, визуалов и сайтов сервисных центров",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    client = request.client.host if request.client else "unknown"
    content_length = request.headers.get("content-length", "0")
    logger.info(
        "→ %s %s client=%s content-length=%s query=%s",
        request.method,
        request.url.path,
        client,
        content_length,
        dict(request.query_params) or "-",
    )
    try:
        response = await call_next(request)
    except Exception:
        elapsed = time.time() - start_time
        logger.exception("Необработанная ошибка %s %s за %.3f с", request.method, request.url.path, elapsed)
        raise
    elapsed = time.time() - start_time
    logger.info(
        "← %s %s status=%s time=%.3fs",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response


@app.on_event("startup")
async def startup_event():
    logger.info("===== СЕРВЕР ЗАПУЩЕН =====")
    logger.info("  Адрес: http://%s:%s", settings.api_host, settings.api_port)
    logger.info("  Docs: http://localhost:%s/docs", settings.api_port)
    logger.info("  Модель текста: %s", settings.openai_model)
    logger.info("  Модель vision: %s", settings.openai_vision_model)
    logger.info("  Ключ ProxyAPI: %s", "готов" if settings.api_key_ready else "НЕ ЗАДАН или шаблон")
    logger.info("  Лог-файл: %s", settings.log_file)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Остановка сервера, закрытие парсера")
    await parser_service.close()
    logger.info("Ресурсы освобождены")


@app.get("/")
async def root():
    logger.debug("Отдача frontend/index.html")
    return FileResponse("frontend/index.html")


@app.post("/analyze_text", response_model=TextAnalysisResponse)
async def analyze_text(request: TextAnalysisRequest):
    logger.info("API analyze_text: %s символов, превью=%s", len(request.text), request.text[:80].replace("\n", " "))
    try:
        start_time = time.time()
        analysis = await openai_service.analyze_text(request.text)
        logger.info("analyze_text готов за %.2f с, score=%s", time.time() - start_time, analysis.overall_score)
        history_service.add_entry(
            request_type="text",
            request_summary=request.text[:100] + ("..." if len(request.text) > 100 else ""),
            response_summary=analysis.summary or f"Оценка пакета услуг: {analysis.overall_score}/10",
        )
        return TextAnalysisResponse(success=True, analysis=analysis)
    except RuntimeError as e:
        logger.error("analyze_text: %s", e)
        return TextAnalysisResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("Ошибка analyze_text")
        return TextAnalysisResponse(success=False, error=str(e))


@app.post("/analyze_image", response_model=ImageAnalysisResponse)
async def analyze_image(file: UploadFile = File(...)):
    logger.info("API analyze_image: filename=%s type=%s", file.filename, file.content_type)
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        logger.warning("Неподдерживаемый MIME: %s", file.content_type)
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый тип файла. Разрешены: {', '.join(allowed_types)}",
        )
    try:
        start_time = time.time()
        content = await file.read()
        logger.info("Файл прочитан: %.1f KB", len(content) / 1024)
        image_base64 = base64.b64encode(content).decode("utf-8")
        analysis = await openai_service.analyze_image(image_base64=image_base64, mime_type=file.content_type)
        logger.info("analyze_image готов за %.2f с, score=%s", time.time() - start_time, analysis.visual_quality_score)
        history_service.add_entry(
            request_type="image",
            request_summary=f"Изображение услуг ТО: {file.filename}",
            response_summary=analysis.description[:200] if analysis.description else "Анализ визуала услуг ТО",
        )
        return ImageAnalysisResponse(success=True, analysis=analysis)
    except RuntimeError as e:
        logger.error("analyze_image: %s", e)
        return ImageAnalysisResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("Ошибка analyze_image")
        return ImageAnalysisResponse(success=False, error=str(e))


@app.post("/parse_demo", response_model=ParseDemoResponse)
async def parse_demo(request: ParseDemoRequest):
    logger.info("API parse_demo url=%s", request.url)
    try:
        total_start = time.time()
        parse_start = time.time()
        page = await parser_service.parse_url(request.url)
        logger.info("Парсинг %.2f с, error=%s, links=%s", time.time() - parse_start, page.error, len(page.links))
        if page.error:
            return ParseDemoResponse(success=False, error=page.error)

        screenshot_base64 = parser_service.screenshot_to_base64(page.screenshot) if page.screenshot else None
        ai_start = time.time()
        if screenshot_base64:
            analysis = await openai_service.analyze_website_screenshot(
                screenshot_base64=screenshot_base64,
                url=request.url,
                title=page.title,
                h1=page.h1,
                first_paragraph=page.first_paragraph,
            )
        else:
            logger.warning("Скриншот недоступен, текстовый fallback")
            analysis = await openai_service.analyze_parsed_content(
                title=page.title, h1=page.h1, paragraph=page.first_paragraph
            )
        logger.info("AI-анализ сайта %.2f с, score=%s", time.time() - ai_start, analysis.overall_score)

        parsed_content = ParsedContent(
            url=request.url,
            title=page.title,
            h1=page.h1,
            first_paragraph=page.first_paragraph,
            analysis=analysis,
            links=page.links,
        )
        history_service.add_entry(
            request_type="parse",
            request_summary=f"URL услуг ТО: {request.url}",
            response_summary=analysis.summary[:100] if analysis.summary else f"Title: {page.title or 'N/A'}",
        )
        sites_service.record_parse(url=parsed_content.url, title=page.title, discovered=page.links)
        logger.info("parse_demo успех за %.2f с", time.time() - total_start)
        return ParseDemoResponse(success=True, data=parsed_content)
    except RuntimeError as e:
        logger.error("parse_demo: %s", e)
        return ParseDemoResponse(success=False, error=str(e))
    except Exception as e:
        logger.exception("Ошибка parse_demo")
        return ParseDemoResponse(success=False, error=str(e))


@app.get("/history", response_model=HistoryResponse)
async def get_history():
    items = history_service.get_history()
    logger.info("API history: %s записей", len(items))
    return HistoryResponse(items=items, total=len(items))


@app.delete("/history")
async def clear_history():
    logger.info("API clear history")
    history_service.clear_history()
    return {"success": True, "message": "История очищена"}


@app.get("/parsed_sites", response_model=ParsedSitesResponse)
async def get_parsed_sites():
    tree = sites_service.tree()
    items = sites_service.flat()
    return ParsedSitesResponse(tree=tree, items=items, total=len(items))


@app.delete("/parsed_sites/{site_id}")
async def delete_parsed_site(site_id: str):
    logger.info("API delete parsed site id=%s", site_id)
    if not sites_service.delete(site_id):
        raise HTTPException(status_code=404, detail="Сайт не найден в .config")
    return {"success": True, "message": "Сайт удалён из списка"}


@app.delete("/parsed_sites")
async def clear_parsed_sites():
    logger.info("API clear parsed sites")
    sites_service.clear()
    return {"success": True, "message": "Список сайтов очищен"}


@app.get("/health")
async def health_check():
    logger.debug("Health check")
    return {
        "status": "healthy",
        "service": "CompService Monitor",
        "domain": "computer_maintenance_services",
        "version": "2.0.0",
    }


app.mount("/static", StaticFiles(directory="frontend"), name="static")
logger.info("Статика: /static -> frontend/")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
