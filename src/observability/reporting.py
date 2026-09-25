from __future__ import annotations

from typing import Any

from core.utils import write_text


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase. Moi so lieu lay tu dict truyen vao, khong hardcode."""
    lines = ["# Phase 1 Report — Baseline Pipeline", ""]

    lines += ["## 1. Nguồn dữ liệu & Lineage", "", "| Thuộc tính | Giá trị |", "|---|---|"]
    lines += [f"| {key} | `{value}` |" for key, value in source_summary.items()]

    lines += ["", "## 2. Kết quả đánh giá RAG (Baseline)", "", "| Metric | Giá trị |", "|---|---:|"]
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        if key in metrics:
            lines.append(f"| {key} | {_fmt(metrics[key])} |")
    ragas = metrics.get("ragas")
    if ragas:
        lines.append(f"\nRagas: `{ragas}`")

    lines += ["", "## 3. Data Quality Gate (Great Expectations 1.x)", ""]
    lines.append(f"**Kết quả tổng:** {'✅ PASS' if quality.get('success') else '❌ FAIL'} "
                 f"(row_count = {quality.get('row_count', 'n/a')})")
    lines += ["", "| Expectation | Column | Kết quả | Unexpected |", "|---|---|:---:|---:|"]
    for result in quality.get("results", []):
        lines.append(
            f"| {result.get('expectation', '')} | {result.get('column') or '—'} | "
            f"{'✅' if result.get('success') else '❌'} | {result.get('unexpected_count', '—')} |"
        )

    lines += ["", "## 4. Freshness SLA", "", "| Thuộc tính | Giá trị |", "|---|---|"]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in freshness.items()]
    lines.append("")
    lines.append(
        "**Đánh giá:** dữ liệu " + ("đạt" if freshness.get("is_fresh") else "**KHÔNG đạt**")
        + f" Freshness SLA (tỷ lệ bài có age_days > {freshness.get('threshold_days', 180)} "
        f"phải ≤ {_fmt(freshness.get('max_stale_ratio', 0.25))})."
    )

    lines += [
        "",
        "## 5. Nhận xét",
        "",
        f"- Pipeline index {source_summary.get('clean_rows')} bài báo sạch vào collection "
        f"`{source_summary.get('collection')}` sau khi Quality Gate "
        f"{'pass' if quality.get('success') else 'fail'}.",
        f"- Retrieval hit rate {_fmt(metrics.get('retrieval_hit_rate'))} và Token F1 "
        f"{_fmt(metrics.get('mean_token_f1'))} là mốc baseline để so sánh với trạng thái Corrupted/Repaired ở Phase 2.",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report so sanh baseline/corrupted/repaired."""
    raise NotImplementedError("Student task: implement corruption comparison report.")
