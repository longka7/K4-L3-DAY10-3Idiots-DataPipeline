from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from core.utils import now_utc

import pandas as pd

from config import load_settings
from ingestion.crossref import load_raw_records
from pipelines.cleaning import build_clean_dataframe
from pipelines.corruption import corrupt_clean_dataframe
from pipelines.evaluation import evaluate_pipeline
from pipelines.index import LocalEmbeddingIndex
from pipelines.quality import (
    build_freshness_report,
    run_data_quality_checks,
)



def _read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def _write_dataframe_json(df: pd.DataFrame, path: Path) -> None:
    """Write dataframe as records-oriented JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)

    df.to_json(
        path,
        orient="records",
        force_ascii=False,
        indent=2,
    )


def _metric(metrics: dict[str, Any], name: str) -> Any:
    """Get a metric from the evaluation summary."""
    return metrics.get(name)


def _format_metric(value: Any) -> str:
    """Format a metric for the console comparison table."""
    if value is None:
        return "N/A"

    if isinstance(value, float):
        return f"{value:.4f}"

    return str(value)


def _paper_count(df: pd.DataFrame) -> int:
    return int(len(df))


def _print_corrupted_gate_warning(
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Print explicit warnings when corrupted data fails validation."""
    quality_ok = bool(quality.get("success"))
    freshness_ok = bool(freshness.get("is_fresh"))

    if not quality_ok:
        print(
            "[WARNING] CORRUPTED quality gate FAILED "
            f"({quality.get('failed_expectations', 'unknown')} "
            "failed expectation(s))."
        )

    if not freshness_ok:
        stale_rows = freshness.get("stale_rows", "unknown")
        total_rows = freshness.get("total_rows", "unknown")
        threshold = freshness.get("threshold_days", "unknown")

        print(
            "[WARNING] CORRUPTED freshness check FAILED: "
            f"{stale_rows}/{total_rows} rows are older than "
            f"{threshold} days."
        )

    if quality_ok and freshness_ok:
        print(
            "[WARNING] Corrupted dataset did not fail the expected "
            "quality/freshness gates."
        )


def _print_metrics_table(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> None:
    """Print the requested Baseline / Corrupted / Repaired table."""
    metrics = (
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    )

    print()
    print("=" * 88)
    print("Baseline | Corrupted | Repaired")
    print("=" * 88)

    header = (
        f"{'Metric':<24}"
        f"{'Baseline':>18}"
        f"{'Corrupted':>20}"
        f"{'Repaired':>18}"
    )

    print(header)
    print("-" * len(header))

    for metric_name in metrics:
        baseline = _format_metric(
            _metric(baseline_metrics, metric_name)
        )
        corrupted = _format_metric(
            _metric(corrupted_metrics, metric_name)
        )
        repaired = _format_metric(
            _metric(repaired_metrics, metric_name)
        )

        print(
            f"{metric_name:<24}"
            f"{baseline:>18}"
            f"{corrupted:>20}"
            f"{repaired:>18}"
        )

    print("=" * 88)
    print()


def main() -> None:
    """Run corruption -> silent failure -> repair -> comparison flow."""
    settings = load_settings()

    # ==============================================================
    # 1. Load baseline metrics and clean dataset.
    # ==============================================================

    baseline_metrics_path = settings.paths.baseline_metrics
    clean_json_path = settings.paths.clean_json

    if not baseline_metrics_path.exists() or not clean_json_path.exists():
        raise FileNotFoundError(
            "Không tìm thấy baseline metrics hoặc clean dataset. "
            "Hãy chạy script/run_phase1.py trước."
        )

    baseline_metrics = _read_json(baseline_metrics_path)

    clean_df = pd.read_json(
        clean_json_path,
        orient="records",
    )

    if clean_df.empty:
        raise ValueError(
            f"Clean dataset is empty: {clean_json_path}. "
            "Hãy chạy script/run_phase1.py trước."
        )

    print(
        f"[corruption] Loaded clean dataset: "
        f"{_paper_count(clean_df)} rows"
    )

    # ==============================================================
    # 2. CORRUPTED
    # ==============================================================

    corrupted_df = corrupt_clean_dataframe(
        clean_df,
        settings.paths.corruption_log,
    )

    print(
        f"[corruption] Created corrupted dataset: "
        f"{_paper_count(corrupted_df)} rows"
    )

    # ==============================================================
    # 3. Save corrupted CSV + JSON
    # ==============================================================

    settings.paths.corrupted_clean_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    corrupted_df.to_csv(
        settings.paths.corrupted_clean_csv,
        index=False,
    )

    _write_dataframe_json(
        corrupted_df,
        settings.paths.corrupted_clean_json,
    )

    print(
        "[corruption] Saved CSV: "
        f"{settings.paths.corrupted_clean_csv}"
    )
    print(
        "[corruption] Saved JSON: "
        f"{settings.paths.corrupted_clean_json}"
    )

    # ==============================================================
    # 4. Quality gate + freshness on corrupted data
    # ==============================================================

    print("[quality] Running corrupted quality gate...")

    corrupted_quality = run_data_quality_checks(
        corrupted_df,
        settings,
        "corrupted",
    )

    corrupted_freshness_path = (
        settings.paths.quality_dir
        / "corrupted_freshness_report.json"
    )

    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        corrupted_freshness_path,
    )

    _print_corrupted_gate_warning(
        corrupted_quality,
        corrupted_freshness,
    )

    # The expected state is:
    #   corrupted_quality["success"] == False
    #   corrupted_freshness["is_fresh"] == False
    #
    # IMPORTANT:
    # We deliberately DO NOT stop here.
    # Continuing demonstrates the Silent Failure scenario.
    print(
        "[corruption] Continuing to downstream retrieval/evaluation "
        "despite the corrupted validation result (Silent Failure demo)."
    )

    # ==============================================================
    # 5. Index corrupted data and evaluate it
    # ==============================================================

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )

    corrupted_bundle = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )

    corrupted_metrics = corrupted_bundle.summary

    # ==============================================================
    # 6. REPAIR
    #
    # NEVER repair from corrupted_df.
    # Rebuild entirely from raw_records_json.
    # ==============================================================

    raw_records_path = settings.paths.raw_records_json

    if not raw_records_path.exists():
        raise FileNotFoundError(
            f"Raw records not found: {raw_records_path}. "
            "Hãy chạy script/run_phase1.py trước."
        )

    print("[repair] Loading raw records...")

    records = load_raw_records(raw_records_path)

    if not records:
        raise ValueError(
            f"No raw records found in {raw_records_path}."
        )

    print(
        f"[repair] Loaded {len(records)} raw records. "
        "Rebuilding clean dataframe from raw..."
    )

    repaired_df = build_clean_dataframe(
        records,
        now_utc(),
    )

    print(
        f"[repair] Rebuilt repaired dataset: "
        f"{_paper_count(repaired_df)} rows"
    )

    # ==============================================================
    # 7. Save repaired CSV + JSON
    # ==============================================================

    settings.paths.repaired_clean_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    repaired_df.to_csv(
        settings.paths.repaired_clean_csv,
        index=False,
    )

    _write_dataframe_json(
        repaired_df,
        settings.paths.repaired_clean_json,
    )

    print(
        "[repair] Saved CSV: "
        f"{settings.paths.repaired_clean_csv}"
    )
    print(
        "[repair] Saved JSON: "
        f"{settings.paths.repaired_clean_json}"
    )

    # ==============================================================
    # 8. Quality gate + freshness on repaired data
    # ==============================================================

    print("[quality] Running repaired quality gate...")

    repaired_quality = run_data_quality_checks(
        repaired_df,
        settings,
        "repaired",
    )

    repaired_freshness_path = (
        settings.paths.quality_dir
        / "repaired_freshness_report.json"
    )

    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        repaired_freshness_path,
    )

    if not repaired_quality.get("success"):
        raise RuntimeError(
            "REPAIRED quality gate FAILED unexpectedly. "
            f"failed_expectations="
            f"{repaired_quality.get('failed_expectations')}"
        )

    if not repaired_freshness.get("is_fresh"):
        raise RuntimeError(
            "REPAIRED freshness check FAILED unexpectedly."
        )

    print("[repair] Quality gate: PASSED")
    print("[repair] Freshness: PASSED")

    # ==============================================================
    # 9. Index repaired data and evaluate
    # ==============================================================

    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )

    repaired_bundle = evaluate_pipeline(
        settings,
        repaired_index,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers,
    )

    repaired_metrics = repaired_bundle.summary

    # ==============================================================
    # 10. Generate comparison report
    # ==============================================================

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )

    print(
        "[report] Generated comparison report: "
        f"{settings.paths.comparison_report}"
    )

    # ==============================================================
    # 11. Console metrics comparison
    # ==============================================================

    _print_metrics_table(
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
    )


if __name__ == "__main__":
    main()
