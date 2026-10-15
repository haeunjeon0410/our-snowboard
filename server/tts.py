"""AI 목소리로 읽어 주기: 학교 AI API의 음성 합성(TTS)으로 문장을 소리(wav)로 만든다. 한 번 만든 소리는 디스크에 보관한다."""
import hashlib
import io
import threading
import time
import wave

from openai import OpenAI

from . import config

# 고른 목소리 이름 → 화면에 보일 이름. 키는 Gemini TTS의 목소리 이름이다.
VOICES = {
    "Kore":   "수아 · 차분한 여성",
    "Aoede":  "하린 · 밝은 여성",
    "Charon": "도윤 · 낮고 차분한 남성",
    "Puck":   "시우 · 경쾌한 남성",
}
MAX_CHARS = 400
SAMPLE_RATE = 24000          # Gemini TTS는 24kHz 16비트 모노 PCM을 준다

_dir = config.CACHE_DIR / "tts"
_dir.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()
_day = {"date": "", "n": 0}
_client = None


def _daily_ok() -> bool:
    if not config.DAILY_TTS_LIMIT:
        return True
    today = time.strftime("%Y-%m-%d")
    with _lock:
        if _day["date"] != today:
            _day.update(date=today, n=0)
        if _day["n"] >= config.DAILY_TTS_LIMIT:
            return False
        _day["n"] += 1
        return True


def _wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def speak(text: str, voice: str) -> bytes:
    """문장 하나를 wav 바이트로. 잘못된 입력은 ValueError, 한도를 넘으면 RuntimeError."""
    text = " ".join(text.split())
    if voice not in VOICES or not text or len(text) > MAX_CHARS:
        raise ValueError("읽을 수 없는 요청이에요")
    if len(text) < 6 and not text.endswith((".", "!", "?")):
        text += "."                                  # '1쪽'처럼 아주 짧은 글은 모델이 소리를 만들지 못해서 문장 부호를 붙인다
    path = _dir / (hashlib.sha256(f"{config.TTS_MODEL}|{voice}|{text}".encode("utf-8")).hexdigest()[:40] + ".wav")
    if path.exists():
        return path.read_bytes()
    if not _daily_ok():
        raise RuntimeError("오늘 AI 목소리 사용 한도를 다 썼어요")
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL, timeout=60, max_retries=1)
    r = _client.audio.speech.create(model=config.TTS_MODEL, voice=voice, input=text, response_format="pcm")
    wav = _wav(r.content)
    path.write_bytes(wav)
    return wav
