from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class MessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: Content


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ConversationCreate(BaseModel):
    """POST /api/conversations: 대화를 직접 저장할 때 사용."""

    title: Title | None = Field(default=None, description="비우면 첫 사용자 메시지로 자동 생성")
    messages: list[MessageIn] = Field(min_length=1)


class ConversationListItem(BaseModel):
    """GET /api/conversations 응답 항목. messages는 포함하지 않는다."""

    id: str
    title: str
    created_at: str
    message_count: int


class ConversationDetail(BaseModel):
    """GET /api/conversations/{id} 응답. 전체 messages 포함."""

    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[Message]


class ConversationDeleteResult(BaseModel):
    id: str
    deleted: bool = True
