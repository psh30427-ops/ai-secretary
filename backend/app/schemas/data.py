"""data 컬렉션 요청/응답 스키마. 과제 형식 (date, value, memo)만 사용한다."""
import datetime as dt
import re
from typing import Annotated

from pydantic import BaseModel, Field, StrictInt, StringConstraints, field_validator

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

Memo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Importance = Annotated[StrictInt, Field(ge=1, le=5, description="중요도 1~5")]


class DataIn(BaseModel):
    """POST /api/data, PUT /api/data/{id} 요청 본문."""

    date: dt.date = Field(description="YYYY-MM-DD 형식의 날짜", examples=["2026-12-11"])
    value: Importance = Field(examples=[4])
    memo: Memo = Field(
        description="[분류] 강좌 - 제목 (마감 HH:MM)",
        examples=["[과제] 경영정보시스템(종합설계) - 팀원 상호 평가 과제 (마감 24:00)"],
    )

    @field_validator("date", mode="before")
    @classmethod
    def _date_must_be_iso_string(cls, v):
        # Pydantic은 기본적으로 숫자(타임스탬프)나 다른 형식도 날짜로 받아주므로,
        # 과제 형식인 'YYYY-MM-DD' 문자열만 허용하도록 막는다.
        if isinstance(v, dt.date):
            return v
        if not isinstance(v, str) or not _DATE_RE.match(v):
            raise ValueError("date는 YYYY-MM-DD 형식의 문자열이어야 합니다.")
        return v


class DataOut(BaseModel):
    id: str
    date: str
    value: int
    memo: str


class DeleteResult(BaseModel):
    id: str
    deleted: bool = True
