# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `3Idiots`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-3Idiots-DataPipeline` — https://github.com/longka7/K4-L3-DAY10-3Idiots-DataPipeline

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Nguyễn Long Khánh | 2A202602649 | khanhdev2003@gmail.com | Trưởng nhóm — Ingestion, Cleaning, Observability (GX 1.x + Freshness), Evaluation, Phase 1, tích hợp cuối (`crossref.py`, `cleaning.py`, `quality.py`, `testset.py`, `phase1.py`) | `report/2A202602649_NguyenLongKhanh.md` |
| 2 | Nguyễn Văn An | 2A202602776 | nva2004gl81@gmail.com | TV2: Flow Orchestration, Repair & Comparison (`corruption_flow.py`, `reporting.py`, Bonus B2) | `report/2A202602776_NguyenVanAn.md` |
| 3 | Nguyễn Tuấn Khanh | 2A202602819 | tuankhan1245@gmail.com | TV3: Corruption Suite — bản đầu `corruption.py`, `corruption_flow.py`, `generate_corruption_report` | `report/2A202602819_NguyenTuanKhanh.md` |

Chi tiết phân công và data contract giữa các thành viên: [`docs/TASKS_TEAM.md`](TASKS_TEAM.md).

---

## # Cá nhân

### ## NguyenLongKhanh-2A202602649
- **Vai trò:** Trưởng nhóm — Data Foundation, Observability, Evaluation & Integration.
- **Công việc chi tiết đã hoàn thành:**
  - `src/ingestion/crossref.py`: parse payload Crossref (bỏ JATS tag, ghép tên tác giả, ưu tiên ngày published → online → print → issued), gọi API có retry/backoff cho 429/5xx và fallback snapshot offline; lưu 2 raw artifact.
  - `src/ingestion/cleaning.py`: chuẩn hóa text/ngày, lọc row xấu, dedup `paper_id`, `age_days`, `text_for_embedding` 5 phần; helper `rebuild_derived_columns()` dùng chung cho corruption/repair.
  - `src/observability/quality.py`: Quality Gate Great Expectations 1.x (ephemeral context, 7 expectations) + Freshness SLA (> 25% bài có `age_days` > 180 → `is_fresh=False`).
  - `src/evaluation/testset.py`: test set 10 câu cố định, 4 dạng câu hỏi, có 3 bài mới nhất.
  - `src/pipelines/phase1.py` + `generate_phase1_report`: Quality Gate đặt trước bước index, tái sử dụng test set, demo agent.
  - Tích hợp: viết `docs/TASKS_TEAM.md` (data contract); sửa import `corruption_flow.py`; viết lại logic `corruption.py` theo đề (tỷ lệ, tập dòng tách biệt, tính lại `age_days`); self-healing chỉ repair khi gate FAIL + `serving_state.json`; retry LLM judge; bỏ commit manifest chứa đường dẫn tuyệt đối; dọn ChromaDB và chạy lại bản nộp.
- **Điều học được / Đóng góp chính:**
  - Quality Gate phải đặt trước vector store, và GX chỉ bắt được lỗi cấu trúc — mất dữ liệu và nhiễu ngữ nghĩa cần tín hiệu khác (đối chiếu với raw, freshness).
  - Data contract rõ ràng giữa các module giúp nhiều người code song song mà vẫn ghép được.

### ## NguyenVanAn-2A202602776
- **Vai trò:** TV2 – Flow Orchestration, Repair & Comparison (+ Bonus B2 Self-Healing).
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng luồng thực thi trong `src/pipelines/corruption_flow.py`: điều phối tiêm lỗi, kiểm soát Data Quality Gate (GX 1.x) & Freshness SLA, index collection `papers-corrupted` để chứng minh Silent Failure.
  - Thiết kế và lập trình cơ chế Idempotent Repair & Bonus B2 (Self-Healing): phát hiện lỗi tự động rollback về nguồn gốc `crossref_records.json`, tái tạo độc lập qua `build_clean_dataframe`, cách ly collection lỗi và thăng cấp `papers-repaired` làm serving collection.
  - Triển khai hàm `generate_corruption_report` trong `src/observability/reporting.py`: xuất báo cáo Markdown đối chiếu 3 trạng thái đầy đủ cột Delta, bảng chi tiết từng Expectation, bảng Freshness SLA, tóm tắt 6 lỗi và phân tích chuyên sâu.
  - Đảm bảo tính đẳng biến (Idempotent) của toàn bộ quy trình và xuất bảng so sánh 3 cột trên console.
- **Điều học được / Đóng góp chính:**
  - Hiểu sâu sắc bản chất hiểm họa Silent Failure khi dữ liệu bị lỗi nhưng AI Agent không báo đỏ.
  - Nắm vững nguyên tắc Data Lineage và thiết kế Idempotent Pipeline để khôi phục dữ liệu an toàn từ Raw Source of Truth.

### ## NguyenTuanKhanh-2A202602819
> Bản nháp do trưởng nhóm soạn theo lịch sử commit — thành viên tự đọc, chỉnh sửa và commit xác nhận.

- **Vai trò:** TV3 — Corruption Suite.
- **Công việc chi tiết đã hoàn thành:**
  - Commit `ba9930d`: bản đầu `src/ingestion/corruption.py` (6 dạng lỗi, deterministic, không sửa df gốc, ghi corruption log), bản đầu `src/pipelines/corruption_flow.py` (luồng corrupt → gate → Silent Failure demo → repair từ raw → report → bảng console 3 cột) và bản đầu `generate_corruption_report`.
  - Sau review, trưởng nhóm sửa import của flow và viết lại tỷ lệ/logic tiêm lỗi; TV2 viết lại flow và report ở bản hiện tại.
- **Điều học được / Đóng góp chính:**
  - {{TV3 tự điền}}
