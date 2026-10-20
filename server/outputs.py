"""점자 변환 결과를 문단 단위로 만든다 (파일 만들기는 render.py)."""
import re

from . import braille_ko as B

# 한글 점자 규정에 없는 수학·화학 기호는 점자로 옮기지 못해 글자가 통째로 빠졌다. 정식 수학 점자(수식 표기)를 구현한 것은 아니고,
# 빠지는 대신 소리 내어 읽는 말로 풀어서 점역한다 (예: 'A → B' → 'A 화살표 B'). 점역본을 읽는 사람이 뜻을 놓치지 않게 하는 임시 방편이다.
SYMBOL_WORDS = {"=": "같음", "≠": "같지 않음", "≈": "거의 같음", "→": "화살표", "←": "왼쪽 화살표", "↔": "양방향 화살표", "↑": "위 화살표", "↓": "아래 화살표",
                "⇒": "화살표", "+": "더하기", "×": "곱하기", "÷": "나누기", "±": "플러스마이너스", "≥": "크거나 같음", "≤": "작거나 같음",
                "%": "퍼센트", "&": "앤드", "⁺": "플러스", "⁻": "마이너스", "°": "도", "μ": "마이크로", "α": "알파", "β": "베타", "γ": "감마", "Δ": "델타"}
_SYM_RE = re.compile("[" + re.escape("".join(SYMBOL_WORDS)) + "]")


def spell_symbols(text: str) -> str:
    """점역 전에 기호를 말로 푼다. 기호가 없으면 글을 그대로 돌려준다."""
    if not text or not _SYM_RE.search(text):
        return text
    return re.sub(r"[ \t]{2,}", " ", _SYM_RE.sub(lambda m: f" {SYMBOL_WORDS[m.group(0)]} ", text)).strip()


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
            text = d.get("desc") or " ".join(x for x in (d.get("summary"), d.get("detail")) if x)
            if d.get("color_note"):
                text += " 색 설명: " + d["color_note"]
            texts = [t for t in dict.fromkeys(b.get("inner_text", []) + (d.get("texts") or [])) if t] if figures and text else []
            if texts:                                  # 웹 문서의 "그림 속 글자"와 같은 내용
                text += " 그림 속 글자: " + ", ".join(texts)
            yield ("figure", spell_symbols(text), True, {"id": b["id"], "img": b["img"], "texts": texts})


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
                label = "그림 설명. " + text if text else "그림"
                segs.append(seg("figure", label, True, B.encode(label, stats)))
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
