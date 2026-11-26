from fastapi import APIRouter, Depends

from app.schemas.conversation import (
    ConversationCreate,
    ConversationDeleteResult,
    ConversationDetail,
    ConversationListItem,
)
from app.services import conversation_service
from app.services.firestore import get_db

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationDetail, status_code=201, summary="대화 저장")
def create_conversation(body: ConversationCreate, db=Depends(get_db)):
    messages = [m.model_dump() for m in body.messages]
    return conversation_service.create_conversation(db, messages, body.title)


@router.get(
    "",
    response_model=list[ConversationListItem],
    summary="대화 목록 (최신순, messages 미포함)",
)
def list_conversations(db=Depends(get_db)):
    return conversation_service.list_conversations(db)


@router.get("/{conv_id}", response_model=ConversationDetail, summary="특정 대화 불러오기")
def get_conversation(conv_id: str, db=Depends(get_db)):
    return conversation_service.get_conversation(db, conv_id)


@router.delete("/{conv_id}", response_model=ConversationDeleteResult, summary="대화 삭제")
def delete_conversation(conv_id: str, db=Depends(get_db)):
    conversation_service.delete_conversation(db, conv_id)
    return {"id": conv_id}
