# Member Role Report — Day 10: Data Pipeline & Data Observability

> BẢN NHÁP do trưởng nhóm soạn dựa trên lịch sử commit. Thành viên cần tự đọc, sửa cho đúng với hiểu biết của mình, điền các mục `{{...}}`, xóa dòng này và **tự commit bằng tài khoản của mình**.

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Tuấn Khanh |
| MSSV | 2A202602819 |
| Khóa/Lớp | K4 |
| Tên nhóm | 3Idiots |
| Vai trò chính | TV3 — Corruption Suite |
| Repository | https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Corruption suite (bản đầu) | `ingestion/corruption.py`: `corrupt_clean_dataframe` | Clean dataframe | Corrupted dataframe + `corruption_log.json` | Một phần — logic tỷ lệ/chọn dòng được trưởng nhóm viết lại |
| Corruption flow (bản đầu) | `pipelines/corruption_flow.py`: `main` | Artifacts Phase 1 | Corrupted/repaired metrics, bảng console 3 cột | Một phần — import được sửa, TV2 viết lại bản hiện tại |
| Báo cáo so sánh (bản đầu) | `reporting.generate_corruption_report` | Metrics, quality, freshness | `corruption_report.md` | Một phần — TV2 viết lại bản hiện tại |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra và xác nhận lại `rebuild_derived_columns()` để các cột suy ra khớp với dữ liệu bị corrupt | TV1 — `ingestion.cleaning` | Đảm bảo `age_days`, `text_for_embedding` được tính lại sau `summary`/`published` bị sửa; không còn lệch schema giữa clean/corrupted/repaired |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Khung 6 dạng lỗi deterministic, không sửa df gốc, ghi log | `src/ingestion/corruption.py` (commit `ba9930d`) | Hàm chạy được, gate `success=False` (trùng id, summary ngắn) | CP4 signal `Corrupted ... dòng` |
| Khung flow corrupt → gate → Silent Failure demo → repair từ raw | `src/pipelines/corruption_flow.py` (commit `ba9930d`) | Cấu trúc các bước được TV2 giữ lại | Review code |

Sau review, bản đầu có các vấn đề được nhóm sửa: import sai package (`config`, `pipelines.cleaning`…), mỗi lỗi chỉ tác động 1 dòng và cùng một dòng, lùi ngày nhưng không tính lại `age_days` (freshness không phát hiện), title cắt vẫn ≥ 11 ký tự (GX không bắt). Output cụ thể là: `run_corruption_flow.py` không chạy được trong bản nháp do import sai, `is_fresh` vẫn trả về `True` trên dữ liệu bẩn vì `published` đã bị lùi mà `age_days` không được rebuild, và expectation `title` length pass dù title đã bị cắt xuống 7 ký tự vì trường bị cắt chỉ ở một subset nhỏ. Những lỗi này đã được khắc phục bằng cách dùng `df.copy()`, tính lại thuộc tính suy ra và tách tập dòng theo từng lỗi riêng biệt.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mô phỏng 6 sự cố dữ liệu thường gặp để chứng minh Quality Gate/Freshness báo động và RAG suy giảm trong im lặng (Silent Failure).

### Cách triển khai

Tôi làm trên `df.copy()` để tránh sửa trực tiếp dataframe sạch gốc. Điều này quan trọng vì pipeline cần giữ nguồn dữ liệu sạch làm ground truth để repair có thể rollback từ raw và tránh làm hỏng baseline khi chạy lại thử nghiệm. Việc deterministic là bắt buộc vì chúng ta cần cùng một đầu vào sinh ra cùng một log, cùng một tập dòng bị ảnh hưởng, từ đó dễ so sánh giữa baseline, corrupted và repaired và tránh lệch dữ liệu do thứ tự nhập bừa bãi. Khi sửa `summary` hoặc `published`, ta phải tính lại `age_days` và `text_for_embedding` vì đó là các cột suy ra từ nội dung; nếu không rebuild, freshness và index embedding sẽ đánh giá trên dữ liệu không còn đồng bộ với nội dung thực tế, dẫn đến báo cáo sai và silent failure khó phát hiện. Ngoài ra, các lỗi được tách thành các tập dòng không chồng nhau để mỗi dạng dữ liệu có tác động riêng, không bị gộp thành một lỗi chung làm khó xác định nguyên nhân.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean dataframe theo data contract (`docs/TASKS_TEAM.md`) |
| Output | Corrupted dataframe cùng schema + `data/results/corruption_log.json` |
| Module phụ thuộc | `ingestion.cleaning` (`rebuild_derived_columns`) |
| Module sử dụng output | `observability.quality`, `retrieval.index`, `pipelines.corruption_flow` |
| Điều kiện lỗi cần xử lý | Dataframe rỗng, thiếu cột, ngày không parse được |

### Cách xác minh

```bash
uv run python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
```

- **Kết quả mong đợi:** hàm `corrupt_clean_dataframe()` trả về một DataFrame có cùng schema, có log 6 bước lỗi, và in ra tín hiệu `Corrupted <n> dòng` mà không sửa dataframe gốc.
- **Kết quả thực tế:** DataFrame corrupted được sinh thành công, các cột không mất schema, `corruption_log.json` chứa 6 bước với `affected_paper_ids`, `rows_before`, `rows_after`, và pipeline có thể tiếp tục chạy quality/freshness và repair.
- **Artifact/log:** `data/results/corruption_log.json`

## 5. Một quyết định kỹ thuật quan trọng

Một quyết định quan trọng là giữ nguyên `paper_id` khi nhân bản dòng trong bước `duplicate_rows`. Lý do là `paper_id` chính là khóa định danh của bài báo, nên giữ nó nguyên phản ánh đúng lỗi dữ liệu thực tế: một tập hợp dấu hiệu trùng lặp chứ không phải một paper mới. Nếu đổi `paper_id`, ta đã biến lỗi duplicate thành một dataset mới, làm mất tính kiểm chứng của rule `ExpectColumnValuesToBeUnique` và không còn thể hiện đúng sự cố thực tế. Cùng lúc, ta vẫn tiếp tục index dữ liệu bẩn sau khi gate FAIL để minh họa Silent Failure: hệ thống không báo đỏ nhưng câu trả lời vẫn bị suy yếu, chứng tỏ quality gate cần đi kèm các cảnh báo về data lineage và freshness thay vì chỉ mở index nếu thấy không có lỗi rõ ràng.

## 6. Một lỗi hoặc blocker đã xử lý

Một blocker đáng kể là `ModuleNotFoundError: No module named 'config'` khi chạy `script/run_corruption_flow.py`. Lỗi xuất hiện vì bản nháp cũ import sai package, ví dụ `import config` hoặc `from pipelines.cleaning import ...` thay vì `from core.config import load_settings` và `from ingestion.cleaning import rebuild_derived_columns`. Sửa xong, luồng có thể tìm đúng module, đọc dữ liệu sạch, chạy corruption và lưu log đúng đường dẫn. Đây là bước cần thiết để pipeline có thể đi tiếp vào Gate, Index và Repair; nếu không sửa, cả chế độ self-healing đều không thể thực thi được.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đầu vào từ đâu? Từ `build_clean_dataframe` sau khi Crossref được parse và clean ở Phase 1; đó là `data/clean/papers_clean.json` và dạng schema chuẩn của data contract.
2. Corruption suite làm gì? Nó tạo ra bản sao `df.copy()`, áp dụng 6 lỗi deterministic và lưu log vào `data/results/corruption_log.json`; không sửa dữ liệu gốc, nên có thể so sánh trực tiếp với baseline.
3. Tại sao lại cần Quality Gate và Freshness sau khi corrupt? Vì nhiều lỗi không thể thấy bằng mắt thường hay bằng số lượng dòng, ví dụ `inject_noise` và `drop_latest_records` vẫn giữ số dòng hợp lệ. Gate và freshness là tầng cảnh báo để phát hiện sự suy giảm ngay khi dữ liệu bắt đầu sai lệch.
4. Repair lấy dữ liệu từ đâu? Từ raw source of truth `data/raw/crossref_records.json`, không từ corrupted dataframe. Điều này đảm bảo tái tạo lại đúng dataset sạch và idempotent.
5. Quy trình kết thúc ra sao? Sau khi corrupted, ta index và đánh giá để chứng minh silent failure; sau đó repair từ raw, chạy lại gate, đổi serving collection và so sánh 3 trạng thái trong báo cáo Markdown. Đây là lý do toàn bộ luồng không chỉ là xử lý từng module mà là một vòng đời dữ liệu có kiểm soát.

## 8. Phân tích kết quả

### Metrics chính (số liệu thật từ `data/results/`)

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.6000 | 1.0000 | Dữ liệu bẩn làm 4 câu mất tài liệu chính xác, nên hit rate giảm mạnh dù hệ thống vẫn trả lời được phần lớn câu hỏi. |
| `mean_token_f1` | 1.0000 | 0.7741 | 1.0000 | Suy giảm chủ yếu do `summary` trống và tài liệu đúng bị mất, dẫn F1 của vài câu xuống 0 hoặc thấp. |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 | Gemini chấm sai 2/10 câu trong trạng thái corrupted, cho thấy silent failure thực sự xảy ra trong evaluation. |
| `mean_judge_score` | 5.00 | 4.20 | 5.00 | Điểm trung bình rơi xuống vì 2 câu bị chấm kém hơn dù hệ thống vẫn trả lời theo kiểu hợp lý. |
| Quality checks | 7/7 | 4/7 | 7/7 | Corruption làm fail 3 expectation: unique `paper_id`, title too short, summary too short. |
| Freshness status | Fresh (4.2%) | Stale (39.1%) | Fresh (4.2%) | Freshness SLA bắt đúng lỗi `stale_date` và xác nhận repair về lại trạng thái an toàn. |

### Kết luận từ số liệu

1. Nguyên nhân đầu tiên là `drop_latest_records`: tài liệu mới nhất bị mất trong corrupted index, dẫn 4 câu hỏi có retrieval miss và hit rate giảm từ 1.0 xuống 0.6. Bằng chứng rõ nhất là `data/results/corrupted_answers.json` cho thấy các câu `eval_001`–`eval_004` không còn trích xuất tài liệu đúng, đồng thời `data/reports/corruption_report.md` liệt kê lỗi mất record mới là yếu tố chính gây suy giảm.
2. Nguyên nhân thứ hai là `blank_summary` và `truncate_title`: các field bị phá vỡ làm `summary` rỗng và `title` quá ngắn, dẫn quality check fail và F1 giảm ở câu summary. Bằng chứng là `corrupted_answers.json` có câu `eval_009` trả về chuỗi rỗng với `Token F1 = 0`, còn `quality` report cho thấy 3 expectation fail trong corrupted; repair từ raw lại vượt qua hết 7/7 expectation và metrics trở về baseline.

## 9. Điều học được và hướng cải thiện

Tôi học được rằng trong pipeline dữ liệu, chất lượng không chỉ là số liệu diện tích của model hay độ chính xác của agent, mà còn là độ tin cậy của dữ liệu đầu vào. Một pipeline có thể trả lời thêm câu hỏi nhưng vẫn đang chạy trên dataset bị hỏng, đó chính là Silent Failure. Nếu không có `data lineage` và kiểm tra freshness, hệ thống sẽ trông sống động nhưng thực chất đang phục vụ dữ liệu sai. Hướng cải thiện tiếp theo là thêm expectation đối chiếu với raw và kiểm tra sự mất mát bài mới trước khi index, đồng thời mở rộng `qa.py` hoặc Ragas để đánh giá chất lượng ngữ nghĩa thay vì chỉ dựa vào extractive F1. Tôi cũng thấy cần giữ riêng `corruption_log` và `serving_state` nhằm dễ theo dõi khi sửa và khi thay đổi serving collection.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Tuấn Khanh
**Ngày xác nhận:** 2026-09-26
