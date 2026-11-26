"""서비스 계층에서 쓰는 예외. 라우터/전역 핸들러에서 HTTP 응답으로 바꾼다."""


class ServiceNotConfiguredError(RuntimeError):
    """필수 환경변수가 없어서 외부 서비스를 쓸 수 없을 때 (HTTP 503)."""


class NotFoundError(LookupError):
    """요청한 문서가 없을 때 (HTTP 404)."""


class UpstreamError(RuntimeError):
    """OpenAI 같은 외부 API 호출이 실패했을 때 (HTTP 502)."""
