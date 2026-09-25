# Báo Cáo Đối Chiếu 3 Trạng Thái: Baseline vs Corrupted vs Repaired

> **Báo cáo Data Observability, Silent Failure & Idempotent Self-Healing**  
> Nhóm: **3Idiots** | Lab Day 10 — VinUni AI20k (Khóa 4)  
> Thành viên TV2 phụ trách: **Nguyễn Văn An** (Flow Orchestration & Repair)

---

## 1. Bảng So Sánh Hiệu Năng 3 Trạng Thái (Benchmark Comparison)

| Metric / Chỉ số | Baseline (Sạch) | Corrupted (Lỗi) | Repaired (Phục hồi) | Δ(Corrupted−Baseline) | Δ(Repaired−Baseline) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Retrieval Hit Rate** | 1.0000 | 0.6000 | 1.0000 | `-0.4000` | `+0.0000` |
| **Mean Token F1** | 1.0000 | 0.7741 | 1.0000 | `-0.2259` | `+0.0000` |
| **Judge Accuracy** | 1.0000 | 0.8000 | 1.0000 | `-0.2000` | `+0.0000` |
| **Mean Judge Score** | 5 | 4.2000 | 5 | `-0.8000` | `+0.0000` |
| **Số lượng câu test (Samples)** | 10 | 10 | 10 | `+0.0000` | `+0.0000` |

---

## 2. Trạm Kiểm Soát Dữ Liệu: Data Quality Gate (Great Expectations 1.x)

- **Trạng thái Corrupted:** ❌ FAILED (Phát hiện vi phạm) — 3 expectation(s) không đạt.
- **Trạng thái Repaired:** ✅ PASSED (Sạch 100%) — 0 expectation(s) không đạt.

### Bảng chi tiết từng Expectation trên 2 trạng thái:

| Expectation | Cột kiểm định | Corrupted | Repaired | Đánh giá nghiệp vụ |
| :--- | :--- | :---: | :---: | :--- |
| `expect_table_row_count_to_be_between` | *(Toàn bảng)* | ✅ PASS | ✅ PASS | Đạt chuẩn |
| `expect_column_values_to_not_be_null` | `paper_id` | ✅ PASS | ✅ PASS | Đạt chuẩn |
| `expect_column_values_to_be_unique` | `paper_id` | ❌ FAIL (8 lỗi) | ✅ PASS | Vi phạm ngưỡng schema |
| `expect_column_values_to_not_be_null` | `title` | ✅ PASS | ✅ PASS | Đạt chuẩn |
| `expect_column_value_lengths_to_be_between` | `title` | ❌ FAIL (4 lỗi) | ✅ PASS | Vi phạm ngưỡng schema |
| `expect_column_values_to_not_be_null` | `text_for_embedding` | ✅ PASS | ✅ PASS | Đạt chuẩn |
| `expect_column_value_lengths_to_be_between` | `summary` | ❌ FAIL (3 lỗi) | ✅ PASS | Vi phạm ngưỡng schema |

---

## 3. Giám Sát Độ Tươi Dữ Liệu (Freshness SLA)

| Thuộc tính Freshness | Corrupted (Dữ liệu Lỗi) | Repaired (Sau Phục Hồi) | Ngưỡng Chuẩn SLA |
| :--- | :---: | :---: | :---: |
| **Số bài quá hạn (`age_days` > 180 ngày)** | 9 / 23 (39.1300%) | 1 / 24 (4.1700%) | Tỷ lệ ≤ 25.0000% |
| **Bài mới nhất (`latest_published`)** | `2026-06-11` | `2026-07-22` | — |
| **Bài cũ nhất (`oldest_published`)** | `2025-04-30` | `2026-03-28` | — |
| **Đánh giá Freshness SLA** | ❌ KHÔNG ĐẠT (Cảnh báo data cũ) | ✅ ĐẠT (Tươi mới) | SLA: `is_fresh = True` |

---

## 4. Tóm Tắt 6 Lỗi Dữ Liệu Đã Tiêm (Injected Corruptions Suite)

| # | Dạng lỗi | Mô tả nghiệp vụ thực tế | Số bài bị ảnh hưởng | Dòng trước → sau | GX/SLA bắt được? | Tác động lên RAG |
|---:|---|---|---:|---|:---:|---|
| 1 | `drop_latest_records` | Dropped 5 most recently published papers. | 5 | 24 → 19 | ❌ Không (Số dòng vẫn trong [5, 5000]) | Mất 20% bài mới nhất → Retrieval Miss, Agent không tìm thấy context |
| 2 | `blank_summary` | Set summary to empty string. | 3 | 19 → 19 | ✅ Có (`summary` length ≥ 30) | Summary rỗng → Token F1 = 0 với các câu hỏi tóm tắt |
| 3 | `inject_noise` | Shuffled words and inserted junk tokens into summary. | 3 | 19 → 19 | ❌ Không (Độ dài vẫn ≥ 30 ký tự) | Context bị xáo trộn từ và chèn ký tự rác → Phá vỡ ngữ nghĩa, F1 giảm |
| 4 | `truncate_title` | Truncated title to 7 characters. | 3 | 19 → 19 | ✅ Có (`title` length ≥ 8) | Tiêu đề bị cắt < 8 ký tự → Exact match lookup thất bại |
| 5 | `stale_date` | Shifted published date back 365 days. | 7 | 19 → 19 | ✅ Freshness SLA (Tỷ lệ cũ > 25%) | Lùi ngày 365 ngày → Agent trả lời sai mốc thời gian xuất bản |
| 6 | `duplicate_rows` | Appended 4 duplicated rows with the same paper_id. | 4 | 19 → 23 | ✅ Có (`paper_id` unique) | Bản sao chiếm chỗ trong top-k → Ngữ cảnh bị loãng, giảm đa dạng context |

---

## 5. Cơ Chế Tự Phục Hồi Dữ Liệu (Bonus B2 — Automated Self-Healing)

- **Auto-repair triggered:** `YES`
- **Lý do kích hoạt (Reason):** Quality Gate FAILED (3 expectations vi pham); Freshness SLA FAILED (9/23 bai qua han)
- **Quyết định an toàn (Safety Quarantine):** Bộ kiểm duyệt đã **CÁCH LY** collection `papers-corrupted`, tuyệt đối **KHÔNG PROMOTE** collection lỗi này lên môi trường phục vụ (Serving Layer) để chặn đứng Silent Failure.
- **Quy trình phục hồi (Recovery Workflow):**
  1. Tự động kích hoạt cơ chế Rollback về nguồn dữ liệu gốc đáng tin cậy: `data/raw/crossref_records.json`.
  2. Tái tạo độc lập Clean DataFrame thông qua hàm chuẩn hóa `build_clean_dataframe(records, now_utc())`.
  3. Tái kiểm định qua trạm kiểm soát chất lượng (Great Expectations 1.x & Freshness SLA).
  4. Sau khi đạt 100% tiêu chí sạch & tươi mới, tự động promote collection `papers-repaired` làm Serving Collection.
- **Kết quả:** Collection `papers-repaired` đã được kiểm chứng an toàn và sẵn sàng phục vụ các tác vụ hỏi đáp của AI Agent.

---

## 6. Phân Tích Chuyên Sâu (Impact & Lineage Analysis)

### 6.1. Bản chất hiểm họa Silent Failure
- **Hệ thống không hề báo lỗi đỏ:** Khi chạy trên tập dữ liệu bị tiêm lỗi, toàn bộ pipeline vẫn thực thi trơn tru từ đầu đến cuối, không hề văng `Exception` hay crash chương trình. AI Agent vẫn sinh câu trả lời cho toàn bộ 10 câu hỏi trong đề thi một cách lưu loát và tự tin.
- **Chỉ số suy giảm rõ rệt:** Tuy nhiên, khi đối chiếu với Ground Truth, hiệu năng thực tế bị sụt giảm nặng nề: Retrieval Hit Rate thay đổi `-0.4000`, Mean Token F1 thay đổi `-0.2259`. Có 5/10 câu hỏi bị trả lời sai hoặc trích xuất thiếu thông tin.
- **Ý nghĩa thực tiễn:** Nếu không có Data Observability Gate (GX 1.x) và Freshness SLA đứng chốt trước bước nạp Vector Store, dữ liệu độc hại sẽ âm thầm lọt vào Production, khiến Agent trả lời sai sự thật (Hallucination) mà người vận hành không hề hay biết.

### 6.2. Giới hạn của kiểm định Schema và sự cần thiết của Freshness SLA
- **GX 1.x bắt rất tốt các lỗi schema/cấu trúc:** Bắt trọn vẹn `blank_summary` (độ dài summary < 30), `truncate_title` (độ dài title < 8), và `duplicate_rows` (vi phạm tính duy nhất của `paper_id`).
- **GX 1.x bất lực trước lỗi ngữ nghĩa và mất dữ liệu:**   + Với `drop_latest_records` (bỏ rơi 20% bài mới nhất): Số dòng giảm từ 24 xuống 19, nhưng vẫn nằm trong dải cho phép `[5, 5000]` của `ExpectTableRowCountToBeBetween`, do đó GX vẫn báo `PASS` dù bài mới nhất đã biến mất hoàn toàn!
  + Với `inject_noise` (chèn ký tự rác và xáo trộn từ): Độ dài tóm tắt vẫn đủ ≥ 30 ký tự, cột không null, nên GX hoàn toàn không phát hiện được sự phá hủy ngữ nghĩa.
- **Vai trò bổ trợ của Freshness SLA:** Kiểm tra `stale_date` nhờ vào việc giám sát phân bố thời gian `age_days`. Khi tỷ lệ bài quá 180 ngày vượt ngưỡng 25%, Freshness SLA lập tức gióng chuông cảnh báo `is_fresh = False`, lấp đầy khoảng trống mà các Expectation thông thường bỏ sót.

### 6.3. Tính Đẳng Biến (Idempotency) của Luồng Phục Hồi (Repair Flow)
- **Không bao giờ sửa từ dữ liệu bẩn:** Pipeline tuân thủ nguyên tắc cốt lõi: khi dữ liệu đã bị tha hóa (mất bài mới, xáo trộn nội dung), việc cố gắng 'chắp vá' trên dataframe bẩn là bất khả thi và dễ tạo ra sai số dây chuyền.
- **Tái tạo từ nguồn thô (Raw Lineage):** Quá trình Repair đọc lại bản ghi nguyên bản từ `data/raw/crossref_records.json` (bảo toàn từ CP0) và áp dụng hàm biến đổi thuần túy `build_clean_dataframe(records, now_utc())`.
- **Đẳng biến tuyệt đối (Idempotent):** Dù lệnh repair được thực thi 1 lần hay n lần liên tiếp, kết quả phục hồi luôn đồng nhất: độ lệch so với Baseline Hit Rate là `+0.0000`, Token F1 là `+0.0000`. Dữ liệu sau phục hồi lấy lại 100% phong độ sạch và tươi mới, chứng minh tính tin cậy tuyệt đối của hệ thống.

