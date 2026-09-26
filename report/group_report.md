# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 |
| Tên nhóm | 3Idiots |
| Repository | https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Long Khánh | 2A202602649 | Trưởng nhóm — Ingestion, Cleaning, Observability, Evaluation, Integration | `ingestion/crossref.py`, `ingestion/cleaning.py`, `observability/quality.py`, `evaluation/testset.py`, `pipelines/phase1.py`, `generate_phase1_report`; tích hợp & sửa `corruption.py`, self-healing gate, judge retry |
| 2 | Nguyễn Văn An | 2A202602776 | Flow Orchestration, Repair & Comparison Report | `pipelines/corruption_flow.py` (bản hiện tại), `generate_corruption_report`, khung Bonus B2 |
| 3 | Nguyễn Tuấn Khanh | 2A202602819 | Corruption Suite (bản đầu) | Bản đầu `ingestion/corruption.py`, `corruption_flow.py`, `generate_corruption_report` (sau đó được TV1/TV2 refactor để phù hợp với pipeline) |

## 2. Tóm tắt kết quả

Nhóm hoàn thành đủ CP0–CP5: pipeline Crossref → raw → clean → Quality Gate (Great Expectations 1.18, ephemeral context) + Freshness SLA → ChromaDB (MiniLM-L6-v2) → đánh giá RAG, và luồng Phase 2 tiêm 6 lỗi → đánh giá lại → repair idempotent từ raw → báo cáo 3 trạng thái. Hai lệnh `run_phase1.py` và `run_corruption_flow.py` đều exit 0 trên phiên bản nộp.

Baseline trên 24 bài / 10 câu hỏi đạt Hit Rate 1.0, Token F1 1.0, Judge Accuracy 1.0. Sau corruption, Hit Rate giảm còn 0.6, Token F1 0.7741, Judge Accuracy 0.8, trong khi hệ thống vẫn trả lời đủ 10 câu mà không báo lỗi (Silent Failure). Quality Gate phát hiện 3/7 expectation bị vi phạm (trùng `paper_id`, `title` < 8 ký tự, `summary` < 30 ký tự) và Freshness SLA báo `is_fresh=False` (9/23 = 39.1% bài quá 180 ngày).

Lỗi ảnh hưởng mạnh nhất là `drop_latest_records`: 4/10 câu hỏi mất tài liệu đúng khỏi index, và GX **không** bắt được vì số dòng (19) vẫn nằm trong ngưỡng. Repair tái tạo từ `crossref_records.json` đưa mọi chỉ số về đúng baseline; dataset repaired trùng khớp 100% với dataset clean.

Giới hạn chính: `qa.py` là extractive nên baseline đạt tuyệt đối (1.0) — thang đo nhạy với mất tài liệu nhưng ít nhạy với nhiễu ngữ nghĩa; GX không có kiểm tra đối chiếu với nguồn nên bỏ sót mất dữ liệu.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API (REFRESH_SOURCE=1) | snapshot offline data/raw/crossref_response.json
    -> parse_crossref_payload -> data/raw/crossref_records.json          (raw preservation, lineage)
    -> build_clean_dataframe  -> data/clean/papers_clean.{csv,json}
    -> QUALITY GATE (GX 1.x + Freshness SLA)  --FAIL--> dừng, không index
    -> LocalEmbeddingIndex.build -> ChromaDB collection papers-baseline
    -> build_test_set (cố định) -> evaluate_pipeline -> baseline_metrics.json, phase1_report.md
    -> corrupt_clean_dataframe (6 lỗi) -> quality/freshness (FAIL) -> papers-corrupted -> corrupted_metrics.json
    -> self-healing: gate FAIL => cách ly papers-corrupted, repair từ raw records
    -> quality/freshness (PASS) -> papers-repaired (serving) -> repaired_metrics.json
    -> corruption_report.md (3 trạng thái) + serving_state.json
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref `/works` hoặc snapshot | Retry + backoff cho 429/5xx, fallback snapshot, parse DOI/title/abstract/author/subject/date, bỏ JATS tag | `data/raw/crossref_response.json`, `crossref_records.json` | TV1 |
| Cleaning | `list[PaperRecord]` | Normalize text/list, ngày `YYYY-MM-DD`, lọc row xấu, dedup `paper_id`, `age_days`, `text_for_embedding` 5 phần | `data/clean/papers_clean.{csv,json}` | TV1 |
| Embedding/index | Clean dataframe | MiniLM-L6-v2 (normalize), Chroma cosine, 1 collection/trạng thái | `data/chroma/` (3 collections) | Starter code |
| Evaluation | Clean dataframe | Test set 10 câu cố định; Hit Rate, Token F1, LLM Judge (retry lỗi mạng) | `data/eval/test_set.json`, `data/results/*_metrics.json` | TV1 |
| Observability | Dataframe | GX 1.x: row count, not-null, unique, value length; Freshness SLA | `data/quality/*_quality_report.json`, `*_freshness_report.json` | TV1 |
| Corruption/repair | Clean df / raw records | 6 lỗi deterministic (seed 42); repair = rebuild từ raw | `corruption_log.json`, `papers_clean_{corrupted,repaired}.*` | TV3 (bản đầu), TV1 (logic hiện tại) |
| Orchestration | Artifacts Phase 1 | Corrupt → gate → Silent Failure demo → self-healing → report | `corruption_report.md`, `serving_state.json` | TV2 (flow), TV1 (gate logic B2) |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `gemini` |
| `LLM_MODEL` | `gemini-3.1-flash-lite` (`gemini-2.5-flash` trả 404 với tài khoản mới) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 (`max_results=24`, snapshot offline) |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày, tối đa 25% bài quá hạn |
| Random seed | 42 (corruption) |

### Lệnh cài đặt

```bash
uv sync
cp .env.example .env   # điền GOOGLE_API_KEY
```

### Lệnh chạy

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công (exit 0) | 2026-09-25 17:40 (GMT+7) | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công (exit 0) | 2026-09-25 17:41 (GMT+7) | `data/results/{corrupted,repaired}_metrics.json`, `data/reports/corruption_report.md` |

Cả 30 lượt LLM Judge (3 trạng thái × 10 câu) đều được Gemini chấm thật — không lượt nào rơi về heuristic fallback (kiểm tra `judge.reasoning` trong `data/results/*_answers.json`).

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API `https://api.crossref.org/works` (chạy nộp bài dùng snapshot offline) |
| Query/filter | `agentic retrieval augmented generation large language model`; `from-pub-date:<run_date-180d>,has-abstract:true` |
| Thời điểm lấy dữ liệu | Snapshot kèm starter repo; bài mới nhất 2026-07-22 |
| Số record nhận được | 24 (24 hợp lệ sau parse) |
| Cơ chế retry/backoff | 3 lần, backoff 2s/4s cho 429/500/502/503/504 và lỗi mạng; hết lượt thì fallback snapshot |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | str (DOI, lowercase) | Có | Khóa định danh | Bỏ record |
| `title` | str | Có (≥ 8 ký tự) | Tiêu đề | Bỏ record |
| `summary` | str | Có (≥ 30 ký tự) | Abstract đã bỏ JATS | Bỏ record |
| `authors`, `categories` | list[str] | Không | Tác giả / subject | List rỗng |
| `published` | str `YYYY-MM-DD` | Có | Ngày xuất bản | Fallback online → print → issued → created; không có thì bỏ |
| `updated` | str `YYYY-MM-DD` | Không | Ngày cập nhật | Lấy `published` |
| `age_days` | int | Có | `(run_date - published).days` | Tính lại mỗi lần chạy |
| `text_for_embedding` | str | Có | Văn bản đưa vào embedding | Sinh từ 5 trường |

### Quy tắc cleaning

| Quy tắc | Quality dimension | Số record bị tác động | Cách xác minh |
| --- | --- | --: | --- |
| Bỏ JATS/HTML tag, decode entity, gom khoảng trắng | Validity | 24 (mọi abstract có `<jats:p>`) | Không còn `<` trong `summary` |
| Loại record thiếu id/ngày, title < 8, summary < 30 | Completeness | 0 | Log `[cleaning]` không in dòng bị loại |
| Dedup `paper_id`, giữ bản `updated` mới nhất | Uniqueness | 0 | GX unique `paper_id` pass |
| Chuẩn hóa ngày về `YYYY-MM-DD` | Consistency | 24 | `pd.read_json` giữ `published` là chuỗi |

`text_for_embedding` gồm 5 dòng cố định `Title / Authors / Published / Categories / Summary` để embedding ổn định giữa các lần chạy. Document ID trong Chroma là `<paper_id>::<row_index>` (cho phép bản trùng trong trạng thái corrupted mà không đụng ID). `age_days` được tính so với ngày chạy (UTC); helper `rebuild_derived_columns()` dùng chung cho cleaning, corruption và repair để các cột phái sinh luôn khớp nội dung.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| Các `question_type` | summary (3), authors (3), date (2), categories (2) |
| Ground-truth document ID | `paper_id` của bài được chọn; câu hỏi chứa tiêu đề trong `'...'` |
| Embedding model | `all-MiniLM-L6-v2` |
| Vector store/collection | ChromaDB persistent `data/chroma/`, cosine; `papers-baseline` / `papers-corrupted` / `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | Gemini `gemini-3.1-flash-lite` (judge + agent demo) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (sha1 `1939640eeb71…`) |

Test set được sinh một lần từ dữ liệu sạch rồi tái sử dụng (`REFRESH_TEST_SET` mặc định tắt). Nếu sinh lại trên dữ liệu bẩn, đáp án chuẩn sẽ bị hỏng theo (ví dụ lấy title bị cắt làm ground truth), và việc so sánh ba trạng thái mất ý nghĩa. Test set chọn 10 bài trải đều theo thời gian, gồm 3 bài mới nhất, để lỗi mất bài mới thể hiện được trên chỉ số.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | Records khớp 100% với snapshot của starter |
| Cleaned dataset | `data/clean/` | Có | 24 dòng, 16 cột |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/` | Có (Chroma commit; manifest sinh lại khi chạy) | Manifest chứa đường dẫn tuyệt đối nên không commit |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | |
| Quality/freshness | `data/quality/` | Có | baseline/corrupted/repaired |
| Baseline report | `data/reports/phase1_report.md` | Có | |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | --: | --- |
| `retrieval_hit_rate` | 1.0000 | Tài liệu đúng luôn nằm trong top-4 (câu hỏi có tiêu đề, `qa.py` tra cứu chính xác theo title) |
| `mean_token_f1` | 1.0000 | `qa.py` trích xuất nguyên văn field → khớp tuyệt đối với ground truth |
| `judge_accuracy` | 1.0000 | Gemini xác nhận 10/10 câu đúng |
| `mean_judge_score` | 5.00 | |
| Ragas | N/A | Không bật (`RUN_RAGAS` chậm, tốn quota free tier) |

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| `ExpectTableRowCountToBeBetween` | Completeness | 5–5000 dòng | Pass (24) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` × 3 | Completeness | `paper_id`, `title`, `text_for_embedding` không null | Pass (0 lỗi) | như trên |
| `ExpectColumnValuesToBeUnique` | Uniqueness | `paper_id` duy nhất | Pass (0 lỗi) | như trên |
| `ExpectColumnValueLengthsToBeBetween` | Validity | `summary` ≥ 30 ký tự | Pass (0 lỗi) | như trên |
| `ExpectColumnValueLengthsToBeBetween` (thêm) | Validity | `title` ≥ 8 ký tự | Pass (0 lỗi) | như trên |

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | Clean dataset (cột `age_days`) |
| Timestamp mới nhất | 2026-07-22 (bài cũ nhất 2026-03-28) |
| Ngưỡng freshness | `age_days > 180` là stale; SLA: stale ≤ 25% |
| Trạng thái baseline | Fresh |
| Lý do | 1/24 bài (4.2%) quá 180 ngày, dưới ngưỡng 25% |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | --: | --- | --- | --- |
| `drop_latest_records` | Bỏ 20% bài `published` mới nhất | 5 | Không (GX không biết bài nào thiếu) | 4 câu (eval_001–004) retrieval miss | Rebuild từ raw |
| `blank_summary` | `summary = ""` | 3 | `summary` length fail | eval_009 (summary) Token F1 = 0, judge 1 | Rebuild từ raw |
| `inject_noise` | Xáo trộn từ + chèn token rác | 3 | Không (độ dài vẫn hợp lệ) | Không có câu test nào trúng 3 bài này | Rebuild từ raw |
| `truncate_title` | Cắt title còn 7 ký tự | 3 | `title` length fail (4 dòng, tính cả bản trùng) | Không có câu test nào trúng | Rebuild từ raw |
| `stale_date` | Lùi `published` 365 ngày | 7 | Freshness SLA fail | Freshness 9/23 stale; 3 bài test bị lùi ngày nhưng là câu summary/authors/categories nên đáp án không đổi | Rebuild từ raw |
| `duplicate_rows` | Nhân bản 4 dòng, giữ `paper_id` | 4 | `paper_id` unique fail (8 dòng) | Bản trùng chiếm chỗ trong top-k, không đổi đáp án câu test | Rebuild từ raw |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: đủ 6 bước, mỗi bước có `description`, `affected_paper_ids`, `rows_before`, `rows_after`. Các bước 2–5 dùng các tập dòng không chồng nhau (seed 42), nên có thể quy tác động về đúng một loại lỗi.

Repair **không** sửa trên dataframe bẩn: dữ liệu bị drop hay bị xáo trộn thì không khôi phục được từ chính nó. Luồng repair đọc lại `data/raw/crossref_records.json` (raw preservation từ CP0), chạy lại đúng hàm `build_clean_dataframe`, cho qua Quality Gate và Freshness. Chỉ khi PASS thì mới index vào `papers-repaired` và ghi nó làm serving collection trong `serving_state.json`; `papers-corrupted` bị ghi nhận là cách ly. Repair chỉ phụ thuộc raw nên chạy n lần vẫn ra cùng dataset (đã kiểm tra: `papers_clean_repaired.json` == `papers_clean.json`).

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | --: | --: | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.6000 | 1.0000 | −0.4000 | 100% | 4 câu mất tài liệu do drop latest |
| `mean_token_f1` | 1.0000 | 0.7741 | 1.0000 | −0.2259 | 100% | eval_003 = 0 (sai ngày), eval_009 = 0 (summary rỗng), eval_001 = 0.74 |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 | −0.2000 | 100% | 2/10 câu bị judge đánh sai |
| `mean_judge_score` | 5.00 | 4.20 | 5.00 | −0.80 | 100% | |
| Quality checks pass/fail | 7/7 pass | 4/7 pass | 7/7 pass | −3 expectation | 100% | unique, title length, summary length fail |
| Freshness status | Fresh (4.2%) | Stale (39.1%) | Fresh (4.2%) | +34.9 điểm % | 100% | |

Kết luận nhân quả:

1. `drop_latest_records` (bỏ 5 bài mới nhất) → GX **không** báo (19 dòng vẫn trong ngưỡng) → 4 câu eval_001–004 retrieval miss, Hit Rate 1.0 → 0.6. Hai trong bốn câu (eval_002 authors, eval_004 categories) vẫn trả lời đúng vì snapshot có bài "Advanced Perspectives on …" cùng tác giả/lĩnh vực với bài bị xóa. Đây là Silent Failure: đáp án đúng nhưng dựa trên tài liệu sai.
2. `blank_summary` → expectation `summary` length fail (3 lỗi) → eval_009 trả về chuỗi rỗng, Token F1 = 0, judge = 1. Repair từ raw → gate 7/7 pass, freshness 4.2% → toàn bộ chỉ số về lại 1.0 / 5.0.

Kết quả khác kỳ vọng: `stale_date` và `inject_noise` không làm giảm metric, vì không câu hỏi `date` hay `summary` nào rơi vào đúng các bài bị tác động. Freshness SLA vẫn bắt được `stale_date`, còn `inject_noise` thì không tín hiệu nào bắt được.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Bản `corruption_flow.py` đầu tiên của TV3 báo `ModuleNotFoundError: No module named 'config'`. Sau khi sửa import thì freshness vẫn báo `is_fresh=True` trên dữ liệu bẩn, và title bị cắt không bị GX bắt.
- **Nguyên nhân:** import sai package (`config`, `pipelines.cleaning`… thay vì `core.config`, `ingestion.cleaning`…). `corruption.py` bản đầu chỉ tác động `len//20 = 1` dòng/lỗi, trên cùng một dòng, lùi ngày nhưng không tính lại `age_days`, và cắt title còn ≥ 11 ký tự.
- **Cách xử lý:** sửa import; viết lại `corruption.py` theo data contract (tỷ lệ theo đề, tập dòng tách biệt, gọi `rebuild_derived_columns`). Bổ sung: bỏ commit các manifest embeddings chứa đường dẫn `D:\...`; cho judge retry khi gặp lỗi mạng (trước đó 1–2/10 câu âm thầm rơi về heuristic).
- **Cách xác minh:** `run_corruption_flow.py` exit 0; gate corrupted `success=False`, `is_fresh=False`; `*_answers.json` không còn "Fallback heuristic judge".

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| GX không phát hiện mất dữ liệu (`drop_latest_records`) | Mất 20% bài mới vẫn PASS gate | Thêm expectation so sánh row count / tập `paper_id` với raw records; kỳ vọng gate FAIL trên corrupted |
| `inject_noise` không có tín hiệu | Nhiễu ngữ nghĩa lọt vào index | Kiểm tra tỷ lệ token không phải từ điển hoặc độ tương đồng embedding so với bản trước |
| `qa.py` extractive, baseline 1.0 | Metric ít nhạy với chất lượng ngữ cảnh | Bật Ragas (`RUN_RAGAS=1`) hoặc dùng agent LLM để trả lời, so sánh faithfulness giữa 3 trạng thái |
| Free tier Gemini giới hạn request | Judge có thể rơi về heuristic | Đã thêm retry; có thể cache verdict theo (question, answer) |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
