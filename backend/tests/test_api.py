"""Firestore·OpenAI를 대역으로 바꿔 API 전체 흐름을 확인한다 (키 없이 실행 가능)."""
import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from app.services import chat_service
from app.services.firestore import get_db
from tests.fake_firestore import FakeFirestore


class FakeOpenAI:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        reply = f"답변 {len(self.calls)}"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


class ApiTestBase(unittest.TestCase):
    def setUp(self):
        self.db = FakeFirestore()
        self.ai = FakeOpenAI()
        main.app.dependency_overrides = {
            get_db: lambda: self.db,
            chat_service.get_openai_client: lambda: self.ai,
            chat_service.get_model: lambda: "test-model",
        }
        self.client = TestClient(main.app)

    def tearDown(self):
        main.app.dependency_overrides = {}

    def add(self, date, value=2, memo="[강의시청] 과목 - 제목 (마감 23:59)"):
        r = self.client.post("/api/data", json={"date": date, "value": value, "memo": memo})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()


class HealthAndDocsTests(ApiTestBase):
    def test_health_and_docs(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/docs").status_code, 200)

    def test_cors_preflight(self):
        r = self.client.options(
            "/api/data",
            headers={"Origin": "http://localhost:5500", "Access-Control-Request-Method": "POST"},
        )
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5500")


class DataApiTests(ApiTestBase):
    def test_crud(self):
        a = self.add("2026-12-11", 4, "[과제] B")
        self.add("2026-11-01", 2, "[강의시청] A")
        rows = self.client.get("/api/data").json()
        self.assertEqual([r["date"] for r in rows], ["2026-11-01", "2026-12-11"])

        r = self.client.put(f"/api/data/{a['id']}", json={"date": "2026-12-12", "value": 5, "memo": "[시험] B"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["value"], 5)

        self.assertEqual(self.client.delete(f"/api/data/{a['id']}").status_code, 200)
        self.assertEqual(len(self.client.get("/api/data").json()), 1)

    def test_filter(self):
        for d in ["2026-11-01", "2026-11-15", "2026-11-30"]:
            self.add(d)
        r = self.client.get("/api/data", params={"from": "2026-11-10", "to": "2026-11-30"})
        self.assertEqual([x["date"] for x in r.json()], ["2026-11-15", "2026-11-30"])

    def test_validation_errors(self):
        r = self.client.post("/api/data", json={"date": "2026-13-01", "value": 9, "memo": ""})
        self.assertEqual(r.status_code, 422)
        self.assertEqual({e["loc"][-1] for e in r.json()["detail"]}, {"date", "value", "memo"})

    def test_not_found(self):
        body = {"date": "2026-12-12", "value": 5, "memo": "x"}
        self.assertEqual(self.client.put("/api/data/nope", json=body).status_code, 404)
        self.assertEqual(self.client.delete("/api/data/nope").status_code, 404)

    def test_summary(self):
        self.add("2026-11-01", 5, "[시험] A")
        s = self.client.get("/api/data/summary").json()
        self.assertEqual(s["count"], 1)
        self.assertEqual(s["category_counts"]["시험"], 1)


class ConversationApiTests(ApiTestBase):
    def test_save_list_get_delete(self):
        r = self.client.post(
            "/api/conversations",
            json={"messages": [{"role": "user", "content": "이번 주 일정은?"}, {"role": "assistant", "content": "..."}]},
        )
        self.assertEqual(r.status_code, 201)
        cid = r.json()["id"]

        items = self.client.get("/api/conversations").json()
        self.assertEqual(items, [{"id": cid, "title": "이번 주 일정은?", "created_at": items[0]["created_at"], "message_count": 2}])

        detail = self.client.get(f"/api/conversations/{cid}").json()
        self.assertEqual([m["role"] for m in detail["messages"]], ["user", "assistant"])

        self.assertEqual(self.client.delete(f"/api/conversations/{cid}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/conversations/{cid}").status_code, 404)


class ChatApiTests(ApiTestBase):
    def test_new_chat_injects_summary_and_saves(self):
        self.add("2099-01-01", 4, "[과제] 먼 미래 과제 (마감 24:00)")
        r = self.client.post("/api/chat", json={"message": "다가오는 마감 알려줘"})
        self.assertEqual(r.status_code, 200, r.text)
        cid = r.json()["conversation_id"]
        self.assertEqual(r.json()["reply"], "답변 1")

        call = self.ai.calls[0]
        self.assertEqual(call["model"], "test-model")
        system = call["messages"][0]
        self.assertEqual(system["role"], "system")
        self.assertIn("먼 미래 과제", system["content"])  # 요약(upcoming)이 프롬프트에 들어갔는지
        self.assertIn("지어내지 마", system["content"])

        conv = self.client.get(f"/api/conversations/{cid}").json()
        self.assertEqual([m["content"] for m in conv["messages"]], ["다가오는 마감 알려줘", "답변 1"])

    def test_continue_chat_sends_history(self):
        cid = self.client.post("/api/chat", json={"message": "첫 질문"}).json()["conversation_id"]
        r = self.client.post("/api/chat", json={"message": "두번째", "conversation_id": cid})
        self.assertEqual(r.json()["conversation_id"], cid)
        sent = [m["content"] for m in self.ai.calls[1]["messages"][1:]]
        self.assertEqual(sent, ["첫 질문", "답변 1", "두번째"])
        self.assertEqual(self.client.get("/api/conversations").json()[0]["message_count"], 4)

    def test_unknown_conversation(self):
        r = self.client.post("/api/chat", json={"message": "x", "conversation_id": "nope"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.ai.calls, [])


class NotConfiguredTests(unittest.TestCase):
    """키가 없을 때 500이 아니라 이유가 담긴 503을 돌려주는지."""

    def test_503_without_env(self):
        import os
        from unittest import mock

        get_db.cache_clear()
        chat_service.get_openai_client.cache_clear()
        env = {k: v for k, v in os.environ.items() if k not in ("FIREBASE_CREDENTIALS_BASE64", "OPENAI_API_KEY")}
        with mock.patch.dict(os.environ, env, clear=True):
            client = TestClient(main.app)
            r = client.get("/api/data")
            self.assertEqual(r.status_code, 503)
            self.assertIn("FIREBASE_CREDENTIALS_BASE64", r.json()["detail"])


if __name__ == "__main__":
    unittest.main()


class OpenAIClientConfigTests(unittest.TestCase):
    def setUp(self):
        chat_service.get_openai_client.cache_clear()

    def tearDown(self):
        chat_service.get_openai_client.cache_clear()

    def _client(self, env):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, env):
            return chat_service.get_openai_client()

    def test_default_is_openai(self):
        c = self._client({"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": ""})
        self.assertIn("api.openai.com", str(c.base_url))

    def test_gemini_base_url(self):
        c = self._client({"OPENAI_API_KEY": "k", "OPENAI_BASE_URL": chat_service.GEMINI_BASE_URL})
        self.assertEqual(str(c.base_url), chat_service.GEMINI_BASE_URL)
