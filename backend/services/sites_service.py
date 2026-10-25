"""
Иерархия страниц и найденных ссылок в файле .config.
"""
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urlparse, urlunparse

from backend.config import settings
from backend.models.schemas import ParsedSiteNode

logger = logging.getLogger("compservice.sites")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", parsed.query, ""))


class SitesService:
    def __init__(self):
        self.config_file = Path(settings.sites_config_file)
        logger.info("Файл сайтов: %s", self.config_file.resolve())
        self._ensure_file()

    def _ensure_file(self):
        if not self.config_file.exists():
            self._save({"sites": []})

    def _load(self) -> dict:
        try:
            data = json.loads(self.config_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                data = {"sites": data}
            data.setdefault("sites", [])
            for item in data["sites"]:
                item.setdefault("parent_id", None)
                item.setdefault("analyzed", int(item.get("parse_count", 0)) > 0)
                item.setdefault("parse_count", 0)
                item.setdefault("title", "")
            return data
        except (json.JSONDecodeError, FileNotFoundError):
            return {"sites": []}

    def _save(self, data: dict):
        self.config_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find(self, sites: List[dict], url: str) -> Optional[dict]:
        target = normalize_url(url)
        for item in sites:
            if normalize_url(item.get("url", "")) == target:
                return item
        return None

    def _ancestors(self, sites: List[dict], node: dict) -> set:
        ids = set()
        current = node
        by_id = {s["id"]: s for s in sites}
        while current and current.get("parent_id"):
            parent = by_id.get(current["parent_id"])
            if not parent or parent["id"] in ids:
                break
            ids.add(parent["id"])
            current = parent
        return ids

    def record_parse(self, url: str, title: Optional[str], discovered: List[Dict[str, str]]) -> ParsedSiteNode:
        normalized = normalize_url(url)
        logger.info("Запись разбора %s, найденных ссылок: %s", normalized, len(discovered or []))
        data = self._load()
        sites: List[dict] = data["sites"]
        now = datetime.now().isoformat()
        node = self._find(sites, normalized)
        if node:
            node["analyzed"] = True
            node["last_parsed"] = now
            node["parse_count"] = int(node.get("parse_count", 0)) + 1
            if title:
                node["title"] = title
        else:
            node = {
                "id": str(uuid.uuid4()),
                "url": normalized,
                "title": title or "",
                "parent_id": None,
                "analyzed": True,
                "last_parsed": now,
                "parse_count": 1,
            }
            sites.insert(0, node)

        for link in discovered or []:
            child_url = normalize_url(link.get("url", ""))
            if not child_url or child_url == normalized:
                continue
            existing = self._find(sites, child_url)
            if existing:
                if link.get("title") and not existing.get("title"):
                    existing["title"] = link["title"]
                if existing.get("parent_id") is None and existing["id"] != node["id"]:
                    if existing["id"] not in self._ancestors(sites, node) and not existing.get("analyzed"):
                        existing["parent_id"] = node["id"]
                continue
            child = {
                "id": str(uuid.uuid4()),
                "url": child_url,
                "title": (link.get("title") or "")[:120],
                "parent_id": node["id"],
                "analyzed": False,
                "last_parsed": None,
                "parse_count": 0,
            }
            sites.append(child)

        self._save(data)
        return self._to_node(node, [])

    def _to_node(self, item: dict, children: List[ParsedSiteNode]) -> ParsedSiteNode:
        last = item.get("last_parsed")
        return ParsedSiteNode(
            id=item["id"],
            url=item["url"],
            title=item.get("title") or "",
            parent_id=item.get("parent_id"),
            analyzed=bool(item.get("analyzed")),
            last_parsed=last,
            parse_count=int(item.get("parse_count") or 0),
            children=children,
        )

    def tree(self) -> List[ParsedSiteNode]:
        sites = self._load()["sites"]
        by_parent: Dict[Optional[str], List[dict]] = {}
        for item in sites:
            by_parent.setdefault(item.get("parent_id"), []).append(item)

        def build(parent_id: Optional[str]) -> List[ParsedSiteNode]:
            nodes = []
            for item in by_parent.get(parent_id, []):
                nodes.append(self._to_node(item, build(item["id"])))
            return nodes

        roots = build(None)
        logger.info("Дерево сайтов: корней=%s, всего=%s", len(roots), len(sites))
        return roots

    def flat(self) -> List[ParsedSiteNode]:
        return [self._to_node(item, []) for item in self._load()["sites"]]

    def delete(self, site_id: str) -> bool:
        data = self._load()
        sites = data["sites"]
        if not any(s.get("id") == site_id for s in sites):
            return False
        remove = {site_id}
        changed = True
        while changed:
            changed = False
            for item in sites:
                if item.get("parent_id") in remove and item["id"] not in remove:
                    remove.add(item["id"])
                    changed = True
        data["sites"] = [s for s in sites if s.get("id") not in remove]
        self._save(data)
        logger.info("Удалены узлы: %s", len(remove))
        return True

    def clear(self):
        self._save({"sites": []})


logger.info("Создание сервиса сохранённых сайтов")
sites_service = SitesService()
