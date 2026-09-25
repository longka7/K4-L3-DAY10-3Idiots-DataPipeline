from __future__ import annotations

import math

import numpy as np
import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import rebuild_derived_columns

SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_RATIO = 0.15
NOISE_RATIO = 0.15
TRUNCATE_TITLE_RATIO = 0.15
# > 25% bai qua 180 ngay moi vi pham Freshness SLA -> lam cu >= 35% de chac chan bat canh bao.
STALE_DATE_RATIO = 0.35
DUPLICATE_RATIO = 0.20
STALE_SHIFT_DAYS = 365
TRUNCATED_TITLE_CHARS = 7  # < 8 ky tu -> vi pham ExpectColumnValueLengthsToBeBetween(title, min 8)
NOISE_TOKENS = ("@@##%%", "lorem", "ipsum", "¤¤", "###", "null", "��")

REQUIRED_COLUMNS = {"paper_id", "title", "summary", "authors", "categories", "published"}


def _count(ratio: float, n_rows: int) -> int:
    return min(n_rows, max(1, math.ceil(ratio * n_rows)))


def _paper_ids(df: pd.DataFrame, indices) -> list[str]:
    """Return paper IDs for logging."""
    return [str(value) for value in df.loc[indices, "paper_id"].tolist()]


def _inject_noise(text: str, rng: np.random.Generator) -> str:
    """Xao tron thu tu tu va chen token rac -> van du dai de qua GX, nhung nghia bi pha (GX khong bat duoc)."""
    words = text.split()
    rng.shuffle(words)
    for _ in range(max(3, len(words) // 4)):
        words.insert(int(rng.integers(0, len(words) + 1)), str(rng.choice(NOISE_TOKENS)))
    return " ".join(words)


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path,
) -> pd.DataFrame:
    """Simulate deterministic corruption of a clean dataframe (6 loai loi).

    1. drop_latest_records : bo 20% bai moi nhat (ingestion fail -> stale data).
    2. blank_summary       : xoa trang summary (~15%).
    3. inject_noise        : chen ky tu rac + xao tron tu trong summary (~15%).
    4. truncate_title      : cat title con < 8 ky tu (~15%).
    5. stale_date          : lui published 365 ngay (>= 35%) -> vi pham Freshness SLA.
    6. duplicate_rows      : nhan ban ~20% dong (trung paper_id).

    Buoc 2-5 dung cac tap dong KHONG chong nhau de moi loi co tac dong rieng, ro rang.
    Deterministic: cung input -> cung output + log (seed 42). Input khong bi sua in-place.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if df.empty:
        raise ValueError("Cannot corrupt an empty clean dataframe.")
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise ValueError("Clean dataframe is missing required columns: " + ", ".join(missing))

    rng = np.random.default_rng(SEED)
    # Sort on dinh truoc khi chon dong -> ket qua khong phu thuoc thu tu dau vao.
    result = df.copy(deep=True).sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    log: list[dict] = []

    def record(step: int, name: str, description: str, paper_ids: list[str], rows_before: int) -> None:
        log.append(
            {
                "step": step,
                "corruption": name,
                "description": description,
                "affected_paper_ids": paper_ids,
                "rows_before": rows_before,
                "rows_after": int(len(result)),
            }
        )

    # 1. Drop latest records (result da sort moi nhat truoc).
    rows_before = len(result)
    n_drop = _count(DROP_LATEST_RATIO, rows_before)
    dropped_ids = result["paper_id"].iloc[:n_drop].astype(str).tolist()
    result = result.iloc[n_drop:].reset_index(drop=True)
    record(1, "drop_latest_records", f"Dropped {n_drop} most recently published papers.", dropped_ids, rows_before)

    # Chia cac dong con lai thanh cac tap rieng cho buoc 2-5.
    n_rows = len(result)
    order = rng.permutation(n_rows).tolist()
    sizes = [
        _count(BLANK_SUMMARY_RATIO, n_rows),
        _count(NOISE_RATIO, n_rows),
        _count(TRUNCATE_TITLE_RATIO, n_rows),
        _count(STALE_DATE_RATIO, n_rows),
    ]
    groups, start = [], 0
    for size in sizes:
        groups.append(sorted(order[start:start + size]))
        start += size
    blank_idx, noise_idx, truncate_idx, stale_idx = groups

    # 2. Blank summary.
    result.loc[blank_idx, "summary"] = ""
    record(2, "blank_summary", "Set summary to empty string.", _paper_ids(result, blank_idx), n_rows)

    # 3. Inject noise.
    result.loc[noise_idx, "summary"] = [_inject_noise(str(text), rng) for text in result.loc[noise_idx, "summary"]]
    record(3, "inject_noise", "Shuffled words and inserted junk tokens into summary.", _paper_ids(result, noise_idx), n_rows)

    # 4. Truncate title.
    result.loc[truncate_idx, "title"] = result.loc[truncate_idx, "title"].astype(str).str[:TRUNCATED_TITLE_CHARS]
    record(4, "truncate_title", f"Truncated title to {TRUNCATED_TITLE_CHARS} characters.", _paper_ids(result, truncate_idx), n_rows)

    # 5. Stale date (giu format YYYY-MM-DD).
    shifted = pd.to_datetime(result.loc[stale_idx, "published"], format="%Y-%m-%d") - pd.Timedelta(days=STALE_SHIFT_DAYS)
    result.loc[stale_idx, "published"] = shifted.dt.strftime("%Y-%m-%d")
    record(5, "stale_date", f"Shifted published date back {STALE_SHIFT_DAYS} days.", _paper_ids(result, stale_idx), n_rows)

    # 6. Duplicate rows (giu nguyen paper_id -> vi pham unique).
    n_dup = _count(DUPLICATE_RATIO, n_rows)
    dup_idx = sorted(rng.choice(n_rows, size=n_dup, replace=False).tolist())
    dup_ids = _paper_ids(result, dup_idx)
    result = pd.concat([result, result.loc[dup_idx]], ignore_index=True)
    record(6, "duplicate_rows", f"Appended {n_dup} duplicated rows with the same paper_id.", dup_ids, n_rows)

    # 7. Tinh lai cot phai sinh (age_days, summary_chars, text_for_embedding...) cho khop noi dung bi hong.
    result = rebuild_derived_columns(result, now_utc())

    # 8. Ghi log.
    write_json(output_log_path, log)
    return result
