"""Firestore 클라이언트 생성.

서비스 계정 키는 FIREBASE_CREDENTIALS_BASE64 환경변수(JSON을 base64 인코딩한 값)로만 받는다.
"""
import base64
import binascii
import json
import os
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore

from app.errors import ServiceNotConfiguredError

DATA_COLLECTION = "data"
CONVERSATIONS_COLLECTION = "conversations"


def _load_credentials_info() -> dict:
    raw = os.getenv("FIREBASE_CREDENTIALS_BASE64", "").strip()
    if not raw:
        raise ServiceNotConfiguredError(
            "FIREBASE_CREDENTIALS_BASE64 환경변수가 설정되지 않았습니다."
        )
    try:
        return json.loads(base64.b64decode(raw))
    except (binascii.Error, ValueError):
        # 키 내용이 로그에 남지 않도록 원본 예외는 버린다.
        raise ServiceNotConfiguredError(
            "FIREBASE_CREDENTIALS_BASE64 값을 해석할 수 없습니다. base64 인코딩을 확인하세요."
        ) from None


@lru_cache
def get_db():
    """FastAPI 의존성. 처음 호출될 때 한 번만 초기화한다 (실패하면 캐시되지 않음)."""
    info = _load_credentials_info()
    try:
        app = firebase_admin.get_app()
    except ValueError:
        app = firebase_admin.initialize_app(credentials.Certificate(info))
    return firestore.client(app)
