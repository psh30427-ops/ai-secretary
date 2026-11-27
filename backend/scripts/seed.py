"""data/smartlead_seed.csv를 Firestore data 컬렉션에 넣는다.

같은 (date, memo)가 이미 있으면 건너뛴다.
실행 (backend 폴더에서):
    python scripts/seed.py              # 실제 저장
    python scripts/seed.py --dry-run    # Firestore 없이 CSV 검증만
"""
import argparse
import csv
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from pydantic import ValidationError  # noqa: E402

from app import config  # noqa: E402,F401  (backend/.env 로딩)
from app.schemas.data import DataIn  # noqa: E402

DEFAULT_CSV = BACKEND_DIR.parent / "data" / "smartlead_seed.csv"
BATCH_SIZE = 400  # Firestore 배치 한도 500 이하


def read_rows(path: Path) -> tuple[list[DataIn], list[str]]:
    items, errors = [], []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            try:
                value = int(row["value"])
                items.append(DataIn(date=row["date"], value=value, memo=row["memo"]))
            except (ValueError, KeyError, ValidationError) as exc:
                errors.append(f"{line_no}행: {exc}".splitlines()[0])
    return items, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"CSV 파일이 없습니다: {args.csv}")
        return 1

    items, errors = read_rows(args.csv)
    print(f"CSV {len(items)}건 읽음, 오류 {len(errors)}건")
    for e in errors:
        print("  -", e)

    # CSV 안의 중복도 제거
    unique: dict[tuple[str, str], DataIn] = {}
    for it in items:
        unique.setdefault((it.date.isoformat(), it.memo), it)

    if args.dry_run:
        print(f"[dry-run] 중복 제거 후 {len(unique)}건. Firestore에는 쓰지 않았습니다.")
        return 0

    from app.services.data_service import _to_doc
    from app.services.firestore import DATA_COLLECTION, get_db

    db = get_db()
    col = db.collection(DATA_COLLECTION)
    existing = {(d.get("date"), d.get("memo")) for d in (s.to_dict() for s in col.stream())}
    to_add = [it for key, it in unique.items() if key not in existing]

    for i in range(0, len(to_add), BATCH_SIZE):
        batch = db.batch()
        for it in to_add[i : i + BATCH_SIZE]:
            batch.set(col.document(), _to_doc(it))
        batch.commit()

    print(f"추가 {len(to_add)}건, 이미 있어서 건너뜀 {len(unique) - len(to_add)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
