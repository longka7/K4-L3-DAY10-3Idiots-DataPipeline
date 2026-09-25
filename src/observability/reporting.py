from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import load_settings
from core.utils import read_json, write_text


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
    """Write Markdown report comparing baseline/corrupted/repaired states."""

    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    corrupted_quality_ok = bool(
        corrupted_quality.get("success")
    )
    repaired_quality_ok = bool(
        repaired_quality.get("success")
    )

    corrupted_freshness_ok = bool(
        corrupted_freshness.get("is_fresh")
    )
    repaired_freshness_ok = bool(
        repaired_freshness.get("is_fresh")
    )

    corrupted_failed_expectations = corrupted_quality.get(
        "failed_expectations",
        0,
    )

    corrupted_stale_rows = corrupted_freshness.get(
        "stale_rows",
        0,
    )

    corrupted_total_rows = corrupted_freshness.get(
        "total_rows",
        0,
    )

    freshness_threshold = corrupted_freshness.get(
        "threshold_days",
        180,
    )

    max_stale_ratio = corrupted_freshness.get(
        "max_stale_ratio",
        0.25,
    )

    corrupted_stale_ratio = corrupted_freshness.get(
        "stale_ratio",
        0.0,
    )

    repaired_stale_rows = repaired_freshness.get(
        "stale_rows",
        0,
    )

    repaired_total_rows = repaired_freshness.get(
        "total_rows",
        0,
    )

    def metric_value(
        metrics: dict[str, Any],
        name: str,
    ) -> str:
        value = metrics.get(name)

        if value is None:
            return "N/A"

        if isinstance(value, float):
            return f"{value:.4f}"

        return str(value)

    corrupted_quality_text = (
        "❌ FAILED (Phát hiện lỗi)"
        if not corrupted_quality_ok
        else "⚠️ PASSED (không phát hiện lỗi)"
    )

    repaired_quality_text = (
        "✅ PASSED (Phục hồi sạch)"
        if repaired_quality_ok
        else "❌ FAILED"
    )

    corrupted_freshness_text = (
        f"❌ FAILED ({corrupted_stale_rows}/{corrupted_total_rows} "
        f"rows > {freshness_threshold} ngày)"
        if not corrupted_freshness_ok
        else "⚠️ Đạt chuẩn"
    )

    repaired_freshness_text = (
        f"✅ PASSED ({repaired_stale_rows}/{repaired_total_rows} "
        "stale rows)"
        if repaired_freshness_ok
        else "❌ FAILED"
    )

    lines = [
        "# Corruption / Silent Failure / Repair Report",
        "",
        "## Comparison",
        "",
        "| Metric / Chỉ số | Baseline (Dữ liệu Sạch) | "
        "Corrupted (Dữ liệu Bị Lỗi) | "
        "Repaired (Sau Khi Phục Hồi) |",
        "| :--- | :--- | :--- | :--- |",
        (
            "| **Data Quality Gate** | "
            "Baseline từ Phase 1 | "
            f"{corrupted_quality_text} | "
            f"{repaired_quality_text} |"
        ),
        (
            "| **Kiểm tra Độ Tươi (Freshness)** | "
            "Baseline từ Phase 1 | "
            f"{corrupted_freshness_text} | "
            f"{repaired_freshness_text} |"
        ),
        (
            "| **Retrieval Hit Rate** | "
            f"{metric_value(baseline_metrics, 'retrieval_hit_rate')} | "
            f"{metric_value(corrupted_metrics, 'retrieval_hit_rate')} | "
            f"{metric_value(repaired_metrics, 'retrieval_hit_rate')} |"
        ),
        (
            "| **Mean Token F1** | "
            f"{metric_value(baseline_metrics, 'mean_token_f1')} | "
            f"{metric_value(corrupted_metrics, 'mean_token_f1')} | "
            f"{metric_value(repaired_metrics, 'mean_token_f1')} |"
        ),
        (
            "| **Judge Accuracy** | "
            f"{metric_value(baseline_metrics, 'judge_accuracy')} | "
            f"{metric_value(corrupted_metrics, 'judge_accuracy')} | "
            f"{metric_value(repaired_metrics, 'judge_accuracy')} |"
        ),
        (
            "| **Mean Judge Score** | "
            f"{metric_value(baseline_metrics, 'mean_judge_score')} | "
            f"{metric_value(corrupted_metrics, 'mean_judge_score')} | "
            f"{metric_value(repaired_metrics, 'mean_judge_score')} |"
        ),
        "",
        "## Quality Gate Details",
        "",
        (
            f"- Corrupted: "
            f"`{'PASSED' if corrupted_quality_ok else 'FAILED'}`"
        ),
        (
            f"- Corrupted failed expectations: "
            f"`{corrupted_failed_expectations}`"
        ),
        (
            f"- Repaired: "
            f"`{'PASSED' if repaired_quality_ok else 'FAILED'}`"
        ),
        "",
        "## Freshness Details",
        "",
        f"- Threshold: `{freshness_threshold}` days",
        f"- Maximum stale ratio: `{max_stale_ratio}`",
        f"- Corrupted stale ratio: `{corrupted_stale_ratio}`",
        f"- Corrupted stale rows: "
        f"`{corrupted_stale_rows}/{corrupted_total_rows}`",
        f"- Repaired stale rows: "
        f"`{repaired_stale_rows}/{repaired_total_rows}`",
        "",
        "## Silent Failure Demonstration",
        "",
        "Corrupted data được đưa qua Quality Gate trước. "
        "Khi Quality Gate FAILED, pipeline **không dừng** mà vẫn "
        "index và evaluate corrupted data. Đây là chủ ý để chứng minh "
        "Silent Failure.",
        "",
        "Mỗi state sử dụng một embedding artifact / Chroma collection "
        "riêng:",
        "",
        "- `papers-baseline`",
        "- `papers-corrupted`",
        "- `papers-repaired`",
        "",
        *_corruption_analysis_lines(baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality),
        "## Repair Strategy",
        "",
        "Repair không chỉnh sửa corrupted dataframe và không sử dụng "
        "corrupted dataframe làm nguồn phục hồi.",
        "",
        "Nguồn phục hồi là:",
        "",
        "```text",
        "raw_records_json",
        "    -> load_raw_records()",
        "    -> build_clean_dataframe(records, now_utc())",
        "    -> repaired clean CSV/JSON",
        "    -> repaired quality + freshness",
        "    -> repaired embedding index",
        "    -> repaired evaluation",
        "```",
        "",
        "Do đó repaired state được tái tạo độc lập từ raw data.",
        "",
    ]

    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


# Tac dong ky vong cua tung loai loi len RAG / Quality Gate (dung de doi chieu voi so lieu thuc te).
CORRUPTION_EFFECTS = {
    "drop_latest_records": ("Không (GX không biết bài nào bị thiếu)", "Tài liệu đúng không còn trong index → retrieval miss"),
    "blank_summary": ("Có — summary length ≥ 30", "Câu hỏi summary trả về rỗng → Token F1 = 0"),
    "inject_noise": ("Không (độ dài vẫn hợp lệ)", "Câu trả lời chứa từ rác/đảo trật tự → F1 giảm"),
    "truncate_title": ("Có — title length ≥ 8", "Tra cứu theo tiêu đề chính xác thất bại → phụ thuộc semantic search"),
    "stale_date": ("Freshness SLA (không phải GX expectation)", "Câu hỏi ngày xuất bản trả sai ngày"),
    "duplicate_rows": ("Có — paper_id unique", "Top-k bị chiếm bởi bản trùng, ngữ cảnh bị loãng"),
}


def _corruption_analysis_lines(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
) -> list[str]:
    """Bang 6 loi da tiem + phan tich tu artifact thuc te (corruption_log, corrupted_answers)."""
    settings = load_settings()
    lines = ["## Injected Corruptions (từ corruption_log.json)", ""]
    log = read_json(settings.paths.corruption_log) if settings.paths.corruption_log.exists() else []
    lines += [
        "| # | Corruption | Số bài bị ảnh hưởng | Rows before → after | GX/SLA phát hiện? | Tác động lên RAG |",
        "|---:|---|---:|---|---|---|",
    ]
    for entry in log:
        detected, impact = CORRUPTION_EFFECTS.get(entry.get("corruption", ""), ("—", "—"))
        lines.append(
            f"| {entry.get('step')} | `{entry.get('corruption')}` | {len(entry.get('affected_paper_ids', []))} | "
            f"{entry.get('rows_before')} → {entry.get('rows_after')} | {detected} | {impact} |"
        )

    failed = [r for r in corrupted_quality.get("results", []) if not r.get("success")]
    lines += ["", "### Expectation bị vi phạm trên dữ liệu Corrupted", ""]
    lines += [
        f"- `{r.get('expectation')}` (column `{r.get('column') or 'table'}`): {r.get('unexpected_count')} giá trị lỗi"
        for r in failed
    ] or ["- (không có)"]

    lines += ["", "### Câu hỏi bị trả lời sai trên dữ liệu Corrupted (từ corrupted_answers.json)", ""]
    answers = read_json(settings.paths.corrupted_answers) if settings.paths.corrupted_answers.exists() else []
    wrong = [a for a in answers if not a.get("retrieval_hit") or a.get("token_f1", 0) < 1.0]
    if wrong:
        lines += ["| ID | Loại | Retrieval hit | Token F1 | Judge | Câu trả lời của hệ thống |", "|---|---|:---:|---:|---:|---|"]
        for a in wrong:
            answer = str(a.get("answer", "")).replace("|", "\\|").replace("\n", " ")[:90]
            lines.append(
                f"| {a.get('id')} | {a.get('question_type')} | {'✅' if a.get('retrieval_hit') else '❌'} | "
                f"{a.get('token_f1', 0):.2f} | {a.get('judge', {}).get('score')} | {answer} |"
            )
    else:
        lines.append("- Không có câu nào bị sai.")

    def delta(name: str, other: dict[str, Any]) -> str:
        base, value = baseline_metrics.get(name), other.get(name)
        return "N/A" if base is None or value is None else f"{value - base:+.4f}"

    lines += [
        "",
        "## Phân tích",
        "",
        f"- **Suy giảm:** Hit Rate {delta('retrieval_hit_rate', corrupted_metrics)}, "
        f"Token F1 {delta('mean_token_f1', corrupted_metrics)}, "
        f"Judge Accuracy {delta('judge_accuracy', corrupted_metrics)} so với Baseline.",
        f"- **Silent Failure:** hệ thống vẫn trả lời đủ {len(answers)} câu, không raise lỗi nào; "
        f"{len(wrong)} câu sai/thiếu chỉ lộ ra khi đối chiếu ground truth. "
        "Chỉ Quality Gate + Freshness SLA đặt TRƯỚC bước index mới cảnh báo được sớm.",
        "- **Giới hạn của GX:** `drop_latest_records` và `inject_noise` không vi phạm expectation nào "
        "(số dòng vẫn trong ngưỡng, độ dài summary vẫn hợp lệ) → cần thêm kiểm tra so khớp với nguồn (row count so với raw) "
        "hoặc kiểm tra ngữ nghĩa để bắt các lỗi này.",
        f"- **Phục hồi:** Repaired lệch Baseline Hit Rate {delta('retrieval_hit_rate', repaired_metrics)}, "
        f"Token F1 {delta('mean_token_f1', repaired_metrics)}. Repair tái tạo từ raw nên chạy lại bao nhiêu lần "
        "cũng cho cùng dataset (idempotent).",
        "",
    ]
    return lines
