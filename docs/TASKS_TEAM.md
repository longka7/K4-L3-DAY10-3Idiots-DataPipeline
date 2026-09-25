# Phân công nhóm 3Idiots — Task cụ thể cho từng thành viên

Repo nhóm: https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline

| Thành viên | Phần việc | File sở hữu (chỉ sửa file của mình) |
|---|---|---|
| **TV1 – Trưởng nhóm** | CP0, CP1-cleaning, CP3: ingestion, cleaning, pipeline Phase 1 | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/pipelines/phase1.py`, `generate_phase1_report()` trong `src/observability/reporting.py` |
| **TV2 – Corruption & Repair** | CP4, CP5 (+ bonus B2) | `src/ingestion/corruption.py`, `src/pipelines/corruption_flow.py`, `generate_corruption_report()` trong `src/observability/reporting.py` |
| **TV3 – Observability & Evaluation** | CP1-quality, CP2 (+ bonus B1) | `src/observability/quality.py`, `src/evaluation/testset.py`, `app/dashboard.py` (bonus) |

Thứ tự phụ thuộc: TV1 push `cleaning.py` + `data/clean/papers_clean.json` trước → TV3 chạy thử được → TV1 chạy `run_phase1.py` → TV2 chạy `run_corruption_flow.py`.
Tuy nhiên **ai cũng có thể code ngay từ bây giờ** dựa trên "Hợp đồng dữ liệu" bên dưới.

---

## HỢP ĐỒNG DỮ LIỆU CHUNG (cả 3 người phải tuân theo)

### Clean DataFrame (output của `ingestion.cleaning.build_clean_dataframe`)
Mỗi dòng = 1 bài báo, các cột:

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `paper_id` | str | DOI, ví dụ `10.1145/3637528.3671801` |
| `title` | str | đã normalize khoảng trắng |
| `summary` | str | đã bỏ tag JATS `<jats:p>` |
| `authors` | list[str] | |
| `categories` | list[str] | |
| `primary_category` | str | |
| `published` | str | **định dạng `YYYY-MM-DD`** |
| `updated` | str | `YYYY-MM-DD` |
| `abs_url`, `pdf_url`, `comment` | str | |
| `age_days` | int | `(run_date - published).days` |
| `authors_joined` | str | `", ".join(authors)` |
| `categories_joined` | str | `", ".join(categories)` |
| `summary_chars` | int | `len(summary)` |
| `text_for_embedding` | str | 5 dòng: `Title: ...\nAuthors: ...\nPublished: ...\nCategories: ...\nSummary: ...` |

Helper dùng chung (TV1 viết trong `cleaning.py`):
```python
from ingestion.cleaning import rebuild_derived_columns
df = rebuild_derived_columns(df, run_date)  # tính lại age_days, authors_joined, categories_joined, summary_chars, text_for_embedding
```

Dữ liệu sạch lưu tại `data/clean/papers_clean.json` (list records) — đọc bằng `pd.read_json(settings.paths.clean_json)`.
Snapshot gốc: 24 bài báo, bài cũ nhất ~181 ngày, summary ngắn nhất 193 ký tự.

### Các hàm/đường dẫn có sẵn (không cần viết)
- `from core.config import load_settings` → `settings.paths.*` chứa mọi đường dẫn (KHÔNG hardcode path).
- `from core.utils import write_json, read_json, write_text, write_csv, now_utc, first_sentence`
- `from retrieval.index import LocalEmbeddingIndex` → `LocalEmbeddingIndex.build(df, settings, embeddings_output_path=...)`
- `from evaluation.metrics import evaluate_pipeline` → `evaluate_pipeline(settings, index, test_set_path, metrics_output_path, answers_output_path)` trả về bundle có `.summary` = `{samples, retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score, ragas}`.
- `retrieval/qa.py` trả lời dựa trên **từ khóa trong câu hỏi** (xem mục TV3) — đừng sửa file này.

---
---

## 📋 PROMPT CHO TV2 — Corruption & Repair (copy nguyên khối dưới vào AI assistant)

````text
Tôi là thành viên TV2 nhóm 3Idiots, làm bài lab "Day 10 — Data Pipeline & Data Observability" (VinUni AI20k K4).
Repo: https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline (Python 3.11–3.13, package trong src/, cài bằng `uv sync` hoặc `pip install -e .`).
Hãy đọc trước: README.md, docs/Guide.md (Bước 7–8), docs/CHECKPOINTS.md (CP4, CP5), docs/RUBRIC.md (tiêu chí 8), docs/TASKS_TEAM.md (mục "HỢP ĐỒNG DỮ LIỆU CHUNG"), cùng các file src/core/config.py, src/core/utils.py, src/retrieval/index.py, src/retrieval/qa.py, src/evaluation/metrics.py.

NHIỆM VỤ: chỉ sửa 3 chỗ sau, không sửa file khác của thành viên khác.

1) src/ingestion/corruption.py — hàm `corrupt_clean_dataframe(df, output_log_path) -> pd.DataFrame`
   - Deterministic: dùng `random_state=42` / `numpy.random.default_rng(42)`, KHÔNG sửa df gốc (làm trên `df.copy()`).
   - Tiêm đủ 6 lỗi theo thứ tự, mỗi lỗi chọn tập dòng riêng:
     a. drop_latest_records: bỏ 20% bài có `published` mới nhất (24 bài → bỏ 5).
     b. blank_summary: đặt `summary = ""` cho ~15% dòng.
     c. inject_noise: chèn chuỗi rác (ví dụ "@@##%% lorem ipsum ¤¤ ###") và xáo trộn/thay từ trong `summary` cho ~15% dòng.
     d. truncate_title: cắt `title` còn < 8 ký tự (ví dụ `title[:7]`) cho ~15% dòng.
     e. stale_date: lùi `published` về 365 ngày trước cho ĐỦ nhiều dòng (≥ 35%) để Freshness SLA bật cảnh báo (ngưỡng: > 25% bài có age_days > 180).
     f. duplicate_rows: nhân bản ~20% dòng (giữ nguyên paper_id → vi phạm unique).
   - Sau cùng gọi `rebuild_derived_columns(df, run_date=now_utc())` từ `ingestion.cleaning` để tính lại age_days, summary_chars, text_for_embedding.
   - Ghi log bằng `write_json(output_log_path, log)` với log là list 6 phần tử:
     `{"step": 1, "corruption": "drop_latest_records", "description": "...", "affected_paper_ids": [...], "rows_before": int, "rows_after": int}`.
   - Tín hiệu hoàn thành:
     python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"

2) src/pipelines/corruption_flow.py — hàm `main()` (chạy qua `python script/run_corruption_flow.py`, exit code 0)
   Các bước:
   a. settings = load_settings(); đọc `settings.paths.baseline_metrics` và `pd.read_json(settings.paths.clean_json)` (nếu chưa có thì báo lỗi rõ ràng: "Hãy chạy script/run_phase1.py trước").
   b. CORRUPTED: `corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)` → lưu `settings.paths.corrupted_clean_csv` + `corrupted_clean_json` (json dạng `orient="records"`, list → giữ nguyên).
   c. Quality gate trên corrupted: `run_data_quality_checks(corrupted_df, settings, "corrupted")` (ghi ra data/quality/corrupted_quality_report.json, kỳ vọng success=False) và `build_freshness_report(corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness_report.json")` (kỳ vọng is_fresh=False). In cảnh báo rõ ra console khi gate FAIL.
   d. Để chứng minh "Silent Failure", VẪN index corrupted vào collection riêng: `LocalEmbeddingIndex.build(corrupted_df, settings, embeddings_output_path=settings.paths.corrupted_embeddings_json)` → `evaluate_pipeline(settings, index, settings.paths.eval_testset, settings.paths.corrupted_metrics, settings.paths.corrupted_answers)`.
   e. REPAIR (idempotent): KHÔNG sửa từ dữ liệu bẩn, mà tái tạo từ raw: `load_raw_records(settings.paths.raw_records_json)` → `build_clean_dataframe(records, now_utc())` → lưu `repaired_clean_csv/json` → quality `"repaired"` (phải success=True) + freshness `quality_dir / "repaired_freshness_report.json"` → index `repaired_embeddings_json` → evaluate ra `repaired_metrics`, `repaired_answers`.
   f. Gọi `generate_corruption_report(settings.paths.comparison_report, baseline_metrics, corrupted_metrics, repaired_metrics, corrupted_quality, repaired_quality, corrupted_freshness, repaired_freshness)`.
   g. In ra console bảng 3 cột Baseline | Corrupted | Repaired cho retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score.
   - Idempotent: chạy lệnh 2 lần liên tiếp phải ra cùng kết quả repaired (không phụ thuộc lần chạy trước).
   - Mỗi state dùng 1 Chroma collection riêng: papers-baseline / papers-corrupted / papers-repaired (index.py tự suy ra tên từ embeddings_output_path).

3) src/observability/reporting.py — CHỈ viết hàm `generate_corruption_report(...)` (hàm generate_phase1_report là của TV1)
   Markdown ghi bằng `write_text(report_path, md)`, gồm:
   - Bảng so sánh 3 trạng thái: metric | Baseline | Corrupted | Repaired | Δ(Corrupted−Baseline) | Δ(Repaired−Baseline).
   - Bảng Quality Gate: từng expectation pass/fail cho Corrupted vs Repaired; Freshness (stale_rows/total_rows, is_fresh).
   - Tóm tắt 6 lỗi đã tiêm (đọc từ corruption_log nếu cần — có thể đọc settings path qua load_settings()).
   - Phần "Phân tích": giải thích Silent Failure (agent vẫn trả lời tự tin trên data bẩn), lỗi nào ảnh hưởng metric nào, vì sao repair từ raw là idempotent. Số liệu phải lấy từ dict truyền vào, KHÔNG bịa/hardcode.

BONUS B2 (+5, làm sau khi phần chính chạy được): "Self-healing" — trong corruption_flow, nếu quality gate của một dataset FAIL thì tự động kích hoạt repair (rollback về raw) và KHÔNG promote collection lỗi làm collection phục vụ; ghi quyết định vào report (ví dụ mục "Auto-repair triggered: yes, reason: ...").

RÀNG BUỘC:
- Dùng settings.paths.*, không hardcode đường dẫn tuyệt đối. Không commit file .env.
- Tôi phải hiểu và giải thích được từng dòng code (sẽ bị hỏi khi demo). Thêm comment ngắn ở chỗ quan trọng.
- Chỉ sửa đúng các hàm/file nêu trên để tránh conflict với TV1, TV3.
- Nếu hàm của TV1/TV3 (cleaning, quality, testset, phase1) chưa có trên main, hãy code theo hợp đồng trong docs/TASKS_TEAM.md; test end-to-end sau khi họ push.

GIT:
git config user.name "<tên GitHub của tôi>"; git config user.email "<email GitHub của tôi>"   # để được tính vào Insights > Contributors
git pull --rebase origin main   # trước mỗi lần commit
git add <chỉ file của tôi>; git commit -m "feat(corruption): ..."; git push origin main
Commit nhỏ, nhiều lần (corruption.py, rồi corruption_flow.py, rồi report) — không gộp 1 commit khổng lồ.
````

Sau khi xong code, TV2 tự làm thêm:
- Copy `report/individual_report.md` → `report/<MSSV>_HoTen.md` và điền.
- Điền mục của mình trong `docs/TEAM.md` (`### ## HoVaTen-MSSV`), ghi đúng phần đã làm.

---
---

## 📋 PROMPT CHO TV3 — Observability & Evaluation (copy nguyên khối dưới vào AI assistant)

````text
Tôi là thành viên TV3 nhóm 3Idiots, làm bài lab "Day 10 — Data Pipeline & Data Observability" (VinUni AI20k K4).
Repo: https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline (Python 3.11–3.13, package trong src/, cài bằng `uv sync` hoặc `pip install -e .`).
Hãy đọc trước: README.md, docs/Guide.md (Bước 4–5), docs/CHECKPOINTS.md (CP1, CP2), docs/RUBRIC.md (tiêu chí 6, 7), docs/TASKS_TEAM.md (mục "HỢP ĐỒNG DỮ LIỆU CHUNG"), cùng src/core/config.py, src/core/utils.py, src/retrieval/qa.py, src/evaluation/metrics.py.

NHIỆM VỤ: chỉ sửa 2 file sau (+ bonus), không sửa file của thành viên khác.

1) src/observability/quality.py

 a) `run_data_quality_checks(df, settings, report_name) -> dict`
   - BẮT BUỘC dùng cú pháp Great Expectations 1.x (dùng cú pháp cũ như context.sources.pandas_default sẽ bị trừ 10 điểm):
       import great_expectations as gx
       context = gx.get_context(mode="ephemeral")
       data_source = context.data_sources.add_pandas(name="papers_source")
       data_asset = data_source.add_dataframe_asset(name="papers_asset")
       batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
       batch = batch_def.get_batch(batch_parameters={"dataframe": df})
   - Chỉ validate các cột scalar (bỏ cột list `authors`, `categories` trước khi đưa vào GX để tránh lỗi hash).
   - 4 nhóm expectation (gx.expectations.*):
       ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)
       ExpectColumnValuesToNotBeNull cho paper_id, title, text_for_embedding
       ExpectColumnValuesToBeUnique(column="paper_id")
       ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30)
     (có thể thêm: title length ≥ 8 — để bắt lỗi truncate title.)
   - Gom vào 1 ExpectationSuite rồi validate batch (context.suites.add(...), batch.validate(suite)).
   - Trả về dict JSON-serializable (ép numpy int/bool về int/bool của Python):
       {"report_name": ..., "success": bool, "row_count": int,
        "results": [{"expectation": "expect_column_values_to_be_unique", "column": "paper_id", "success": bool, "unexpected_count": int|None}, ...],
        "freshness": {...kết quả build_freshness_report...}}
   - Ghi ra `settings.paths.quality_dir / f"{report_name}_quality_report.json"` bằng write_json
     (report_name dùng trong lab: "baseline", "corrupted", "repaired" → khớp settings.paths.baseline_quality_report / corrupted_quality_report).
   - Freshness trong hàm này: gọi build_freshness_report với path `settings.paths.quality_dir / f"{report_name}_freshness_report.json"`; riêng report_name=="baseline" dùng `settings.paths.freshness_report`.
     `success` của quality chỉ phụ thuộc 4 expectation (freshness là cảnh báo riêng).

 b) `build_freshness_report(df, settings, report_path) -> dict`
   - Dùng `settings.freshness_threshold_days` (=180). stale = age_days > 180.
   - Payload: {"latest_published": "YYYY-MM-DD", "oldest_published": "YYYY-MM-DD", "stale_rows": int, "total_rows": int,
               "stale_ratio": float, "threshold_days": 180, "max_stale_ratio": 0.25, "is_fresh": stale_ratio <= 0.25}
   - Ghi JSON ra report_path, return payload.

   Tín hiệu hoàn thành (dữ liệu sạch → True):
   python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
   Tự test thêm: nhân đôi 1 dòng hoặc set summary="" → success phải False.

2) src/evaluation/testset.py — `build_test_set(df, output_path) -> list[dict]`
   - Kiểm tra df có ≥ 10 dòng, nếu không raise ValueError.
   - Deterministic (không random không seed). Chọn 10 bài trải đều theo thời gian, BẮT BUỘC có mặt ít nhất 3 trong 5 bài `published` mới nhất
     (để khi TV2 xoá 20% bài mới nhất thì hit rate giảm thấy rõ).
   - 10 câu, phân bố: 3 summary, 3 authors, 2 date, 2 categories. Tiêu đề bài báo đặt trong dấu nháy đơn '...' (qa.py dùng regex '([^']+)' để lookup chính xác).
   - Câu hỏi PHẢI chứa đúng cụm từ khoá mà src/retrieval/qa.py nhận diện, và ground_truth phải khớp đúng field qa.py trả về:
       summary    : "What is the main contribution of the paper '<title>'?"   → ground_truth = first_sentence(summary)   (from core.utils import first_sentence)
       authors    : "Who authored the paper '<title>'?"                        → ground_truth = authors_joined
       date       : "When was the paper '<title>' published?"                 → ground_truth = published  (YYYY-MM-DD)
       categories : "What categories does the paper '<title>' belong to?"     → ground_truth = categories_joined
   - Mỗi item: {"id": "eval_001", "question_type": "summary", "question": ..., "ground_truth": ..., "ground_truth_doc_ids": [paper_id]}
   - write_json(output_path, items); return items.
   Tín hiệu hoàn thành:
   python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"

BONUS B1 (+5, làm sau khi phần chính chạy được): app/dashboard.py bằng Streamlit (`uv add streamlit`), chạy `streamlit run app/dashboard.py`:
   - Trạng thái Quality Gate (baseline/corrupted/repaired) từ data/quality/*_quality_report.json: mỗi expectation xanh/đỏ.
   - Biểu đồ histogram age_days (clean vs corrupted) + đường ngưỡng 180 ngày; badge is_fresh.
   - Bảng + bar chart so sánh metrics từ data/results/{baseline,corrupted,repaired}_metrics.json.
   - Dùng đường dẫn tương đối qua core.config.load_settings(), xử lý khi file chưa tồn tại (hiện hướng dẫn chạy pipeline).

RÀNG BUỘC:
- Dùng settings.paths.*, không hardcode đường dẫn tuyệt đối. Không commit file .env.
- Tôi phải hiểu và giải thích được từng dòng code (sẽ bị hỏi về GX 1.x, Freshness SLA khi demo). Thêm comment ngắn ở chỗ quan trọng.
- Nếu data/clean/papers_clean.json chưa có trên main (TV1 chưa push), tạm tự tạo df test nhỏ theo hợp đồng cột trong docs/TASKS_TEAM.md.

GIT:
git config user.name "<tên GitHub của tôi>"; git config user.email "<email GitHub của tôi>"   # để được tính vào Insights > Contributors
git pull --rebase origin main   # trước mỗi lần commit
git add <chỉ file của tôi>; git commit -m "feat(quality): ..."; git push origin main
Commit nhỏ, nhiều lần (quality.py, rồi testset.py, rồi dashboard) — không gộp 1 commit khổng lồ.
````

Sau khi xong code, TV3 tự làm thêm:
- Copy `report/individual_report.md` → `report/<MSSV>_HoTen.md` và điền.
- Điền mục của mình trong `docs/TEAM.md` (`### ## HoVaTen-MSSV`), ghi đúng phần đã làm.

---

## Checklist tích hợp cuối (TV1 chạy)
1. `git pull` → `python script/run_phase1.py` (exit 0) → `python script/run_corruption_flow.py` (exit 0), chạy lần 2 vẫn ra cùng kết quả.
2. Kiểm tra đủ artifacts theo `docs/SUBMISSION.md` mục 3.
3. Insights > Contributors có đủ 3 người trên nhánh `main`.
4. Cả 3 người tự nộp link repo lên VLearn LMS.
