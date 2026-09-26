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
| {{Điền nếu có}} | | |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Khung 6 dạng lỗi deterministic, không sửa df gốc, ghi log | `src/ingestion/corruption.py` (commit `ba9930d`) | Hàm chạy được, gate `success=False` (trùng id, summary ngắn) | CP4 signal `Corrupted ... dòng` |
| Khung flow corrupt → gate → Silent Failure demo → repair từ raw | `src/pipelines/corruption_flow.py` (commit `ba9930d`) | Cấu trúc các bước được TV2 giữ lại | Review code |

Sau review, bản đầu có các vấn đề được nhóm sửa: import sai package (`config`, `pipelines.cleaning`…), mỗi lỗi chỉ tác động 1 dòng và cùng một dòng, lùi ngày nhưng không tính lại `age_days` (freshness không phát hiện), title cắt vẫn ≥ 11 ký tự (GX không bắt). {{Tự nêu output cụ thể của bạn.}}

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Mô phỏng 6 sự cố dữ liệu thường gặp để chứng minh Quality Gate/Freshness báo động và RAG suy giảm trong im lặng (Silent Failure).

### Cách triển khai

{{Tự mô tả: vì sao làm trên `df.copy()`, vì sao phải deterministic, vì sao sau khi sửa `summary`/`published` phải tính lại `text_for_embedding` và `age_days`.}}

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

- **Kết quả mong đợi:** {{…}}
- **Kết quả thực tế:** {{…}}
- **Artifact/log:** `data/results/corruption_log.json`

## 5. Một quyết định kỹ thuật quan trọng

{{Tự điền — ví dụ: vì sao giữ nguyên `paper_id` khi nhân bản dòng, hoặc vì sao tiếp tục index dữ liệu bẩn sau khi gate FAIL.}}

## 6. Một lỗi hoặc blocker đã xử lý

{{Tự điền.}} Gợi ý: `ModuleNotFoundError: No module named 'config'` khi chạy `script/run_corruption_flow.py` — nguyên nhân là package thực tế là `core.config`, `ingestion.*`, `observability.*`, `retrieval.*`, `evaluation.*`.

## 7. Hiểu biết về luồng end-to-end

{{Tự trả lời 5 câu hỏi của template bằng lời của mình.}}

## 8. Phân tích kết quả

### Metrics chính (số liệu thật từ `data/results/`)

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.6000 | 1.0000 | {{…}} |
| `mean_token_f1` | 1.0000 | 0.7741 | 1.0000 | {{…}} |
| `judge_accuracy` | 1.0000 | 0.8000 | 1.0000 | {{…}} |
| `mean_judge_score` | 5.00 | 4.20 | 5.00 | {{…}} |
| Quality checks | 7/7 | 4/7 | 7/7 | {{…}} |
| Freshness status | Fresh (4.2%) | Stale (39.1%) | Fresh (4.2%) | {{…}} |

### Kết luận từ số liệu

{{Tự điền 2 chuỗi nguyên nhân–bằng chứng. Tham khảo `data/reports/corruption_report.md` và `data/results/corrupted_answers.json`.}}

## 9. Điều học được và hướng cải thiện

{{Tự điền.}}

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Tuấn Khanh
**Ngày xác nhận:** {{YYYY-MM-DD}}
