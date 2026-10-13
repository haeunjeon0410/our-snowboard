"""AI 작업: 띄어쓰기 복원, 그림 설명, 쉬운 한국어, 영어 용어. 모든 호출은 캐시되고, 체크한 항목에서만 부른다."""
import json
import re

from . import llm

_WS = re.compile(r"\s+")


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
            res = llm.chat_json(SPACING_PROMPT.format(payload=json.dumps(chunk, ensure_ascii=False)), max_tokens=2500)
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


def describe_figure(png_bytes: bytes, fig_kind: str, context: str, fullpage: bool) -> dict:
    kind = {"image": "그림", "diagram": "도식"}.get(fig_kind, "그림")
    note = ("이 이미지는 쪽 전체이다(스캔본일 수 있다). 본문 글자가 있으면 labels에 문단 단위로, 읽는 순서대로 빠짐없이 옮겨 적어라. 줄 끝에서 끊지 말고 문장을 이어서 한 문단으로 적는다.\n" if fullpage else "")
    try:
        res = llm.chat_json(FIG_PROMPT.format(kind=kind, page_note=note, context=context[:400] or "없음"),
                            images=[png_bytes], max_tokens=1800 if fullpage else 700)
        if isinstance(res, list):
            res = res[0] if res else {}
        return {"desc": str(res.get("desc", "")), "texts": [str(t) for t in (res.get("labels") or [])][:60],
                "color_note": str(res.get("colors", ""))}
    except Exception as e:
        return {"error": str(e)[:160]}


# ───────────── 쉬운 한국어 / 영어 병기 ─────────────
EASYWORD_PROMPT = """다음은 대학 강의 자료의 문장들이다. 한국어가 서툰 교환학생(외국인 학생)이 막히는 어려운 단어를 골라, 단어 바로 뒤에 괄호로 붙일 쉬운 우리말 풀이와 영어 뜻을 적어라.
- 한자어·문어체·학술적인 단어만 골라라. 일상에서 흔한 쉬운 단어(예: 기존, 비용, 방식)은 제외한다. (예: 용이하다 → 쉽다 / easy, 상이하다 → 다르다 / different, 점진적 → 조금씩 / gradual)
- easy: 5글자 안팎의 짧은 쉬운 우리말 하나. en: 짧은 영어 단어나 구(소문자, 3단어 이내). 뜻이 바뀌면 안 된다.
- 단어(ko)은 문장에 나온 그대로의 표기여야 한다. 전문 용어(예: 신경관)는 제외한다.
- 많아야 12개. JSON 배열 하나만 출력: [{{"ko": "용이하다", "easy": "쉽다", "en": "easy"}}]

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
        res = llm.chat_json(EASYWORD_PROMPT.format(payload=json.dumps(texts, ensure_ascii=False)), max_tokens=1500)
    except Exception:
        return None
    joined = " ".join(texts)
    out, seen = [], set()
    for r in res if isinstance(res, list) else []:
        if not (isinstance(r, dict) and r.get("ko") and r.get("easy")):
            continue
        ko, easy, en = str(r["ko"]).strip(), str(r["easy"]).strip(), str(r.get("en") or "").strip()
        if ko in joined and ko not in seen and 0 < len(easy) <= 14 and easy != ko:
            seen.add(ko)
            out.append({"ko": ko, "easy": easy, "en": en[:30]})
    return out[:12]


def english_terms(texts: list[str]) -> list[dict] | None:
    """영어 병기 목록. AI가 실패하면 None (빈 목록 []은 '찾은 게 없음'이라는 정상 결과)."""
    try:
        res = llm.chat_json(TERMS_PROMPT.format(payload=json.dumps(texts, ensure_ascii=False)), max_tokens=1500)
    except Exception:
        return None
    joined = " ".join(texts)
    out = []
    for r in res if isinstance(res, list) else []:
        if isinstance(r, dict) and r.get("ko") and r.get("en") and r["ko"] in joined:
            out.append({"ko": str(r["ko"]), "en": str(r["en"])})
    return out[:15]
