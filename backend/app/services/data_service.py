"""data 컬렉션 CRUD."""
import datetime as dt

from google.cloud.firestore_v1.base_query import FieldFilter

from app.errors import NotFoundError
from app.schemas.data import DataIn
from app.services.firestore import DATA_COLLECTION


def _to_doc(item: DataIn) -> dict:
    # 과제 형식 그대로 세 필드만 저장한다. 날짜는 문자열이라 사전순 = 시간순.
    return {"date": item.date.isoformat(), "value": item.value, "memo": item.memo}


def _to_out(doc_id: str, data: dict) -> dict:
    return {"id": doc_id, "date": data["date"], "value": data["value"], "memo": data["memo"]}


def list_data(db, date_from: dt.date | None = None, date_to: dt.date | None = None) -> list[dict]:
    """date 오름차순 목록. from/to는 양 끝 포함."""
    query = db.collection(DATA_COLLECTION)
    if date_from:
        query = query.where(filter=FieldFilter("date", ">=", date_from.isoformat()))
    if date_to:
        query = query.where(filter=FieldFilter("date", "<=", date_to.isoformat()))
    query = query.order_by("date")
    return [_to_out(snap.id, snap.to_dict()) for snap in query.stream()]


def create_data(db, item: DataIn) -> dict:
    ref = db.collection(DATA_COLLECTION).document()
    doc = _to_doc(item)
    ref.set(doc)
    return _to_out(ref.id, doc)


def update_data(db, doc_id: str, item: DataIn) -> dict:
    ref = db.collection(DATA_COLLECTION).document(doc_id)
    if not ref.get().exists:
        raise NotFoundError(f"데이터 {doc_id}를 찾을 수 없습니다.")
    doc = _to_doc(item)
    ref.set(doc)
    return _to_out(doc_id, doc)


def delete_data(db, doc_id: str) -> None:
    ref = db.collection(DATA_COLLECTION).document(doc_id)
    if not ref.get().exists:
        raise NotFoundError(f"데이터 {doc_id}를 찾을 수 없습니다.")
    ref.delete()
