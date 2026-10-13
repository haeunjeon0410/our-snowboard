"""학교 AI API 호출. 응답은 디스크에 캐시하고, 쓴 토큰을 기록한다."""
import base64
import hashlib
import json
import threading
import time

from openai import OpenAI

from . import config

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
                for line in open(config.CACHE_DIR / "usage.jsonl", encoding="utf-8"):
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


def image_part(png_bytes: bytes) -> dict:
    b64 = base64.b64encode(png_bytes).decode()
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}


def chat(prompt: str, *, images=(), model=None, system=None, max_tokens=1500, cache_extra="") -> str:
    """텍스트(+이미지) 한 번 호출. 같은 입력이면 캐시를 돌려준다."""
    model = model or (config.VISION_MODEL if images else config.TEXT_MODEL)
    img_hash = "".join(hashlib.sha256(i).hexdigest()[:16] for i in images)
    key = json.dumps([model, system, prompt, img_hash, cache_extra], ensure_ascii=False)
    cp = _cache_path(key)
    if cp.exists():
        with _lock:
            usage_totals["cache_hits"] += 1
        return json.loads(cp.read_text(encoding="utf-8"))["text"]
    if not available():
        raise RuntimeError("API 키가 없습니다 (.env의 GATEWAY_API_KEY)")
    _check_daily_limit()

    content = [image_part(i) for i in images] + [{"type": "text", "text": prompt}]
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]

    last_err = None
    for attempt, m in enumerate([model, model, config.FALLBACK_MODEL]):
        try:
            extra = {"reasoning_effort": "none"} if m.startswith("gpt-6") else {}
            r = _get_client().chat.completions.create(
                model=m, messages=messages, max_tokens=max_tokens, extra_body=extra)
            text = (r.choices[0].message.content or "").strip()
            with _lock:
                usage_totals["calls"] += 1
                usage_totals["input_tokens"] += r.usage.prompt_tokens
                usage_totals["output_tokens"] += r.usage.completion_tokens
                with open(config.CACHE_DIR / "usage.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"t": time.time(), "model": m, "in": r.usage.prompt_tokens,
                                        "out": r.usage.completion_tokens}) + "\n")
            if text:
                cp.write_text(json.dumps({"text": text}, ensure_ascii=False), encoding="utf-8")
            return text
        except Exception as e:  # 429나 일시 오류는 잠깐 쉬고 다시, 그래도 안 되면 다른 모델
            last_err = e
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
