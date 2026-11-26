from pydantic import BaseModel


class Period(BaseModel):
    start: str | None
    end: str | None


class ValueStats(BaseModel):
    mean: float | None
    max: int | None
    min: int | None


class WeeklyCount(BaseModel):
    week_start: str  # 월요일 날짜
    count: int


class MonthlyCount(BaseModel):
    month: str  # YYYY-MM
    count: int


class Trend(BaseModel):
    direction: str  # 증가 | 감소 | 유지
    recent_weekly_avg: float
    previous_weekly_avg: float
    change_rate: float | None
    threshold: float
    recent_range: Period
    previous_range: Period


class UpcomingItem(BaseModel):
    date: str
    memo: str


class Summary(BaseModel):
    today: str
    period: Period
    count: int
    value_stats: ValueStats
    category_counts: dict[str, int]
    weekly_counts: list[WeeklyCount]
    monthly_counts: list[MonthlyCount]
    trend: Trend
    upcoming: list[UpcomingItem]
