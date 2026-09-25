# Phân công nhóm 3Idiots — Task cụ thể cho từng thành viên

Repo nhóm: https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline

| Thành viên | Phần việc | File sở hữu (chỉ sửa file của mình) |
|---|---|---|
| **TV1 – Trưởng nhóm** | CP0–CP3: ingestion, cleaning, quality gate GX 1.x, test set, pipeline Phase 1 — **ĐÃ XONG** | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/observability/quality.py`, `src/evaluation/testset.py`, `src/pipelines/phase1.py`, `generate_phase1_report()` |
| **TV2 – Repair & Comparison** | CP5: corruption flow, repair idempotent, báo cáo 3 trạng thái (+ bonus B2) | `src/pipelines/corruption_flow.py`, `generate_corruption_report()` trong `src/observability/reporting.py` |
| **TV3 – Corruption Suite** | CP4: tiêm 6 lỗi dữ liệu (+ bonus B1 dashboard) | `src/ingestion/corruption.py`, `app/dashboard.py` (bonus) |

**Trạng thái hiện tại:** Phase 1 đã chạy xong trên `main` (`python script/run_phase1.py` exit 0; baseline hit_rate = 1.0, token_f1 = 1.0).
Đã có sẵn: `data/clean/papers_clean.json`, `data/eval/test_set.json` (10 câu, CỐ ĐỊNH — không tạo lại), `data/results/baseline_metrics.json`, `data/quality/baseline_quality_report.json`.

Thứ tự: TV3 push `corruption.py` → TV2 chạy `run_corruption_flow.py` end-to-end. TV2 có thể code `corruption_flow.py` song song ngay bây giờ.

**LLM:** dùng `LLM_MODEL=gemini-3.1-flash-lite` (bản `gemini-2.5-flash` đã bị Google ngừng cho user mới; `gemini-3.8-flash` free tier chỉ 20 request/ngày). Kiểm tra LLM judge có chạy thật không: trong `data/results/*_answers.json`, `judge.reasoning` KHÔNG được là "Fallback heuristic judge...".

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

## 📋 PROMPT CHO TV2 — Repair & Comparison (copy nguyên khối dưới vào AI assistant)

````text
Tôi là thành viên TV2 nhóm 3Idiots, làm bài lab "Day 10 — Data Pipeline & Data Observability" (VinUni AI20k K4).
Repo: https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline (Python 3.11–3.13, package trong src/, cài bằng `uv sync` hoặc `pip install -e .`).
Hãy đọc trước: README.md, docs/Guide.md (Bước 7–8), docs/CHECKPOINTS.md (CP4, CP5), docs/RUBRIC.md (tiêu chí 8), docs/TASKS_TEAM.md (mục "HỢP ĐỒNG DỮ LIỆU CHUNG"), cùng các file src/core/config.py, src/core/utils.py, src/retrieval/index.py, src/retrieval/qa.py, src/evaluation/metrics.py.

NHIỆM VỤ: chỉ sửa 2 chỗ sau (corruption.py do TV3 viết, quality/testset/phase1 do TV1 đã viết xong), không sửa file khác của thành viên khác.

1) src/pipelines/corruption_flow.py — hàm `main()` (chạy qua `python script/run_corruption_flow.py`, exit code 0)
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

2) src/observability/reporting.py — CHỈ viết hàm `generate_corruption_report(...)` (hàm generate_phase1_report là của TV1)
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
- `corrupt_clean_dataframe(df, output_log_path)` của TV3: nếu chưa có trên main thì code theo chữ ký này, test end-to-end sau khi TV3 push.
- Dùng sẵn: `run_data_quality_checks`, `build_freshness_report` (observability.quality), `load_raw_records` (ingestion.crossref), `build_clean_dataframe` (ingestion.cleaning), `save_clean_artifacts(df, csv_path, json_path)` (pipelines.phase1), hàm `_fmt` trong reporting.py.
- Free tier Gemini có giới hạn request/ngày: mỗi lần chạy flow tốn ~20 lời gọi LLM judge — đừng chạy lại liên tục khi debug (đặt tạm LLM_PROVIDER=mock để debug logic, nhớ chạy lại bằng gemini trước khi commit số liệu).

GIT:
git config user.name "<tên GitHub của tôi>"; git config user.email "<email GitHub của tôi>"   # để được tính vào Insights > Contributors
git pull --rebase origin main   # trước mỗi lần commit
git add <chỉ file của tôi>; git commit -m "feat(corruption): ..."; git push origin main
Commit nhỏ, nhiều lần (corruption_flow.py, rồi report, rồi artifacts data/) — không gộp 1 commit khổng lồ.
````

Sau khi xong code, TV2 tự làm thêm:
- Copy `report/individual_report.md` → `report/<MSSV>_HoTen.md` và điền.
- Điền mục của mình trong `docs/TEAM.md` (`### ## HoVaTen-MSSV`), ghi đúng phần đã làm.

---
---

## 📋 PROMPT CHO TV3 — Corruption Suite (copy nguyên khối dưới vào AI assistant)

````text
Tôi là thành viên TV3 nhóm 3Idiots, làm bài lab "Day 10 — Data Pipeline & Data Observability" (VinUni AI20k K4).
Repo: https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline (Python 3.11–3.13, package trong src/, cài bằng `uv sync` hoặc `pip install -e .`).
Hãy đọc trước: README.md, docs/Guide.md (Bước 7), docs/CHECKPOINTS.md (CP4), docs/RUBRIC.md (tiêu chí 8), docs/TASKS_TEAM.md (mục "HỢP ĐỒNG DỮ LIỆU CHUNG"), cùng src/ingestion/cleaning.py, src/observability/quality.py, src/evaluation/testset.py, src/core/utils.py.

NHIỆM VỤ: chỉ sửa src/ingestion/corruption.py (+ bonus), không sửa file của thành viên khác.

src/ingestion/corruption.py — hàm `corrupt_clean_dataframe(df, output_log_path) -> pd.DataFrame`
   - Deterministic: dùng `numpy.random.default_rng(42)` / `random_state=42`, KHÔNG sửa df gốc (làm trên `df.copy()`).
   - Tiêm đủ 6 lỗi theo thứ tự, mỗi lỗi chọn tập dòng riêng (không chồng lên nhau khi có thể):
     a. drop_latest_records: bỏ 20% bài có `published` mới nhất (24 bài → bỏ 5). Mô phỏng ingestion fail → stale data.
     b. blank_summary: đặt `summary = ""` cho ~15% dòng còn lại.
     c. inject_noise: chèn chuỗi rác (ví dụ "@@##%% lorem ipsum ¤¤ ###") và thay/xáo trộn từ trong `summary` cho ~15% dòng.
     d. truncate_title: cắt `title` còn < 8 ký tự (ví dụ `title[:7]`) cho ~15% dòng.
     e. stale_date: lùi `published` về 365 ngày (giữ format "YYYY-MM-DD") cho ĐỦ nhiều dòng (≥ 35%) để Freshness SLA bật cảnh báo
        (quality.py: is_fresh=False khi > 25% bài có age_days > 180).
     f. duplicate_rows: nhân bản ~20% dòng (giữ nguyên paper_id → vi phạm ExpectColumnValuesToBeUnique).
   - Sau cùng gọi `rebuild_derived_columns(df, run_date=now_utc())` từ `ingestion.cleaning` để tính lại age_days, summary_chars, text_for_embedding (now_utc từ core.utils).
   - Ghi log bằng `write_json(output_log_path, log)` với log là list 6 phần tử:
     {"step": 1, "corruption": "drop_latest_records", "description": "...", "affected_paper_ids": [...], "rows_before": int, "rows_after": int}
   - Return corrupted df (giữ đủ cột như hợp đồng dữ liệu).

   Tín hiệu hoàn thành:
   python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"

   Tự kiểm tra thêm: Quality Gate PHẢI bắt được lỗi:
   python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); r=run_data_quality_checks(c, s, 'tv3check'); print('success =', r['success'], '| fresh =', r['freshness']['is_fresh']); print([(x['expectation'], x['column'], x['unexpected_count']) for x in r['results'] if not x['success']])"
   → kỳ vọng success = False, fresh = False, fail ở unique paper_id, summary length, title length. Xoá file data/quality/tv3check_* sau khi test.
   Chạy 2 lần phải ra cùng kết quả (deterministic).

BONUS B1 (+5, làm sau khi phần chính xong): app/dashboard.py bằng Streamlit (`uv add streamlit`), chạy `streamlit run app/dashboard.py`:
   - Trạng thái Quality Gate (baseline/corrupted/repaired) từ data/quality/*_quality_report.json: mỗi expectation xanh/đỏ.
   - Histogram age_days (clean vs corrupted) + đường ngưỡng 180 ngày; badge is_fresh.
   - Bảng + bar chart so sánh metrics từ data/results/{baseline,corrupted,repaired}_metrics.json.
   - Dùng đường dẫn qua core.config.load_settings(), xử lý khi file chưa tồn tại (hiện hướng dẫn chạy pipeline).

RÀNG BUỘC:
- Dùng settings.paths.*, không hardcode đường dẫn tuyệt đối. Không commit file .env.
- Tôi phải hiểu và giải thích được từng dòng code (sẽ bị hỏi khi demo: vì sao mỗi lỗi gây Silent Failure, Quality Gate bắt được lỗi nào, lỗi nào GX KHÔNG bắt được — ví dụ inject_noise và drop_latest_records). Thêm comment ngắn ở chỗ quan trọng.

GIT:
git config user.name "<tên GitHub của tôi>"; git config user.email "<email GitHub của tôi>"   # để được tính vào Insights > Contributors
git pull --rebase origin main   # trước mỗi lần commit
git add <chỉ file của tôi>; git commit -m "feat(corruption): ..."; git push origin main
Commit nhỏ, nhiều lần — không gộp 1 commit khổng lồ.
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
