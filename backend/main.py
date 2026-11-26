"""FastAPI 진입점. 실행: uvicorn main:app --reload"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_allowed_origins
from app.errors import NotFoundError, ServiceNotConfiguredError, UpstreamError
from app.routers import chat, conversations, data

app = FastAPI(
    title="내 학사 일정을 아는 AI 비서 API",
    description="SmartLEAD 일정 데이터를 요약해 GPT 시스템 프롬프트에 주입하는 AI 비서",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(NotFoundError)
async def _not_found(_: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ServiceNotConfiguredError)
async def _not_configured(_: Request, exc: ServiceNotConfiguredError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(UpstreamError)
async def _upstream(_: Request, exc: UpstreamError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health", tags=["health"], summary="헬스 체크 (콜드스타트 깨우기용)")
def health():
    return {"status": "ok"}


app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)
