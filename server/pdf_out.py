"""원본 PDF에 접근성을 '더해서' 내보낸다 (.pdf). 쪽 수·쪽 방향·크기·글자와 그림의 위치는 원본 그대로다.
강의에서 "8슬라이드 보세요"라고 하면 결과물의 8쪽이 그 쪽이고, 그 위에 필기할 수도 있다.

더하는 것 (모두 눈에 보이는 모습은 바꾸지 않는다):
- 그림 자리에 보이지 않는 글자(그림 설명·그림 속 글자)  → 스크린리더·읽어 주기가 읽는다
- 스캔된 쪽에 보이지 않는 글자층(AI가 읽은 글자)
- 색 구분: 색으로만 구분된 그림을 같은 자리에서 보정본(+무늬)으로 바꾼다
- 고대비: 쪽 위에 색 반전 막을 씌운다(글자는 그대로 글자). 사진처럼 반전하면 필름처럼 보이는 그림은 제외
- 제목 책갈피, 문서 제목·언어, 파일 끝의 접근성 부록(그림 설명 · 쉬운 한국어 · 용어 사전. 원본 쪽 번호는 밀리지 않는다)

원본의 글자는 그대로 둔다. 글자를 그림으로 바꾸면 확대할 때 뭉개지고 복사도 안 되기 때문이다.
띄어쓰기 복원은 웹 문서·점자에 적용된다."""
import io
import os
import re
from pathlib import Path

import pymupdf

from . import render

_FONT_CANDIDATES = [
    ("NanumGothic.ttf", "NanumGothicBold.ttf"),
    ("malgun.ttf", "malgunbd.ttf"),
    ("AppleGothic.ttf", "AppleGothic.ttf"),          # macOS
]
_FONT_DIRS = [
    os.environ.get("OSB_FONT_DIR", ""),
    os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts"),
    "/usr/share/fonts/truetype/nanum",
    "/usr/share/fonts/nanum",
    "/usr/share/fonts/truetype/noto",
    "/System/Library/Fonts/Supplemental",
    "/Library/Fonts",
]
FONT = "OSBK"


def find_fonts():
    """(글꼴 폴더, 보통 파일, 굵은 파일). 한글 글꼴이 없으면 None."""
    for d in filter(None, _FONT_DIRS):
        for reg, bold in _FONT_CANDIDATES:
            if os.path.exists(os.path.join(d, reg)):
                return d, reg, bold if os.path.exists(os.path.join(d, bold)) else reg
    return None


def available() -> bool:
    return find_fonts() is not None


# ───────────── 쪽별 글자 / 그림 설명 ─────────────
def _figures(pg):
    return [b for b in pg["blocks"] if b["type"] == "figure"]


def _page_text(pg) -> str:
    """읽는 순서대로 쪽 전체 글자 (복원된 띄어쓰기·스캔본 글자 포함)."""
    out = []
    for b in pg["blocks"]:
        t = b["type"]
        if t in ("paragraph", "heading"):
            out.append(b["text"])
        elif t == "list":
            out += ["· " + it["text"] for it in b["items"]]
        elif t == "table":
            out += [" | ".join(r) for r in b["rows"]]
        elif t == "code":
            out.append(b["text"])
    return "\n".join(x for x in out if x and x.strip())


def _fig_texts(b):
    d = b.get("ai_desc") or {}
    desc = d.get("desc") or " ".join(x for x in (d.get("summary"), d.get("detail")) if x)
    inner = [t for t in dict.fromkeys((b.get("inner_text") or []) + (d.get("texts") or [])) if t]
    return desc, inner, d.get("color_note", "")


def _hidden(page, rect, text: str, fontfile: str):
    """보이지 않는 글자(render_mode=3)를 rect 안에 넣는다. 안 들어가면 더 작은 글씨로 다시."""
    text = (text or "").strip()
    if not text:
        return
    for fs in (6, 4, 3, 2, 1.5):
        if page.insert_textbox(rect, text, fontsize=fs, fontname=FONT, fontfile=fontfile, render_mode=3) >= 0:
            return


# ───────────── 부록 (그림 설명 · 쉬운 한국어 · 용어 사전) ─────────────
def _orig_texts(pg) -> dict:
    """블록 id → 글 (쉬운 한국어 부록에서 원문을 같이 보여 주려고)"""
    out = {}
    for b in pg["blocks"]:
        if b["type"] in ("paragraph", "heading"):
            out[b["id"]] = b["text"]
        elif b["type"] == "list":
            for i, it in enumerate(b["items"]):
                out[f"{b['id']}:{i}"] = it["text"]
    return out


def _section_figures(doc) -> str:
    e = render._e
    items = []
    for pg in doc["pages"]:
        rows = []
        for k, b in enumerate(_figures(pg), 1):
            if b.get("fullpage") and pg.get("ocr_done"):
                continue
            desc, inner, note = _fig_texts(b)
            if not desc:
                continue
            row = f"<p><b>그림 {k}.</b> {e(desc)}"
            if note:
                row += f" <b>색 설명</b> {e(note)}"
            if inner:
                row += f"<br><span class=\"sub\">그림 속 글자: {e(', '.join(inner))}</span>"
            rows.append(row + "</p>")
        if rows:
            items.append(f"<h3>{pg['n']}쪽</h3>" + "".join(rows))
    if not items:
        return ""
    return ("<h2>그림 설명</h2><p class=\"sub\">원본의 각 쪽에 있는 그림을 글로 설명한 목록이에요. AI가 쓴 설명이라 틀릴 수 있어요.</p>" + "".join(items))


def _section_easy(doc) -> str:
    e = render._e
    items = []
    for pg in doc["pages"]:
        easy = pg.get("easy") or {}
        if not easy:
            continue
        orig = _orig_texts(pg)
        rows = [f"<p><span class=\"sub\">{e(orig.get(k, '')[:90])}</span><br><b>→</b> {e(v)}</p>" for k, v in easy.items() if v]
        if rows:
            items.append(f"<h3>{pg['n']}쪽</h3>" + "".join(rows))
    if not items:
        return ""
    return ("<h2>쉬운 한국어</h2><p class=\"sub\">어려운 문장을 AI가 쉬운 말로 바꾼 목록이에요. 원문과 조금 다를 수 있어요. 위의 작은 글씨가 원문이에요.</p>" + "".join(items))


def _section_terms(doc) -> str:
    e = render._e
    seen = {}
    for pg in doc["pages"]:
        for t in pg.get("terms") or []:
            seen.setdefault(t["ko"], {"en": t["en"], "pages": []})["pages"].append(pg["n"])
    if not seen:
        return ""
    rows = []
    for ko, v in sorted(seen.items(), key=lambda kv: (kv[1]["pages"][0], kv[0])):
        pages = ", ".join(f"{n}쪽" for n in dict.fromkeys(v["pages"][:5]))
        rows.append(f"<p><b>{e(ko)}</b> ({e(v['en'])}) <span class=\"sub\">· {pages}</span></p>")
    return "<h2>용어 사전</h2><p class=\"sub\">전문 용어의 영어 표기예요. 뒤의 숫자는 그 용어가 나오는 원본 쪽이에요.</p>" + "".join(rows)


def _appendix(doc, fonts, size, o) -> tuple[bytes, list] | None:
    """(PDF 바이트, 제목 목록[(단계, 글, 부록 안의 쪽)]). 넣을 내용이 없으면 None."""
    parts = []
    if o["figures"]:
        parts.append(_section_figures(doc))
    if o["easy"]:
        parts.append(_section_easy(doc))
    if o["terms"]:
        parts.append(_section_terms(doc))
    parts = [p for p in parts if p]
    if not parts:
        return None
    hc = o["contrast"]
    fg, mut, line = ("#ffe600", "#ffffff", "#ffffff") if hc else ("#1c2230", "#5a6b88", "#c9d1de")
    html = ("<h1>접근성 부록</h1><p class=\"sub\">원본의 쪽 번호는 그대로이고, 이 부록은 맨 끝에 붙어 있어요.</p>" + "".join(parts))
    css = f"""@font-face{{font-family:K;src:url({fonts[1]})}}
@font-face{{font-family:K;font-weight:bold;src:url({fonts[2]})}}
body{{font-family:K;font-size:13pt;line-height:1.7;color:{fg}}}
h1{{font-size:22pt;margin:0 0 6pt}}
h2{{font-size:19pt;margin:18pt 0 6pt}} h3{{font-size:14pt;margin:14pt 0 2pt;border-top:1px solid {line};padding-top:6pt}}
p{{margin:3pt 0}} .sub{{color:{mut};font-size:11.5pt}}"""
    story = pymupdf.Story(html=html, user_css=css, archive=pymupdf.Archive(fonts[0]))
    heads = []

    def positionfn(pos):
        if pos.heading and pos.heading <= 2 and pos.text:
            heads.append((pos.heading, re.sub(r"\s+", " ", pos.text).strip()[:60], pos.page_num))

    buf = io.BytesIO()
    w = pymupdf.DocumentWriter(buf)
    media = pymupdf.Rect(0, 0, size[0], size[1])
    where = media + (42, 42, -42, -42)
    story.write(w, lambda n, f: (media, where, None), positionfn=positionfn)
    w.close()
    return buf.getvalue(), heads


# ───────────── 고대비 (쪽 위에 색 반전 막) ─────────────
def _invert_page(out, page, holes):
    """쪽 전체를 색 반전(Difference 혼합)한다. 글자는 그대로 글자로 남아 선택·읽기가 된다.
    holes: 반전하지 않을 영역(사진처럼 반전하면 필름처럼 보이는 그림). 회전된 쪽은 영역 없이 전체를 반전한다."""
    W, H = page.rect.width, page.rect.height
    holes = holes if page.rotation == 0 else []
    tmp = pymupdf.open()
    tp = tmp.new_page(width=W, height=H)
    gs = tmp.get_new_xref()
    tmp.update_object(gs, "<</Type/ExtGState/BM/Difference>>")
    tmp.xref_set_key(tp.xref, "Resources", f"<</ExtGState<</GSosb {gs} 0 R>>>>")
    path = f"0 0 {W:.2f} {H:.2f} re " + "".join(f"{r.x0:.2f} {H - r.y1:.2f} {r.width:.2f} {r.height:.2f} re " for r in holes)
    cx = tmp.get_new_xref()
    tmp.update_object(cx, "<<>>")
    tmp.update_stream(cx, f"q /GSosb gs 1 1 1 rg {path}f* Q".encode())
    tmp.xref_set_key(tp.xref, "Contents", f"{cx} 0 R")
    page.show_pdf_page(page.rect, tmp, 0, overlay=True)
    tmp.close()


def _photo_figures(doc, job_dir: Path) -> set:
    """색이 번지는 그림(사진 등)의 id. 고대비에서 이 그림은 반전하지 않는다."""
    ids = []
    for pg in doc["pages"]:
        for b in _figures(pg):
            if b.get("fullpage") and pg.get("ocr_done"):
                continue
            if (job_dir / b["img"]).exists():
                ids.append(b)
    if not ids:
        return set()
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image
    from . import color
    with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as ex:
        flats = list(ex.map(lambda b: color.flat_fraction(Image.open(job_dir / b["img"])), ids))
    return {b["id"] for b, f in zip(ids, flats) if f < color.FLAT_MIN}


# ───────────── 본 작업 ─────────────
def to_pdf(doc: dict, job_dir: Path, o: dict, title: str = "", brf: tuple | None = None) -> bytes:
    """brf: (파일 이름, 점자 텍스트)를 주면 점자 파일을 PDF 안에 첨부한다 (PDF 뷰어의 첨부 파일 목록에서 꺼낼 수 있다)."""
    fonts = find_fonts()
    if not fonts:
        raise RuntimeError("PDF에 글자를 더할 한글 글꼴(나눔고딕 등)이 서버에 없어요")
    fontfile = os.path.join(fonts[0], fonts[1])
    out = pymupdf.open(str(job_dir / "original.pdf"))
    fixed = render._fix_all(doc, job_dir, o) if o["color"] else {}

    for pg in doc["pages"]:
        i = pg["n"] - 1
        if i >= len(out):
            break
        page = out[i]

        if pg.get("ocr_done"):
            # 2) 스캔본: 원본 그림은 그대로 두고 AI가 읽은 글자를 보이지 않게 얹는다
            _hidden(page, page.rect + (6, 6, -6, -6), _page_text(pg), fontfile)

        # 3) 그림: 색 구분은 같은 자리에서 보정본으로 바꾸고, 그림 설명은 보이지 않는 글자로 얹는다
        for b in _figures(pg):
            if b.get("fullpage") and pg.get("ocr_done"):
                continue
            if not b.get("bbox"):
                continue
            rect = pymupdf.Rect(*b["bbox"])
            if rect.is_empty:
                continue
            if o["color"] and b["id"] in fixed and fixed[b["id"]][1]:
                img = fixed[b["id"]][0].convert("RGB")
                px_w = max(300, round(rect.width * 150 / 72))        # 쪽에서 차지하는 실제 크기(150dpi)면 충분하다
                if img.width > px_w:
                    img = img.resize((px_w, round(img.height * px_w / img.width)))
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=80, optimize=True)
                page.insert_image(rect, stream=buf.getvalue(), overlay=True)
            if o["figures"]:
                desc, inner, note = _fig_texts(b)
                if desc:
                    text = f"그림 설명. {desc}"
                    if note:
                        text += f" 색 설명. {note}"
                    if inner:
                        text += " 그림 속 글자: " + ", ".join(inner)
                    _hidden(page, rect, text, fontfile)

    # 3-1) 고대비: 쪽마다 색 반전 막을 씌운다 (사진은 제외, 부록은 따로 검은 바탕으로 만든다)
    if o["contrast"]:
        photos = _photo_figures(doc, job_dir)
        for pg in doc["pages"]:
            i = pg["n"] - 1
            if i >= len(out):
                break
            holes = [pymupdf.Rect(*b["bbox"]) for b in _figures(pg) if b["id"] in photos and b.get("bbox")]
            _invert_page(out, out[i], holes)

    # 4) 책갈피: 원본에 있으면 그대로 두고, 없으면 제목으로 만든다
    toc = out.get_toc()
    if not toc:
        prev = 0
        for pg in doc["pages"]:
            for b in pg["blocks"]:
                if b["type"] == "heading" and b.get("level", 2) <= 3 and b["text"].strip():
                    lv = min(b.get("level", 2), prev + 1) if prev else 1
                    toc.append([lv, re.sub(r"\s+", " ", b["text"]).strip()[:80], pg["n"]])
                    prev = lv

    # 5) 맨 끝 접근성 부록 (원본 쪽 번호는 그대로): 그림 설명 · 쉬운 한국어 · 용어 사전
    if len(out):
        first = out[0].rect
        res = _appendix(doc, fonts, (first.width, first.height), o)
        if res:
            app, heads = res
            n_before = len(out)
            out.insert_pdf(pymupdf.open("pdf", app))
            if o["contrast"]:                              # 부록도 검은 바탕 + 밝은 글씨
                for k in range(n_before, len(out)):
                    out[k].draw_rect(out[k].rect, color=None, fill=(0, 0, 0), overlay=False)
            toc = toc + [[1 if lv == 1 else 2, text, n_before + pn] for lv, text, pn in heads]
    if toc:
        try:
            out.set_toc(toc)
        except Exception:
            pass

    if brf:
        # 첨부 파일 이름은 영문으로 둔다 (뷰어에 따라 한글 이름이 깨져 보인다). 설명은 한글이어도 괜찮다.
        out.embfile_add("braille", render.brf_bytes(brf[1]), filename="braille.brf", ufilename="braille.brf",
                        desc=f"{brf[0]} · 한글 점자 파일. 점자 프린터·점자정보단말기에서 읽는 파일이에요")

    meta = dict(out.metadata or {})
    meta.update({"title": title or doc.get("title", "") or meta.get("title", ""), "producer": "Our Snowboard"})
    out.set_metadata(meta)
    try:
        out.xref_set_key(out.pdf_catalog(), "Lang", "(ko-KR)")      # 스크린리더가 한국어로 읽도록
    except Exception:
        pass
    try:
        out.subset_fonts()                                           # 쓴 글자만 남겨 글꼴 용량을 줄인다
    except Exception:
        pass
    data = out.tobytes(garbage=3, deflate=True)
    out.close()
    return data
