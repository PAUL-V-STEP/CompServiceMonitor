"""
Pydantic-схемы API анализа услуг технического обслуживания компьютерной техники.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TextAnalysisRequest(BaseModel):
    """Запрос на анализ описания услуг ТО."""
    text: str = Field(..., min_length=10, description="Текст прайса, договора, лендинга или оффера услуг ТО")


class ParseDemoRequest(BaseModel):
    """Запрос на парсинг сайта сервисного центра."""
    url: str = Field(..., description="URL страницы с услугами ТО компьютерной техники")


class ServiceAnalysis(BaseModel):
    """Структурированный разбор пакета услуг ТО компьютерной техники."""
    service_types: List[str] = Field(
        default_factory=list,
        description="Виды услуг: диагностика, ремонт, профилактика, выезд, абонентское ТО, настройка ПО",
    )
    equipment_coverage: List[str] = Field(
        default_factory=list,
        description="Какая техника покрывается: ПК, ноутбуки, серверы, периферия, сети, СХД",
    )
    sla_and_process: List[str] = Field(
        default_factory=list,
        description="Сроки реакции, гарантия, этапы работ, выезд, запчасти, документооборот",
    )
    pricing_notes: List[str] = Field(
        default_factory=list,
        description="Цены, пакеты, скрытые условия, что входит и не входит в стоимость",
    )
    strengths: List[str] = Field(default_factory=list, description="Сильные стороны оффера услуг")
    gaps: List[str] = Field(
        default_factory=list,
        description="Пробелы оффера и риски для заказчика (нет SLA, нет гарантии, размытый прайс)",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Рекомендации по улучшению пакета услуг ТО",
    )
    overall_score: int = Field(0, ge=0, le=10, description="Оценка полноты и прозрачности пакета услуг (0-10)")
    summary: str = Field("", description="Краткое резюме анализа услуг ТО")


class ImageAnalysis(BaseModel):
    """Разбор визуала, связанного с услугами ТО (прайс, баннер, фото сервиса, чек-лист)."""
    description: str = Field("", description="Что изображено")
    detected_services: List[str] = Field(default_factory=list, description="Услуги ТО, которые читаются с изображения")
    equipment_shown: List[str] = Field(default_factory=list, description="Типы техники / рабочего места, которые видны")
    communication_quality: str = Field(
        "",
        description="Насколько ясно визуал объясняет состав, сроки и условия услуг ТО",
    )
    visual_quality_score: int = Field(0, ge=0, le=10, description="Оценка информативности визуала (0-10)")
    visual_quality_analysis: str = Field("", description="Разбор читаемости, иерархии и полезности для заказчика")
    recommendations: List[str] = Field(default_factory=list, description="Как улучшить визуальную подачу услуг")


class DiscoveredLink(BaseModel):
    """Внутренняя ссылка, найденная на разобранной странице."""
    url: str
    title: str = ""


class ParsedContent(BaseModel):
    """Результат парсинга страницы услуг."""
    url: str
    title: Optional[str] = None
    h1: Optional[str] = None
    first_paragraph: Optional[str] = None
    analysis: Optional[ServiceAnalysis] = None
    links: List[DiscoveredLink] = Field(default_factory=list)
    error: Optional[str] = None


class TextAnalysisResponse(BaseModel):
    success: bool
    analysis: Optional[ServiceAnalysis] = None
    error: Optional[str] = None


class ImageAnalysisResponse(BaseModel):
    success: bool
    analysis: Optional[ImageAnalysis] = None
    error: Optional[str] = None


class ParseDemoResponse(BaseModel):
    success: bool
    data: Optional[ParsedContent] = None
    error: Optional[str] = None


class HistoryItem(BaseModel):
    id: str
    timestamp: datetime
    request_type: str  # "text", "image", "parse"
    request_summary: str
    response_summary: str


class HistoryResponse(BaseModel):
    items: List[HistoryItem]
    total: int


class ParsedSiteNode(BaseModel):
    id: str
    url: str
    title: str = ""
    parent_id: Optional[str] = None
    analyzed: bool = False
    last_parsed: Optional[str] = None
    parse_count: int = 0
    children: List["ParsedSiteNode"] = Field(default_factory=list)


class ParsedSitesResponse(BaseModel):
    tree: List[ParsedSiteNode] = Field(default_factory=list)
    items: List[ParsedSiteNode] = Field(default_factory=list)
    total: int = 0


ParsedSiteNode.model_rebuild()
