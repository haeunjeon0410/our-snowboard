"""원본 PDF에 접근성을 '더해서' 내보낸다 (.pdf). 쪽 수·쪽 방향·크기·글자와 그림의 위치는 원본 그대로다.
원본 쪽의 모습은 그대로이고, 그 위에 필기할 수도 있다.

더하는 것 (모두 눈에 보이는 모습은 바꾸지 않는다):
- 그림 자리에 보이지 않는 글자(그림 설명·그림 속 글자)  → 스크린리더·읽어 주기가 읽는다
- 스캔된 쪽에 보이지 않는 글자층(AI가 읽은 글자)
- 색 구분: 색으로만 구분된 그림을 같은 자리에서 보정본(+무늬)으로 바꾼다
- 고대비: 쪽 위에 색 반전 막을 씌운다(글자는 그대로 글자). 사진처럼 반전하면 필름처럼 보이는 그림은 제외
- 제목 책갈피, 문서 제목·언어, 설명이 필요한 쪽 바로 뒤에 끼워 넣는 보충 쪽(그림 설명 · 쉬운 한국어 · 영어 용어). 쪽 번호가 밀리는 대신 필요한 곳에서 바로 읽힌다

원본의 글자는 그대로 둔다. 글자를 그림으로 바꾸면 확대할 때 뭉개지고 복사도 안 되기 때문이다.
띄어쓰기 복원은 웹 문서·점자에 적용된다."""
import io
import os
import re
from pathlib import Path

import pymupdf

from . import render, tagger

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


def _hidden(page, rect, text: str, fontfile: str) -> bool:
    """보이지 않는 글자(render_mode=3)를 rect 안에 넣는다. 안 들어가면 더 작은 글씨로 다시, 그래도 안 되면 앞부분만이라도 넣는다 (전체는 보충 쪽에 있다)."""
    text = (text or "").strip()
    if not text:
        return True
    for fs in (6, 4, 3, 2, 1.5):
        if page.insert_textbox(rect, text, fontsize=fs, fontname=FONT, fontfile=fontfile, render_mode=3) >= 0:
            return True
    for n in (600, 300, 150, 80, 40, 20):
        if len(text) > n and page.insert_textbox(rect, text[:n] + "…", fontsize=1.5, fontname=FONT, fontfile=fontfile, render_mode=3) >= 0:
            return True
    return False


def _underline_emphasis(page, pg, hc: bool) -> int:
    """색(빨강 등)으로만 강조된 글씨에 굵은 밑줄 주석을 단다. 색을 구분하지 못해도 강조된 곳을 알 수 있다. 원본 글자는 그대로 두고 주석만 더한다. 단 개수를 돌려준다."""
    phrases = []
    for b in pg["blocks"]:
        if b["type"] in ("paragraph", "heading"):
            phrases += b.get("emph") or []
        elif b["type"] == "list":
            for it in b["items"]:
                phrases += it.get("emph") or []
    ink = (1, 0.9, 0) if hc else (0.1, 0.1, 0.1)
    n, seen = 0, set()
    for ph in phrases:
        ph = re.sub(r"\s+", " ", ph).strip()
        if len(ph) < 2 or ph in seen:
            continue
        seen.add(ph)
        try:
            quads = page.search_for(ph, quads=True)
            if not quads:
                continue
            a = page.add_underline_annot(quads=quads)
            a.set_colors(stroke=ink)
            a.set_info(title="Our Snowboard", content="색으로만 강조된 글씨")
            a.update()
            n += 1
        except Exception:
            continue
    return n


# ───────────── 보충 쪽 (그림 설명 · 쉬운 한국어 · 영어 용어) ─────────────
# 맨 뒤에 모아 두면 아무도 찾아가 보지 않으므로, 설명이 필요한 쪽 바로 뒤에 한 쪽씩 끼워 넣는다 (쪽 번호는 그만큼 밀린다).
def _page_parts(pg, o) -> str:
    """이 쪽에 더할 내용 (HTML). 없으면 빈 글."""
    e = render._e
    parts = []
    if o["figures"]:
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
            if render.needs_check(b):
                row += f"<br><b>{e(render.WARN_TEXT)}</b>"
            rows.append(row + "</p>")
        if rows:
            parts.append("<h2>그림 설명</h2>" + "".join(rows))
    if o["easy"] and pg.get("easy_words"):
        parts.append("<h2>단어 뜻</h2>" + "".join(f"<p><b>{e(w['ko'])}</b> ({e(w['easy'])})</p>" for w in pg["easy_words"]))
    if o["terms"] and pg.get("terms"):
        parts.append("<h2>영어 용어</h2>" + "".join(f"<p><b>{e(t['ko'])}</b> ({e(t['en'])})</p>" for t in pg["terms"]))
    return "".join(parts)


def _companions(doc, fonts, size, o) -> tuple[bytes, dict] | None:
    """보충 쪽을 한꺼번에 만든다 (쪽마다 따로 만들면 글꼴이 쪽마다 중복으로 들어가 느리고 커진다).
    반환: (PDF 바이트, {원본 쪽 번호: (시작, 끝)} — 이 PDF 안의 쪽 번호, 0부터). 더할 내용이 없으면 None."""
    sections = [(pg["n"], _page_parts(pg, o)) for pg in doc["pages"]]
    sections = [(n, body) for n, body in sections if body]
    if not sections:
        return None
    hc = o["contrast"]
    fg, mut, line = ("#ffe600", "#ffffff", "#ffffff") if hc else ("#1c2230", "#5a6b88", "#c9d1de")
    css = f"""@font-face{{font-family:K;src:url({fonts[1]})}}
@font-face{{font-family:K;font-weight:bold;src:url({fonts[2]})}}
body{{font-family:K;font-size:13pt;line-height:1.7;color:{fg}}}
h1{{font-size:20pt;margin:0 0 6pt}}
h2{{font-size:15pt;margin:14pt 0 2pt;border-top:1px solid {line};padding-top:6pt}}
p{{margin:3pt 0}} .sub{{color:{mut};font-size:11.5pt}}"""
    arch = pymupdf.Archive()                           # 글꼴 파일 둘만 넣는다 (폴더 전체를 훑지 않는다)
    for name in dict.fromkeys(fonts[1:]):
        arch.add((Path(fonts[0]) / name).read_bytes(), name)
    buf = io.BytesIO()
    w = pymupdf.DocumentWriter(buf)
    media = pymupdf.Rect(0, 0, size[0], size[1])
    where = media + (42, 42, -42, -42)
    ranges, total = {}, 0
    for n, body in sections:                           # 구역마다 새 쪽에서 시작한다 (Story의 page-break는 멈추는 경우가 있어 쓰지 않는다)
        html = f'<h1>{n}쪽 보충 설명</h1><p class="sub">앞 쪽 바로 뒤에 넣은 쪽이에요. AI가 쓴 내용이라 틀릴 수 있어요.</p>{body}'
        calls = [0]

        def rectfn(num, filled):
            calls[0] += 1
            return media, where, None
        pymupdf.Story(html=html, user_css=css, archive=arch).write(w, rectfn)
        ranges[n] = (total, total + calls[0] - 1)
        total += calls[0]
    w.close()
    sub = pymupdf.open("pdf", buf.getvalue())
    ink = (1, 0.9, 0) if hc else (0.35, 0.42, 0.53)
    fontfile = os.path.join(fonts[0], fonts[1])
    for n, (a, z) in ranges.items():                   # 아래에 "N쪽 보충 설명 (k/m)": 어느 쪽의 보충인지, 이어지는지 알 수 있게
        for k, idx in enumerate(range(a, z + 1)):
            pgx = sub[idx]
            if hc:                                     # 검은 바탕 + 밝은 글씨
                pgx.draw_rect(pgx.rect, color=None, fill=(0, 0, 0), overlay=False)
            pgx.insert_text((42, pgx.rect.height - 22), f"{n}쪽 보충 설명 ({k + 1}/{z - a + 1})", fontname=FONT,
                            fontfile=fontfile, fontsize=9, color=ink)
    data = sub.tobytes(garbage=3, deflate=True)
    sub.close()
    return data, ranges


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
    base = job_dir / "original.pdf"
    tagged = tagger.tag(base, job_dir) if (o.get("tagged", True) and tagger.available()) else None      # 구조 태그를 단 PDF (Java가 없거나 실패하면 None → 원본 그대로)
    out = pymupdf.open(str(tagged or base))
    tagged_ids = tagger.apply_alts(out, doc, o) if (tagged and o["figures"]) else set()                # 그림 설명을 Alt로 넣은 그림 (이 그림은 숨은 글자를 또 얹지 않는다)
    fixed = render._fix_all(doc, job_dir, o) if o["color"] else {}
    emph_n = 0

    for pg in doc["pages"]:
        i = pg["n"] - 1
        if i >= len(out):
            break
        page = out[i]
        if o["color"]:
            emph_n += _underline_emphasis(page, pg, o["contrast"])

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
                if desc and b["id"] not in tagged_ids:
                    text = f"그림 설명. {desc}"
                    if note:
                        text += f" 색 설명. {note}"
                    if inner:
                        text += " 그림 속 글자: " + ", ".join(inner)
                    _hidden(page, rect, text, fontfile)

    o["_emph_done"] = emph_n                            # 변환 요약에서 쓴다
    # 3-1) 고대비: 쪽마다 색 반전 막을 씌운다 (사진은 제외, 부록은 따로 검은 바탕으로 만든다)
    if o["contrast"]:
        photos = _photo_figures(doc, job_dir) | {bid for bid, v in fixed.items() if v[1]}      # 색 보정한 그림도 반전하지 않는다 (보정한 색이 뒤집히면 구분이 달라진다)
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

    # 5) 보충 쪽: 그림 설명 · 쉬운 한국어 · 영어 용어를, 필요한 쪽 바로 뒤에 한 쪽씩 끼워 넣는다 (뒤쪽 쪽 번호는 그만큼 밀린다)
    inserted = {}                                       # 원본 쪽 번호 → 그 뒤에 넣은 쪽 수
    if len(out):
        first = out[0].rect
        res = _companions(doc, fonts, (first.width, first.height), o)
        if res:
            sub = pymupdf.open("pdf", res[0])
            for n in sorted(res[1], reverse=True):      # 뒤에서부터 넣어야 앞쪽 위치가 안 바뀐다
                if n - 1 >= len(out):
                    continue
                a, z = res[1][n]
                out.insert_pdf(sub, from_page=a, to_page=z, start_at=n)
                inserted[n] = z - a + 1
            sub.close()
    if inserted:
        def shifted(pn):                                # 원본 pn쪽이 지금은 몇 쪽인지
            return pn + sum(c for q, c in inserted.items() if q < pn)
        toc = [[lv, text, shifted(pn)] for lv, text, pn in toc]
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
    pymupdf.TOOLS.mupdf_display_errors(False)           # 구조 태그 PDF를 정리할 때 나오는 무해한 경고(invalid key in dict)가 로그를 덮지 않게
    try:
        data = out.tobytes(garbage=3, deflate=True)
    finally:
        pymupdf.TOOLS.mupdf_display_errors(True)
    out.close()
    return data
