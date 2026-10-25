# Документация API — анализ услуг ТО компьютерной техники

## Эндпоинты

Базовый URL: `http://localhost:8000`

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Веб-интерфейс |
| POST | `/analyze_text` | Разбор текста услуг ТО |
| POST | `/analyze_image` | Разбор визуала (прайс, баннер, фото сервиса) |
| POST | `/parse_demo` | Парсинг одной страницы: контент, AI-анализ, сбор внутренних ссылок |
| GET | `/parsed_sites` | Дерево и плоский список сохранённых ссылок (файл `.config`) |
| DELETE | `/parsed_sites/{site_id}` | Удаление узла и его потомков |
| DELETE | `/parsed_sites` | Очистка истории ссылок |
| GET | `/history` | История запросов анализа |
| DELETE | `/history` | Очистка истории запросов |
| GET | `/health` | Проверка работоспособности |
| GET | `/docs` | Swagger UI |

## Анализ текста `POST /analyze_text`

```bash
curl -X POST "http://localhost:8000/analyze_text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Сервисный центр: диагностика ПК и ноутбуков от 500 ₽, выезд мастера в течение 24 часов, профилактика систем охлаждения, установка ОС, абонентское ТО офисного парка SLA 8/5, гарантия на работы 90 дней. Запчасти отдельно."
  }'
```

Ответ:

```json
{
  "success": true,
  "analysis": {
    "service_types": ["диагностика", "выездной ремонт", "профилактика", "абонентское ТО"],
    "equipment_coverage": ["ПК", "ноутбуки", "офисный парк"],
    "sla_and_process": ["выезд до 24 часов", "гарантия 90 дней", "SLA 8/5"],
    "pricing_notes": ["диагностика от 500 ₽", "запчасти отдельно"],
    "strengths": ["явные сроки выезда", "абонентский формат"],
    "gaps": ["нет SLA 24/7", "не указаны серверы и сети"],
    "recommendations": ["описать этапы заявки", "добавить прайс на типовые работы"],
    "overall_score": 7,
    "summary": "Рабочий пакет ТО для офиса с понятным выездом, но без покрытия серверов и круглосуточного SLA."
  },
  "error": null
}
```

Минимальная длина текста: 10 символов.

## Анализ изображения `POST /analyze_image`

```bash
curl -X POST "http://localhost:8000/analyze_image" \
  -F "file=@price-list.jpg"
```

Ответ:

```json
{
  "success": true,
  "analysis": {
    "description": "Прайс-лист сервисного центра с колонками работ и цен.",
    "detected_services": ["диагностика", "чистка ноутбука", "установка Windows"],
    "equipment_shown": ["ноутбуки", "системные блоки"],
    "communication_quality": "Цены читаются, сроки реакции не указаны.",
    "visual_quality_score": 7,
    "visual_quality_analysis": "Иерархия цен понятна, нет блока гарантии и SLA.",
    "recommendations": ["добавить сроки ремонта", "выделить абонентские пакеты"]
  },
  "error": null
}
```

Форматы: JPEG, PNG, GIF, WEBP. Рекомендуемый размер до 4 MB.

## Парсинг страницы `POST /parse_demo`

Разбирается **только указанный URL**. Сайт целиком не обходится.

Парсер открывает страницу в headless Chrome (`page_load_strategy=eager`), извлекает title/h1/абзац, собирает внутренние ссылки того же origin (до 80, без PDF/изображений и т.п.), снимает скриншот и передаёт его в vision-модель.

```bash
curl -X POST "http://localhost:8000/parse_demo" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example-service.ru/to"}'
```

В `data` приходят `url`, `title`, `h1`, `first_paragraph`, `links` (найденные на странице) и `analysis` схемы `ServiceAnalysis`.

```json
{
  "success": true,
  "data": {
    "url": "https://example-service.ru/to",
    "title": "Услуги ТО",
    "h1": "Техническое обслуживание",
    "first_paragraph": "...",
    "links": [
      {"url": "https://example-service.ru/to/laptops", "title": "Ноутбуки"},
      {"url": "https://example-service.ru/price", "title": "Прайс"}
    ],
    "analysis": {}
  },
  "error": null
}
```

После успеха страница и найденные ссылки записываются в `.config` (см. ниже). Следующие страницы нужно парсить вручную: выбрать URL из дерева и снова вызвать `/parse_demo`.

## История ссылок `.config`

Файл в корне проекта (путь: `SITES_CONFIG_FILE`, по умолчанию `.config`). Это **не** история AI-запросов, а дерево URL:

- корень — страница, которую разобрали первой (или вручную введённый URL);
- дети — внутренние ссылки, собранные с этой страницы;
- `analyzed: true` — страница уже проходила `/parse_demo`;
- `parse_count` / `last_parsed` — сколько раз разбирали и когда.

Веб и desktop показывают дерево с иерархией. Уже проанализированные узлы выделены цветом и отмеченным чекбоксом статуса. Чекбокс выбора + «Парсить выбранные» запускают разбор отмеченных ссылок по очереди.

### `GET /parsed_sites`

```json
{
  "tree": [
    {
      "id": "...",
      "url": "https://example-service.ru/to",
      "title": "Услуги ТО",
      "parent_id": null,
      "analyzed": true,
      "last_parsed": "2026-10-25T13:57:40",
      "parse_count": 1,
      "children": [
        {
          "id": "...",
          "url": "https://example-service.ru/price",
          "title": "Прайс",
          "parent_id": "...",
          "analyzed": false,
          "last_parsed": null,
          "parse_count": 0,
          "children": []
        }
      ]
    }
  ],
  "items": [],
  "total": 2
}
```

`tree` — иерархия. `items` — плоский список тех же узлов (без вложенности).

### Удаление

`DELETE /parsed_sites/{site_id}` — узел и все потомки.  
`DELETE /parsed_sites` — очистить `.config`.

## История запросов

`GET /history` — последние 10 записей анализов (`text` | `image` | `parse`) в `history.json`.  
`DELETE /history` — очистка этого файла. С деревом ссылок не связана.

## Health

```json
{
  "status": "healthy",
  "service": "CompService Monitor",
  "domain": "computer_maintenance_services",
  "version": "2.0.0"
}
```

## Модели

### ServiceAnalysis

```typescript
{
  service_types: string[]
  equipment_coverage: string[]
  sla_and_process: string[]
  pricing_notes: string[]
  strengths: string[]
  gaps: string[]
  recommendations: string[]
  overall_score: number  // 0-10
  summary: string
}
```

### DiscoveredLink / ParsedContent.links

```typescript
{ url: string, title: string }
```

### ParsedSiteNode

```typescript
{
  id: string
  url: string
  title: string
  parent_id: string | null
  analyzed: boolean
  last_parsed: string | null
  parse_count: number
  children: ParsedSiteNode[]
}
```

### ImageAnalysis

```typescript
{
  description: string
  detected_services: string[]
  equipment_shown: string[]
  communication_quality: string
  visual_quality_score: number  // 0-10
  visual_quality_analysis: string
  recommendations: string[]
}
```

## Промпты

Тексты системных ролей лежат в `backend/prompts.py`:

- `TEXT_SYSTEM_PROMPT` — прайс / КП / договор / лендинг
- `IMAGE_SYSTEM_PROMPT` — визуал услуг ТО
- `WEBSITE_SYSTEM_PROMPT` — сайт сервисного центра

Модель отвечает строго JSON; недостающие факты (нет SLA, нет прайса) должны попадать в `gaps`, а не выдумываться.

## Логирование

| Куда | Уровень | Файл / поток |
|------|---------|----------------|
| Консоль | INFO+ | stdout |
| Файл backend | `LOG_LEVEL` (по умолчанию DEBUG) | `logs/compservice.log` |
| Файл desktop | DEBUG | `logs/desktop.log` |

Формат записи:

```
YYYY-MM-DD HH:MM:SS | LEVEL | logger.name | func:line | message
```

Ротация: 5 МБ, 5 бэкапов (`LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`).

В лог попадает:

- каждый HTTP-запрос: метод, путь, клиент, content-length, статус, время
- длина текста/файла, превью без полного ключа API
- токены prompt/completion/total
- полный traceback через `logger.exception`

## Конфигурация

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PROXY_API_KEY` | Ключ ProxyAPI | — |
| `OPENAI_MODEL` | Модель текста | `gpt-4o-mini` |
| `OPENAI_VISION_MODEL` | Модель изображений | `gpt-4o-mini` |
| `API_HOST` | Хост | `0.0.0.0` |
| `API_PORT` | Порт | `8000` |
| `LOG_LEVEL` | Уровень логов | `DEBUG` |
| `LOG_FILE` | Путь к лог-файлу | `logs/compservice.log` |
| `HISTORY_FILE` | История запросов анализа | `history.json` |
| `SITES_CONFIG_FILE` | Дерево собранных ссылок | `.config` |
| `PARSER_TIMEOUT` | Таймаут загрузки страницы, сек | `20` |

## Коды ошибок

| Код | Описание |
|-----|----------|
| 200 | Успех |
| 400 | Неверный тип файла или короткий текст |
| 422 | Ошибка валидации |
| 500 | Внутренняя ошибка (детали в логе) |
