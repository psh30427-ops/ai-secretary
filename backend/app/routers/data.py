import datetime as dt

from fastapi import APIRouter, Depends, Query

from app.schemas.data import DataIn, DataOut, DeleteResult
from app.schemas.summary import Summary
from app.services import data_service, summary_service
from app.services.firestore import get_db

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/summary", response_model=Summary, summary="데이터 요약 (프롬프트 주입용)")
def get_summary(db=Depends(get_db)):
    return summary_service.get_summary(db)


@router.get("", response_model=list[DataOut], summary="데이터 목록 (date 오름차순)")
def list_data(
    date_from: dt.date | None = Query(None, alias="from", description="시작일 (포함)"),
    date_to: dt.date | None = Query(None, alias="to", description="종료일 (포함)"),
    db=Depends(get_db),
):
    return data_service.list_data(db, date_from, date_to)


@router.post("", response_model=DataOut, status_code=201, summary="데이터 추가")
def create_data(item: DataIn, db=Depends(get_db)):
    return data_service.create_data(db, item)


@router.put("/{doc_id}", response_model=DataOut, summary="데이터 수정")
def update_data(doc_id: str, item: DataIn, db=Depends(get_db)):
    return data_service.update_data(db, doc_id, item)


@router.delete("/{doc_id}", response_model=DeleteResult, summary="데이터 삭제")
def delete_data(doc_id: str, db=Depends(get_db)):
    data_service.delete_data(db, doc_id)
    return {"id": doc_id}
