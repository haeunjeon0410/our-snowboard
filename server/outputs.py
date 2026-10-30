"""점자 변환 결과를 문단 단위로 만든다 (파일 만들기는 render.py)."""
import re
import unicodedata

from . import braille_ko as B

# 한글 점자 규정에 없는 수학·화학 기호는 점자로 옮기지 못해 글자가 통째로 빠졌다. 정식 수학 점자(수식 표기)를 구현한 것은 아니고,
# 빠지는 대신 소리 내어 읽는 말로 풀어서 점역한다 (예: 'A → B' → 'A 화살표 B'). 점역본을 읽는 사람이 뜻을 놓치지 않게 하는 임시 방편이다.
SYMBOL_WORDS = {"=": "같음", "≠": "같지 않음", "≈": "거의 같음", "→": "화살표", "←": "왼쪽 화살표", "↔": "양방향 화살표", "↑": "위 화살표", "↓": "아래 화살표",
                "⇒": "화살표", "+": "더하기", "×": "곱하기", "÷": "나누기", "±": "플러스마이너스", "≥": "크거나 같음", "≤": "작거나 같음",
                "%": "퍼센트", "&": "앤드", "⁺": "플러스", "⁻": "마이너스", "°": "도", "μ": "마이크로", "α": "알파", "β": "베타", "γ": "감마", "Δ": "델타",
                "−": "빼기", "≡": "합동", "≢": "합동 아님", "≅": "합동", "∤": "나누어떨어지지 않음", "⊕": "엑스오어", "⋯": "점점점", "*": "별표", "#": "샵", "_": "밑줄",
                "^": "캐럿", "|": "세로선", "{": "여는 중괄호", "}": "닫는 중괄호", "<": "보다 작음", ">": "보다 큼", "²": "제곱", "³": "세제곱", "✕": "곱하기",
                "⇄": "양방향 화살표", "⇢": "화살표", "↺": "회전 화살표", "↙": "화살표", "↘": "화살표", "①": "동그라미 1", "②": "동그라미 2", "③": "동그라미 3", "④": "동그라미 4",
                "⑤": "동그라미 5", "「": '"', "」": '"', "ε": "엡실론", "ζ": "제타", "η": "에타", "θ": "세타", "ι": "요타", "κ": "카파", "λ": "람다", "ν": "뉴", "ξ": "크시",
                "π": "파이", "ρ": "로", "σ": "시그마", "τ": "타우", "υ": "입실론", "φ": "파이", "ϕ": "파이", "𝜙": "파이", "χ": "카이", "ψ": "프사이", "ω": "오메가",
                "Σ": "시그마", "Ω": "오메가", "Π": "파이", "Φ": "파이", "Θ": "세타", "Λ": "람다"}
_DROP = re.compile("[─-╿■-◿•·]")      # 선·도형·글머리표처럼 뜻이 없는 장식은 조용히 버려도 된다 (그 밖의 글자는 버리지 않는다)
_HANJA_GLOSS = re.compile(r"(?<=[가-힣])\s*[(（]\s*[㐀-鿿]+\s*[)）]")
_probe: dict[str, bool] = {}


def _braille_handles(c: str) -> bool:
    """이 글자를 점자 변환기가 그대로 옮길 수 있는가 (옮기지 못하면 글자가 통째로 빠진다)."""
    if c not in _probe:
        st = {}
        B.encode(c, st)
        _probe[c] = not st.get("unmapped")
    return _probe[c]


def _plain(c: str) -> str:
    """수학 서체·위아래 첨자·악센트 글자를 바탕 글자로 (𝟷 → 1, ₃ → 3, è → e). 바탕 글자가 아니면 빈 글."""
    base = unicodedata.normalize("NFKD", c)
    base = "".join(x for x in base if not unicodedata.combining(x))
    return base if base and all(x.isascii() and x.isalnum() for x in base) else ""


def spell_symbols(text: str) -> str:
    """점역 전에 기호를 말로 푼다. 풀 수 없는 글자는 조용히 빼지 않고 '기호'(한자는 '한자')로 남겨, 읽는 사람이 빠진 것이 있음을 알게 한다."""
    if not text:
        return text
    text = _HANJA_GLOSS.sub("", text)                     # 한글 바로 뒤의 '(한자)' 병기는 앞 한글과 같은 말이라 점자본에서는 뺀다 (예: 매매(賣買) → 매매)
    out, changed = [], False
    for c in text:
        if c in SYMBOL_WORDS:
            out.append(f" {SYMBOL_WORDS[c]} ")
        elif c.isascii() or c.isspace() or _braille_handles(c):
            out.append(c)
            continue
        elif _DROP.match(c):
            out.append(" ")
        elif _plain(c):
            out.append(_plain(c))
        elif unicodedata.category(c) == "Lo" and "CJK" in unicodedata.name(c, ""):
            out.append(" 한자 ")
        else:
            out.append(" 기호 ")
        changed = True
    return re.sub(r"[ \t]{2,}", " ", re.sub(r"(?: ?한자 ?)+", " 한자 ", "".join(out))).strip() if changed else text


def _items(page, use_easy: dict | None = None, figures: bool = True):
    """쪽의 블록을 (종류, 글, ai여부, 부가) 목록으로 풀어낸다. use_easy: {블록id: 쉬운 한국어}, figures: 그림 설명을 넣을지"""
    easy = use_easy or {}
    for b in page["blocks"]:
        t = b["type"]
        if t in ("paragraph", "heading"):
            yield (t, spell_symbols(easy.get(b["id"], b["text"])), bool(b.get("ai")) or b["id"] in easy, {"level": b.get("level", 2), "id": b["id"]})
        elif t == "list":
            for i, it in enumerate(b["items"]):
                key = f"{b['id']}:{i}"
                yield ("listitem", spell_symbols(easy.get(key, it["text"])), bool(it.get("ai")) or key in easy, {"id": key})
        elif t == "code":
            yield ("code", spell_symbols(b["text"]), False, {"id": b["id"]})
        elif t == "table":
            yield ("table", "", False, {"rows": b["rows"], "id": b["id"]})
        elif t == "figure":
            d = (b.get("ai_desc") or {}) if figures else {}
            desc = d.get("desc") or " ".join(x for x in (d.get("summary"), d.get("detail")) if x)
            text = desc
            if desc and d.get("color_note"):
                text += " 색 설명: " + d["color_note"]
            # 그림 속 글자는 원본 PDF에 글자로 들어 있던 것이라 AI 설명이 없어도 넣는다 (넣지 않으면 도식 안의 내용이 점자에서 통째로 사라진다)
            texts = [t for t in dict.fromkeys(b.get("inner_text", []) + ((d.get("texts") or []) if desc else [])) if t]
            if texts:                                  # 웹 문서의 "그림 속 글자"와 같은 내용
                text += (" " if text else "") + "그림 속 글자: " + ", ".join(texts)
            yield ("figure", spell_symbols(text), bool(desc), {"id": b["id"], "img": b["img"], "texts": texts, "desc": bool(desc)})


def braille_pages(doc: dict, easy_by_page: dict | None = None, figures: bool = True, verify: bool = True):
    """쪽별 점자. 반환: ([{n, segs:[{type,text,braille,ai}]}], 점역하지 못한 글자 집계)
    verify=False 이면 측정용 역점역 비교를 건너뛴다 (파일만 만들 때)."""
    stats = {"unmapped": {}, "chars": 0}

    def seg(kind, text, ai, br):
        if not verify:
            return {"type": kind, "text": text, "braille": br, "ai": ai}
        back = B.decode(br)
        n_text, n_back = B.normalize_for_compare(text), B.normalize_for_compare(back)
        return {"type": kind, "text": text, "braille": br, "ai": ai, "back": back,
                "match": n_text == n_back, "cells_same": n_text == n_back or B.encode(back) == br}

    pages = []
    for pg in doc["pages"]:
        segs = []
        easy = (easy_by_page or {}).get(str(pg["n"]), {})
        for kind, text, ai, extra in _items(pg, easy, figures):
            if kind == "table":
                rows = [(B.SP * 2).join(B.encode(spell_symbols(c), stats) for c in r) for r in extra["rows"]]
                flat = " ".join(spell_symbols(c) for r in extra["rows"] for c in r)
                sg = seg("table", "\n".join(" | ".join(spell_symbols(c) for c in r) for r in extra["rows"]), False, "\n".join(rows))
                if verify:
                    back = B.decode(B.encode(flat))
                    ok = B.normalize_for_compare(flat) == B.normalize_for_compare(back)
                    sg.update(back=back, match=ok, cells_same=ok or B.encode(back) == B.encode(flat))
                segs.append(sg)
                continue
            if kind == "figure":
                label = (("그림 설명. " if extra.get("desc") else "그림. ") + text) if text else "그림"
                segs.append(seg("figure", label, bool(extra.get("desc")), B.encode(label, stats)))
                continue
            prefix = "· " if kind == "listitem" else ""
            segs.append(seg(kind, prefix + text, ai, B.encode(prefix + text, stats)))
        pages.append({"n": pg["n"], "segs": segs})
    return pages, stats


def to_braille_text(doc: dict, width=32, ascii_brf=False, easy_by_page=None, figures: bool = True) -> str:
    pages, _ = braille_pages(doc, easy_by_page, figures, verify=False)
    out = []
    for pg in pages:
        out.append(B.encode(f"{pg['n']}쪽"))
        out.append("")
        for s in pg["segs"]:
            if s["type"] == "heading":
                out.append("")
            out.extend(B.wrap(s["braille"], width))
        out.append("")
    text = "\n".join(out)
    return B.to_brf(text) if ascii_brf else text
