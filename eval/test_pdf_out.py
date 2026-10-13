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

print("\n모두 통과" if not fail else f"\n{fail}개 실패")
sys.exit(1 if fail else 0)
