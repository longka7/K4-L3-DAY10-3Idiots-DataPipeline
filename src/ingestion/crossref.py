from __future__ import annotations

from dataclasses import asdict, dataclass
import html
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
REQUEST_TIMEOUT_SECONDS = 30
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _strip_markup(value: str) -> str:
    """Bo JATS/HTML tag (vd `<jats:p>`), decode entity va gom khoang trang."""
    return normalize_whitespace(html.unescape(TAG_PATTERN.sub(" ", value or "")))


def _first(values: list | None) -> str:
    return values[0] if values else ""


def _date_from_parts(block: dict | None) -> str:
    """Crossref date: {"date-parts": [[2026, 5, 20]]} -> "2026-05-20" (thieu thang/ngay thi mac dinh 01)."""
    if not block:
        return ""
    parts = (block.get("date-parts") or [[]])[0]
    if not parts or parts[0] is None:
        return ""
    year, month, day = (list(parts) + [1, 1])[:3]
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _published_date(item: dict) -> str:
    # Uu tien ngay xuat ban chinh thuc, fallback dan ve ngay tao record.
    for key in ("published", "published-online", "published-print", "issued"):
        value = _date_from_parts(item.get(key))
        if value:
            return value
    return str((item.get("created") or {}).get("date-time", ""))[:10]


def _updated_date(item: dict, published: str) -> str:
    for key in ("indexed", "deposited", "created"):
        value = str((item.get(key) or {}).get("date-time", ""))[:10]
        if value:
            return value
    return published


def _author_name(author: dict) -> str:
    name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
    return normalize_whitespace(name or author.get("name", ""))


def _pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link") or []:
        if "pdf" in str(link.get("content-type", "")).lower() and link.get("URL"):
            return link["URL"]
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref `/works` payload thanh list PaperRecord, bo record thieu DOI/title/abstract/ngay."""
    records: list[PaperRecord] = []
    seen: set[str] = set()
    for item in (payload.get("message") or {}).get("items") or []:
        paper_id = str(item.get("DOI", "")).strip().lower()
        title = _strip_markup(_first(item.get("title")))
        summary = _strip_markup(item.get("abstract", ""))
        published = _published_date(item)
        if not paper_id or not title or not summary or not published or paper_id in seen:
            continue
        seen.add(paper_id)

        authors = [name for name in (_author_name(a) for a in item.get("author") or []) if name]
        categories = [normalize_whitespace(s) for s in item.get("subject") or [] if s]
        abs_url = item.get("URL") or f"https://doi.org/{paper_id}"
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=_updated_date(item, published),
                abs_url=abs_url,
                pdf_url=_pdf_url(item, abs_url),
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def _request_crossref(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
    }
    headers = {"User-Agent": "day10-data-observability-lab/0.1 (educational use)"}
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(CROSSREF_WORKS_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code in RETRYABLE_STATUS:
                raise requests.HTTPError(f"Crossref returned {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                # Exponential backoff: 2s, 4s ... de khong bi Crossref chan khi dinh 429.
                time.sleep(2**attempt)
    raise RuntimeError(f"Crossref API failed after {MAX_RETRIES} attempts: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay records tu Crossref (live) hoac snapshot offline, luon luu 2 raw artifact de giu lineage.

    - Mac dinh (dev/offline): doc snapshot `data/raw/crossref_response.json` neu da ton tai.
    - REFRESH_SOURCE=1: goi Crossref API co retry; loi mang/429 thi fallback ve snapshot.
    """
    raw_path = settings.paths.raw_api_response
    payload: dict | None = None

    if settings.refresh_source or not raw_path.exists():
        try:
            payload = _request_crossref(settings)
            write_json(raw_path, payload)  # raw response giu nguyen, khong chinh sua
            print(f"[ingestion] Fetched live data from {settings.source_api}.")
        except RuntimeError as exc:
            if not raw_path.exists():
                raise
            print(f"[ingestion] {exc} -> fallback to offline snapshot {raw_path.name}.")

    if payload is None:
        payload = read_json(raw_path)
        print(f"[ingestion] Loaded offline snapshot {raw_path.name}.")

    records = parse_crossref_payload(payload)
    if not records:
        raise RuntimeError("Crossref payload contained no valid records.")
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc `crossref_records.json` va map thanh `PaperRecord` (bo qua key thua neu co)."""
    list_fields = {"authors", "categories"}
    fields = PaperRecord.__dataclass_fields__.keys()
    return [
        PaperRecord(**{key: row.get(key) or ([] if key in list_fields else "") for key in fields})
        for row in read_json(path)
    ]
