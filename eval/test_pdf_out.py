"""원본 보존 PDF(server/pdf_out.py) 시험. 실행: python eval/test_pdf_out.py   (AI는 쓰지 않는다. 그림 설명은 가짜 값을 넣어 시험한다)

지키려는 약속:
  1. 원본의 쪽 수·크기·방향이 그대로다 (부록은 맨 끝에만 붙는다)
  2. 그림 설명이 그림 자리에 보이지 않는 글자로 들어간다 (스크린리더가 읽음)
  3. 색 구분을 켜도 쪽 수·크기는 그대로고, 끄면 눈에 보이는 모습이 원본과 같다
  4. 스캔본 쪽에는 AI가 읽은 글자가 보이지 않게 들어간다
  5. 글자 선택(복사)이 원본 그대로 된다 (글자를 그림으로 바꾸지 않는다)"""
import copy
import os
import sys
from pathlib import Path

os.environ["GATEWAY_API_KEY"] = ""
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pymupdf  # noqa: E402

from server import jobs, ops, pdf_out  # noqa: E402

fail = 0


def check(name, ok, extra=""):
    global fail
    print(("PASS " if ok else "FAIL ") + name + (f"  {extra}" if extra else ""))
    fail += 0 if ok else 1


def norm(t):
    return t.replace("\xa0", " ")


if not pdf_out.available():
    print("SKIP 한글 글꼴(나눔고딕 등)이 없어 PDF를 만들 수 없는 환경이에요")
    sys.exit(0)

pdf_bytes = (ROOT / "samples" / "MIS_Week02.pdf").read_bytes()
jid = jobs.create(pdf_bytes, "MIS_Week02.pdf", "시험 과목", "시험 자료")
job = jobs.get(jid)
base = copy.deepcopy(job["doc"])
src = pymupdf.open(str(jobs.job_dir(jid) / "original.pdf"))

# 가짜 그림 설명 + 가짜 스캔본 쪽
doc = copy.deepcopy(base)
n = 0
for pg in doc["pages"]:
    for b in pg["blocks"]:
        if b["type"] == "figure" and not b.get("fullpage"):
            n += 1
            b["ai_desc"] = {"desc": f"시험용그림설명{n}", "texts": ["가짜글자"], "color_note": ""}
scan = doc["pages"][0]
scan["blocks"] = [{"type": "paragraph", "text": "스캔본에서읽은글자", "id": "p1o1", "ai": ["ocr"]}]
scan["ocr_done"] = True

o = dict(ops.DEFAULTS, figures=True, color=False, ai=False, pdf=True, html=False)
out = pymupdf.open("pdf", pdf_out.to_pdf(doc, jobs.job_dir(jid), o, title="시험"))


def same_pages(a, b, n):
    return all((round(a[i].rect.width), round(a[i].rect.height), a[i].rotation) == (round(b[i].rect.width), round(b[i].rect.height), b[i].rotation) for i in range(n))


check("1. 쪽 수·크기·방향이 원본과 같다 (부록은 뒤에만)", len(out) >= len(src) and same_pages(src, out, len(src)), f"원본 {len(src)}쪽 → 결과 {len(out)}쪽")
all_text = norm(" ".join(p.get_text() for p in out))
check("2. 그림 설명이 그림 쪽에 숨은 글자로 들어감", "시험용그림설명1" in norm(out[2].get_text()) or any(f"시험용그림설명{k}" in norm(out[i].get_text()) for k in (1,) for i in range(len(src))))
check("2-1. 그림 속 글자도 함께 들어감", "가짜글자" in all_text)
check("3. 맨 끝에 접근성 부록이 붙음", len(out) > len(src) and "접근성 부록" in norm(out[len(src)].get_text()), f"부록 {len(out) - len(src)}쪽")
check("4. 스캔본 쪽에 AI가 읽은 글자가 숨어 있음", "스캔본에서읽은글자" in norm(out[0].get_text()))

# 눈에 보이는 모습: 색 구분을 끄면 (설명 글자는 보이지 않으므로) 부록 앞 모든 쪽이 원본과 같다
def px(d, i):
    return np.frombuffer(d[i].get_pixmap(dpi=50).samples, dtype=np.uint8).astype(int)


diffs = [float(np.abs(px(src, i) - px(out, i)).mean()) for i in range(len(src))]
check("5. 숨은 글자를 얹어도 눈에 보이는 모습은 원본과 같다", max(diffs) < 0.05, f"쪽별 최대 차이 {max(diffs):.3f}")

# 원본 글자 그대로 (그림으로 바꾸지 않음)
orig_words = norm(src[5].get_text()).split()[:8]
check("6. 원본 글자가 그대로 선택·복사된다", all(w in norm(out[5].get_text()) for w in orig_words))
check("7. 책갈피(목차)가 들어감", len(out.get_toc()) > 0, f"{len(out.get_toc())}개")

# 색 구분: 쪽 수·크기는 그대로
o2 = dict(o, color=True)
out2 = pymupdf.open("pdf", pdf_out.to_pdf(doc, jobs.job_dir(jid), o2, title="시험"))
check("8. 색 구분을 켜도 쪽 수·크기·방향이 같다", len(out2) == len(out) and same_pages(src, out2, len(src)))
changed = sum(1 for i in range(len(src)) if float(np.abs(px(src, i) - px(out2, i)).mean()) > 0.05)
check("9. 색 구분은 색이 칠해진 그림이 있는 쪽만 바뀐다", 0 < changed < len(src), f"{changed}/{len(src)}쪽 바뀜")

# 그림 설명을 끄면 부록이 없다
o3 = dict(o, figures=False)
out3 = pymupdf.open("pdf", pdf_out.to_pdf(doc, jobs.job_dir(jid), o3, title="시험"))
check("10. 그림 설명을 끄면 부록이 붙지 않는다", len(out3) == len(src))

# ── 점자 첨부: PDF 한 파일에서도 .brf를 꺼낼 수 있다 ──
from server import render  # noqa: E402

o_b = dict(o, braille=True)
brf_text = render.to_brf(doc, o_b)
out_b = pymupdf.open("pdf", pdf_out.to_pdf(doc, jobs.job_dir(jid), o_b, title="시험", brf=("시험 (점자).brf", brf_text)))
check("14. 점자를 고르면 PDF에 .brf가 첨부되고 내용이 똑같다", out_b.embfile_names() == ["braille"] and out_b.embfile_get("braille") == render.brf_bytes(brf_text), f"{len(brf_text.splitlines())}줄")
check("15. 점자 첨부는 영문 이름(braille.brf)이라 뷰어에서 깨지지 않는다", out_b.embfile_info("braille")["filename"] == "braille.brf")
check("16. 점자를 끄면 첨부가 없다", out.embfile_names() == [])

# ── 고대비 / 쉬운 한국어·용어 사전 부록 (원본 PDF) ──
doc_e = copy.deepcopy(doc)
for pg in doc_e["pages"][2:5]:
    pg["easy"] = {b["id"]: "쉬운말시험문장" for b in pg["blocks"] if b["type"] == "paragraph"}
    pg["terms"] = [{"ko": "경쟁", "en": "competition"}]
o_c = dict(o, contrast=True, easy=True, terms=True)
out_c = pymupdf.open("pdf", pdf_out.to_pdf(doc_e, jobs.job_dir(jid), o_c, title="시험"))


def lum(d, i):
    pm = d[i].get_pixmap(dpi=30)
    return float(np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width, pm.n)[..., :3].mean())


check("17. 고대비: 쪽 수·크기가 같고 본문 쪽이 어두워진다(검은 바탕)", same_pages(src, out_c, len(src)) and all(lum(out_c, i) < 0.6 * lum(src, i) for i in (0, 5)),
      f"밝기 {lum(src, 0):.0f}→{lum(out_c, 0):.0f}")
check("18. 고대비를 해도 원본 글자를 선택·복사할 수 있다", all(w in norm(out_c[5].get_text()) for w in orig_words))
toc_c = [t[1] for t in out_c.get_toc()]
txt_c = norm(" ".join(out_c[i].get_text() for i in range(len(src), len(out_c))))
check("19. 쉬운 한국어·용어 사전이 맨 끝 부록에 들어간다", "쉬운말시험문장" in txt_c and "competition" in txt_c and "쉬운 한국어" in toc_c and "용어 사전" in toc_c, f"부록 {len(out_c) - len(src)}쪽")
check("20. 부록도 고대비(검은 바탕)", lum(out_c, len(src)) < 60, f"밝기 {lum(out_c, len(src)):.0f}")

# ── 읽기용 PDF (내용을 다시 흐르게 한 큰 글씨 PDF) ──
from server import pdf_read  # noqa: E402

o_r = dict(o, readpdf=True, large=True, easy=True, terms=True, color=False)
rd = pymupdf.open("pdf", pdf_read.to_read_pdf(doc_e, jobs.job_dir(jid), o_r, title="시험"))
rd_text = norm(" ".join(p.get_text() for p in rd))
sizes = [sp["size"] for pg in rd[:3] for b in pg.get_text("dict")["blocks"] if b["type"] == 0 for ln in b["lines"] for sp in ln["spans"]]
check("21. 읽기용 PDF: 큰 글씨(본문 15pt 이상 비중이 높다)", sizes and sum(1 for z in sizes if z >= 15) / len(sizes) > 0.5, f"쪽 {len(rd)}")
check("22. 읽기용 PDF에 원본 쪽 번호 표시와 쉬운 말이 들어간다", "원본 3쪽" in rd_text and "쉬운말시험문장" in rd_text)
check("23. 읽기용 PDF에 책갈피가 있다", len(rd.get_toc()) > 0)

# ── 가로 슬라이드(제2장, 960×540) ──
pdf2 = (ROOT / "samples" / "제2장.pdf").read_bytes()
jid2 = jobs.create(pdf2, "제2장.pdf", "시험 과목", "시험 자료2")
job2 = jobs.get(jid2)
src2 = pymupdf.open(str(jobs.job_dir(jid2) / "original.pdf"))
doc2 = copy.deepcopy(job2["doc"])
for pg in doc2["pages"]:
    for b in pg["blocks"]:
        if b["type"] == "figure" and not b.get("fullpage"):
            b["ai_desc"] = {"desc": "시험용 그림 설명", "texts": [], "color_note": ""}
out4 = pymupdf.open("pdf", pdf_out.to_pdf(doc2, jobs.job_dir(jid2), dict(o, color=True), title="가로"))
landscape = all(p.rect.width > p.rect.height for p in src2)
check("11. 가로 슬라이드는 결과도 모든 쪽(부록 포함)이 가로", landscape and all(p.rect.width > p.rect.height for p in out4), f"{len(src2)}쪽 → {len(out4)}쪽")
check("12. 가로 슬라이드의 원본 쪽 크기·방향이 같다", same_pages(src2, out4, len(src2)))
photo_changed = sum(1 for i in range(len(src2)) if float(np.abs(px(src2, i) - px(out4, i)).mean()) > 0.05)
n_fig2 = sum(1 for pg in doc2["pages"] for b in pg["blocks"] if b["type"] == "figure")
check("13. 사진·현미경처럼 색이 번지는 그림에는 색 구분 무늬를 덮지 않는다", photo_changed <= 3, f"{len(src2)}쪽 중 {photo_changed}쪽만 바뀜 (그림 {n_fig2}개)")

print("\n모두 통과" if not fail else f"\n{fail}개 실패")
sys.exit(1 if fail else 0)
