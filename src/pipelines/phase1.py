from __future__ import annotations

import json
import sys
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex

DEMO_QUESTIONS = 2


def save_clean_artifacts(df: pd.DataFrame, csv_path, json_path) -> None:
    """Luu CSV + JSON (list records). Qua to_json de ep kieu numpy/Int64 ve JSON thuan."""
    write_csv(df, csv_path)
    write_json(json_path, json.loads(df.to_json(orient="records", force_ascii=True)))


def _load_or_build_test_set(df: pd.DataFrame, settings: Settings) -> list[dict[str, Any]]:
    # Test set co dinh giua cac lan chay de so sanh baseline/corrupted/repaired cong bang.
    if settings.paths.eval_testset.exists() and not settings.refresh_test_set:
        print(f"[phase1] Reusing fixed test set {settings.paths.eval_testset.name}.")
        return read_json(settings.paths.eval_testset)
    return build_test_set(df, settings.paths.eval_testset)


def _run_agent_demo(settings: Settings, index: LocalEmbeddingIndex, test_set: list[dict[str, Any]]) -> None:
    """Demo LLM agent (tool-calling) tren vai cau hoi. Loi LLM khong duoc lam hong pipeline."""
    demo: list[dict[str, Any]] = []
    try:
        agent = build_agent(settings, index)
        for item in test_set[:DEMO_QUESTIONS]:
            demo.append({"question": item["question"], "answer": str(run_agent_question(agent, item["question"]))})
    except Exception as exc:  # noqa: BLE001 - demo la optional
        demo.append({"error": f"Agent demo skipped: {exc}"})
    write_json(settings.paths.demo_answers, demo)


def main() -> None:
    settings = load_settings()
    run_date = now_utc()
    print(f"[phase1] Run date: {run_date.isoformat()}")

    # 1-2. Ingestion + raw preservation (live API hoac snapshot offline).
    records = fetch_source_records(settings)
    print(f"[phase1] Raw records: {len(records)}")

    # 3-4. Cleaning + luu clean artifacts.
    clean_df = build_clean_dataframe(records, run_date)
    save_clean_artifacts(clean_df, settings.paths.clean_csv, settings.paths.clean_json)
    print(f"[phase1] Clean rows: {len(clean_df)} -> {settings.paths.clean_csv.name}, {settings.paths.clean_json.name}")

    # 5. Quality gate TRUOC khi index: data xau khong duoc vao vector store.
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(f"[phase1] Quality gate success={quality['success']} | fresh={freshness['is_fresh']} "
          f"({freshness['stale_rows']}/{freshness['total_rows']} stale)")
    if not quality["success"]:
        print("[phase1] Quality gate FAILED -> stop, khong index du lieu xau. Xem data/quality/.", file=sys.stderr)
        sys.exit(1)

    # 6. Index vao Chroma collection `papers-baseline`.
    index = LocalEmbeddingIndex.build(clean_df, settings, embeddings_output_path=settings.paths.embeddings_json)
    print(f"[phase1] Indexed {len(index.documents)} docs into collection '{index.collection_name}'.")

    # 7-8. Test set co dinh + evaluate baseline.
    test_set = _load_or_build_test_set(clean_df, settings)
    bundle = evaluate_pipeline(
        settings, index, settings.paths.eval_testset, settings.paths.baseline_metrics, settings.paths.baseline_answers
    )
    metrics = bundle.summary
    print(f"[phase1] Baseline: hit_rate={metrics['retrieval_hit_rate']:.3f} token_f1={metrics['mean_token_f1']:.3f} "
          f"judge_acc={metrics['judge_accuracy']:.3f} judge_score={metrics['mean_judge_score']:.2f}")

    # 9. Report.
    source_summary = {
        "source_api": settings.source_api,
        "mode": "live API" if settings.refresh_source else "offline snapshot (set REFRESH_SOURCE=1 for live)",
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "run_date": run_date.date().isoformat(),
        "raw_records": len(records),
        "clean_rows": len(clean_df),
        "test_questions": len(test_set),
        "collection": index.collection_name,
        "embedding_model": settings.embedding_model,
        "llm": f"{settings.llm_provider}/{settings.model_name}",
    }
    generate_phase1_report(settings.paths.baseline_report, source_summary, metrics, quality, freshness)
    print(f"[phase1] Report -> {settings.paths.baseline_report}")

    # 10. Demo agent (optional).
    _run_agent_demo(settings, index, test_set)
    print("[phase1] Done.")
