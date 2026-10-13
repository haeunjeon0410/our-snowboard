"""읽기용 PDF (.pdf): 내용을 다시 흐르게 해서 큰 글씨·고대비·쉬운 한국어·영어 병기를 인라인으로 넣은 문서.
원본 배치를 바꾸는 방식이라 '원본 PDF'(pdf_out.py)와 따로 고르는 선택 형식이다. 웹 문서(render.py)와 내용·옵션이 같고,
PDF라서 태블릿·스마트폰·인쇄에 쓰기 쉽다. pymupdf의 Story(HTML+CSS → PDF)를 쓴다."""
import io
import os
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


def _css(fonts, o) -> str:
    base = 17 if o["large"] else 11.5
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
.ai{{color:{mut};font-size:{base * 0.6}pt;font-weight:bold}}
.cap{{background-color:{soft};padding:6pt 9pt;font-size:{base * 0.85}pt;margin:3pt 0 10pt}}
.leg{{color:{mut};font-size:{base * 0.8}pt}}
img{{margin:6pt 0}}
table{{border-collapse:collapse;margin:8pt 0;font-size:{base * 0.85}pt}}
th,td{{border:1px solid {line};padding:3pt 5pt;vertical-align:top}}
th{{background-color:{soft};font-weight:bold}}
pre{{background-color:{soft};padding:6pt 8pt;font-size:{base * 0.8}pt;white-space:pre-wrap;margin:6pt 0}}
mark{{font-weight:bold;color:{acc};text-decoration:underline}}
.foot{{color:{mut};font-size:{base * 0.7}pt;margin-top:20pt;border-top:1px solid {line};padding-top:6pt}}
"""


def _figure(b, pg, job_dir: Path, o, fixed, tmp: Path) -> str:
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
            legend = '<p class="leg">색을 무늬로도 구분했어요: ' + ", ".join(f"{e(g['name'])}={e(g['pattern'])}" for g in pal[:6]) + "</p>"
        else:
            img = None
    if img is None:
        img = Image.open(src)
    img = img.convert("RGB")
    if img.width > 1100:                            # 웹 문서와 같은 크기·압축
        img = img.resize((1100, round(img.height * 1100 / img.width)), Image.LANCZOS)
    name = f"i_{b['id']}.jpg"
    img.save(tmp / name, "JPEG", quality=82, optimize=True)
    parts = [f'<img src="{name}" style="width:100%">']
    if o["figures"] and desc:
        extra = f" <b>색 설명</b> {e(note)}" if note else ""
        inn = f"<br><b>그림 속 글자</b> {e(', '.join(inner))}" if inner else ""
        parts.append(f'<p class="cap"><b>그림 설명</b> <span class="ai">[AI]</span> {e(desc)}{extra}{inn}</p>')
    parts.append(legend)
    return "".join(parts)


def _html(doc, job_dir: Path, o, title: str, tmp: Path) -> str:
    e = render._e
    fixed = render._fix_all(doc, job_dir, o)
    parts = [f"<h1>{e(title or doc.get('title', ''))}</h1>",
             f'<p class="meta">{e((doc.get("course") + " · ") if doc.get("course") else "")}{doc["n_pages"]}쪽</p>']
    if o["easy"] and any(p.get("easy") for p in doc["pages"]):
        parts.append('<p class="cap"><span class="ai">AI</span> 어려운 문장을 AI가 쉬운 한국어로 바꿨어요. 원문과 조금 다를 수 있어요.</p>')
    for pg in doc["pages"]:
        easy = (pg.get("easy") or {}) if o["easy"] else {}
        terms = pg.get("terms") if o["terms"] else None
        used: set = set()
        parts.append(f'<p class="pg">원본 {pg["n"]}쪽</p>')              # 원본 쪽 번호를 그대로 표시해 강의와 맞춰 볼 수 있게

        def text_of(obj, key):
            if key in easy:
                return _nb(render._with_terms(e(easy[key]), terms, used))
            h = render._emph_html(obj["text"], obj.get("emph")) if obj.get("emph") else e(obj["text"])
            return _nb(render._with_terms(h, terms, used))

        for b in pg["blocks"]:
            t = b["type"]
            if t == "heading":
                lv = min(b.get("level", 2) + 1, 4)
                parts.append(f"<h{lv}>{text_of(b, b['id'])}</h{lv}>")
            elif t == "paragraph":
                ocr = ' <span class="ai">[AI]</span>' if "ocr" in (b.get("ai") or []) else ""
                parts.append(f"<p>{text_of(b, b['id'])}{ocr}</p>")
            elif t == "list":
                parts.append("<ul>" + "".join(f"<li>{text_of(it, f'{b['id']}:{i}')}</li>" for i, it in enumerate(b["items"])) + "</ul>")
            elif t == "table":
                rows = b["rows"]
                parts.append("<table><tr>" + "".join(f"<th>{e(c)}</th>" for c in rows[0]) + "</tr>"
                             + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</table>")
            elif t == "code":
                parts.append(f"<pre>{e(b['text'])}</pre>")
            elif t == "figure":
                parts.append(_figure(b, pg, job_dir, o, fixed, tmp))
    parts.append('<p class="foot">Our Snowboard로 변환했어요. [AI] 표시가 있는 내용은 AI가 만들었고 틀릴 수 있어요.</p>')
    return "".join(parts)


def to_read_pdf(doc: dict, job_dir: Path, o: dict, title: str = "") -> bytes:
    fonts = pdf_out.find_fonts()
    if not fonts:
        raise RuntimeError("PDF를 만들 한글 글꼴(나눔고딕 등)이 서버에 없어요")
    tmp = Path(tempfile.mkdtemp(prefix="osb_read_"))
    try:
        arch = pymupdf.Archive(fonts[0])
        arch.add(pymupdf.Archive(str(tmp)))
        story = pymupdf.Story(html=_html(doc, job_dir, o, title, tmp), user_css=_css(fonts, o), archive=arch)
        buf = io.BytesIO()
        writer = pymupdf.DocumentWriter(buf)
        media = pymupdf.paper_rect("a4")
        where = media + (48, 56, -48, -56)
        toc = []

        def positionfn(pos):
            if pos.heading and pos.heading <= 3 and pos.text:
                toc.append([pos.heading, re.sub(r"\s+", " ", pos.text).strip()[:80], pos.page_num])

        story.write(writer, lambda n, f: (media, where, None), positionfn=positionfn)
        writer.close()
        pdf = pymupdf.open("pdf", buf.getvalue())
        if o["contrast"]:                           # 고대비: 모든 쪽 바닥을 검게
            for page in pdf:
                page.draw_rect(page.rect, color=None, fill=(0, 0, 0), overlay=False)
        if toc:
            fixed_toc, prev = [], 0
            for lv, text, pn in toc:                # 목차 단계는 앞 단계보다 2 이상 커지면 안 된다
                lv = min(lv, prev + 1) if prev else 1
                fixed_toc.append([lv, text, pn])
                prev = lv
            pdf.set_toc(fixed_toc)
        pdf.set_metadata({"title": (title or doc.get("title", "")) + " (읽기용)", "producer": "Our Snowboard"})
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
