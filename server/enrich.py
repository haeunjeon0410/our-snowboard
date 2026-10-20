"""AI 작업: 띄어쓰기 복원, 그림 설명, 쉬운 한국어, 영어 용어. 모든 호출은 캐시되고, 체크한 항목에서만 부른다."""
import io
import json
import re

from PIL import Image

from . import llm, obs

_WS = re.compile(r"\s+")

# 프롬프트를 고칠 때마다 올린다 (사용량 기록과 eval/experiments.py의 비교에 쓰인다)
SPACING_VER, FIG_VER, WORDS_VER = "v1", "v2-verify", "v2-merged"


def _strip_ws(s: str) -> str:
    return _WS.sub("", s)


# ───────────── 띄어쓰기 복원 (글자는 하나도 바꾸지 않았는지 검증) ─────────────
SPACING_PROMPT = """다음은 한국어 대학 강의 자료의 문장들인데 띄어쓰기가 빠져 있다.
각 문장의 띄어쓰기만 올바르게 바로잡아라.
- 글자·숫자·기호를 추가하거나 지우거나 바꾸지 마라. 오탈자도 그대로 둔다.
- 영어 단어와 괄호 안 표기는 그대로 둔다.
- 영문 대문자나 숫자가 붙어 있는 제목·라벨도 단어 단위로 띄운다. (예: PARTI → PART I, PAGE02 → PAGE 02)
- 입력과 같은 개수의 JSON 문자열 배열 하나만 출력한다. 설명은 쓰지 않는다.

입력:
{payload}"""


def restore_spacing(texts: list[str]) -> list[str | None]:
    """결과는 입력과 같은 길이. AI가 실패한 묶음의 항목은 None (나중에 다시 시도할 수 있게 구분한다)."""
    out: list[str | None] = list(texts)
    for start in range(0, len(texts), 12):
        chunk = texts[start:start + 12]
        try:
            res = llm.chat_json(SPACING_PROMPT.format(payload=json.dumps(chunk, ensure_ascii=False)), max_tokens=2500, feature="spacing", ver=SPACING_VER)
            if not isinstance(res, list) or len(res) != len(chunk):
                raise ValueError("개수가 맞지 않음")
        except Exception:
            out[start:start + len(chunk)] = [None] * len(chunk)
            continue
        for i, (a, b) in enumerate(zip(chunk, res)):
            if isinstance(b, str) and _strip_ws(a) == _strip_ws(b):
                out[start + i] = b.strip()
    return out


# ───────────── 그림 설명 (짧게: 설명 한 덩어리 + 그림 속 글자 + 색 의미) ─────────────
FIG_PROMPT = """시각장애 대학생이 강의 자료를 이해하도록 첨부 이미지({kind})를 한국어로 설명한다.
{page_note}맥락: {context}

JSON 객체 하나만 출력한다:
{{"desc": "무엇을 그린 그림이고 핵심이 무엇인지, 구성 요소의 관계를 왼쪽→오른쪽·위→아래 순서로 2~4문장",
 "labels": ["그림 안에 보이는 글자(이름표·수치)를 읽는 순서대로. 없으면 빈 배열"],
 "colors": "색이 의미를 구분하는 데 쓰였다면 '색=의미'를 짝지어, 아니면 빈 문자열"}}
규칙: 보이지 않는 것은 추측하지 말고, 글자가 흐리면 '읽기 어려움'이라고 쓴다. 전문 용어는 번역하지 않고 그대로 쓴다."""


def _shrink(img_bytes: bytes, fullpage: bool) -> bytes:
    """AI에 보내기 전에 그림을 줄인다. 큰 PNG는 올리는 데만 오래 걸리고 읽는 데 도움이 되지 않는다 (글자가 많은 쪽 전체는 조금 더 크게)."""
    try:
        im = Image.open(io.BytesIO(img_bytes))
        limit = 1800 if fullpage else 1280
        if max(im.size) <= limit and len(img_bytes) < 150_000:
            return img_bytes
        im = im.convert("RGB")
        im.thumbnail((limit, limit))
        jpg = io.BytesIO()
        im.save(jpg, "JPEG", quality=88)
        if len(jpg.getvalue()) < len(img_bytes) or max(Image.open(io.BytesIO(img_bytes)).size) > limit:
            png = io.BytesIO()                                  # 단색에 가까운 그림은 PNG가 더 작다. 어느 쪽이든 줄인 크기로 보낸다 (큰 그림은 크기가 토큰을 좌우한다)
            im.save(png, "PNG", optimize=True)
            return jpg.getvalue() if len(jpg.getvalue()) <= len(png.getvalue()) else png.getvalue()
        return img_bytes
    except Exception:
        return img_bytes


def describe_figure(png_bytes: bytes, fig_kind: str, context: str, fullpage: bool, known: list[str] | None = None) -> dict:
    kind = {"image": "그림", "diagram": "도식"}.get(fig_kind, "그림")
    note = ("이 이미지는 쪽 전체이다(스캔본일 수 있다). 본문 글자가 있으면 labels에 문단 단위로, 읽는 순서대로 빠짐없이 옮겨 적어라. 줄 끝에서 끊지 말고 문장을 이어서 한 문단으로 적는다.\n" if fullpage else "")
    if known:
        note += "이 그림 안에는 원본 PDF에서 확인된 글자가 있다: " + json.dumps(known[:40], ensure_ascii=False) + ". 그림에서 읽을 수 있는 것은 labels에 빠짐없이 넣는다.\n"
    try:
        res = llm.chat_json(FIG_PROMPT.format(kind=kind, page_note=note, context=context[:400] or "없음"),
                            images=[_shrink(png_bytes, fullpage)], max_tokens=1800 if fullpage else 700, feature="figure", ver=FIG_VER)
        if isinstance(res, list):
            res = res[0] if res else {}
        return {"desc": str(res.get("desc", "")), "texts": [str(t) for t in (res.get("labels") or [])][:60],
                "color_note": str(res.get("colors", ""))}
    except Exception as e:
        return {"error": str(e)[:160]}


# ───────────── 쉬운 한국어 / 영어 병기 ─────────────
EASYWORD_PROMPT = """다음은 대학 강의 자료의 문장들이다. 한국어가 서툰 교환학생(외국인 학생)이 막히는 어려운 단어를 골라, 단어 바로 뒤에 괄호로 붙일 쉬운 우리말 풀이를 적어라.
- 한자어·문어체·학술적인 단어만 골라라. 일상에서 흔한 쉬운 단어(예: 기존, 비용, 방식)은 제외한다. (예: 용이하다 → 쉽다, 상이하다 → 다르다, 점진적 → 조금씩)
- easy: 5글자 안팎의 짧은 쉬운 우리말 하나. 뜻이 바뀌면 안 된다.
- 단어(ko)은 문장에 나온 그대로의 표기여야 한다. 전문 용어(예: 신경관)는 제외한다.
- 많아야 12개. JSON 배열 하나만 출력: [{{"ko": "용이하다", "easy": "쉽다"}}]

입력:
{payload}"""

TERMS_PROMPT = """다음 한국어 강의 문장들에서 영어를 함께 적어 주면 좋은 전문 용어를 골라라.
- 확실한 학술 용어만. 이미 괄호로 영어가 붙은 것, 일반 단어는 제외.
- 문장에 나온 그대로의 한국어 표기(ko)와 영어(en)를 짝지어 최대 15개.
- JSON 배열 하나만 출력: [{{"ko": "신경관", "en": "neural tube"}}]

입력:
{payload}"""


def easy_words(texts: list[str]) -> list[dict] | None:
    """어려운 단어와 쉬운 말 목록. AI가 실패하면 None (빈 목록 []은 '붙일 단어가 없음'이라는 정상 결과)."""
    try:
        res = llm.chat_json(EASYWORD_PROMPT.format(payload=json.dumps(texts, ensure_ascii=False)), max_tokens=1500, feature="easy", ver=WORDS_VER)
    except Exception:
        return None
    joined = " ".join(texts)
    out, seen = [], set()
    for r in res if isinstance(res, list) else []:
        if not (isinstance(r, dict) and r.get("ko") and r.get("easy")):
            continue
        ko, easy = str(r["ko"]).strip(), str(r["easy"]).strip()
        if ko in joined and ko not in seen and 0 < len(easy) <= 14 and easy != ko:
            seen.add(ko)
            out.append({"ko": ko, "easy": easy})
    return out[:12]


def english_terms(texts: list[str]) -> list[dict] | None:
    """영어 병기 목록. AI가 실패하면 None (빈 목록 []은 '찾은 게 없음'이라는 정상 결과)."""
    try:
        res = llm.chat_json(TERMS_PROMPT.format(payload=json.dumps(texts, ensure_ascii=False)), max_tokens=1500, feature="terms", ver=WORDS_VER)
    except Exception:
        return None
    joined = " ".join(texts)
    out = []
    for r in res if isinstance(res, list) else []:
        if isinstance(r, dict) and r.get("ko") and r.get("en") and r["ko"] in joined:
            out.append({"ko": str(r["ko"]), "en": str(r["en"])})
    return out[:15]


BOTH_PROMPT = """다음은 대학 강의 자료의 문장들이다. 아래 두 가지를 한 번에 골라라.
1) easy: 한국어가 서툰 교환학생이 막히는 어려운 단어(한자어·문어체·학술적인 단어)와 그 바로 뒤에 괄호로 붙일 5글자 안팎의 쉬운 우리말 하나. 일상에서 흔한 단어(예: 기존, 비용, 방식)와 전문 용어는 제외한다. 많아야 12개.
2) terms: 영어를 함께 적어 주면 좋은 확실한 학술 전문 용어와 영어. 이미 괄호로 영어가 붙은 것, 일반 단어는 제외한다. 많아야 15개.
- ko는 문장에 나온 그대로의 표기여야 한다. 뜻이 바뀌면 안 된다.
- JSON 객체 하나만 출력: {{"easy": [{{"ko": "용이하다", "easy": "쉽다"}}], "terms": [{{"ko": "신경관", "en": "neural tube"}}]}}

입력:
{payload}"""


def _clean_easy(res, joined: str) -> list[dict]:
    out, seen = [], set()
    for r in res if isinstance(res, list) else []:
        if not (isinstance(r, dict) and r.get("ko") and r.get("easy")):
            continue
        ko, easy = str(r["ko"]).strip(), str(r["easy"]).strip()
        if ko in joined and ko not in seen and 0 < len(easy) <= 14 and easy != ko:
            seen.add(ko)
            out.append({"ko": ko, "easy": easy})
    return out[:12]


def _clean_terms(res, joined: str) -> list[dict]:
    out = []
    for r in res if isinstance(res, list) else []:
        if isinstance(r, dict) and r.get("ko") and r.get("en") and r["ko"] in joined:
            out.append({"ko": str(r["ko"]), "en": str(r["en"])})
    return out[:15]


def words_and_terms(texts: list[str]) -> tuple[list[dict] | None, list[dict] | None]:
    """(단어 뜻, 영어 용어). AI가 실패하면 둘 다 None (나중에 다시 시도할 수 있게)."""
    try:
        res = llm.chat_json(BOTH_PROMPT.format(payload=json.dumps(texts, ensure_ascii=False)), max_tokens=2200, feature="easy+terms", ver=WORDS_VER)
    except Exception:
        return None, None
    if not isinstance(res, dict):
        return None, None
    joined = " ".join(texts)
    return _clean_easy(res.get("easy"), joined), _clean_terms(res.get("terms"), joined)


# ───────────── 그림 설명 자기검증: PDF 안에 글자로 들어 있던 라벨이 정답지가 된다 ─────────────
VERIFY_MIN_LABELS = 3        # 정답지로 삼을 라벨이 이보다 적으면 검증하지 않는다
VERIFY_PASS = 0.8            # AI 설명이 라벨을 이만큼 담지 못하면 한 번 더 시도하고, 그래도 모자라면 '확인 필요'로 표시한다


def _truth_labels(inner_text) -> list[str]:
    return list(dict.fromkeys(_strip_ws(t) for t in (inner_text or []) if len(_strip_ws(t)) >= 2))


def label_recall(res: dict, inner_text) -> tuple[float | None, int]:
    """AI 설명이 PDF 안의 실제 그림 속 글자를 얼마나 담았는지. 정답지가 모자라면 (None, 개수)."""
    truth = _truth_labels(inner_text)
    if len(truth) < VERIFY_MIN_LABELS:
        return None, len(truth)
    blob = _strip_ws(" ".join((res.get("texts") or []) + [res.get("desc", "")]))
    return sum(t in blob for t in truth) / len(truth), len(truth)


def describe_checked(png_bytes: bytes, fig_kind: str, context: str, fullpage: bool, inner_text=None) -> dict:
    """그림 설명을 만들고, 그림 속 글자를 PDF의 실제 글자와 대조한다. 모자라면 확인된 글자를 알려 주고 한 번 더 묻는다.
    결과의 verify: {n: 정답 라벨 수, recall: 담은 비율, retried: 다시 물었는지, flag: 끝내 모자라 사람이 확인해야 하는지}"""
    with obs.span("figure-check", ver=FIG_VER, kind=fig_kind):             # 이 그림의 AI 호출들을 한 묶음으로 기록하고, 검증 점수를 단다
        res = describe_figure(png_bytes, fig_kind, context, fullpage)
        if "error" in res:
            return res
        rec, n = label_recall(res, inner_text)
        if rec is None:
            return res
        first, retried = rec, False
        if rec < VERIFY_PASS:
            retried = True
            again = describe_figure(png_bytes, fig_kind, context, fullpage, known=_truth_labels(inner_text))
            if "error" not in again:
                rec2, _ = label_recall(again, inner_text)
                if rec2 is not None and rec2 >= rec:
                    res, rec = again, rec2
        res["verify"] = {"n": n, "recall": round(rec, 2), "first": round(first, 2), "retried": retried, "flag": rec < VERIFY_PASS}
        obs.score("label_recall_first", first, f"라벨 {n}개")
        obs.score("label_recall_final", rec, "재시도함" if retried else "재시도 없음")
        return res


# ───────────── 띄어쓰기 대체 수단: Kiwi (AI를 못 쓸 때) ─────────────
_kiwi = {"tried": False, "obj": None}


def kiwi_space(text: str) -> str | None:
    """AI 없이 한국어 띄어쓰기를 바로잡는다 (kiwipiepy). 글자가 하나라도 달라지거나 Kiwi가 없으면 None.
    AI(F1 97.0%)보다 낮지만(F1 93.1%, 같은 방식으로 잰 값) 크레딧 없이 바로 되므로 AI를 쓸 수 없을 때의 대체 수단이다."""
    if not _kiwi["tried"]:
        _kiwi["tried"] = True
        try:
            from kiwipiepy import Kiwi
            _kiwi["obj"] = Kiwi()
        except Exception:
            _kiwi["obj"] = None
    k = _kiwi["obj"]
    if k is None:
        return None
    try:
        out = k.space(_strip_ws(text)).strip()
    except Exception:
        return None
    return out if out and _strip_ws(out) == _strip_ws(text) else None
