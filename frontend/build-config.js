// Vercel 빌드 스크립트 (Node 내장 모듈만 사용, npm 패키지 없음)
// 정적 파일을 dist/로 복사하고, 환경변수 API_BASE_URL로 dist/config.js를 생성한다.
// 순수 정적 사이트는 브라우저에서 환경변수를 읽을 수 없으므로 빌드 시점에 값을 파일에 박아 넣는다.
const fs = require("fs");
const path = require("path");

const SRC = __dirname;
const OUT = path.join(SRC, "dist");
const STATIC_FILES = ["index.html", "style.css", "app.js"];

const apiBaseUrl = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");
if (!apiBaseUrl) {
  if (process.env.VERCEL) {
    console.error("API_BASE_URL 환경변수가 없습니다. Vercel 프로젝트 설정에서 추가하세요.");
    process.exit(1);
  }
  console.warn("API_BASE_URL이 없어 http://localhost:8000을 사용합니다.");
}

fs.rmSync(OUT, { recursive: true, force: true });
fs.mkdirSync(OUT);
for (const f of STATIC_FILES) fs.copyFileSync(path.join(SRC, f), path.join(OUT, f));

const config = { API_BASE_URL: apiBaseUrl || "http://localhost:8000" };
fs.writeFileSync(
  path.join(OUT, "config.js"),
  `window.APP_CONFIG = ${JSON.stringify(config)};\n`
);
console.log(`dist/ 생성 완료 (API_BASE_URL=${config.API_BASE_URL})`);
