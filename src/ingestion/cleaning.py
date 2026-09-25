from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import html
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

TAG_PATTERN = re.compile(r"<[^>]+>")
MIN_TITLE_CHARS = 8
MIN_SUMMARY_CHARS = 30


def _clean_text(value: object) -> str:
    """Bo tag JATS/HTML con sot, decode entity, gom khoang trang."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return normalize_whitespace(html.unescape(TAG_PATTERN.sub(" ", str(value))))


def _clean_list(values: object) -> list[str]:
    """Normalize tung phan tu, bo rong va bo trung nhung giu thu tu."""
    if not isinstance(values, (list, tuple)):
        return []
    seen: dict[str, None] = {}
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


def _to_iso_date(value: object) -> str:
    """Chuan hoa ngay ve `YYYY-MM-DD`; tra '' neu khong parse duoc."""
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    return "" if pd.isna(parsed) else parsed.strftime("%Y-%m-%d")


def _build_text_for_embedding(row: pd.Series) -> str:
    # Cau truc 5 phan co dinh -> embedding on dinh giua cac lan chay.
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def rebuild_derived_columns(df: pd.DataFrame, run_date: datetime) -> pd.DataFrame:
    """Tinh lai cac cot phai sinh tu cot goc. Dung chung cho cleaning, corruption va repair.

    Cot duoc tinh lai: age_days, authors_joined, categories_joined, summary_chars, text_for_embedding.
    """
    out = df.copy()
    run_ts = pd.Timestamp(run_date)
    run_day = run_ts.tz_localize(UTC) if run_ts.tzinfo is None else run_ts.tz_convert(UTC)
    published = pd.to_datetime(out["published"], errors="coerce", utc=True)
    out["age_days"] = (run_day.normalize() - published).dt.days.astype("Int64")
    out["authors_joined"] = out["authors"].apply(lambda items: compact_join(items or []))
    out["categories_joined"] = out["categories"].apply(lambda items: compact_join(items or []))
    out["summary"] = out["summary"].fillna("").astype(str)
    out["summary_chars"] = out["summary"].str.len()
    out["text_for_embedding"] = out.apply(_build_text_for_embedding, axis=1)
    return out


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed (theo hop dong trong docs/TASKS_TEAM.md)."""
    df = pd.DataFrame([asdict(record) for record in records])
    if df.empty:
        raise ValueError("No raw records to clean.")

    # 1. Normalize text va list.
    df["paper_id"] = df["paper_id"].map(_clean_text).str.lower()
    for column in ("title", "summary", "primary_category", "abs_url", "pdf_url", "comment"):
        df[column] = df[column].map(_clean_text)
    df["authors"] = df["authors"].map(_clean_list)
    df["categories"] = df["categories"].map(_clean_list)
    df["primary_category"] = df.apply(
        lambda row: row["primary_category"] or (row["categories"][0] if row["categories"] else ""), axis=1
    )

    # 2. Parse ngay ve YYYY-MM-DD; updated thieu thi lay published.
    df["published"] = df["published"].map(_to_iso_date)
    df["updated"] = df["updated"].map(_to_iso_date)
    df["updated"] = df["updated"].where(df["updated"] != "", df["published"])

    # 3. Loc row xau: thieu id/ngay, title qua ngan, summary qua ngan.
    valid = (
        (df["paper_id"] != "")
        & (df["published"] != "")
        & (df["title"].str.len() >= MIN_TITLE_CHARS)
        & (df["summary"].str.len() >= MIN_SUMMARY_CHARS)
    )
    dropped = int((~valid).sum())
    if dropped:
        print(f"[cleaning] Dropped {dropped} invalid rows.")
    df = df[valid]

    # 4. Khu trung theo paper_id: giu ban co `updated` moi nhat.
    before = len(df)
    df = df.sort_values(["paper_id", "updated"], ascending=[True, False]).drop_duplicates("paper_id", keep="first")
    if len(df) < before:
        print(f"[cleaning] Removed {before - len(df)} duplicate paper_id rows.")

    # 5. Cot phai sinh (age_days, *_joined, summary_chars, text_for_embedding).
    df = rebuild_derived_columns(df, run_date)

    # 6. Sort on dinh: moi nhat truoc, tie-break theo paper_id -> output deterministic.
    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "abs_url", "pdf_url", "comment",
        "age_days", "authors_joined", "categories_joined", "summary_chars", "text_for_embedding",
    ]
    return df[columns]
