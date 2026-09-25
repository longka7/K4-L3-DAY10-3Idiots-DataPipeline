from __future__ import annotations

import sys
from typing import Any
import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import _fmt, generate_corruption_report
from pipelines.phase1 import save_clean_artifacts
from retrieval.index import LocalEmbeddingIndex

# Dam bao terminal Windows (cp1252) khong bi loi UnicodeEncodeError
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _print_corrupted_gate_warning(
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """In canh bao ro rang ra console khi tap corrupted vi pham Quality Gate hoac Freshness SLA."""
    quality_ok = bool(quality.get("success"))
    freshness_ok = bool(freshness.get("is_fresh"))

    print()
    print("!" * 80)
    if not quality_ok:
        print(
            f"[CANH BAO CHAT LUONG] Corrupted Quality Gate FAILED: "
            f"{quality.get('failed_expectations', 'unknown')} expectation(s) bi vi pham!"
        )
        for r in quality.get("results", []):
            if not r.get("success"):
                print(
                    f"  - Vi pham: {r.get('expectation')} tren cot "
                    f"`{r.get('column') or 'table'}` ({r.get('unexpected_count')} loi)"
                )

    if not freshness_ok:
        stale_rows = freshness.get("stale_rows", "unknown")
        total_rows = freshness.get("total_rows", "unknown")
        threshold = freshness.get("threshold_days", "unknown")
        ratio = freshness.get("stale_ratio", 0.0)
        print(
            f"[CANH BAO DO TUOI] Corrupted Freshness SLA FAILED: "
            f"{stale_rows}/{total_rows} bai bao ({ratio*100:.1f}%) co tuoi doi vuot nguong {threshold} ngay!"
        )
    print("!" * 80)
    print()


def _print_metrics_table(
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> None:
    """In bang so sanh 3 cot: Baseline | Corrupted | Repaired theo yeu cau de bai."""
    metrics = (
        ("retrieval_hit_rate", "Retrieval Hit Rate"),
        ("mean_token_f1", "Mean Token F1"),
        ("judge_accuracy", "Judge Accuracy"),
        ("mean_judge_score", "Mean Judge Score"),
    )

    print()
    print("=" * 86)
    print(f"{'BANG SO SANH HIEU NANG 3 TRANG THAI: BASELINE | CORRUPTED | REPAIRED':^86}")
    print("=" * 86)

    header = f"{'Metric / Chi so':<26} | {'Baseline':^16} | {'Corrupted':^16} | {'Repaired':^16}"
    print(header)
    print("-" * len(header))

    for key, display_name in metrics:
        b_val = _fmt(baseline_metrics.get(key))
        c_val = _fmt(corrupted_metrics.get(key))
        r_val = _fmt(repaired_metrics.get(key))
        print(f"{display_name:<26} | {b_val:^16} | {c_val:^16} | {r_val:^16}")

    print("=" * 86)
    print()


def main() -> None:
    """Luong thuc thi Phase 2: Corruption -> Silent Failure Demo -> Idempotent Self-Healing Repair -> Comparison.

    Thanh vien phu trach: TV2 (Nguyen Van An).
    Cac buoc:
    a. Load settings, kiem tra baseline artifacts.
    b. Tiem 6 loi du lieu (corrupt_clean_dataframe) & luu corrupted artifacts.
    c. Kiem dinh Quality Gate GX 1.x & Freshness SLA tren corrupted (ky vong FAIL).
    d. VAN index vao collection 'papers-corrupted' va evaluate de chung minh Silent Failure.
    e. BONUS B2 & REPAIR: Tu dong kich hoat co che Self-healing (rollback ve raw records).
       Tai tao doc lap qua build_clean_dataframe (Idempotent), kiem dinh lai (phai PASS).
    f. Thang cap collection 'papers-repaired' lam serving collection, evaluate repaired.
    g. Xuat bao cao doi chieu Markdown (generate_corruption_report) & in bang console 3 cot.
    """
    settings = load_settings()

    # -------------------------------------------------------------------------
    # BUOC a: Kiem tra du lieu dau vao tu Phase 1
    # -------------------------------------------------------------------------
    baseline_metrics_path = settings.paths.baseline_metrics
    clean_json_path = settings.paths.clean_json

    if not baseline_metrics_path.exists() or not clean_json_path.exists():
        raise FileNotFoundError(
            "Khong tim thay baseline metrics hoac clean dataset. "
            "Hay chay script/run_phase1.py truoc."
        )

    baseline_metrics = read_json(baseline_metrics_path)
    clean_df = pd.read_json(clean_json_path, orient="records")

    if clean_df.empty:
        raise ValueError(
            f"Tap du lieu sach tai {clean_json_path} bi rong. Hay chay script/run_phase1.py truoc."
        )

    print(f"[flow] Da tai tap du lieu sach Baseline: {len(clean_df)} dong tu {clean_json_path.name}")

    # -------------------------------------------------------------------------
    # BUOC b: Tiem loi co kiem soat (Data Corruption Suite)
    # -------------------------------------------------------------------------
    print("[flow] Tien hanh tiem 6 loi du lieu thuc te bang corrupt_clean_dataframe...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    print(f"[flow] Da sinh tap du lieu Corrupted: {len(corrupted_df)} dong")

    # Luu artifacts CSV va JSON (orient='records', giu nguyen list columns)
    save_clean_artifacts(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    print(
        f"[flow] Da luu Corrupted artifacts: "
        f"{settings.paths.corrupted_clean_csv.name}, {settings.paths.corrupted_clean_json.name}"
    )

    # -------------------------------------------------------------------------
    # BUOC c: Tram kiem soat chat luong du lieu (Data Quality Gate & Freshness)
    # -------------------------------------------------------------------------
    print("[flow] Chay Quality Gate (Great Expectations 1.x) tren du lieu Corrupted...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")

    corrupted_freshness_path = settings.paths.quality_dir / "corrupted_freshness_report.json"
    corrupted_freshness = build_freshness_report(corrupted_df, settings, corrupted_freshness_path)

    # In canh bao ro rang ra console khi gate FAIL
    _print_corrupted_gate_warning(corrupted_quality, corrupted_freshness)

    # -------------------------------------------------------------------------
    # BUOC d: Silent Failure Demonstration
    # Du du lieu loi, ta VAN index vao collection rieng 'papers-corrupted'
    # de chung minh Agent van tra loi tu tin nhung ket qua sai lech nghiem trong.
    # -------------------------------------------------------------------------
    print(
        "[flow] CHUNG MINH SILENT FAILURE: Van index du lieu loi vao collection "
        f"'{settings.corrupted_collection_name}' de danh gia muc do suy giam..."
    )
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
    print(
        f"[flow] Corrupted Evaluation: Hit Rate = {_fmt(corrupted_metrics['retrieval_hit_rate'])}, "
        f"Token F1 = {_fmt(corrupted_metrics['mean_token_f1'])}, "
        f"Judge Accuracy = {_fmt(corrupted_metrics['judge_accuracy'])}"
    )

    # -------------------------------------------------------------------------
    # BUOC e (BONUS B2): Co che Tu Phuc Hoi (Automated Self-Healing) & Cach Ly
    # -------------------------------------------------------------------------
    quality_failed = not corrupted_quality.get("success")
    freshness_failed = not corrupted_freshness.get("is_fresh")
    auto_repair_triggered = quality_failed or freshness_failed

    reasons: list[str] = []
    if quality_failed:
        reasons.append(
            f"Quality Gate FAILED ({corrupted_quality.get('failed_expectations', 0)} expectations vi pham)"
        )
    if freshness_failed:
        reasons.append(
            f"Freshness SLA FAILED ({corrupted_freshness.get('stale_rows', 0)}/{corrupted_freshness.get('total_rows', 0)} bai qua han)"
        )
    auto_repair_reason = "; ".join(reasons) if reasons else "Manual / preventative repair flow triggered."

    print()
    print("=" * 86)
    print(f"{'BONUS B2: AUTOMATED SELF-HEALING & SERVING PROMOTION GATE':^86}")
    print("=" * 86)
    if auto_repair_triggered:
        print(f"  [!] Auto-repair triggered: YES")
        print(f"  [!] Ly do: {auto_repair_reason}")
        print(
            f"  [!] Chinh sach an toan (Safety Quarantine): CACH LY collection "
            f"'{settings.corrupted_collection_name}' -> KHONG promote lam Serving Collection!"
        )
        print(f"  [!] Hanh dong: Tu dong kich hoat luong rollback ve nguon tho (Raw Preservation).")
    else:
        print("  [*] Du lieu dat chuan. Khong can kich hoat auto-repair.")
    print("=" * 86)
    print()

    # -------------------------------------------------------------------------
    # BUOC e (tiep): REPAIR (Idempotent: Tai tao tu Raw Preservation)
    # KHONG BAO GIO sua chap va tu du lieu ban. Ta tai tao doc lap tu raw_records_json.
    # -------------------------------------------------------------------------
    raw_records_path = settings.paths.raw_records_json
    if not raw_records_path.exists():
        raise FileNotFoundError(
            f"Khong tim thay raw records tai {raw_records_path}. Hay chay script/run_phase1.py truoc."
        )

    print("[repair] Tai raw records nguyen ban tu Data Lineage...")
    records = load_raw_records(raw_records_path)
    if not records:
        raise ValueError(f"Khong co ban ghi nao trong {raw_records_path}.")

    print(f"[repair] Tai tao Clean DataFrame tu {len(records)} raw records (Idempotent transformation)...")
    repaired_df = build_clean_dataframe(records, now_utc())

    # Luu repaired artifacts
    save_clean_artifacts(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    print(
        f"[repair] Da luu Repaired artifacts: "
        f"{settings.paths.repaired_clean_csv.name}, {settings.paths.repaired_clean_json.name}"
    )

    # Chay Quality Gate va Freshness SLA tren du lieu Repaired
    print("[repair] Kiem dinh Quality Gate va Freshness SLA tren du lieu Repaired...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")

    repaired_freshness_path = settings.paths.quality_dir / "repaired_freshness_report.json"
    repaired_freshness = build_freshness_report(repaired_df, settings, repaired_freshness_path)

    if not repaired_quality.get("success"):
        raise RuntimeError(
            f"Repaired Quality Gate THAT BAI: {repaired_quality.get('failed_expectations')} loi vi pham!"
        )
    if not repaired_freshness.get("is_fresh"):
        raise RuntimeError("Repaired Freshness SLA THAT BAI bat ngo!")

    print("[repair] Quality Gate: PASSED (100% expectations thoa man)")
    print("[repair] Freshness SLA: PASSED (Dat tieu chuan do tuoi)")

    # Thang cap collection phuc vu sau khi kiem dinh dat chuan
    promoted_collection = settings.repaired_collection_name
    print(f"[Self-Healing] PHE DUYET: Thang cap collection '{promoted_collection}' lam Serving Collection chinh thuc.")

    # Index du lieu da phuc hoi vao collection rieng 'papers-repaired'
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
    print(
        f"[repair] Repaired Evaluation: Hit Rate = {_fmt(repaired_metrics['retrieval_hit_rate'])}, "
        f"Token F1 = {_fmt(repaired_metrics['mean_token_f1'])}, "
        f"Judge Accuracy = {_fmt(repaired_metrics['judge_accuracy'])}"
    )

    # -------------------------------------------------------------------------
    # BUOC f: Xuat Bao Cao Doi Chieu 3 Trang Thai (Markdown Report)
    # -------------------------------------------------------------------------
    auto_repair_info = {
        "auto_repair_triggered": auto_repair_triggered,
        "reason": auto_repair_reason,
        "quarantined_collection": settings.corrupted_collection_name,
        "promoted_collection": promoted_collection,
    }

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_metrics,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        auto_repair_info=auto_repair_info,
    )
    print(f"[flow] Da tao thanh cong bao cao so sanh 3 trang thai -> {settings.paths.comparison_report}")

    # -------------------------------------------------------------------------
    # BUOC g: In Bang Console Doi Chieu 3 Cot (Baseline | Corrupted | Repaired)
    # -------------------------------------------------------------------------
    _print_metrics_table(baseline_metrics, corrupted_metrics, repaired_metrics)
    print("[flow] Hoan tat luong Corruption & Idempotent Repair (Exit code 0).")


if __name__ == "__main__":
    main()
