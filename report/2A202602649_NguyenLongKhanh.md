# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Long Khánh |
| MSSV | 2A202602649 |
| Khóa/Lớp | K4 |
| Tên nhóm | 3Idiots |
| Vai trò chính | Trưởng nhóm — Ingestion, Cleaning, Observability, Evaluation & Integration |
| Repository | https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Ingestion & lineage | `ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref `/works` hoặc snapshot | `data/raw/crossref_response.json`, `crossref_records.json` | Hoàn thành |
| Cleaning | `ingestion/cleaning.py`: `build_clean_dataframe`, `rebuild_derived_columns` | `list[PaperRecord]` | `data/clean/papers_clean.{csv,json}` | Hoàn thành |
| Quality Gate & Freshness | `observability/quality.py`: `run_data_quality_checks`, `build_freshness_report` | Dataframe | `data/quality/*_quality_report.json`, `*_freshness_report.json` | Hoàn thành |
| Test set | `evaluation/testset.py`: `build_test_set` | Clean dataframe | `data/eval/test_set.json` | Hoàn thành |
| Baseline pipeline | `pipelines/phase1.py`, `reporting.generate_phase1_report` | Settings | `baseline_metrics.json`, `phase1_report.md`, collection `papers-baseline` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Viết data contract + prompt giao việc | TV2, TV3 — `docs/TASKS_TEAM.md` | Hai thành viên code song song dựa trên cùng schema |
| Sửa import + viết lại logic tiêm lỗi | TV3 — `corruption_flow.py`, `corruption.py` | Flow từ `ModuleNotFoundError` → exit 0; gate bắt được lỗi, freshness FAIL |
| Self-healing có điều kiện | TV2 — `corruption_flow.py` | Repair chỉ chạy khi gate FAIL; `data/results/serving_state.json` |
| Sửa lỗi báo cáo và artifact | TV2 — `reporting.py`, `data/embeddings/` | Ghi chú expectation hiển thị đúng; bỏ commit đường dẫn `D:\...` |
| Retry LLM judge | `evaluation/metrics.py` | 30/30 lượt judge do Gemini chấm, 0 fallback |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse Crossref + fallback offline | `ingestion/crossref.py` | 24 records | CP0: `Tín hiệu hoàn thành: Đã tải 24 bài báo`; `git diff data/raw` rỗng |
| Cleaning 24 dòng, 16 cột | `ingestion/cleaning.py` | `papers_clean.json` | CP1: `Clean thành công 24 dòng`, không còn `<` trong summary |
| Quality Gate GX 1.x | `observability/quality.py` | Baseline 7/7 pass, corrupted 4/7 | CP1: `Quality check status = True`; `corrupted_quality_report.json` |
| Test set 10 câu | `evaluation/testset.py` | 3/3/2/2 theo loại | CP2: `Sinh được 10 câu hỏi test` |
| Baseline end-to-end | `pipelines/phase1.py` | Hit Rate 1.0, F1 1.0, Judge 1.0 | `uv run python script/run_phase1.py` exit 0 |

Output cụ thể: `data/quality/corrupted_quality_report.json` cho thấy Quality Gate mình viết bắt được đúng 3 loại lỗi TV3 tiêm vào (`paper_id` trùng 8 dòng, `title` < 8 ký tự 4 dòng, `summary` < 30 ký tự 3 dòng), và `corrupted_freshness_report.json` báo 9/23 = 39.1% bài quá hạn.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Đưa dữ liệu Crossref thành corpus sạch, có lineage, và đặt một "chốt kiểm dịch" trước vector store để dữ liệu hỏng không âm thầm đi vào RAG. Đồng thời tạo bộ đề thi cố định để đo được mức suy giảm.

### Cách triển khai

- **Ingestion:** mặc định đọc snapshot (tái lập được, không phụ thuộc mạng); `REFRESH_SOURCE=1` thì gọi API, retry 3 lần với backoff 2s/4s cho 429/5xx, hết lượt thì fallback về snapshot. Raw response ghi nguyên vẹn; records đã parse ghi riêng.
- **Cleaning:** bỏ tag bằng regex, `html.unescape`, gom khoảng trắng; ngày về `YYYY-MM-DD`; lọc record thiếu id/ngày hoặc title < 8 / summary < 30; dedup `paper_id` giữ bản `updated` mới nhất; sort `published desc, paper_id` để output deterministic. Các cột phái sinh gom vào `rebuild_derived_columns()` để corruption và repair tính lại giống hệt.
- **Quality Gate:** GX 1.x `get_context(mode="ephemeral")` → `add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `batch.validate(suite)`. Bỏ cột list (`authors`, `categories`) trước khi validate vì GX không hash được list. Thêm expectation `title` length ≥ 8 để bắt `truncate_title`. `success` chỉ phụ thuộc expectation; freshness là tín hiệu SLA riêng.
- **Test set:** chọn các vị trí 0,1,2,4,7,…,22 theo thứ tự mới → cũ; câu hỏi dùng đúng cụm từ khóa mà `qa.py` nhận diện ("Who authored", "When was", "What categories") và ground truth đúng field `qa.py` trả về.
- **Phase 1:** gate chạy **trước** index; gate FAIL thì `exit 1`, không index.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref payload (`message.items[]`) hoặc snapshot |
| Output | Clean dataframe 16 cột theo data contract trong `docs/TASKS_TEAM.md`; quality report dict `{success, row_count, results[], freshness}` |
| Module phụ thuộc | `core.config`, `core.utils`, `retrieval.index`, `evaluation.metrics` |
| Module sử dụng output | `corruption.py`, `corruption_flow.py` (TV2/TV3), `reporting.py` |
| Điều kiện lỗi cần xử lý | API 429/5xx, record thiếu abstract/DOI/ngày, cột list trong GX, numpy type khi ghi JSON |

### Cách xác minh

```bash
uv run python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
uv run python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
uv run python script/run_phase1.py
```

- **Kết quả mong đợi:** 24 bài; quality `True`; phase1 exit 0 kèm baseline metrics.
- **Kết quả thực tế:** đúng như kỳ vọng; thử thêm trên dataframe có dòng trùng + summary rỗng + title ngắn → `success=False`, đúng 3 expectation fail.
- **Artifact/log:** `data/quality/baseline_quality_report.json`, `data/results/baseline_metrics.json`, `data/reports/phase1_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Đặt Quality Gate ở đâu trong Phase 1.
- **Các phương án đã cân nhắc:** (A) index xong rồi mới chạy GX làm báo cáo; (B) chạy GX ngay sau cleaning, FAIL thì dừng không index.
- **Phương án đã chọn:** B.
- **Lý do:** Mục tiêu của gate là chặn dữ liệu xấu trước khi agent dùng. Với A, dữ liệu hỏng vẫn vào vector store và gây đúng Silent Failure mà lab muốn phòng. Ở Phase 2, flow vẫn cố ý index dữ liệu bẩn vào collection riêng `papers-corrupted` để *đo* Silent Failure, nhưng không promote nó làm serving.
- **Bằng chứng quyết định phù hợp:** corrupted gate `success=False` trong khi agent vẫn trả lời đủ 10 câu với Hit Rate 0.6 — nếu không có gate thì lỗi chỉ lộ ra khi đối chiếu ground truth.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `Error calling model 'gemini-2.5-flash' (NOT_FOUND): 404 NOT_FOUND ... This model models/gemini-2.5-flash is no longer available to new users`; sau đó `429 RESOURCE_EXHAUSTED ... GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit: 20`.
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_phase1.py` với `LLM_MODEL=gemini-2.5-flash`.
- **Nguyên nhân gốc:** model mặc định của starter đã ngừng cung cấp cho tài khoản mới; `gemini-3.8-flash` free tier chỉ có 20 request/ngày. `metrics.py` bắt mọi exception và âm thầm dùng heuristic judge, nên pipeline vẫn "thành công" với điểm judge không phải của LLM.
- **Cách xử lý:** liệt kê model khả dụng qua API, chuyển sang `gemini-3.1-flash-lite`; thêm retry 3 lần cho judge trước khi fallback; kiểm tra `judge.reasoning` trong `*_answers.json`.
- **Cách xác minh sau khi sửa:** 30/30 lượt judge (3 trạng thái × 10 câu) có reasoning từ Gemini, 0 lượt "Fallback heuristic judge".
- **Điều học được:** exit 0 không có nghĩa là đúng — chính evaluation cũng có thể silent failure; phải kiểm tra artifact chứ không chỉ log.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref payload → `parse_crossref_payload` (raw records, lưu làm lineage) → `build_clean_dataframe` (text sạch, `age_days`, `text_for_embedding`) → Quality Gate → MiniLM encode `text_for_embedding` (normalize) → Chroma collection cosine, metadata gồm title/authors/published/categories/summary.
2. Mỗi câu hỏi có `ground_truth_doc_ids`; Hit Rate = tỷ lệ câu có tài liệu đúng trong top-4; Token F1 so câu trả lời với `ground_truth`; LLM Judge chấm 1–5 và đúng/sai.
3. Quality checks (GX) kiểm tra từng bản ghi/cột tại một thời điểm: null, unique, độ dài, số dòng. Freshness đo phân bố tuổi dữ liệu so với ngày chạy (tỷ lệ bài > 180 ngày) — dữ liệu có thể hoàn toàn hợp lệ về schema nhưng vẫn cũ.
4. Nếu test set đổi theo dữ liệu thì đáp án chuẩn cũng hỏng theo (title bị cắt, summary rỗng), không còn cơ sở so sánh; giữ nguyên test set thì mọi thay đổi metric đều quy được về dữ liệu.
5. Repair thành công khi: repaired gate 7/7 pass, freshness `is_fresh=True`, `papers_clean_repaired.json` == `papers_clean.json`, và `repaired_metrics.json` về đúng baseline (1.0 / 1.0 / 1.0 / 5.0).

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.6000 | 1.0000 | Giảm hoàn toàn do `drop_latest_records` (eval_001–004) |
| `mean_token_f1` | 1.0000 | 0.7741 | 1.0000 | Hai câu về 0: sai ngày (eval_003), summary rỗng (eval_009) |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 | Judge vẫn chấm đúng 2 câu miss vì bài "Advanced Perspectives" trùng tác giả/lĩnh vực |
| `mean_judge_score` | 5.00 | 4.20 | 5.00 | |
| Quality checks | 7/7 | 4/7 | 7/7 | unique, title length, summary length fail |
| Freshness status | Fresh (4.2%) | Stale (39.1%) | Fresh (4.2%) | Bắt được `stale_date` |

### Kết luận từ số liệu

1. `blank_summary` → expectation `summary` length fail (3 dòng) → eval_009 trả về chuỗi rỗng, Token F1 = 0, judge = 1.
2. Repair từ `crossref_records.json` → gate 7/7 + freshness 4.2% → mọi metric về lại baseline; dataset repaired trùng khớp 100% dataset clean.

Corruption ảnh hưởng rõ nhất là `drop_latest_records`: Hit Rate giảm 0.4, và đây cũng là lỗi GX không bắt được (19 dòng vẫn trong ngưỡng 5–5000).

Kết quả khác kỳ vọng: `stale_date` không làm giảm metric dù freshness FAIL. Kiểm tra `corruption_log.json` thì 3 bài test bị lùi ngày đều là câu summary/authors/categories, không có câu `date` nào — nên đáp án không đổi. Tương tự, không câu test nào trúng các bài bị `inject_noise`/`truncate_title`.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw preservation + hàm biến đổi thuần túy giúp repair idempotent: chỉ cần chạy lại từ raw, không phải "vá" dữ liệu bẩn.
2. GX bắt tốt lỗi cấu trúc nhưng mù với mất dữ liệu và nhiễu ngữ nghĩa — cần thêm đối chiếu với nguồn và freshness.
3. RAG có thể trả lời đúng dựa trên tài liệu sai (eval_002, eval_004) — Hit Rate cần được đo song song với chất lượng câu trả lời.

### Nếu có thêm thời gian

Thêm expectation đối chiếu tập `paper_id` của clean data với raw records (ví dụ `ExpectTableRowCountToEqual` theo số raw hợp lệ). Đo: chạy lại corruption flow, kỳ vọng corrupted gate bắt thêm `drop_latest_records` (từ 4/7 pass thành 4/8 pass) trong khi baseline vẫn 8/8.

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Long Khánh
**Ngày xác nhận:** 2026-09-25
