import datetime as dt
import unittest

from app.services.summary_service import (
    TREND_THRESHOLD,
    UPCOMING_LIMIT,
    build_summary,
    parse_category,
    parse_deadline_minutes,
)

TODAY = dt.date(2026, 11, 26)  # 목요일


def item(date, value=2, memo="[강의시청] 과목 - 제목 (마감 23:59)"):
    return {"date": date, "value": value, "memo": memo}


def spread(start: dt.date, days: int, count: int):
    """start부터 days일 안에 count건을 고르게 만든다."""
    return [item((start + dt.timedelta(days=i % days)).isoformat()) for i in range(count)]


class ParseTests(unittest.TestCase):
    def test_category(self):
        self.assertEqual(parse_category("[과제] 마케팅원론 - 과제"), "과제")
        self.assertEqual(parse_category("  [개인] 운동"), "개인")
        self.assertEqual(parse_category("분류 없는 메모"), "기타")

    def test_deadline(self):
        self.assertEqual(parse_deadline_minutes("x (마감 13:15)"), 13 * 60 + 15)
        self.assertEqual(parse_deadline_minutes("x (마감 24:00)"), 24 * 60)
        self.assertEqual(parse_deadline_minutes("마감 표시 없음"), 24 * 60)


class EmptyTests(unittest.TestCase):
    def test_empty_data(self):
        s = build_summary([], TODAY)
        self.assertEqual(s["count"], 0)
        self.assertEqual(s["period"], {"start": None, "end": None})
        self.assertEqual(s["value_stats"], {"mean": None, "max": None, "min": None})
        self.assertEqual(s["weekly_counts"], [])
        self.assertEqual(s["upcoming"], [])
        self.assertEqual(s["trend"]["direction"], "유지")
        self.assertEqual(s["today"], "2026-11-26")


class BasicStatsTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            item("2026-11-10", 5, "[시험] A - 중간고사 (마감 20:00)"),
            item("2026-11-03", 3, "[퀴즈] A - 퀴즈 (마감 13:15)"),
            item("2026-11-20", 4, "[과제] B - 과제 (마감 23:59)"),
            item("2026-11-20", 1, "메모만 있음"),
        ]
        self.s = build_summary(self.items, TODAY)

    def test_period_and_count(self):
        self.assertEqual(self.s["period"], {"start": "2026-11-03", "end": "2026-11-20"})
        self.assertEqual(self.s["count"], 4)

    def test_value_stats(self):
        self.assertEqual(self.s["value_stats"], {"mean": 3.25, "max": 5, "min": 1})

    def test_category_counts_keep_fixed_order_and_zero(self):
        cats = self.s["category_counts"]
        self.assertEqual(list(cats)[:7], ["시험", "과제", "퀴즈", "강의시청", "법정교육", "신청", "개인"])
        self.assertEqual(cats["시험"], 1)
        self.assertEqual(cats["신청"], 0)
        self.assertEqual(cats["기타"], 1)

    def test_weekly_counts_include_empty_weeks(self):
        # 11/03(화)=11/02 주, 11/10=11/09 주, 11/20=11/16 주
        self.assertEqual(
            self.s["weekly_counts"],
            [
                {"week_start": "2026-11-02", "count": 1},
                {"week_start": "2026-11-09", "count": 1},
                {"week_start": "2026-11-16", "count": 2},
            ],
        )

    def test_monthly_counts(self):
        self.assertEqual(self.s["monthly_counts"], [{"month": "2026-11", "count": 4}])


class TrendTests(unittest.TestCase):
    # 최근 창: 11/13~11/26, 직전 창: 10/30~11/12
    RECENT = dt.date(2026, 11, 13)
    PREV = dt.date(2026, 10, 30)

    def trend(self, recent_n, prev_n):
        items = spread(self.RECENT, 14, recent_n) + spread(self.PREV, 14, prev_n)
        return build_summary(items, TODAY)["trend"]

    def test_ranges(self):
        t = self.trend(1, 1)
        self.assertEqual(t["recent_range"], {"start": "2026-11-13", "end": "2026-11-26"})
        self.assertEqual(t["previous_range"], {"start": "2026-10-30", "end": "2026-11-12"})

    def test_increase(self):
        t = self.trend(13, 10)  # +30%
        self.assertEqual(t["direction"], "증가")
        self.assertEqual(t["recent_weekly_avg"], 6.5)
        self.assertEqual(t["previous_weekly_avg"], 5.0)
        self.assertAlmostEqual(t["change_rate"], 0.3)

    def test_decrease(self):
        self.assertEqual(self.trend(7, 10)["direction"], "감소")  # -30%

    def test_stable_within_threshold(self):
        self.assertEqual(self.trend(11, 10)["direction"], "유지")  # +10%

    def test_exact_threshold_is_stable(self):
        t = self.trend(12, 10)  # 정확히 +20%
        self.assertAlmostEqual(t["change_rate"], TREND_THRESHOLD)
        self.assertEqual(t["direction"], "유지")

    def test_previous_zero(self):
        t = self.trend(3, 0)
        self.assertEqual(t["direction"], "증가")
        self.assertIsNone(t["change_rate"])

    def test_future_items_are_not_counted(self):
        items = spread(self.RECENT, 14, 10) + spread(self.PREV, 14, 10)
        items += [item("2026-11-27")] * 20  # 내일 이후 일정은 '최근'이 아니다
        self.assertEqual(build_summary(items, TODAY)["trend"]["direction"], "유지")

    def test_today_is_injectable(self):
        items = [item("2026-12-01")] * 4
        self.assertEqual(build_summary(items, TODAY)["trend"]["recent_weekly_avg"], 0)
        later = build_summary(items, dt.date(2026, 12, 2))["trend"]
        self.assertEqual(later["recent_weekly_avg"], 2.0)


class UpcomingTests(unittest.TestCase):
    def test_from_today_sorted_by_date_then_deadline(self):
        items = [
            item("2026-11-25", 4, "[과제] 어제 마감"),
            item("2026-11-27", 2, "[강의시청] 27일 (마감 23:59)"),
            item("2026-11-26", 4, "[과제] 오늘 밤 (마감 24:00)"),
            item("2026-11-26", 3, "[퀴즈] 오늘 낮 (마감 13:15)"),
        ]
        up = build_summary(items, TODAY)["upcoming"]
        self.assertEqual(
            [u["memo"] for u in up],
            ["[퀴즈] 오늘 낮 (마감 13:15)", "[과제] 오늘 밤 (마감 24:00)", "[강의시청] 27일 (마감 23:59)"],
        )
        self.assertEqual(set(up[0]), {"date", "memo"})

    def test_limit(self):
        items = spread(TODAY, 30, 25)
        self.assertEqual(len(build_summary(items, TODAY)["upcoming"]), UPCOMING_LIMIT)


if __name__ == "__main__":
    unittest.main()
