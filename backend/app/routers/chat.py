from fastapi import APIRouter, Depends

from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service
from app.services.firestore import get_db

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, summary="데이터 요약 기반 AI 채팅")
def chat(
    body: ChatRequest,
    db=Depends(get_db),
    client=Depends(chat_service.get_openai_client),
    model: str = Depends(chat_service.get_model),
):
    return chat_service.chat(db, client, model, body.message, body.conversation_id)
