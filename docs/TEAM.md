# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `[Điền tên nhóm]`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-TenNhom-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | | | | Trưởng nhóm / Pipeline Integrator (`core/`, `phase1.py`, `corruption_flow.py`) | `report/<MSSV1>_HoTen.md` |
| 2 | Nguyễn Văn An | 2A202602776 | nva2004gl81@gmail.com | TV2: Flow Orchestration, Repair & Comparison (`corruption_flow.py`, `reporting.py`, Bonus B2) | `report/2A202602776_NguyenVanAn.md` |
| 3 | | | | RAG & Vector Index (`retrieval/index.py`, `embeddings.py`, ChromaDB) | `report/<MSSV3>_HoTen.md` |
| 4 | | | | Observability & Evaluation (`quality.py` GX 1.x, `testset.py`, reporting) | `report/<MSSV4>_HoTen.md` |

*(Nếu nhóm có 3 hoặc 5-6 thành viên, xem bảng phân công chi tiết theo vai trò trong file `CHECKPOINTS.md`)*.

---

## # Cá nhân

### ## HoVaTen1-MSSV1
- **Vai trò:** Trưởng nhóm & Điều phối Pipeline.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập cấu hình hệ thống `core/config.py` và đường dẫn artifacts `core/utils.py`.
  - Kết nối luồng thực thi trong `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py`.
  - Kiểm tra tính nhất quán của các artifacts và theo dõi Contributor tracking trên GitHub nhánh `main`.
- **Điều học được / Đóng góp chính:**
  - Hiểu sâu sắc về thiết kế Idempotent Pipeline và quản lý trạng thái luồng dữ liệu đa tầng.

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

### ## HoVaTen3-MSSV3
- **Vai trò:** Phụ trách RAG, Vector Database & Embedding.
- **Công việc chi tiết đã hoàn thành:**
  - Quản lý mô hình embedding `sentence-transformers/all-MiniLM-L6-v2`.
  - Nạp và quản lý 3 collection riêng biệt trong ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
  - Xây dựng QA Agent truy vấn ngữ cảnh chính xác theo tài liệu.
- **Điều học được / Đóng góp chính:**
  - Cách cô lập các không gian vector để so sánh khách quan giữa dữ liệu sạch và dữ liệu bị lỗi.

### ## HoVaTen4-MSSV4
- **Vai trò:** Phụ trách Data Observability & Benchmark Evaluation.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập Quality Gate theo chuẩn mới **Great Expectations 1.x** và giám sát Freshness SLA trong `src/observability/quality.py`.
  - Xây dựng bộ câu hỏi đánh giá chuẩn trong `src/evaluation/testset.py`.
  - Đo lường và xuất bảng đối chiếu 3 trạng thái vào `data/reports/corruption_report.md`.
- **Điều học được / Đóng góp chính:**
  - Cách thiết lập hệ thống cảnh báo sớm chặn đứng hiện tượng Silent Failure trước khi dữ liệu vào serving layer.
