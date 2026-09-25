# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Văn An             |
| MSSV               | 2A202602776               |
| Khóa/Lớp         | VinUni AI20k — Khóa 4 (K4-L3) |
| Tên nhóm         | 3Idiots                   |
| Vai trò chính    | TV2 — Flow Orchestration, Repair & Comparison (+ Bonus B2 Self-Healing) |
| Repository         | https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline |
| Ngày hoàn thành | 2026-09-25                |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | :---: |
| Corruption & Repair Flow Pipeline | `src/pipelines/corruption_flow.py` (hàm `main`) | `settings.paths.baseline_metrics`, `clean_json`, `raw_records_json` | `corrupted_clean_csv/json`, `repaired_clean_csv/json`, `corrupted/repaired_metrics.json`, `corrupted/repaired_answers.json` | Hoàn thành |
| 3-State Markdown Report | `src/observability/reporting.py` (hàm `generate_corruption_report`) | Metrics & Quality & Freshness dicts của 3 trạng thái, log lỗi | `data/reports/corruption_report.md` | Hoàn thành |
| Bonus B2: Automated Self-Healing | `src/pipelines/corruption_flow.py` & `reporting.py` | Kết quả Quality Gate (GX 1.x) & Freshness SLA | Cơ chế tự động kích hoạt repair, cách ly collection lỗi, không promote lên serving | Hoàn thành (+5đ Bonus) |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Tích hợp luồng Phase 1 với Phase 2 | TV1 (`src/pipelines/phase1.py`) | Đảm bảo hợp đồng dữ liệu chuẩn hóa, đọc đúng baseline metrics và test set cố định |
| Kiểm thử trạm kiểm dịch Great Expectations | TV3 (`src/ingestion/corruption.py`) | Xác minh 6 loại lỗi tiêm làm kích hoạt chính xác các cảnh báo trong GX 1.x và Freshness SLA |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ---------------- | ------------- |
| Điều phối luồng Phase 2 (Corruption -> Repair) | `src/pipelines/corruption_flow.py` | Chạy trơn tru end-to-end qua `python script/run_corruption_flow.py`, exit code 0 | Chạy script kiểm tra console output |
| Chứng minh Silent Failure trên Vector DB | `src/pipelines/corruption_flow.py`, `LocalEmbeddingIndex` | Collection `papers-corrupted`, `corrupted_metrics.json` | Hit Rate giảm từ 1.0 xuống 0.6, Token F1 giảm từ 1.0 xuống 0.7741 |
| Thiết kế cơ chế Idempotent Repair | `src/pipelines/corruption_flow.py`, `ingestion.cleaning` | Collection `papers-repaired`, `repaired_metrics.json` | Hit Rate và Token F1 phục hồi hoàn hảo về 1.0; chạy n lần kết quả không đổi |
| Triển khai Bonus B2 Self-Healing | `src/pipelines/corruption_flow.py`, `reporting.py` | Mục Self-Healing trong báo cáo, cách ly `papers-corrupted`, promote `papers-repaired` | Báo cáo `data/reports/corruption_report.md` ghi nhận quyết định auto-repair |
| Xuất báo cáo Markdown đối chiếu 3 trạng thái | `src/observability/reporting.py` | `data/reports/corruption_report.md` | Đầy đủ bảng đối chiếu kèm các cột Delta, bảng từng expectation GX, bảng Freshness SLA, phân tích chuyên sâu |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Trong các hệ thống RAG thực tế, khi dữ liệu bị lỗi (mất bản ghi mới, xóa nội dung tóm tắt, chèn ký tự rác, trùng lặp dòng), hệ thống AI thông thường **không hề ném lỗi đỏ hay dừng hoạt động**. Agent vẫn tự tin trả lời người dùng nhưng nội dung hoàn toàn sai lệch (**Silent Failure**). Bài toán đặt ra là:
1. Thiết lập trạm kiểm soát dữ liệu tự động (Great Expectations 1.x và Freshness SLA) để phát hiện vi phạm trước khi nạp vào Vector Store.
2. Xây dựng luồng phục hồi dữ liệu tự động (**Self-Healing**) đảm bảo tính **Đẳng biến (Idempotent)** — không bao giờ sửa chắp vá trên dữ liệu bẩn mà tái tạo từ nguồn cội (**Source of Truth**).
3. Định lượng mức độ sụt giảm và phục hồi trên cả 3 trạng thái: Baseline vs Corrupted vs Repaired.

### Cách triển khai
1. **Luồng Corrupted:** Đọc Clean DataFrame từ Phase 1, gọi `corrupt_clean_dataframe` tiêm 6 lỗi dữ liệu, lưu artifacts `papers_clean_corrupted.csv/json`.
2. **Data Observability Gate:** Chạy kiểm định chất lượng bằng Great Expectations 1.x (`run_data_quality_checks`) và đo lường độ tươi (`build_freshness_report`). Ghi nhận và in cảnh báo khi Quality Gate bị FAIL.
3. **Silent Failure Demo:** Để chứng minh tác hại ngầm, pipeline vẫn tiếp tục index dữ liệu lỗi vào collection độc lập `papers-corrupted` trong ChromaDB và gọi `evaluate_pipeline` trên bộ 10 câu test set cố định.
4. **Bonus B2 (Self-Healing & Safety Promotion):** Kiểm tra trạng thái của Quality Gate và Freshness SLA. Nếu phát hiện vi phạm (`success=False` hoặc `is_fresh=False`), hệ thống tự động:
   - Đánh dấu kích hoạt Auto-repair: `auto_repair_triggered = True`.
   - Cách ly collection `papers-corrupted`, ngăn chặn promote lên Serving Layer.
   - Kích hoạt rollback về nguồn thô: đọc `data/raw/crossref_records.json` (bảo toàn lineage).
   - Tái tạo dữ liệu sạch qua `build_clean_dataframe(records, now_utc())` (Idempotent transformation).
   - Kiểm định lại trên dữ liệu phục hồi (yêu cầu bắt buộc phải đạt `success=True` và `is_fresh=True`).
   - Phê duyệt thăng cấp collection `papers-repaired` làm serving collection chính thức.
5. **Reporting & Console:** Gọi `generate_corruption_report` xuất báo cáo Markdown toàn diện và in bảng console đối chiếu 3 cột rõ ràng.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | `settings.paths.baseline_metrics`, `clean_json`, `raw_records_json`, `eval_testset` |
| Output | `corrupted_clean_csv/json`, `repaired_clean_csv/json`, `corrupted/repaired_metrics.json`, `corrupted/repaired_answers.json`, `corruption_report.md` |
| Module phụ thuộc | `ingestion.corruption`, `ingestion.crossref`, `ingestion.cleaning`, `observability.quality`, `retrieval.index`, `evaluation.metrics` |
| Module sử dụng output | `script/run_corruption_flow.py`, hệ thống RAG Serving, tài liệu báo cáo của nhóm |
| Điều kiện lỗi cần xử lý | Thiếu file baseline -> raise FileNotFoundError yêu cầu chạy `run_phase1.py` trước; lỗi encode Unicode trên Windows console -> reconfigure UTF-8; Repaired data không pass quality -> raise RuntimeError dừng promotion |

### Cách xác minh

```bash
.\.venv\Scripts\python.exe script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Exit code 0, in cảnh báo Quality Gate Corrupted FAIL (3 expectations, 39.1% stale), kích hoạt Self-healing, phục hồi thành công, in bảng 3 cột Baseline | Corrupted | Repaired, tạo file `data/reports/corruption_report.md`.
- **Kết quả thực tế:** Hoàn toàn khớp 100% với kỳ vọng. Khi chạy lại lần thứ hai, kết quả Repaired không đổi (chứng minh tính Idempotent).

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi tập dữ liệu bị nhiễm lỗi, làm thế nào để phục hồi (repair) an toàn và đáng tin cậy nhất?
- **Các phương án đã cân nhắc:**
  1. *Phương án A (In-place patching / Sửa trên dữ liệu bẩn):* Tìm các dòng summary rỗng để điền lại, xóa các dòng trùng lặp, cố gắng sửa các tiêu đề bị cắt ngắn.
  2. *Phương án B (Idempotent Raw Rebuild / Tái tạo từ nguồn thô):* Bỏ qua hoàn toàn dữ liệu bẩn, rollback về file snapshot nguyên bản `data/raw/crossref_records.json` và chạy lại hàm chuyển đổi chuẩn hóa `build_clean_dataframe`.
- **Phương án đã chọn:** Phương án B (Tái tạo từ nguồn thô).
- **Lý do:** Phương án A gặp vấn đề bất khả thi về mặt toán học và logic: khi 20% bài báo mới nhất bị drop (`drop_latest_records`), thông tin đó đã biến mất vĩnh viễn khỏi dataframe bẩn, không thể "đoán" hay tự sinh lại được; các từ bị xáo trộn bởi `inject_noise` cũng không thể đảo ngược hoàn hảo. Ngoài ra, sửa trên dữ liệu bẩn vi phạm tính Đẳng biến (Idempotency) vì mỗi lần sửa sẽ phụ thuộc vào trạng thái lỗi trước đó. Phương án B đảm bảo Data Lineage, tính tất định (deterministic) và đẳng biến tuyệt đối.
- **Bằng chứng:** Sau khi phục hồi từ raw, chỉ số của Repaired đạt Hit Rate = 1.0, Token F1 = 1.0 (khôi phục 100% phong độ so với Baseline), chạy lặp lại 2 lần liên tiếp đều ra đúng kết quả.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  UnicodeEncodeError: 'charmap' codec can't encode character '\u0110' in position 7: character maps to <undefined>
  ```
- **Lệnh hoặc bước tái hiện:** Chạy `python script/run_corruption_flow.py` trên môi trường Windows PowerShell mặc định.
- **Nguyên nhân gốc:** Windows console sử dụng bảng mã mặc định `cp1252`, không hỗ trợ ký tự tiếng Việt có dấu như `Đ` (`\u0110`) và các biểu tượng emoji (`✅`, `❌`) khi in ra `sys.stdout`.
- **Cách xử lý:** 
  1. Thêm cấu hình tái thiết lập stream đầu ra ở đầu file `src/pipelines/corruption_flow.py`:
     ```python
     if sys.stdout and hasattr(sys.stdout, "reconfigure"):
         sys.stdout.reconfigure(encoding="utf-8", errors="replace")
     ```
  2. Chuẩn hóa các thông báo print trên console về dạng ký tự không dấu an toàn, trong khi file báo cáo Markdown `corruption_report.md` vẫn ghi bằng UTF-8 đầy đủ dấu tiếng Việt chuyên nghiệp.
- **Cách xác minh sau khi sửa:** Chạy lại script, toàn bộ log console in mượt mà, exit code 0.
- **Điều học được:** Khi phát triển pipeline đa nền tảng (Cross-platform MLOps), luôn cần chú ý xử lý encoding UTF-8 ở tầng I/O console và file writer để tránh crash không đáng có trên Windows.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu được kéo qua Crossref REST API (hoặc fallback snapshot offline) -> lưu bản gốc bất biến vào `data/raw/crossref_records.json` (Lineage) -> làm sạch, khử trùng lặp, tính `age_days` và ghép ngữ cảnh `text_for_embedding` trong `src/ingestion/cleaning.py` -> kiểm định qua Great Expectations 1.x & Freshness SLA -> sinh vector nhúng qua mô hình `sentence-transformers/all-MiniLM-L6-v2` -> lưu trữ phân tán vào vector database ChromaDB.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Bộ test gồm 10 câu hỏi chuẩn hóa qua 4 nhóm (`summary`, `authors`, `date`, `categories`). `ground_truth_doc_ids` chứa DOI của bài báo đúng: nếu trong top-k tài liệu retriever trả về có chứa DOI này thì tính là Hit (`retrieval_hit = True`). Câu trả lời của hệ thống được so sánh với `ground_truth` qua độ tương đồng từ vựng (Token F1) và ngữ nghĩa (LLM Judge chấm điểm từ 1 đến 5).
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - Quality checks (Great Expectations 1.x) kiểm soát tính toàn vẹn về mặt **Schema và cú pháp dữ liệu** (không null, số dòng hợp lệ, unique ID, độ dài chuỗi tối thiểu).
   - Freshness monitoring (Freshness SLA) kiểm soát khía cạnh **Thời gian và độ tươi mới** của tri thức (`age_days <= 180`). Dữ liệu có thể hoàn toàn đúng schema nhưng đã quá cũ (stale data), khiến AI tư vấn kiến thức lỗi thời.
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Để đảm bảo tính khách quan và khoa học của thực nghiệm (Controlled Experiment). Khi giữ cố định đề thi (Test Set), mọi sự biến thiên về Hit Rate hay Token F1 chỉ phản ánh chất lượng của tầng dữ liệu (Data Pipeline), loại bỏ hoàn toàn nhiễu từ sự thay đổi câu hỏi.
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - Về mặt Observability: `repaired_quality_report.json` có `success = True` (0 expectation lỗi) và `repaired_freshness_report.json` có `is_fresh = True`.
   - Về mặt RAG Benchmark: `repaired_metrics.json` có `retrieval_hit_rate = 1.0` và `mean_token_f1 = 1.0` (khôi phục bằng đúng mốc Baseline ban đầu).

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | --------------------- |
| `retrieval_hit_rate` |   1.0000 |    0.6000 |   1.0000 | Sụt giảm mạnh `-0.4000` do lỗi drop 20% bài mới, phục hồi hoàn hảo về `1.0` |
| `mean_token_f1`      |   1.0000 |    0.7741 |   1.0000 | Giảm `-0.2259` do các câu hỏi bị blank summary và inject noise |
| `judge_accuracy`     |   1.0000 |    0.8000 |   1.0000 | LLM Judge đánh giá 2/10 câu sai nội dung trên dữ liệu corrupted |
| `mean_judge_score`   |   5.0000 |    4.2000 |   5.0000 | Điểm trung bình giảm từ 5.0 xuống 4.2 trên thang điểm 5 |
| Quality checks (GX)  | ✅ PASSED |  ❌ FAILED | ✅ PASSED | Corrupted vi phạm 3 expectations; Repaired đạt 100% |
| Freshness status     | ✅ PASSED |  ❌ FAILED | ✅ PASSED | Corrupted có 39.1% bài quá hạn (>25%); Repaired chỉ có 4.2% |

### Kết luận từ số liệu

1. **Chuỗi nguyên nhân – bằng chứng 1:**
   `[Tiêm 6 lỗi dữ liệu]` → `[Quality Gate FAILED (3 lỗi) & Freshness SLA FAILED (39.1% stale)]` → `[Retrieval Hit Rate sụt giảm từ 1.0 xuống 0.60, Token F1 giảm xuống 0.7741]`.
2. **Chuỗi nguyên nhân – bằng chứng 2:**
   `[Kích hoạt Self-Healing Repair từ raw_records_json]` → `[Quality Gate PASSED & Freshness PASSED (is_fresh=True)]` → `[Retrieval Hit Rate hồi phục 1.0, Token F1 hồi phục 1.0, thăng cấp papers-repaired làm Serving Collection]`.

- **Corruption nào ảnh hưởng rõ nhất và vì sao?**
  Lỗi `drop_latest_records` (bỏ rơi 20% bài mới nhất) gây ảnh hưởng nghiêm trọng nhất đến Retrieval Hit Rate vì tài liệu mục tiêu hoàn toàn không tồn tại trong vector index. Nguy hiểm hơn, GX hoàn toàn không bắt được lỗi này vì số dòng (19) vẫn trong khoảng hợp lệ [5, 5000].
- **Kết quả nào khác với kỳ vọng ban đầu?**
  Ban đầu em nghĩ rằng khi dữ liệu bị lỗi, LLM Judge Accuracy sẽ rơi xuống gần 0. Tuy nhiên thực tế Judge Accuracy vẫn giữ được 0.80 (8/10 câu vẫn đúng một phần). Điều này minh chứng sâu sắc cho hiện tượng **Silent Failure**: LLM có năng lực suy luận và tự bù đắp context khá tốt, khiến cho câu trả lời nghe vẫn rất "thuyết phục" và "hợp lý", che giấu đi sự mục ruỗng ngầm của dữ liệu!

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Garbage In -> Garbage Out:** Dữ liệu là "thức ăn" của AI. Mô hình dù hiện đại đến đâu (Gemini, GPT-4) cũng sẽ trở nên vô nghĩa nếu dữ liệu đầu vào bị thiếu, nhiễu hoặc lỗi thời.
2. **Data Observability là phòng tuyến sống còn:** Không thể chỉ dựa vào exception handling truyền thống. Cần có Data Quality Gate (GX 1.x) và Freshness SLA đứng chốt trước Vector Store để chặn đứng Silent Failure.
3. **Nguyên lý Idempotency & Data Lineage:** Quá trình phục hồi dữ liệu phải luôn dựa trên nguồn gốc thô bất biến (Raw Preservation), đảm bảo chạy lại bao nhiêu lần vẫn ra kết quả sạch đồng nhất.

### Nếu có thêm thời gian
Em sẽ phát triển thêm cơ chế **Semantic Drift Detection** bằng cách theo dõi sự phân bố vector embeddings của các tài liệu mới nạp vào theo thời gian, phát hiện sớm các hiện tượng lệch phân phối dữ liệu (Data Drift) ngay cả khi schema hoàn toàn hợp lệ.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Văn An  
**Ngày xác nhận:** 2026-09-25
