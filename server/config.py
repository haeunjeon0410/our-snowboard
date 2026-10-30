"""환경 설정과 경로. 키는 .env에서만 읽는다."""
import hashlib
import hmac
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT / "server"
DATA_DIR = ROOT / "output"          # 변환 결과 (커밋 제외)
CACHE_DIR = SERVER_DIR / ".cache"   # AI 응답 캐시 (같은 쪽을 두 번 호출하지 않기 위해)
STATIC_DIR = SERVER_DIR / "static"
for _d in (DATA_DIR, CACHE_DIR, CACHE_DIR / "llm"):
    _d.mkdir(parents=True, exist_ok=True)


def _load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_env()

API_KEY = os.environ.get("GATEWAY_API_KEY", "")
BASE_URL = os.environ.get("GATEWAY_BASE_URL", "https://factchat-cloud.mindlogic.ai/v1/gateway")
# 비용을 아끼기 위해 가장 저렴한 모델을 기본으로 쓴다.
TEXT_MODEL = os.environ.get("TEXT_MODEL", "gpt-6-luna")
VISION_MODEL = os.environ.get("VISION_MODEL", "gpt-6-luna")
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-3.1-flash-tts-preview")     # AI 목소리(읽어 주기)
FALLBACK_MODEL = os.environ.get("FALLBACK_MODEL", "gemini-3.5-flash-lite")
PORT = int(os.environ.get("PORT", "8790"))

# ── 공개 서버(인터넷에 올렸을 때)용 설정. 내 컴퓨터에서만 쓸 때는 모두 비워 둔다. ──
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")            # 예: https://아이디-our-snowboard.hf.space
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")                     # 있으면 이 코드를 아는 사람만 AI 항목을 쓸 수 있다


def _num(name: str, cast, default=0):
    try:
        return cast(os.environ.get(name, "") or default)
    except ValueError:
        return default


DAILY_AI_LIMIT = _num("DAILY_AI_LIMIT", int)         # 하루 AI 호출 상한 (0이면 제한 없음)
DAILY_TTS_LIMIT = _num("DAILY_TTS_LIMIT", int, 5000)       # 하루 AI 목소리 문장 수 상한 (기본 5000, 0이면 제한 없음). 같은 문장은 저장해 둔 소리를 쓰므로 세지 않는다
DATA_TTL_HOURS = _num("DATA_TTL_HOURS", float)       # 올린 자료를 이 시간이 지나면 지운다 (0이면 안 지움)
PUBLIC = bool(PUBLIC_URL)
if PUBLIC:                                           # 공개 서버는 안전한 기본값을 둔다 (비워 두면 크레딧이 끝없이 나가고 남의 강의 파일이 계속 남는다)
    DAILY_AI_LIMIT = DAILY_AI_LIMIT or 2000
    DATA_TTL_HOURS = DATA_TTL_HOURS or 24.0
ALLOWED_EXTENSION_IDS = {x.strip() for x in os.environ.get("ALLOWED_EXTENSION_IDS", "").split(",") if x.strip()}   # 있으면 이 ID의 확장 프로그램만 서버를 부를 수 있다


def _tts_secret() -> str:
    """읽어 주기(AI 목소리) 요청에 붙는 비밀 값. 내려받은 웹 문서에만 들어가므로, 다른 웹사이트가 내 서버로 목소리 요청을 보내 크레딧을 쓰지 못한다. 서버를 다시 켜도 같은 값을 쓴다."""
    p = CACHE_DIR / "tts_secret"
    try:
        s = p.read_text(encoding="utf-8").strip()
        if s:
            return s
    except OSError:
        pass
    s = secrets.token_hex(16)
    try:
        p.write_text(s, encoding="utf-8")
    except OSError:
        pass
    return s


TTS_TOKEN = hmac.new(_tts_secret().encode("utf-8"), b"osb-tts", hashlib.sha256).hexdigest()[:32]
