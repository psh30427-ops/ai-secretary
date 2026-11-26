"""환경변수, Firestore, OpenAI 연결을 한 번에 점검한다. 키 값은 출력하지 않는다.

실행 (backend 폴더에서):
    python scripts\\check_setup.py
    python scripts\\check_setup.py --skip-openai   # OpenAI 키가 아직 없을 때
"""
import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)  # backend/.env를 찾도록

from app import config  # noqa: E402,F401  (.env 로딩)

FIRESTORE_TIMEOUT = 20  # 초
OK, FAIL, SKIP = "[통과]", "[실패]", "[건너뜀]"


def check_env() -> bool:
    print("1) 환경변수")
    all_ok = True
    for key in ("FIREBASE_CREDENTIALS_BASE64", "OPENAI_API_KEY", "OPENAI_MODEL"):
        present = bool(os.getenv(key, "").strip())
        all_ok &= present
        print(f"   {OK if present else FAIL} {key}{'' if present else ' 가 비어 있습니다'}")
    origins = config.get_allowed_origins()
    print(f"   [정보] CORS 허용 출처: {', '.join(origins)}")
    return all_ok


def check_firestore() -> bool:
    print("2) Firestore")
    from google.api_core.retry import Retry

    from app.errors import ServiceNotConfiguredError
    from app.services.firestore import DATA_COLLECTION, _load_credentials_info, get_db

    try:
        info = _load_credentials_info()
        print(f"   {OK} 키 해석 성공 (프로젝트 ID: {info.get('project_id')})")
        db = get_db()
        count = sum(1 for _ in db.collection(DATA_COLLECTION).select([]).stream(
            retry=Retry(timeout=FIRESTORE_TIMEOUT), timeout=FIRESTORE_TIMEOUT
        ))
    except ServiceNotConfiguredError as exc:
        print(f"   {FAIL} {exc}")
        return False
    except Exception as exc:  # 네트워크, 권한, DB 미생성 등
        print(f"   {FAIL} {type(exc).__name__}: {str(exc).splitlines()[0][:200]}")
        print("   - 'does not exist' → Firestore Database를 (default) ID로 만들었는지 확인")
        print("   - 'Permission' / '403' → 키를 받은 프로젝트가 맞는지 확인")
        print("   - 'invalid_grant' → 키가 삭제됐거나 잘못된 파일입니다. 새 키를 받아 setup_env.py를 다시 실행")
        print("   - 'Deadline' / 'Unavailable' / 'RetryError' → 인터넷 연결이나 방화벽 확인")
        return False
    print(f"   {OK} 연결 성공: data 컬렉션 {count}건")
    if count == 0:
        print("   [정보] 데이터가 없습니다. python scripts\\seed.py 를 실행하세요.")
    elif count < 100:
        print(f"   [정보] 과제 요건(100건 이상)까지 {100 - count}건 더 필요합니다.")
    return True


def check_openai() -> bool:
    print("3) OpenAI")
    import openai

    from app.errors import ServiceNotConfiguredError
    from app.services.chat_service import get_model, get_openai_client

    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    provider = "제미나이 호환 API" if "generativelanguage" in base_url else (base_url or "OpenAI")
    print(f"   [정보] 연결 대상: {provider}")
    try:
        client = get_openai_client()
        model = get_model()
        client.models.retrieve(model)  # 토큰을 쓰지 않는 호출로 키와 모델 이름만 확인
    except ServiceNotConfiguredError as exc:
        print(f"   {FAIL} {exc}")
        return False
    except openai.AuthenticationError:
        print(f"   {FAIL} API 키가 올바르지 않습니다.")
        return False
    except openai.BadRequestError as exc:
        # 제미나이 호환 API는 잘못된 키에 401 대신 400을 돌려준다.
        print(f"   {FAIL} 요청이 거부됐습니다 (키나 모델 이름 확인): {str(exc)[:200]}")
        return False
    except openai.NotFoundError:
        print(f"   {FAIL} 모델 '{os.getenv('OPENAI_MODEL')}'을 찾을 수 없습니다. 모델 이름을 확인하세요.")
        return False
    except openai.OpenAIError as exc:
        print(f"   {FAIL} {type(exc).__name__}: {str(exc)[:200]}")
        return False
    print(f"   {OK} 키와 모델 '{model}' 확인 ({provider})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-openai", action="store_true")
    args = parser.parse_args()

    results = [check_env(), check_firestore()]
    if args.skip_openai:
        print(f"3) OpenAI\n   {SKIP}")
    else:
        results.append(check_openai())

    print()
    if all(results[1:]):
        print("점검 통과. uvicorn main:app --reload 로 서버를 실행하세요.")
        return 0
    print("실패한 항목을 고친 뒤 다시 실행하세요.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
