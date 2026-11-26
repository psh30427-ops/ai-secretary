"""환경변수 로딩과 공통 설정."""
import os
from datetime import timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

# 한국은 서머타임이 없으므로 고정 오프셋(UTC+9)으로 충분하다.
# (zoneinfo는 Windows에서 tzdata 패키지가 추가로 필요해서 쓰지 않는다.)
KST = timezone(timedelta(hours=9), name="Asia/Seoul")

DEFAULT_ORIGINS = ["http://localhost:5500", "http://127.0.0.1:5500"]


def get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins or DEFAULT_ORIGINS
