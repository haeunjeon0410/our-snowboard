"""학교 AI API 호출. 응답은 디스크에 캐시하고, 쓴 토큰을 기록한다."""
import base64
import hashlib
import json
import threading
import time

from openai import OpenAI

from . import config, obs

_client = None
_lock = threading.Lock()
usage_totals = {"calls": 0, "cache_hits": 0, "input_tokens": 0, "output_tokens": 0}


def available() -> bool:
    return bool(config.API_KEY)


_day = {"date": "", "calls": 0}


def _check_daily_limit():
    """하루 호출 상한 (공개 서버에서 크레딧이 한꺼번에 나가는 것을 막는다). 서버를 다시 켜도 usage.jsonl로 이어서 센다."""
    if not config.DAILY_AI_LIMIT:
        return
    today = time.strftime("%Y-%m-%d")
    with _lock:
        if _day["date"] != today:
            n = 0
            try:
                start = time.mktime(time.strptime(today, "%Y-%m-%d"))
                with open(config.CACHE_DIR / "usage.jsonl", encoding="utf-8") as f:
                    for line in f:
                        if json.loads(line).get("t", 0) >= start:
                            n += 1
            except Exception:
                pass
            _day.update(date=today, calls=n)
        if _day["calls"] >= config.DAILY_AI_LIMIT:
            raise RuntimeError("오늘 AI 사용 한도를 다 썼어요. 내일 다시 이용해 주세요")
        _day["calls"] += 1


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL, timeout=90, max_retries=0)
    return _client


def _cache_path(key: str):
    return config.CACHE_DIR / "llm" / (hashlib.sha256(key.encode("utf-8")).hexdigest()[:40] + ".json")


def image_part(img_bytes: bytes) -> dict:
    mime = "image/jpeg" if img_bytes[:3] == b"\xff\xd8\xff" else "image/png"
    b64 = base64.b64encode(img_bytes).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64," + b64}}


def chat(prompt: str, *, images=(), model=None, system=None, max_tokens=1500, cache_extra="", feature="", ver="") -> str:
    """텍스트(+이미지) 한 번 호출. 같은 입력이면 캐시를 돌려준다. feature·ver: 어느 기능의 어느 프롬프트 버전인지 (사용량 기록용, 결과에는 영향 없음)."""
    model = model or (config.VISION_MODEL if images else config.TEXT_MODEL)
    img_hash = "".join(hashlib.sha256(i).hexdigest()[:16] for i in images)
    key = json.dumps([model, system, prompt, img_hash, cache_extra], ensure_ascii=False)
    cp = _cache_path(key)
    if cp.exists():
        try:
            text = json.loads(cp.read_text(encoding="utf-8"))["text"]
            with _lock:
                usage_totals["cache_hits"] += 1
            return text
        except Exception:
            pass                                   # 쓰던 도중 끊긴 캐시 파일이면 무시하고 새로 부른다
    if not available():
        raise RuntimeError("API 키가 없습니다 (.env의 GATEWAY_API_KEY)")
    _check_daily_limit()

    content = [image_part(i) for i in images] + [{"type": "text", "text": prompt}]
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]

    last_err = None
    t0 = time.time()
    for attempt, m in enumerate([model, model, config.FALLBACK_MODEL]):
        try:
            extra = {"reasoning_effort": "none"} if m.startswith("gpt-6") else {}
            with obs.generation(feature, m, prompt, ver, len(images)) as g:        # Langfuse 기록 (키가 없으면 아무것도 안 한다)
                r = _get_client().chat.completions.create(
                    model=m, messages=messages, max_tokens=max_tokens, extra_body=extra)
                text = (r.choices[0].message.content or "").strip()
                u = getattr(r, "usage", None)           # 사용량 정보를 안 주는 응답도 있다. 그 때문에 이미 받은 답을 버리고 다시 부르면 크레딧이 두 번 나간다
                tin, tout = (getattr(u, "prompt_tokens", 0) or 0), (getattr(u, "completion_tokens", 0) or 0)
                g.update(output=text, usage_details={"input": tin, "output": tout})
            with _lock:
                usage_totals["calls"] += 1
                usage_totals["input_tokens"] += tin
                usage_totals["output_tokens"] += tout
                with open(config.CACHE_DIR / "usage.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"t": time.time(), "model": m, "in": tin, "out": tout, "feature": feature, "ver": ver,
                                        "sec": round(time.time() - t0, 2), "images": len(images)}) + "\n")
            if text:
                tmp = cp.with_suffix(f".{threading.get_ident()}.tmp")       # 두 곳에서 동시에 써도 반쪽 파일이 남지 않게
                tmp.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
                tmp.replace(cp)
            return text
        except Exception as e:  # 429나 일시 오류는 잠깐 쉬고 다시, 그래도 안 되면 다른 모델
            last_err = e
            if attempt < 2:                        # 마지막 시도 뒤에는 기다릴 필요 없다
                time.sleep(2 + attempt * 3)
    raise RuntimeError(f"AI 호출 실패: {str(last_err)[:200]}")


def chat_json(prompt: str, **kw):
    """JSON으로 답하게 하고 파싱한다. 코드 펜스가 붙어 와도 처리."""
    text = chat(prompt, **kw)
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    s, e = min([i for i in (t.find("["), t.find("{")) if i >= 0], default=0), max(t.rfind("]"), t.rfind("}"))
    return json.loads(t[s:e + 1])
