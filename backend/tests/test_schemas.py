import unittest

from pydantic import ValidationError

from app.schemas.chat import ChatRequest
from app.schemas.conversation import ConversationCreate
from app.schemas.data import DataIn

VALID = {"date": "2026-12-11", "value": 4, "memo": "[과제] 과목 - 제목 (마감 24:00)"}


class DataInTests(unittest.TestCase):
    def ok(self, **kw):
        return DataIn(**{**VALID, **kw})

    def bad(self, **kw):
        with self.assertRaises(ValidationError):
            DataIn(**{**VALID, **kw})

    def test_valid(self):
        d = self.ok()
        self.assertEqual(d.date.isoformat(), "2026-12-11")

    def test_memo_is_stripped(self):
        self.assertEqual(self.ok(memo="  [개인] 운동  ").memo, "[개인] 운동")

    def test_invalid_dates(self):
        for v in ["2026-02-30", "2026/12/11", "20261211", "12-11-2026", "", 1700000000, None]:
            with self.subTest(date=v):
                self.bad(date=v)

    def test_value_range_and_type(self):
        for v in [1, 5]:
            self.ok(value=v)
        for v in [0, 6, -1, 3.5, "3", True, None]:
            with self.subTest(value=v):
                self.bad(value=v)

    def test_memo_rules(self):
        self.ok(memo="가" * 200)
        for v in ["", "   ", "가" * 201, None]:
            with self.subTest(memo=v):
                self.bad(memo=v)

    def test_missing_field(self):
        with self.assertRaises(ValidationError):
            DataIn(date="2026-12-11", value=3)


class OtherSchemaTests(unittest.TestCase):
    def test_chat_request(self):
        self.assertIsNone(ChatRequest(message="안녕").conversation_id)
        with self.assertRaises(ValidationError):
            ChatRequest(message="   ")

    def test_conversation_create(self):
        ConversationCreate(messages=[{"role": "user", "content": "hi"}])
        with self.assertRaises(ValidationError):
            ConversationCreate(messages=[])
        with self.assertRaises(ValidationError):
            ConversationCreate(messages=[{"role": "system", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
