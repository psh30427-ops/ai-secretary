"""서비스 계정 키 파일로 backend/.env를 만든다 (base64 변환을 대신 해 줌).

실행 (backend 폴더에서):
    python scripts\\setup_env.py C:\\keys\\firebase-key.json

- .env가 없으면 .env.example을 복사해서 만든다.
- FIREBASE_CREDENTIALS_BASE64를 키 파일 내용으로 채운다.
- --provider gemini 를 주면 제미나이 호환 주소(OPENAI_BASE_URL)를 넣는다.
- OPENAI_API_KEY, OPENAI_MODEL이 비어 있으면 물어본다 (Enter로 건너뛰기 가능).
  API 키는 입력해도 화면에 보이지 않는다.
- 키 값은 화면에 출력하지 않는다.
"""
import argparse
import base64
import getpass
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
REQUIRED_KEY_FIELDS = ("type", "project_id", "private_key", "client_email")


def load_service_account(path: Path) -> bytes:
    if not path.is_file():
        sys.exit(f"[오류] 키 파일이 없습니다: {path}")
    raw = path.read_bytes()
    try:
        info = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        sys.exit("[오류] JSON 파일이 아닙니다. Firebase에서 받은 서비스 계정 키 파일인지 확인하세요.")
    missing = [k for k in REQUIRED_KEY_FIELDS if not info.get(k)]
    if missing or info.get("type") != "service_account":
        sys.exit(
            "[오류] 서비스 계정 키 형식이 아닙니다. "
            "Firebase 프로젝트 설정 > 서비스 계정 > '새 비공개 키 생성'으로 받은 파일을 쓰세요."
        )
    print(f"키 파일 확인: 프로젝트 ID = {info['project_id']}")
    return raw


def read_env_lines(env_path: Path) -> list[str]:
    if env_path.exists():
        return env_path.read_text(encoding="utf-8").splitlines()
    example = BACKEND_DIR / ".env.example"
    if example.exists():
        print(f"{env_path.name}이 없어서 .env.example을 복사해 만듭니다.")
        return example.read_text(encoding="utf-8").splitlines()
    return []


def get_value(lines: list[str], key: str) -> str:
    for line in lines:
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def set_value(lines: list[str], key: str, value: str) -> list[str]:
    out, done = [], False
    for line in lines:
        if line.startswith(key + "="):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="서비스 계정 키로 .env 만들기")
    parser.add_argument("key_file", type=Path, help="Firebase 서비스 계정 키 JSON 경로")
    parser.add_argument("--env-file", type=Path, default=BACKEND_DIR / ".env")
    parser.add_argument("--no-prompt", action="store_true", help="API 키·모델을 묻지 않음")
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        help="LLM 제공자를 지정 (gemini면 OPENAI_BASE_URL을 제미나이 주소로 설정)",
    )
    args = parser.parse_args()

    raw = load_service_account(args.key_file)
    if args.key_file.resolve().is_relative_to(BACKEND_DIR.parent.resolve()):
        print("[주의] 키 파일이 프로젝트 폴더 안에 있습니다. 실수로 커밋되지 않게 폴더 밖(예: C:\\keys)으로 옮기세요.")

    lines = read_env_lines(args.env_file)
    lines = set_value(lines, "FIREBASE_CREDENTIALS_BASE64", base64.b64encode(raw).decode("ascii"))

    if args.provider == "gemini":
        lines = set_value(lines, "OPENAI_BASE_URL", GEMINI_BASE_URL)
    elif args.provider == "openai":
        lines = set_value(lines, "OPENAI_BASE_URL", "")
    is_gemini = "generativelanguage" in get_value(lines, "OPENAI_BASE_URL")
    label = "제미나이" if is_gemini else "OpenAI"

    if not args.no_prompt:
        if not get_value(lines, "OPENAI_API_KEY"):
            key = getpass.getpass(f"{label} API 키 (입력해도 화면에 안 보임, 없으면 Enter): ").strip()
            if key:
                lines = set_value(lines, "OPENAI_API_KEY", key)
        if not get_value(lines, "OPENAI_MODEL"):
            model = input(f"{label} 모델 이름 (없으면 Enter): ").strip()
            if model:
                lines = set_value(lines, "OPENAI_MODEL", model)

    args.env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장 완료: {args.env_file}")
    print(f"  LLM 제공자: {label}")
    for key in ("FIREBASE_CREDENTIALS_BASE64", "OPENAI_API_KEY", "OPENAI_MODEL"):
        print(f"  {key}: {'설정됨' if get_value(lines, key) else '비어 있음'}")
    print("다음 단계: python scripts\\check_setup.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
