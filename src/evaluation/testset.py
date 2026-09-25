from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

TEST_SET_SIZE = 10
# Vi tri (theo thu tu published moi -> cu) cua 10 bai duoc chon: 3 bai moi nhat + trai deu phan con lai,
# de khi corruption "drop 20% latest" xay ra thi hit rate giam thay ro.
PICK_POSITIONS = (0, 1, 2, 4, 7, 10, 13, 16, 19, 22)
# 3 summary, 3 authors, 2 date, 2 categories, xen ke de moi dang cau hoi phu nhieu moc thoi gian.
QUESTION_TYPES = (
    "summary", "authors", "date", "categories", "summary",
    "authors", "date", "categories", "summary", "authors",
)
# Cau hoi phai chua dung cum tu khoa ma retrieval/qa.py nhan dien, va ground truth phai khop field qa.py tra ve.
TEMPLATES = {
    "summary": ("What is the main contribution of the paper '{title}'?", lambda row: first_sentence(row["summary"])),
    "authors": ("Who authored the paper '{title}'?", lambda row: row["authors_joined"]),
    "date": ("When was the paper '{title}' published?", lambda row: row["published"]),
    "categories": ("What categories does the paper '{title}' belong to?", lambda row: row["categories_joined"]),
}


def _pick_positions(n_rows: int) -> list[int]:
    if n_rows >= max(PICK_POSITIONS) + 1:
        return list(PICK_POSITIONS)
    # Corpus nho hon snapshot chuan: chon trai deu, van giu cac bai moi nhat.
    step = (n_rows - 1) / (TEST_SET_SIZE - 1)
    return sorted({round(i * step) for i in range(TEST_SET_SIZE)})


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Sinh 10 cau hoi benchmark deterministic (4 dang: summary/authors/date/categories) tu clean dataframe."""
    if len(df) < TEST_SET_SIZE:
        raise ValueError(f"Need at least {TEST_SET_SIZE} documents to build the test set, got {len(df)}.")

    # Sort doc lap voi thu tu dau vao -> cung data luon ra cung test set.
    ordered = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    items: list[dict[str, Any]] = []
    for number, (position, question_type) in enumerate(zip(_pick_positions(len(ordered)), QUESTION_TYPES), start=1):
        row = ordered.iloc[position]
        template, ground_truth = TEMPLATES[question_type]
        items.append(
            {
                "id": f"eval_{number:03d}",
                "question_type": question_type,
                "question": template.format(title=row["title"]),
                "ground_truth": str(ground_truth(row)),
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    write_json(output_path, items)
    return items
