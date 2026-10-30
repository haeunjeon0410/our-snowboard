"""읽기용 PDF (.pdf): 내용을 다시 배치해 큰 글씨·고대비·쉬운 한국어·영어 병기를 본문 안에 바로 넣은 문서.
원본 쪽마다 한 쪽씩 만든다: 원본과 같은 크기의 쪽 하나에 그 쪽의 내용을 넣고, 넘치면 글씨를 줄여서(최소 절반까지) 한 쪽에 담는다.
그래도 안 들어가는 쪽만 다음 쪽으로 이어진다. 그래서 단어 뜻·영어를 붙여도 쪽 번호가 거의 밀리지 않는다.
웹 문서(render.py)와 내용·옵션이 같고, PDF라서 태블릿·스마트폰·인쇄에 쓰기 쉽다. pymupdf의 Story(HTML+CSS → PDF)를 쓴다."""
import io
import re
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image

from . import pdf_out, render

_TAG = re.compile(r"(<[^>]+>)")
_WORD = re.compile(r"\S{1,18}")


def _nb(html_s: str) -> str:
    """낱말 단위로만 줄이 바뀌게 한다 (한국어는 글자마다 줄이 바뀌어 '입니/다'처럼 끊긴다). 너무 긴 덩어리는 그대로 둔다."""
    return "".join(p if p.startswith("<") else _WORD.sub(lambda m: f'<span style="white-space:nowrap">{m.group(0)}</span>', p)
                   for p in _TAG.split(html_s))


def _css(fonts, o, base: float) -> str:
    fg = "#ffe600" if o["contrast"] else "#1c2230"
    mut = "#ffffff" if o["contrast"] else "#6b7689"
    line = "#ffffff" if o["contrast"] else "#c9d1de"
    soft = "#222222" if o["contrast"] else "#f2f4f8"
    acc = "#ffffff" if o["contrast"] else "#264e8a"
    return f"""
@font-face{{font-family:K;src:url({fonts[1]})}}
@font-face{{font-family:K;font-weight:bold;src:url({fonts[2]})}}
body{{font-family:K;font-size:{base}pt;line-height:1.8;color:{fg}}}
h1{{font-size:{base * 1.5}pt;line-height:1.3;margin:0 0 4pt;font-weight:bold}}
h2{{font-size:{base * 1.3}pt;line-height:1.35;margin:18pt 0 4pt;font-weight:bold}}
h3{{font-size:{base * 1.15}pt;line-height:1.4;margin:14pt 0 3pt;font-weight:bold}}
h4{{font-size:{base * 1.05}pt;line-height:1.4;margin:12pt 0 3pt;font-weight:bold}}
p{{margin:4pt 0}} ul{{margin:4pt 0 4pt 14pt}} li{{margin:3pt 0}}
.meta{{color:{mut};font-size:{base * 0.75}pt;margin:0 0 14pt}}
.pg{{color:{mut};font-size:{base * 0.7}pt;font-weight:bold;margin:22pt 0 6pt;border-top:1px solid {line};padding-top:6pt}}
.en{{color:{mut};font-size:{base * 0.85}pt}}
.gl{{color:{acc};font-size:{base * 0.9}pt;font-weight:bold}}
.ai{{color:{mut};font-size:{base * 0.6}pt;font-weight:bold}}
.cap{{background-color:{soft};padding:6pt 9pt;font-size:{base * 0.85}pt;margin:3pt 0 10pt}}
.leg{{color:{mut};font-size:{base * 0.8}pt}}
.warn{{font-weight:bold}}
img{{margin:6pt 0}}
table{{border-collapse:collapse;margin:8pt 0;font-size:{base * 0.85}pt}}
th,td{{border:1px solid {line};padding:3pt 5pt;vertical-align:top}}
th{{background-color:{soft};font-weight:bold}}
pre{{background-color:{soft};padding:6pt 8pt;font-size:{base * 0.8}pt;white-space:pre-wrap;margin:6pt 0}}
mark{{font-weight:bold;color:{acc};text-decoration:underline}}
.foot{{color:{mut};font-size:{base * 0.7}pt;margin-top:20pt;border-top:1px solid {line};padding-top:6pt}}
"""


def _figure(b, pg, job_dir: Path, o, fixed, tmp: Path, box=None) -> str:
    """box: (최대 너비, 최대 높이) pt. 그림이 쪽을 다 차지해서 글이 밀려나지 않게 크기를 제한한다."""
    e = render._e
    if pg.get("ocr_done") and b.get("fullpage"):
        return ""                                   # 스캔본은 읽어 낸 글이 이미 본문에 있다
    src = job_dir / b["img"]
    if not src.exists():
        return ""
    desc, inner, note = pdf_out._fig_texts(b)
    legend, img = "", None
    if o["color"] and b["id"] in fixed:
        img, pal = fixed[b["id"]]
        if pal:
            legend = ('<p class="leg">사진의 색을 구분하기 쉽게 보정했어요</p>' if pal[0].get("photo") else
                      '<p class="leg">색을 무늬로도 구분했어요: ' + ", ".join(f"{e(g['name'])}={e(g['pattern'])}" for g in pal[:6]) + "</p>")
        else:
            img = None
    if img is None:
        img = Image.open(src)
    img = img.convert("RGB")
    if img.width > 1100:                            # 웹 문서와 같은 크기·압축
        img = img.resize((1100, round(img.height * 1100 / img.width)), Image.LANCZOS)
    name = f"i_{b['id']}.jpg"
    img.save(tmp / name, "JPEG", quality=82, optimize=True)
    if box:
        w = min(box[0], box[1] * img.width / img.height)                 # 상자 안에서 가로세로 비율을 지켜 가장 크게
        parts = [f'<img src="{name}" style="width:{w:.0f}pt;height:{w * img.height / img.width:.0f}pt">']
    else:
        parts = [f'<img src="{name}" style="width:100%">']
    if o["figures"] and desc:
        extra = f" <b>색 설명</b> {e(note)}" if note else ""
        inn = f"<br><b>그림 속 글자</b> {e(', '.join(inner))}" if inner else ""
        parts.append(f'<p class="cap"><b>그림 설명</b> <span class="ai">[AI]</span> {e(desc)}{extra}{inn}</p>')
        if render.needs_check(b):
            parts.append(f'<p class="cap warn">{e(render.WARN_TEXT)}</p>')
    elif inner:                                     # AI 설명이 없어도 그림 속 글자(원본에 글자로 있던 것)는 읽을 수 있게 둔다
        parts.append(f'<p class="cap"><b>그림 속 글자</b> {e(", ".join(inner))}</p>')
    parts.append(legend)
    return "".join(parts)


def _page_html(pg, doc, job_dir: Path, o, tmp: Path, fixed, state, box=None) -> str:
    """원본 쪽 하나의 내용을 HTML로. state: {'prev_h': 앞 제목 단계}"""
    e = render._e
    words = pg.get("easy_words") if o["easy"] else None
    terms = pg.get("terms") if o["terms"] else None
    used: set = set()
    parts = [f'<p class="pg">원본 {pg["n"]}쪽</p>']                          # 원본 쪽 번호를 그대로 표시해 강의와 맞춰 볼 수 있게

    def text_of(obj):
        h = render._emph_html(obj["text"], obj.get("emph")) if (obj.get("emph") and o["color"]) else e(obj["text"])
        return _nb(render._with_terms(render._with_words(h, words, used), terms, used))

    for b in pg["blocks"]:
        t = b["type"]
        if t == "heading":
            lv = min(b.get("level", 2) + 1, 4, state["prev_h"] + 1)
            state["prev_h"] = lv
            parts.append(f"<h{lv}>{text_of(b)}</h{lv}>")
        elif t == "paragraph":
            ocr = ' <span class="ai">[AI]</span>' if "ocr" in (b.get("ai") or []) else ""
            parts.append(f"<p>{text_of(b)}{ocr}</p>")
        elif t == "list":
            parts.append("<ul>" + "".join(f"<li>{text_of(it)}</li>" for it in b["items"]) + "</ul>")
        elif t == "table":
            rows = b["rows"]
            parts.append("<table><tr>" + "".join(f"<th>{e(c)}</th>" for c in rows[0]) + "</tr>"
                         + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</table>")
        elif t == "code":
            parts.append(f"<pre>{e(b['text'])}</pre>")
        elif t == "figure":
            parts.append(_figure(b, pg, job_dir, o, fixed, tmp, box))
    return "".join(parts)


MIN_FIT = 0.5          # 한 쪽에 담으려고 글씨를 줄일 수 있는 한계 (원래 크기의 절반)
MIN_FIT_LARGE = 0.85   # 큰 글씨를 골랐을 때는 거의 줄이지 않는다 (줄이면 큰 글씨의 뜻이 없어진다. 넘치는 내용은 다음 쪽으로)


def to_read_pdf(doc: dict, job_dir: Path, o: dict, title: str = "", brf: tuple | None = None) -> bytes:
    """brf: (파일 이름, 점자 텍스트)를 주면 점자 파일을 PDF 안에 첨부한다 (PDF 뷰어의 첨부 파일 목록에서 꺼낼 수 있다)."""
    fonts = pdf_out.find_fonts()
    if not fonts:
        raise RuntimeError("PDF를 만들 한글 글꼴(나눔고딕 등)이 서버에 없어요")
    tmp = Path(tempfile.mkdtemp(prefix="osb_read_"))
    try:
        arch = pymupdf.Archive(fonts[0])
        arch.add(pymupdf.Archive(str(tmp)))
        fixed = render._fix_all(doc, job_dir, o)
        buf = io.BytesIO()
        writer = pymupdf.DocumentWriter(buf)
        state = {"prev_h": 1}
        min_fit = MIN_FIT_LARGE if o["large"] else MIN_FIT
        first_page = {}                                   # 원본 쪽 번호 → 결과 PDF의 쪽 번호 (1부터)
        out_pages = 0
        for pg in doc["pages"]:
            W, H = float(pg.get("width") or 595), float(pg.get("height") or 842)
            media = pymupdf.Rect(0, 0, W, H)
            m = max(24.0, W * 0.05)
            where = pymupdf.Rect(m, m * 0.9, W - m, H - m * 0.9)
            base = max(11.0, W * 0.022) * (1.4 if o["large"] else 1.0)         # 쪽이 클수록 글씨도 크게 시작한다
            css = _css(fonts, o, base)
            n_fig = max(1, sum(1 for b_ in pg["blocks"] if b_["type"] == "figure"))
            s = 1.0
            for _ in range(3):                                          # 글씨를 줄이는 정도(s)가 바뀌면 그림 상자도 달라져서 몇 번 맞춰 본다
                state_try = dict(state)
                box = (where.width * s, where.height * s * 0.5 / n_fig)           # 그림은 한 쪽 높이의 절반까지 (여럿이면 나눠서)
                html = _page_html(pg, doc, job_dir, o, tmp, fixed, state_try, box)
                story = pymupdf.Story(html=html, user_css=css, archive=arch)
                fit = story.fit_scale(where, scale_min=1, scale_max=1 / min_fit)          # 담길 때까지 글씨를 줄인다 (scale 2 = 절반 크기)
                s_new = fit.parameter if fit.big_enough else 1 / min_fit
                if abs(s_new - s) < 0.05:
                    s = s_new
                    break
                s = s_new
            state.update(state_try)
            story = pymupdf.Story(html=html, user_css=css, archive=arch)            # fit이 이야기를 소비하므로 새로 만든다
            big = pymupdf.Rect(where.x0 * s, where.y0 * s, where.x1 * s, where.y1 * s)
            mat = pymupdf.Matrix(1 / s, 1 / s)
            first_page[pg["n"]] = out_pages + 1
            while True:
                more, _ = story.place(big)
                dev = writer.begin_page(media)
                story.draw(dev, mat)
                writer.end_page()
                out_pages += 1
                if not more:
                    break
        writer.close()
        pdf = pymupdf.open("pdf", buf.getvalue())
        if o["contrast"]:                           # 고대비: 모든 쪽 바닥을 검게
            for page in pdf:
                page.draw_rect(page.rect, color=None, fill=(0, 0, 0), overlay=False)
        toc, prev = [], 0                           # 책갈피: 제목(1·2단계)을 그 쪽 번호로. 목차 단계는 앞 단계보다 2 이상 커지면 안 된다
        for pg in doc["pages"]:
            for b in pg["blocks"]:
                if b["type"] == "heading" and b.get("level", 2) <= 2 and b["text"].strip():
                    lv = min(b.get("level", 2), prev + 1) if prev else 1
                    toc.append([lv, re.sub(r"\s+", " ", b["text"]).strip()[:80], first_page[pg["n"]]])
                    prev = lv
        if toc:
            pdf.set_toc(toc)
        if brf:                                     # 첨부 파일 이름은 영문으로 둔다 (뷰어에 따라 한글 이름이 깨져 보인다)
            pdf.embfile_add("braille", render.brf_bytes(brf[1]), filename="braille.brf", ufilename="braille.brf",
                            desc=f"{brf[0]} · 한글 점자 파일. 점자 프린터·점자정보단말기에서 읽는 파일이에요")
        pdf.set_metadata({"title": title or doc.get("title", ""), "producer": "Our Snowboard"})
        try:
            pdf.xref_set_key(pdf.pdf_catalog(), "Lang", "(ko-KR)")
        except Exception:
            pass
        try:
            pdf.subset_fonts()                      # 쓴 글자만 남겨 글꼴 용량을 줄인다
        except Exception:
            pass
        data = pdf.tobytes(garbage=3, deflate=True)
        pdf.close()
        return data
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
