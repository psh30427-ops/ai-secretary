"""시계열 데이터 요약. 결과는 /api/data/summary 응답이자 GPT 시스템 프롬프트에 주입된다.

build_summary()는 Firestore와 무관한 순수 함수라서 단위 테스트가 쉽다.
"""
import datetime as dt
import re
from collections import Counter

from app.config import KST
from app.services import data_service

# 최근 추세 판정 기준: 최근 2주 주평균이 직전 2주 대비 ±20%를 넘으면 증가/감소.
TREND_THRESHOLD = 0.20
TREND_WINDOW_DAYS = 14
UPCOMING_LIMIT = 10

CATEGORIES = ["시험", "과제", "퀴즈", "강의시청", "법정교육", "신청", "개인"]
UNKNOWN_CATEGORY = "기타"

_CATEGORY_RE = re.compile(r"^\s*\[([^\]]+)\]")
_DEADLINE_RE = re.compile(r"\(마감\s*(\d{1,2}):(\d{2})\)")


def today_kst() -> dt.date:
    return dt.datetime.now(KST).date()


def parse_category(memo: str) -> str:
    m = _CATEGORY_RE.match(memo)
    return m.group(1).strip() if m else UNKNOWN_CATEGORY


def parse_deadline_minutes(memo: str) -> int:
    """memo의 '(마감 HH:MM)'을 분으로. 없으면 하루 끝(24:00)으로 본다."""
    m = _DEADLINE_RE.search(memo)
    if not m:
        return 24 * 60
    return int(m.group(1)) * 60 + int(m.group(2))


def _week_start(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def _trend(dates: list[dt.date], today: dt.date) -> dict:
    """오늘 포함 최근 14일 vs 그 전 14일의 주평균 건수 비교."""
    recent_start = today - dt.timedelta(days=TREND_WINDOW_DAYS - 1)
    prev_end = recent_start - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=TREND_WINDOW_DAYS - 1)

    recent = sum(1 for d in dates if recent_start <= d <= today)
    previous = sum(1 for d in dates if prev_start <= d <= prev_end)
    weeks = TREND_WINDOW_DAYS / 7
    recent_avg = recent / weeks
    prev_avg = previous / weeks

    if prev_avg == 0:
        change_rate = None
        direction = "증가" if recent_avg > 0 else "유지"
    else:
        change_rate = round((recent_avg - prev_avg) / prev_avg, 3)
        if change_rate > TREND_THRESHOLD:
            direction = "증가"
        elif change_rate < -TREND_THRESHOLD:
            direction = "감소"
        else:
            direction = "유지"

    return {
        "direction": direction,
        "recent_weekly_avg": round(recent_avg, 2),
        "previous_weekly_avg": round(prev_avg, 2),
        "change_rate": change_rate,
        "threshold": TREND_THRESHOLD,
        "recent_range": {"start": recent_start.isoformat(), "end": today.isoformat()},
        "previous_range": {"start": prev_start.isoformat(), "end": prev_end.isoformat()},
    }


def build_summary(items: list[dict], today: dt.date) -> dict:
    """items: [{'date': 'YYYY-MM-DD', 'value': int, 'memo': str}, ...]"""
    parsed = [
        (dt.date.fromisoformat(it["date"]), int(it["value"]), it["memo"]) for it in items
    ]
    dates = [d for d, _, _ in parsed]
    values = [v for _, v, _ in parsed]

    # 분류별 개수: 정해진 분류는 0건이어도 보여주고, 그 밖의 분류는 뒤에 붙인다.
    counter = Counter(parse_category(m) for _, _, m in parsed)
    category_counts = {c: counter.pop(c, 0) for c in CATEGORIES}
    category_counts.update(sorted(counter.items()))

    weekly_counts: list[dict] = []
    monthly_counts: list[dict] = []
    if dates:
        week_counter = Counter(_week_start(d) for d in dates)
        w, last = _week_start(min(dates)), _week_start(max(dates))
        while w <= last:  # 건수가 0인 주도 포함해서 흐름이 보이게 한다.
            weekly_counts.append({"week_start": w.isoformat(), "count": week_counter.get(w, 0)})
            w += dt.timedelta(days=7)
        month_counter = Counter(d.strftime("%Y-%m") for d in dates)
        monthly_counts = [{"month": k, "count": month_counter[k]} for k in sorted(month_counter)]

    upcoming = sorted(
        (p for p in parsed if p[0] >= today),
        key=lambda p: (p[0], parse_deadline_minutes(p[2]), -p[1]),
    )[:UPCOMING_LIMIT]

    return {
        "today": today.isoformat(),
        "period": {
            "start": min(dates).isoformat() if dates else None,
            "end": max(dates).isoformat() if dates else None,
        },
        "count": len(parsed),
        "value_stats": {
            "mean": round(sum(values) / len(values), 2) if values else None,
            "max": max(values) if values else None,
            "min": min(values) if values else None,
        },
        "category_counts": category_counts,
        "weekly_counts": weekly_counts,
        "monthly_counts": monthly_counts,
        "trend": _trend(dates, today),
        "upcoming": [{"date": d.isoformat(), "memo": m} for d, _, m in upcoming],
    }


def get_summary(db, today: dt.date | None = None) -> dict:
    return build_summary(data_service.list_data(db), today or today_kst())
