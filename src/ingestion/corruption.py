from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _rebuild_text_for_embedding(df: pd.DataFrame) -> pd.DataFrame:
    """Rebuild text_for_embedding using the project's exact 5-line format."""
    result = df.copy()

    result["text_for_embedding"] = (
        "Title: "
        + result["title"].fillna("").astype(str)
        + "\nAuthors: "
        + result["authors_joined"].fillna("").astype(str)
        + "\nPublished: "
        + result["published"].fillna("").astype(str)
        + "\nCategories: "
        + result["categories_joined"].fillna("").astype(str)
        + "\nSummary: "
        + result["summary"].fillna("").astype(str)
    )

    return result


def _write_corruption_log(output_log_path, operations: list[dict]) -> None:
    """Write corruption metadata to JSON."""
    path = Path(output_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "operations": operations,
    }

    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
        )


def _paper_ids(df: pd.DataFrame, indices) -> list[str]:
    """Return paper IDs for logging when the column is available."""
    if "paper_id" not in df.columns:
        return []

    return [
        str(value)
        for value in df.loc[indices, "paper_id"].tolist()
    ]


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path,
) -> pd.DataFrame:
    """Simulate deterministic corruption of a clean dataframe.

    Corruptions:
    1. Drop a small number of latest records.
    2. Blank summaries in some rows.
    3. Inject obvious noise into text.
    4. Truncate titles.
    5. Make selected published dates one year older.
    6. Add duplicate rows.
    7. Rebuild text_for_embedding using the exact clean-data format.
    8. Write a corruption log.

    The input dataframe is never modified in-place.

    The corruption is deterministic: repeated calls with the same input
    produce the same corrupted dataframe and corruption log.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    if df.empty:
        raise ValueError("Cannot corrupt an empty clean dataframe.")

    required_columns = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "published",
    }

    missing = sorted(required_columns - set(df.columns))
    if missing:
        raise ValueError(
            "Clean dataframe is missing required columns: "
            + ", ".join(missing)
        )

    result = df.copy(deep=True)
    operations: list[dict] = []

    # Number of rows affected by each corruption.
    # Keep at least one row affected while never consuming the entire dataset.
    corruption_count = min(
        max(1, len(result) // 20),
        max(0, len(result) - 1),
    )

    # ------------------------------------------------------------------
    # 1. Drop latest records.
    # ------------------------------------------------------------------
    published_dates = pd.to_datetime(
        result["published"],
        format="%Y-%m-%d",
        errors="coerce",
    )

    valid_dates = published_dates.notna()

    if valid_dates.any() and corruption_count > 0:
        latest_indices = (
            published_dates[valid_dates]
            .sort_values(ascending=False)
            .index[:corruption_count]
            .tolist()
        )

        dropped_ids = _paper_ids(result, latest_indices)

        result = result.drop(index=latest_indices)

        operations.append(
            {
                "operation": "drop_latest_records",
                "count": len(latest_indices),
                "paper_ids": dropped_ids,
            }
        )

    # ------------------------------------------------------------------
    # 2. Blank summaries.
    # ------------------------------------------------------------------
    if not result.empty:
        count = min(
            max(1, len(result) // 20),
            len(result),
        )

        indices = result.index[:count].tolist()
        affected_ids = _paper_ids(result, indices)

        result.loc[indices, "summary"] = ""

        operations.append(
            {
                "operation": "blank_summary",
                "count": len(indices),
                "paper_ids": affected_ids,
            }
        )

    # ------------------------------------------------------------------
    # 3. Inject noise into text.
    #
    # Modify summary rather than text_for_embedding directly. The embedding
    # text is rebuilt later, so this corruption remains internally consistent.
    # ------------------------------------------------------------------
    if not result.empty:
        count = min(
            max(1, len(result) // 20),
            len(result),
        )

        indices = result.index[:count].tolist()
        affected_ids = _paper_ids(result, indices)

        noise = "[CORRUPTED_NOISE_###]"

        result.loc[indices, "summary"] = (
            result.loc[indices, "summary"]
            .fillna("")
            .astype(str)
            .map(
                lambda value: (
                    f"{value} {noise}".strip()
                    if value
                    else noise
                )
            )
        )

        operations.append(
            {
                "operation": "inject_text_noise",
                "column": "summary",
                "noise": noise,
                "count": len(indices),
                "paper_ids": affected_ids,
            }
        )

    # ------------------------------------------------------------------
    # 4. Truncate titles.
    # ------------------------------------------------------------------
    if not result.empty:
        count = min(
            max(1, len(result) // 20),
            len(result),
        )

        indices = result.index[:count].tolist()
        affected_ids = _paper_ids(result, indices)

        def truncate_title(value: object) -> str:
            if pd.isna(value):
                return ""

            title = str(value).strip()

            if len(title) <= 12:
                return title

            cutoff = max(8, len(title) // 2)
            return title[:cutoff].rstrip() + "..."

        result.loc[indices, "title"] = (
            result.loc[indices, "title"].map(truncate_title)
        )

        operations.append(
            {
                "operation": "truncate_title",
                "count": len(indices),
                "paper_ids": affected_ids,
            }
        )

    # ------------------------------------------------------------------
    # 5. Make published dates older.
    #
    # Keep the project's exact YYYY-MM-DD string representation.
    # ------------------------------------------------------------------
    if not result.empty:
        count = min(
            max(1, len(result) // 20),
            len(result),
        )

        indices = result.index[:count].tolist()
        affected_ids = _paper_ids(result, indices)

        dates = pd.to_datetime(
            result.loc[indices, "published"],
            format="%Y-%m-%d",
            errors="coerce",
        )

        corrupted_dates = dates - pd.Timedelta(days=365)

        result.loc[indices, "published"] = corrupted_dates.map(
            lambda value: (
                value.strftime("%Y-%m-%d")
                if pd.notna(value)
                else ""
            )
        )

        operations.append(
            {
                "operation": "make_published_date_older",
                "days": 365,
                "count": len(indices),
                "paper_ids": affected_ids,
            }
        )

    # ------------------------------------------------------------------
    # 6. Add duplicate rows.
    #
    # Duplicate rows are intentionally retained. This is what makes the
    # corrupted dataframe fail duplicate-related quality checks.
    # ------------------------------------------------------------------
    if not result.empty:
        duplicate_count = min(
            max(1, len(result) // 20),
            len(result),
        )

        duplicate_source = result.iloc[:duplicate_count].copy()
        duplicate_ids = duplicate_source["paper_id"].astype(str).tolist()

        result = pd.concat(
            [result, duplicate_source],
            ignore_index=True,
        )

        operations.append(
            {
                "operation": "add_duplicate_rows",
                "count": len(duplicate_source),
                "paper_ids": duplicate_ids,
            }
        )

    # ------------------------------------------------------------------
    # 7. Keep helper columns consistent with corrupted content.
    # ------------------------------------------------------------------
    result["summary_chars"] = (
        result["summary"]
        .fillna("")
        .astype(str)
        .str.len()
    )

    result = _rebuild_text_for_embedding(result)

    operations.append(
        {
            "operation": "rebuild_text_for_embedding",
            "format": (
                "Title: ...\\n"
                "Authors: ...\\n"
                "Published: ...\\n"
                "Categories: ...\\n"
                "Summary: ..."
            ),
            "count": len(result),
        }
    )

    # ------------------------------------------------------------------
    # Preserve deterministic row order and a clean RangeIndex.
    # ------------------------------------------------------------------
    result = result.reset_index(drop=True)

    # ------------------------------------------------------------------
    # 8. Write corruption log.
    # ------------------------------------------------------------------
    _write_corruption_log(output_log_path, operations)

    return result
