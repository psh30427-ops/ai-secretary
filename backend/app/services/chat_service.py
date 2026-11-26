"""AI 채팅: 데이터 요약을 시스템 프롬프트에 주입(컨텍스트 주입)하고 OpenAI를 호출한다."""
import datetime as dt
import json
import os
from functools import lru_cache

import openai

from app.errors import ServiceNotConfiguredError, UpstreamError
from app.services import conversation_service, summary_service

# 이전 대화 중 최근 몇 개 메시지를 함께 보낼지 (토큰 비용 제한)
HISTORY_LIMIT = 20

SYSTEM_PROMPT_TEMPLATE = """너는 한림대학교 학생의 학사 일정을 관리해 주는 AI 비서야.
오늘 날짜는 {today} (Asia/Seoul)이야.

아래 [일정 데이터 요약]은 학생의 LMS(SmartLEAD)에서 가져온 과제 마감, 퀴즈, 강의 시청 기한,
시험, 신청, 개인 일정을 분석한 결과야. 필드 의미:
- period: 데이터 기간, count: 전체 일정 수
- value_stats: 중요도(1~5, 시험5·과제4·퀴즈3·강의시청2·법정교육/기타1) 통계
- category_counts: 분류별 개수
- weekly_counts / monthly_counts: 주(월요일 시작)별, 월별 일정 수
- trend: 최근 2주와 그 전 2주의 주평균 일정 수 비교 결과
- upcoming: 오늘 이후 가장 가까운 마감 최대 {upcoming_limit}건

[일정 데이터 요약]
{summary_json}

규칙:
1. 반드시 위 요약에 있는 정보만 근거로 답해. 요약에 없는 일정, 날짜, 과목은 절대 지어내지 마.
2. 요약만으로 알 수 없는 질문이면 "요약 데이터에서는 확인할 수 없어요"라고 솔직하게 말해.
3. 마감이 가까운 순서와 중요도를 함께 고려해서 우선순위를 제안해.
4. 한국어로, 간결하게 답해. 날짜는 'M월 D일(요일)' 형식을 써.
"""


@lru_cache
def get_openai_client() -> openai.OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise ServiceNotConfiguredError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
    return openai.OpenAI()  # OPENAI_API_KEY를 환경변수에서 읽는다.


def get_model() -> str:
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not model:
        raise ServiceNotConfiguredError("OPENAI_MODEL 환경변수가 설정되지 않았습니다.")
    return model


def build_system_prompt(summary: dict) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        today=summary["today"],
        upcoming_limit=summary_service.UPCOMING_LIMIT,
        summary_json=json.dumps(summary, ensure_ascii=False, indent=2),
    )


def chat(
    db,
    client,
    model: str,
    message: str,
    conversation_id: str | None = None,
    today: dt.date | None = None,
) -> dict:
    # 0) 이어지는 대화면 먼저 존재 여부를 확인 (없으면 NotFoundError → 404)
    history: list[dict] = []
    if conversation_id:
        conv = conversation_service.get_conversation(db, conversation_id)
        history = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]

    # 1) 데이터 요약 조회  2) 시스템 프롬프트에 삽입
    summary = summary_service.get_summary(db, today=today)
    messages = [{"role": "system", "content": build_system_prompt(summary)}]
    messages += history[-HISTORY_LIMIT:]
    messages.append({"role": "user", "content": message})

    # 3) GPT 호출
    try:
        completion = client.chat.completions.create(model=model, messages=messages)
    except openai.OpenAIError as exc:
        raise UpstreamError(f"OpenAI 호출에 실패했습니다: {type(exc).__name__}") from None
    reply = (completion.choices[0].message.content or "").strip()

    # 4) conversations에 자동 저장
    new_messages = [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
    if conversation_id:
        conversation_service.append_messages(db, conversation_id, new_messages)
    else:
        conversation_id = conversation_service.create_conversation(db, new_messages)["id"]

    return {"conversation_id": conversation_id, "reply": reply}
