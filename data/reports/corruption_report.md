# Corruption / Silent Failure / Repair Report

## Comparison

| Metric / Chỉ số | Baseline (Dữ liệu Sạch) | Corrupted (Dữ liệu Bị Lỗi) | Repaired (Sau Khi Phục Hồi) |
| :--- | :--- | :--- | :--- |
| **Data Quality Gate** | Baseline từ Phase 1 | ❌ FAILED (Phát hiện lỗi) | ✅ PASSED (Phục hồi sạch) |
| **Kiểm tra Độ Tươi (Freshness)** | Baseline từ Phase 1 | ❌ FAILED (9/23 rows > 180 ngày) | ✅ PASSED (1/24 stale rows) |
| **Retrieval Hit Rate** | 1.0000 | 0.6000 | 1.0000 |
| **Mean Token F1** | 1.0000 | 0.7741 | 1.0000 |
| **Judge Accuracy** | 1.0000 | 0.8000 | 1.0000 |
| **Mean Judge Score** | 5 | 4.2000 | 5 |

## Quality Gate Details

- Corrupted: `FAILED`
- Corrupted failed expectations: `3`
- Repaired: `PASSED`

## Freshness Details

- Threshold: `180` days
- Maximum stale ratio: `0.25`
- Corrupted stale ratio: `0.3913`
- Corrupted stale rows: `9/23`
- Repaired stale rows: `1/24`

## Silent Failure Demonstration

Corrupted data được đưa qua Quality Gate trước. Khi Quality Gate FAILED, pipeline **không dừng** mà vẫn index và evaluate corrupted data. Đây là chủ ý để chứng minh Silent Failure.

Mỗi state sử dụng một embedding artifact / Chroma collection riêng:

- `papers-baseline`
- `papers-corrupted`
- `papers-repaired`

## Injected Corruptions (từ corruption_log.json)

| # | Corruption | Số bài bị ảnh hưởng | Rows before → after | GX/SLA phát hiện? | Tác động lên RAG |
|---:|---|---:|---|---|---|
| 1 | `drop_latest_records` | 5 | 24 → 19 | Không (GX không biết bài nào bị thiếu) | Tài liệu đúng không còn trong index → retrieval miss |
| 2 | `blank_summary` | 3 | 19 → 19 | Có — summary length ≥ 30 | Câu hỏi summary trả về rỗng → Token F1 = 0 |
| 3 | `inject_noise` | 3 | 19 → 19 | Không (độ dài vẫn hợp lệ) | Câu trả lời chứa từ rác/đảo trật tự → F1 giảm |
| 4 | `truncate_title` | 3 | 19 → 19 | Có — title length ≥ 8 | Tra cứu theo tiêu đề chính xác thất bại → phụ thuộc semantic search |
| 5 | `stale_date` | 7 | 19 → 19 | Freshness SLA (không phải GX expectation) | Câu hỏi ngày xuất bản trả sai ngày |
| 6 | `duplicate_rows` | 4 | 19 → 23 | Có — paper_id unique | Top-k bị chiếm bởi bản trùng, ngữ cảnh bị loãng |

### Expectation bị vi phạm trên dữ liệu Corrupted

- `expect_column_values_to_be_unique` (column `paper_id`): 8 giá trị lỗi
- `expect_column_value_lengths_to_be_between` (column `title`): 4 giá trị lỗi
- `expect_column_value_lengths_to_be_between` (column `summary`): 3 giá trị lỗi

### Câu hỏi bị trả lời sai trên dữ liệu Corrupted (từ corrupted_answers.json)

| ID | Loại | Retrieval hit | Token F1 | Judge | Câu trả lời của hệ thống |
|---|---|:---:|---:|---:|---|
| eval_001 | summary | ❌ | 0.74 | 4 | An extended empirical study on tatic benchmarks fail to capture domain drift in enterprise |
| eval_002 | authors | ❌ | 1.00 | 5 | Phong Vu, Ngan Hoang |
| eval_003 | date | ❌ | 0.00 | 2 | 2026-06-04 |
| eval_004 | categories | ❌ | 1.00 | 5 | Software Engineering, Data Systems |
| eval_009 | summary | ✅ | 0.00 | 1 |  |

## Phân tích

- **Suy giảm:** Hit Rate -0.4000, Token F1 -0.2259, Judge Accuracy -0.2000 so với Baseline.
- **Silent Failure:** hệ thống vẫn trả lời đủ 10 câu, không raise lỗi nào; 5 câu sai/thiếu chỉ lộ ra khi đối chiếu ground truth. Chỉ Quality Gate + Freshness SLA đặt TRƯỚC bước index mới cảnh báo được sớm.
- **Giới hạn của GX:** `drop_latest_records` và `inject_noise` không vi phạm expectation nào (số dòng vẫn trong ngưỡng, độ dài summary vẫn hợp lệ) → cần thêm kiểm tra so khớp với nguồn (row count so với raw) hoặc kiểm tra ngữ nghĩa để bắt các lỗi này.
- **Phục hồi:** Repaired lệch Baseline Hit Rate +0.0000, Token F1 +0.0000. Repair tái tạo từ raw nên chạy lại bao nhiêu lần cũng cho cùng dataset (idempotent).

## Repair Strategy

Repair không chỉnh sửa corrupted dataframe và không sử dụng corrupted dataframe làm nguồn phục hồi.

Nguồn phục hồi là:

```text
raw_records_json
    -> load_raw_records()
    -> build_clean_dataframe(records, now_utc())
    -> repaired clean CSV/JSON
    -> repaired quality + freshness
    -> repaired embedding index
    -> repaired evaluation
```

Do đó repaired state được tái tạo độc lập từ raw data.

