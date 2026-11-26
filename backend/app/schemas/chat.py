from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

UserMessage = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ChatRequest(BaseModel):
    message: UserMessage = Field(examples=["이번 주에 뭐 해야 해?"])
    conversation_id: str | None = Field(default=None, description="이어서 대화할 때만 전달")


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
