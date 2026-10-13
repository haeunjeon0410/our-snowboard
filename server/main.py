"""Our Snowboard 변환 서버 (내 컴퓨터에서만 동작). 실행: uvicorn server.main:app --port 8790

흐름: 자료 올리기(/api/prepare: 글자 추출 + 요약) → 변환하기(/api/jobs/{id}/make: 체크한 항목만 처리) →
      진행 확인(/api/tasks/{id}) → 파일 받기(/api/tasks/{id}/file/{종류})"""
import hmac
import io
import json
import urllib.parse
import urllib.request
import zipfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import config, jobs, llm, ops

app = FastAPI(title="Our Snowboard")

_ALLOWED_HOSTS = {f"localhost:{config.PORT}", f"127.0.0.1:{config.PORT}"}
_ALLOWED_ORIGINS = {"https://snowboard.sookmyung.ac.kr", f"http://localhost:{config.PORT}", f"http://127.0.0.1:{config.PORT}"}
if config.PUBLIC:                                    # 공개 서버: 자기 주소도 허용
    _pu = urllib.parse.urlparse(config.PUBLIC_URL)
    _ALLOWED_HOSTS.add(_pu.netloc)
    _ALLOWED_ORIGINS.add(f"{_pu.scheme}://{_pu.netloc}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_ALLOWED_ORIGINS),
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)


def ai_allowed(request: Request) -> bool:
    """이 요청이 AI를 써도 되는가: AI 키가 있고, (접속 코드가 정해져 있다면) 코드가 맞아야 한다."""
    if not llm.available():
        return False
    if not config.ACCESS_CODE:
        return True
    given = request.headers.get("x-osb-code", "")
    return hmac.compare_digest(given.encode("utf-8"), config.ACCESS_CODE.encode("utf-8"))


@app.middleware("http")
async def local_only_guard(request: Request, call_next):
    """내 AI 크레딧을 쓰는 서버라서, 다른 웹사이트가 몰래 요청을 보내지 못하게 막는다."""
    host = request.headers.get("host", "")
    if host and host not in _ALLOWED_HOSTS:           # DNS 우회 공격 방지
        return JSONResponse({"detail": "허용되지 않은 접속입니다"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in _ALLOWED_ORIGINS and not origin.startswith("chrome-extension://"):
            return JSONResponse({"detail": "허용되지 않은 출처입니다"}, status_code=403)
    return await call_next(request)


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
if not config.PUBLIC:
    app.mount("/ext", StaticFiles(directory=str(config.ROOT / "extension")), name="ext")   # 개발용: 확장 프로그램 파일 미리보기


@app.on_event("startup")
def _startup():
    jobs.load_existing()
    jobs.start_cleanup_loop(config.DATA_TTL_HOURS)


# ───────────── 화면 ─────────────
@app.get("/", response_class=HTMLResponse)
def index():
    return (config.STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/quality", response_class=HTMLResponse)
def quality_page():
    return (config.STATIC_DIR / "quality.html").read_text(encoding="utf-8")


@app.get("/health")
def health(request: Request):
    return {"ok": True, "ai": ai_allowed(request), "codeRequired": bool(config.ACCESS_CODE) and llm.available(), "public": config.PUBLIC}


@app.get("/extension.zip")
def extension_zip():
    """확장 프로그램 설치 파일. 이 서버 주소를 넣어서 만들어 주므로 받아서 풀고 크롬에 추가하면 바로 이 서버로 연결된다."""
    base = config.PUBLIC_URL or f"http://localhost:{config.PORT}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((config.ROOT / "extension").rglob("*")):
            if f.is_dir() or f.name.startswith("test_") or "__pycache__" in f.parts:
                continue
            rel = f.relative_to(config.ROOT / "extension").as_posix()
            data = f.read_bytes()
            if rel == "background.js":
                data = data.decode("utf-8").replace("const DEFAULT_SERVER = 'http://localhost:8790';", f"const DEFAULT_SERVER = '{base}';").encode("utf-8")
            elif rel == "manifest.json":
                m = json.loads(data.decode("utf-8"))
                m["host_permissions"] = sorted(set(m["host_permissions"]) | {base + "/*"})
                for cs in m["content_scripts"]:
                    if cs["js"] == ["mark.js"]:
                        cs["matches"] = sorted(set(cs["matches"]) | {base + "/*"})
                m["web_accessible_resources"][0]["matches"] = sorted(set(m["web_accessible_resources"][0]["matches"]) | {base + "/*"})
                data = json.dumps(m, ensure_ascii=False, indent=2).encode("utf-8")
            z.writestr("our-snowboard-extension/" + rel, data)
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": "attachment; filename=our-snowboard-extension.zip"})


# ───────────── 변환 ─────────────
@app.post("/api/prepare")
async def prepare(request: Request, filename: str = "lecture.pdf", course: str = "", title: str = ""):
    """PDF를 받아 글자를 뽑아 두고(AI 없음), 패널에 보여 줄 자료 요약을 돌려준다."""
    ai_ok = ai_allowed(request)
    body = await request.body()
    if body[:5] != b"%PDF-":
        raise HTTPException(400, "PDF 파일이 아닙니다")
    if len(body) > 60 * 1024 * 1024:
        raise HTTPException(413, "파일이 너무 큽니다 (60MB 초과)")

    def work():
        jid = jobs.create(body, filename, course[:80], title[:120])
        return jid, ops.analyze(jobs.get(jid), ai_ok)
    jid, info = await run_in_threadpool(work)
    return {"job": jid, "info": info}


@app.post("/api/jobs/{jid}/make")
async def make(jid: str, request: Request):
    job = jobs.get(jid)
    if not job:
        raise HTTPException(404, "자료를 찾을 수 없습니다")
    try:
        options = await request.json()
    except Exception:
        options = {}
    return {"task": ops.start(job, options if isinstance(options, dict) else {}, ai_allowed(request))}


def _task(tid: str):
    t = ops.TASKS.get(tid)
    if not t:
        raise HTTPException(404, "작업을 찾을 수 없습니다")
    return t


@app.get("/api/tasks/{tid}")
def task_status(tid: str):
    t = _task(tid)
    return {"status": t["status"], "done": t["done"], "total": t["total"], "step": t["step"], "error": t["error"], "note": t["note"],
            "files": [{"kind": f["kind"], "name": f["name"], "url": f"/api/tasks/{tid}/file/{f['kind']}"} for f in t["files"]]}


@app.post("/api/tasks/{tid}/cancel")
def task_cancel(tid: str):
    _task(tid)["cancel"] = True
    return {"ok": True}


@app.get("/api/tasks/{tid}/file/{kind}")
def task_file(tid: str, kind: str):
    f = next((f for f in _task(tid)["files"] if f["kind"] == kind), None)
    if not f:
        raise HTTPException(404, "파일이 아직 없습니다")
    media = "text/html" if kind == "html" else "text/plain"
    return FileResponse(f["path"], media_type=media + "; charset=utf-8", filename=f["name"])


# ───────────── 사용량 / 측정표 ─────────────
@app.get("/api/usage")
def usage():
    if config.PUBLIC:
        raise HTTPException(404)
    credits = None
    if llm.available():
        try:
            req = urllib.request.Request(config.BASE_URL + "/credits/", headers={
                "Authorization": "Bearer " + config.API_KEY, "User-Agent": "Mozilla/5.0"})
            credits = json.load(urllib.request.urlopen(req, timeout=15)).get("total")
        except Exception:
            pass
    return {"this_run": llm.usage_totals, "credits": credits, "models": {"text": config.TEXT_MODEL, "vision": config.VISION_MODEL}}


@app.get("/api/quality")
def quality():
    p = config.DATA_DIR / "_eval" / "results.json"
    if not p.exists():
        return JSONResponse({"ready": False})
    return JSONResponse({"ready": True, **json.loads(p.read_text(encoding="utf-8"))})


# ───────────── 개발용 가짜 강의사이트 (확장 프로그램 시험용) ─────────────
SAMPLES = config.ROOT / "samples"


@app.get("/mock", response_class=HTMLResponse)
def mock_course(ext: int = 0):
    if config.PUBLIC:
        raise HTTPException(404)
    files = sorted(SAMPLES.glob("*.pdf")) if SAMPLES.exists() else []
    items = "".join(
        f"<li class='activity ubfile modtype_ubfile'><span class='instancename'>"
        f"<a href='/mock/file/{i}'>{f.stem}</a></span></li>" for i, f in enumerate(files))
    demo = ""
    if ext:   # 개발용: 확장 프로그램 없이도 버튼이 붙은 모습을 미리 본다
        demo = ("<style>@font-face{font-family:'OSB Pretendard';font-weight:45 920;src:url('/static/fonts/PretendardVariable.woff2') format('woff2-variations')}</style>"
                "<link rel='stylesheet' href='/static/osb-ui.css'><script src='/static/dev-bg.js'></script>"
                "<script src='/static/osb-panel.js'></script><script src='/ext/content.js'></script>")
    return (f"<!doctype html><meta charset='utf-8'><title>스노우보드 시험 강좌</title>"
            f"<body style='font:16px sans-serif;max-width:700px;margin:2em auto'><h2>시험 강좌 (개발용 모의 화면)</h2><ul>{items}</ul>{demo}</body>")


@app.get("/mock/file/{i}")
def mock_file(i: int):
    if config.PUBLIC:
        raise HTTPException(404)
    files = sorted(SAMPLES.glob("*.pdf"))
    if i >= len(files):
        raise HTTPException(404)
    return FileResponse(files[i], media_type="application/pdf")
