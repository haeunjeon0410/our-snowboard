"""AI 호출 기록(Langfuse). .env에 LANGFUSE_PUBLIC_KEY·LANGFUSE_SECRET_KEY가 있을 때만 켜지고, 없으면 아무 일도 하지 않는다.
강의 내용은 기본으로 가려서 보내지 않는다 (기능 이름·프롬프트 버전·토큰·걸린 시간·검증 점수만 간다). 내용까지 보려면 LANGFUSE_SEND_CONTENT=1.
기록이 실패해도 변환에는 영향이 없다 (모든 호출을 감싸서 오류를 삼킨다)."""
import os
import threading
from contextlib import contextmanager

_lock = threading.Lock()
_state = {"tried": False, "lf": None}
_SHOW = 60                      # 이 길이를 넘는 글(강의 내용, 이미지 데이터)은 가린다


def _mask(*, data=None, **_):
    if os.environ.get("LANGFUSE_SEND_CONTENT") == "1":
        return data
    if isinstance(data, str):
        return data if len(data) <= _SHOW else f"[강의 내용 숨김 · {len(data)}자]"
    if isinstance(data, dict):
        return {k: _mask(data=v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_mask(data=v) for v in data]
    return data


def client():
    """켜져 있으면 Langfuse 클라이언트, 아니면 None. 처음 부를 때 한 번만 만든다."""
    if _state["tried"]:
        return _state["lf"]
    with _lock:
        if _state["tried"]:
            return _state["lf"]
        _state["tried"] = True
        if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
            try:
                from langfuse import Langfuse
                _state["lf"] = Langfuse(mask=_mask, environment=os.environ.get("LANGFUSE_ENV", "contest"))
            except Exception:
                _state["lf"] = None
    return _state["lf"]


def enabled() -> bool:
    return client() is not None


class _Noop:
    def update(self, **_):
        pass


@contextmanager
def generation(name: str, model: str, prompt: str = "", ver: str = "", images: int = 0):
    """AI 호출 한 번을 기록한다. 쓰는 쪽은 `g.update(output=..., usage_details={"input": n, "output": m})`로 결과를 채운다."""
    lf = client()
    if lf is None:
        yield _Noop()
        return
    try:
        cm = lf.start_as_current_observation(as_type="generation", name=name or "llm", model=model, input=prompt,
                                             metadata={"ver": ver, "images": images})
        g = cm.__enter__()
    except Exception:
        yield _Noop()
        return
    try:
        yield g
    finally:
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass


@contextmanager
def span(name: str, **meta):
    """여러 호출을 한 묶음으로 기록한다 (그 안의 generation이 하위로 붙고, score()는 이 묶음에 달린다)."""
    lf = client()
    if lf is None:
        yield _Noop()
        return
    try:
        cm = lf.start_as_current_observation(as_type="span", name=name, metadata=meta)
        s = cm.__enter__()
    except Exception:
        yield _Noop()
        return
    try:
        yield s
    finally:
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass


def score(name: str, value: float, comment: str = ""):
    """지금 기록 중인 묶음에 점수를 단다 (예: 그림 설명의 라벨 일치율)."""
    lf = client()
    if lf is None:
        return
    try:
        lf.score_current_trace(name=name, value=float(value), comment=comment or None)
    except Exception:
        pass


def flush():
    lf = client()
    if lf is not None:
        try:
            lf.flush()
        except Exception:
            pass
