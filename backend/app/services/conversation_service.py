"""conversations 컬렉션.

문서 구조: {title, created_at, updated_at, message_count, messages: [{role, content, created_at}]}
목록 조회 때 messages를 읽지 않도록 message_count를 따로 저장한다.
"""
import datetime as dt

from google.cloud import firestore

from app.config import KST
from app.errors import NotFoundError
from app.services.firestore import CONVERSATIONS_COLLECTION

TITLE_MAX = 30


def now_iso() -> str:
    return dt.datetime.now(KST).isoformat(timespec="seconds")


def make_title(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= TITLE_MAX else text[: TITLE_MAX - 1] + "…"


def _message(role: str, content: str) -> dict:
    return {"role": role, "content": content, "created_at": now_iso()}


def create_conversation(db, messages: list[dict], title: str | None = None) -> dict:
    stamped = [_message(m["role"], m["content"]) for m in messages]
    first_user = next((m["content"] for m in stamped if m["role"] == "user"), stamped[0]["content"])
    now = now_iso()
    doc = {
        "title": title or make_title(first_user),
        "created_at": now,
        "updated_at": now,
        "message_count": len(stamped),
        "messages": stamped,
    }
    ref = db.collection(CONVERSATIONS_COLLECTION).document()
    ref.set(doc)
    return {"id": ref.id, **doc}


def list_conversations(db) -> list[dict]:
    query = (
        db.collection(CONVERSATIONS_COLLECTION)
        .select(["title", "created_at", "message_count"])
        .order_by("created_at", direction=firestore.Query.DESCENDING)
    )
    return [
        {
            "id": snap.id,
            "title": d.get("title", ""),
            "created_at": d.get("created_at", ""),
            "message_count": d.get("message_count", 0),
        }
        for snap in query.stream()
        for d in [snap.to_dict()]
    ]


def get_conversation(db, conv_id: str) -> dict:
    snap = db.collection(CONVERSATIONS_COLLECTION).document(conv_id).get()
    if not snap.exists:
        raise NotFoundError(f"대화 {conv_id}를 찾을 수 없습니다.")
    return {"id": snap.id, **snap.to_dict()}


def append_messages(db, conv_id: str, messages: list[dict]) -> dict:
    conv = get_conversation(db, conv_id)
    all_messages = conv["messages"] + [_message(m["role"], m["content"]) for m in messages]
    update = {
        "messages": all_messages,
        "message_count": len(all_messages),
        "updated_at": now_iso(),
    }
    db.collection(CONVERSATIONS_COLLECTION).document(conv_id).update(update)
    return {**conv, **update}


def delete_conversation(db, conv_id: str) -> None:
    ref = db.collection(CONVERSATIONS_COLLECTION).document(conv_id)
    if not ref.get().exists:
        raise NotFoundError(f"대화 {conv_id}를 찾을 수 없습니다.")
    ref.delete()
