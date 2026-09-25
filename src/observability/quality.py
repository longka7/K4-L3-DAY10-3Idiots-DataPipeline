from __future__ import annotations

from typing import Any
import logging

import great_expectations as gx
import great_expectations.expectations as gxe
from great_expectations.data_context.types.base import ProgressBarsConfig
import pandas as pd

from core.config import Settings
from core.utils import write_json

MIN_ROWS = 5
MAX_ROWS = 5000
MIN_SUMMARY_CHARS = 30
MIN_TITLE_CHARS = 8
MAX_STALE_RATIO = 0.25
REQUIRED_COLUMNS = ("paper_id", "title", "text_for_embedding")
# GX khong hash duoc cot list -> chi dua cot scalar vao validator.
LIST_COLUMNS = ("authors", "categories")


def _build_expectations() -> list[gxe.Expectation]:
    """4 nhom expectation bat buoc (+ title length de bat loi truncate title)."""
    expectations: list[gxe.Expectation] = [gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS)]
    expectations += [gxe.ExpectColumnValuesToNotBeNull(column=column) for column in REQUIRED_COLUMNS]
    expectations += [
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS),
        gxe.ExpectColumnValueLengthsToBeBetween(column="title", min_value=MIN_TITLE_CHARS),
    ]
    return expectations


def _to_python(value: Any) -> Any:
    """Ep numpy scalar ve kieu Python de ghi JSON."""
    return value.item() if hasattr(value, "item") else value


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay Quality Gate bang Great Expectations 1.x (ephemeral context) + freshness, ghi ra data/quality/."""
    logging.getLogger("great_expectations").setLevel(logging.ERROR)
    scalar_df = df.drop(columns=[c for c in LIST_COLUMNS if c in df.columns]).reset_index(drop=True)

    # Cu phap GX 1.x: context -> data source -> asset -> batch definition -> batch.
    context = gx.get_context(mode="ephemeral")
    context.variables.progress_bars = ProgressBarsConfig(globally=False)  # log gon, khong in progress bar
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": scalar_df})

    suite = context.suites.add(gx.ExpectationSuite(name=f"papers_{report_name}_suite"))
    for expectation in _build_expectations():
        suite.add_expectation(expectation)
    validation = batch.validate(suite)

    results = []
    for item in validation.results:
        config = item.expectation_config
        kwargs = config.kwargs
        results.append(
            {
                "expectation": config.type,
                "column": kwargs.get("column"),
                "kwargs": {k: _to_python(v) for k, v in kwargs.items() if k not in {"column", "batch_id"}},
                "success": bool(item.success),
                "observed_value": _to_python(item.result.get("observed_value")),
                "unexpected_count": _to_python(item.result.get("unexpected_count")),
            }
        )

    freshness_path = (
        settings.paths.freshness_report
        if report_name == "baseline"
        else settings.paths.quality_dir / f"{report_name}_freshness_report.json"
    )
    freshness = build_freshness_report(df, settings, freshness_path)

    report = {
        "report_name": report_name,
        "engine": f"great_expectations {gx.__version__}",
        # success chi phu thuoc expectation; freshness la canh bao rieng (SLA).
        "success": bool(validation.success),
        "row_count": int(len(df)),
        "failed_expectations": sum(1 for r in results if not r["success"]),
        "results": results,
        "freshness": freshness,
    }
    write_json(settings.paths.quality_dir / f"{report_name}_quality_report.json", report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Freshness SLA: canh bao is_fresh=False khi > 25% bai co age_days > threshold (180 ngay)."""
    threshold = settings.freshness_threshold_days
    published = pd.to_datetime(df["published"], errors="coerce")
    age_days = pd.to_numeric(df["age_days"], errors="coerce")
    total_rows = int(len(df))
    stale_rows = int((age_days > threshold).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0

    payload = {
        "latest_published": published.max().strftime("%Y-%m-%d") if published.notna().any() else None,
        "oldest_published": published.min().strftime("%Y-%m-%d") if published.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "threshold_days": threshold,
        "max_stale_ratio": MAX_STALE_RATIO,
        "is_fresh": bool(total_rows > 0 and stale_ratio <= MAX_STALE_RATIO),
    }
    write_json(report_path, payload)
    return payload
