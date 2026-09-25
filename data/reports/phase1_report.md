# Phase 1 Report — Baseline Pipeline

## 1. Nguồn dữ liệu & Lineage

| Thuộc tính | Giá trị |
|---|---|
| source_api | `Crossref REST API` |
| mode | `offline snapshot (set REFRESH_SOURCE=1 for live)` |
| source_query | `agentic retrieval augmented generation large language model` |
| source_filter | `from-pub-date:2026-03-29,has-abstract:true` |
| run_date | `2026-09-25` |
| raw_records | `24` |
| clean_rows | `24` |
| test_questions | `10` |
| collection | `papers-baseline` |
| embedding_model | `sentence-transformers/all-MiniLM-L6-v2` |
| llm | `gemini/gemini-3.1-flash-lite` |

## 2. Kết quả đánh giá RAG (Baseline)

| Metric | Giá trị |
|---|---:|
| samples | 10 |
| retrieval_hit_rate | 1.0000 |
| mean_token_f1 | 1.0000 |
| judge_accuracy | 1.0000 |
| mean_judge_score | 5 |

Ragas: `{'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'}`

## 3. Data Quality Gate (Great Expectations 1.x)

**Kết quả tổng:** ✅ PASS (row_count = 24)

| Expectation | Column | Kết quả | Unexpected |
|---|---|:---:|---:|
| expect_table_row_count_to_be_between | — | ✅ | None |
| expect_column_values_to_not_be_null | paper_id | ✅ | 0 |
| expect_column_values_to_be_unique | paper_id | ✅ | 0 |
| expect_column_values_to_not_be_null | title | ✅ | 0 |
| expect_column_value_lengths_to_be_between | title | ✅ | 0 |
| expect_column_values_to_not_be_null | text_for_embedding | ✅ | 0 |
| expect_column_value_lengths_to_be_between | summary | ✅ | 0 |

## 4. Freshness SLA

| Thuộc tính | Giá trị |
|---|---|
| latest_published | 2026-07-22 |
| oldest_published | 2026-03-28 |
| stale_rows | 1 |
| total_rows | 24 |
| stale_ratio | 0.0417 |
| threshold_days | 180 |
| max_stale_ratio | 0.2500 |
| is_fresh | True |

**Đánh giá:** dữ liệu đạt Freshness SLA (tỷ lệ bài có age_days > 180 phải ≤ 0.2500).

## 5. Nhận xét

- Pipeline index 24 bài báo sạch vào collection `papers-baseline` sau khi Quality Gate pass.
- Retrieval hit rate 1.0000 và Token F1 1.0000 là mốc baseline để so sánh với trạng thái Corrupted/Repaired ở Phase 2.
