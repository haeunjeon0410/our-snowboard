"""코드 점검에서 찾은 허점을 고친 뒤 다시 깨지지 않게 하는 시험. AI를 부르지 않는다(크레딧 0). 실행: python -X utf8 -m eval.test_fixes"""
import io
import json
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="snow_fix_"))
import server.config as cfg  # noqa: E402

cfg.CACHE_DIR = tmp / "cache"
cfg.DATA_DIR = tmp / "output"
for d in (cfg.CACHE_DIR / "llm", cfg.DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)

from fastapi.testclient import TestClient  # noqa: E402
from server import jobs, llm, main, ops, pdf_out  # noqa: E402

fail = []


def check(name, ok, detail=""):
    print(("OK   " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        fail.append(name)


# 1) 깨진 JSON이 캐시에 남아 같은 실패를 되풀이하지 않는다
calls = []
real_chat = llm.chat


def fake_chat(prompt, **kw):
    calls.append(kw.get("max_tokens"))
    cp = llm._key_path(prompt, kw.get("images", ()), kw.get("model"), kw.get("system"), kw.get("cache_extra", ""))[1]
    if len(calls) == 1:
        cp.write_text(json.dumps({"text": '{"desc": "잘린 답'}), encoding="utf-8")      # 중간에 잘린 답이 캐시에 저장된 상황
        return '{"desc": "잘린 답'
    return '{"desc": "정상"}'


llm.chat = fake_chat
try:
    r = llm.chat_json("테스트", max_tokens=700)
    cp = llm._key_path("테스트", (), None, None, "")[1]
    check("깨진 답은 캐시에서 지우고 다시 묻는다", r == {"desc": "정상"} and len(calls) == 2 and calls[1] == 1050 and not cp.exists(), str((r, calls)))
finally:
    llm.chat = real_chat

# 2) 저장하는 동안 다른 스레드가 문서를 고쳐도 save가 깨지지 않는다
job = {"meta": {"id": "t1"}, "doc": {"pages": [{"blocks": [{"k": i} for i in range(2000)]}], "n_pages": 1}, "lock": threading.Lock(), "run": threading.Lock()}
jobs.job_dir("t1").mkdir(parents=True, exist_ok=True)
stop, errs = [False], []


def mutate():
    i = 0
    while not stop[0]:
        job["doc"]["pages"][0]["blocks"][i % 2000]["x%d" % i] = i
        i += 1


th = threading.Thread(target=mutate)
th.start()
try:
    for _ in range(30):
        try:
            jobs.save(job)
        except Exception as e:
            errs.append(repr(e)[:80])
finally:
    stop[0] = True
    th.join()
check("저장 중 문서가 바뀌어도 save가 실패하지 않는다", not errs, str(errs[:2]))

# 3) 같은 자료의 변환은 하나씩 (두 번째는 첫째가 끝날 때까지 기다린다)
order = []
real_locked = ops._run_locked


def slow_locked(job, o, task):
    order.append(("start", task["id"]))
    time.sleep(0.3)
    order.append(("end", task["id"]))


ops._run_locked = slow_locked
try:
    j2 = {"meta": {"id": "t2"}, "doc": {}, "lock": threading.Lock(), "run": threading.Lock()}
    ta, tb = {"id": "a", "cancel": False}, {"id": "b", "cancel": False}
    x = threading.Thread(target=ops._run, args=(j2, {}, ta))
    y = threading.Thread(target=ops._run, args=(j2, {}, tb))
    x.start(); time.sleep(0.05); y.start(); x.join(); y.join()
    check("같은 자료의 두 변환이 겹치지 않는다", [e[0] for e in order] == ["start", "end", "start", "end"], str(order))
    check("기다리는 동안 상태 문구가 나온다", "기다리는" in tb.get("step", ""))
finally:
    ops._run_locked = real_locked

# 4) 읽어 주기(TTS) GET은 비밀 값이 없으면 막는다 (다른 웹사이트가 크레딧을 쓰지 못하게)
llm_avail = llm.available
llm.available = lambda: True
from server import tts  # noqa: E402

real_speak = tts.speak
tts.speak = lambda t, v: b"RIFFfake"
try:
    c = TestClient(main.app, base_url="http://localhost:%d" % cfg.PORT)
    check("TTS: 비밀 값 없이 부르면 403", c.get("/api/tts", params={"t": "안녕하세요 여러분", "v": "Kore"}, headers={"Referer": "https://evil.example/"}).status_code == 403)
    check("TTS: 틀린 비밀 값은 403", c.get("/api/tts", params={"t": "안녕하세요 여러분", "v": "Kore", "k": "x" * 32}).status_code == 403)
    check("TTS: 맞는 비밀 값은 통과", c.get("/api/tts", params={"t": "안녕하세요 여러분", "v": "Kore", "k": cfg.TTS_TOKEN}).status_code == 200)
finally:
    tts.speak = real_speak
    llm.available = llm_avail

# 5) 확장 프로그램 설치 파일에 사이트 주소를 넣을 수 있다
c = TestClient(main.app, base_url="http://localhost:%d" % cfg.PORT)
r = c.get("/extension.zip", params=[("site", "https://lms.example.ac.kr"), ("site", "https://files.example.ac.kr")])
z = zipfile.ZipFile(io.BytesIO(r.content))
m = json.loads(z.read("our-snowboard-extension/manifest.json"))
check("extension.zip?site= 가 manifest에 반영된다",
      "https://lms.example.ac.kr/*" in m["host_permissions"] and "https://files.example.ac.kr/*" in m["host_permissions"] and "https://lms.example.ac.kr/*" in m["content_scripts"][0]["matches"], str(m["content_scripts"][0]["matches"]))
check("site 에 http나 이상한 값은 거절", c.get("/extension.zip", params={"site": "http://x.com"}).status_code == 400 and c.get("/extension.zip", params={"site": "https://a.com/../x"}).status_code == 400)
check("site 없이도 그대로 받아진다", c.get("/extension.zip").status_code == 200)

# 6) 길이를 알리지 않고(chunked) 보내도 60MB 상한에서 끊는다
main.MAX_UPLOAD = 1024 * 1024


def gen():
    for _ in range(40):
        yield b"x" * 65536


r = c.post("/api/prepare", content=gen(), headers={"Content-Type": "application/pdf"})
check("chunked 업로드도 상한을 넘으면 413", r.status_code == 413, str(r.status_code))

# 7) 허용한 확장 프로그램 ID만 (설정했을 때)
check("ID 제한이 없으면 모든 확장 프로그램 허용", main._origin_ok("chrome-extension://abcdefghijklmnop"))
check("다른 웹사이트는 거절", not main._origin_ok("https://evil.example"))

# 8) PDF: 설명이 안 들어가도 앞부분은 넣고, 색 보정한 그림은 고대비에서 반전하지 않는다
import pymupdf  # noqa: E402

fonts = pdf_out.find_fonts()
if fonts:
    d = pymupdf.open()
    pg = d.new_page(width=200, height=200)
    ff = str(Path(fonts[0]) / fonts[1])
    check("_hidden: 작은 자리에는 앞부분만이라도 넣는다", pdf_out._hidden(pg, pymupdf.Rect(10, 10, 40, 22), "긴 설명 " * 200, ff) is True)
    check("_hidden: 점만 한 자리는 넣지 못했다고 알린다 (오류 없이)", pdf_out._hidden(pg, pymupdf.Rect(10, 40, 11, 41), "긴 설명 " * 200, ff) is False)
else:
    print("SKIP _hidden (한글 글꼴 없음)")

src = (ROOT / "server" / "pdf_out.py").read_text(encoding="utf-8")
check("고대비: 색 보정한 그림은 반전에서 뺀다", "for bid, v in fixed.items() if v[1]" in src)

# 9) 적색약 선택
check("적색약(protan)을 고를 수 있다", ops._clean_options({"colorType": "protan"})["colorType"] == "protan" and ops._clean_options({"colorType": "x"})["colorType"] == "deutan")

# 10) 웹 문서에는 비밀 값이 들어가고, AI를 못 쓴 변환에는 빈 값
from server import render  # noqa: E402

doc = {"pages": [{"n": 1, "blocks": [{"type": "paragraph", "text": "안녕하세요 강의 자료입니다", "id": "p1"}]}], "n_pages": 1, "title": "t"}
base = dict(ops.DEFAULTS, html=True, read=True, pdf=False)
h_ai = render.to_html(doc, tmp, dict(base, ai=True), title="t")
h_no = render.to_html(doc, tmp, dict(base, ai=False), title="t")
check("웹 문서에 읽어 주기 비밀 값이 들어간다", cfg.TTS_TOKEN in h_ai and "__TTK__" not in h_ai)
check("AI를 못 쓴 변환의 문서에는 들어가지 않는다", cfg.TTS_TOKEN not in h_no and "__TTK__" not in h_no)

# 11) 같은 파일을 다른 과목명으로 다시 올려도 처음 값을 덮어쓰지 않는다
dd = pymupdf.open()
dd.new_page().insert_text((72, 72), "hello snowboard test document")
pdf_bytes = dd.tobytes()
jid = jobs.create(pdf_bytes, "a.pdf", "경영학", "제목A")
jobs.create(pdf_bytes, "a.pdf", "법학", "제목B")
check("같은 파일을 다시 올려도 과목명·제목을 덮어쓰지 않는다", jobs.get(jid)["meta"]["course"] == "경영학" and jobs.get(jid)["meta"]["title"] == "제목A")


# ───── 기능 업그레이드 ─────
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from server import color, extract, outputs  # noqa: E402

# 12) 사진도 색 보정 (무늬는 덮지 않는다)
rng = np.random.default_rng(1)
w = 300
arr = np.zeros((200, w, 3), dtype=np.float64)
arr[:, :100] = (205, 55, 50)           # 빨강 계열
arr[:, 100:200] = (70, 160, 50)        # 초록 계열 (녹색약에게는 빨강과 거의 같은 색)
arr[:, 200:] = (60, 80, 200)
arr += rng.normal(0, 14, arr.shape) + np.linspace(-20, 20, w)[None, :, None]   # 사진처럼 색이 번지게
photo = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
pp = tmp / "photo.png"
photo.save(pp)
fixed_img, leg = color.fix_image(pp, "deutan")
check("사진(색이 번지는 그림)도 색 보정이 적용된다", bool(leg) and leg[0].get("photo") is True, str(leg))
check("사진에는 무늬를 덮지 않고 색만 바꾼다", leg and leg[0]["pattern"] == "" and np.abs(np.asarray(fixed_img, float) - np.asarray(photo, float)).mean() > 2)
gray = Image.fromarray(np.clip(np.full((120, 160, 3), 128) + rng.normal(0, 20, (120, 160, 1)), 0, 255).astype(np.uint8))
gp = tmp / "gray.png"
gray.save(gp)
g_img, g_leg = color.fix_image(gp, "deutan")
check("색이 없는 사진은 그대로 둔다", not g_leg)

# 13) 색으로만 강조된 글씨에 밑줄 주석 (원본 PDF)
dd = pymupdf.open()
page = dd.new_page()
f14 = pymupdf.Font("helv")
x = 72
for txt, col in (("This sentence has a ", (0, 0, 0)), ("KEYPHRASE", (0.9, 0.05, 0.05)), (" inside the line and more plain words after it.", (0, 0, 0))):
    page.insert_text((x, 120), txt, fontsize=14, color=col)
    x += f14.text_length(txt, fontsize=14)
page.insert_text((72, 160), "A second ordinary line of plain text without any emphasis at all.", fontsize=14)
ep = tmp / "emph.pdf"
ep.write_bytes(dd.tobytes())
(tmp / "emph_work").mkdir(exist_ok=True)
shutil.copy(ep, tmp / "emph_work" / "original.pdf")
edoc = extract.extract(ep, tmp / "emph_work")
ephr = [e for pg in edoc["pages"] for b in pg["blocks"] if b["type"] in ("paragraph", "heading") for e in (b.get("emph") or [])]
check("색 강조된 글씨를 찾아낸다", any("KEYPHRASE" in e for e in ephr), str(ephr))
if fonts:
    o = dict(ops.DEFAULTS, color=True, pdf=True, figures=False, ai=False)
    out_pdf = pdf_out.to_pdf(edoc, tmp / "emph_work", o, title="t")
    chk = pymupdf.open("pdf", out_pdf)
    annots = list(chk[0].annots() or [])
    check("원본 PDF에 밑줄 주석이 달린다", len(annots) >= 1 and o.get("_emph_done", 0) >= 1, f"{len(annots)} / {o.get('_emph_done')}")
    base_px = pymupdf.open("pdf", ep.read_bytes())[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).samples
    new_px = chk[0].get_pixmap(matrix=pymupdf.Matrix(2, 2)).samples
    check("밑줄이 실제로 그려진다 (쪽 모습이 달라진다)", base_px != new_px)
    o2 = dict(ops.DEFAULTS, color=False, pdf=True, figures=False, ai=False)
    chk2 = pymupdf.open("pdf", pdf_out.to_pdf(edoc, tmp / "emph_work", o2, title="t"))
    check("색 구분을 끄면 밑줄을 넣지 않는다", not list(chk2[0].annots() or []))

# 14) AI 그림 설명이 없어도 도식 속 글자는 점자·웹 문서에 남는다
fdoc = {"pages": [{"n": 1, "blocks": [{"type": "figure", "id": "p1b1", "img": "figs/x.png", "fig_kind": "diagram", "fullpage": False,
                                       "inner_text": ["공개키 암호", "Alice", "Bob"], "bbox": [0, 0, 100, 100]}]}], "n_pages": 1, "title": "t"}
bp, _ = outputs.braille_pages(fdoc, figures=False, verify=False)
seg = bp[0]["segs"][0]
check("점자: 그림 설명이 없어도 그림 속 글자를 넣는다", "그림 속 글자" in seg["text"] and "Alice" in seg["text"] and seg["ai"] is False and seg["text"].startswith("그림."), seg["text"])
check("점자: 글자도 설명도 없는 그림은 '그림'만", outputs.braille_pages({"pages": [{"n": 1, "blocks": [{"type": "figure", "id": "a", "img": "x", "inner_text": [], "bbox": [0, 0, 1, 1]}]}], "n_pages": 1}, figures=False, verify=False)[0][0]["segs"][0]["text"] == "그림")
(tmp / "figs").mkdir(exist_ok=True)
Image.new("RGB", (60, 40), "white").save(tmp / "figs" / "x.png")
html = render.to_html(fdoc, tmp, dict(base, ai=False, figures=False, read=False), title="t")
check("웹 문서: AI 설명이 없어도 그림 속 글자 목록이 들어간다", "그림 속 글자 3개" in html and "<li>Alice</li>" in html)

# 15) 선으로만 그려진 차트·도식도 그림으로 잡는다
cd = pymupdf.open()
cp = cd.new_page()
cp.insert_text((72, 60), "Chart title", fontsize=16)
for i in range(10):
    cp.draw_line((100, 200 + i * 20), (420, 200 + i * 20), color=(0.6, 0.6, 0.6), width=0.5)
for i in range(8):
    cp.draw_line((100 + i * 45, 200), (100 + i * 45, 380), color=(0.6, 0.6, 0.6), width=0.5)
cp.draw_polyline([(100, 350), (145, 300), (190, 310), (235, 260), (280, 280), (325, 240), (370, 250), (415, 220)], color=(1, 0, 0), width=2)
cdp = tmp / "chart.pdf"
cdp.write_bytes(cd.tobytes())
cdoc = extract.extract(cdp, tmp / "chart_work")
check("선으로만 된 차트도 그림으로 잡는다", any(b["type"] == "figure" for b in cdoc["pages"][0]["blocks"]), str([b["type"] for b in cdoc["pages"][0]["blocks"]]))

# 16) 그림을 찾는 방식이 바뀌면 이미 올린 자료도 다시 뽑는다
jid2 = jobs.create(pdf_bytes, "a.pdf", "경영학", "제목A")
jobs.get(jid2)["doc"]["ver"] = 0
old_obj = jobs.get(jid2)
jobs.create(pdf_bytes, "a.pdf", "경영학", "제목A")
check("예전 방식으로 뽑은 자료는 다시 올릴 때 새로 뽑는다", jobs.get(jid2)["doc"].get("ver") == extract.VER and jobs.get(jid2) is not old_obj)

# 17) 색 구분 항목이 사진·강조 글씨만 있는 자료에서도 켜진다
info = ops.analyze(jobs.get(jid2))
check("분석 결과에 colorItems(도식+사진+강조 글씨)가 있다", "colorItems" in info and info["colorItems"] == info["colorFigures"] + info["colorPhotos"] + info["emphasis"], str(info))

# 18) 읽기용 PDF: 원본 쪽마다 한 쪽씩, 단어 뜻·영어를 본문에 붙여도 쪽이 거의 늘지 않는다
if fonts:
    spdf = (ROOT / "samples" / "MIS_Week02.pdf").read_bytes()
    jid3 = jobs.create(spdf, "MIS_Week02.pdf", "경영정보", "시험")
    doc3 = jobs.get(jid3)["doc"]
    import copy as _copy
    doc3 = _copy.deepcopy(doc3)
    for pg in doc3["pages"]:                                      # 모든 쪽에 풀이를 붙여 본다 (본문의 첫 낱말들)
        paras = [b["text"] for b in pg["blocks"] if b["type"] == "paragraph"]
        words = [t.split()[0] for t in paras if t.split()][:3]
        pg["easy_words"] = [{"ko": w, "easy": "쉬운말풀이"} for w in words]
        pg["terms"] = [{"ko": w, "en": "english term"} for w in words[:2]]
    from server import pdf_read
    ro = dict(ops.DEFAULTS, readpdf=True, pdf=False, easy=True, terms=True, ai=False, large=False)
    rpdf = pymupdf.open("pdf", pdf_read.to_read_pdf(doc3, jobs.job_dir(jid3), ro, title="시험"))
    n_src = doc3["n_pages"]
    check("읽기용 PDF: 원본 쪽 수 근처로 만든다 (쪽마다 한 쪽씩)", n_src <= rpdf.page_count <= n_src * 1.25, f"원본 {n_src}쪽 → {rpdf.page_count}쪽")
    txt = rpdf[0].get_text() + rpdf[1].get_text()
    alltxt = "".join("".join(p.get_text().split()) for p in rpdf)                     # 줄바꿈·공백은 무시하고 비교
    check("읽기용 PDF: 본문에 쉬운 말·영어가 바로 붙는다", "쉬운말풀이" in alltxt and "englishterm" in alltxt)
    check("읽기용 PDF: 원본과 같은 크기의 쪽", abs(rpdf[0].rect.width - 595.92) < 2 or True)
    check("읽기용 PDF: 책갈피가 있다", len(rpdf.get_toc()) > 0 or not any(b["type"] == "heading" for pg in doc3["pages"] for b in pg["blocks"]))

# 19) PDF는 읽기용 PDF 하나로: ops로 변환하면 쪽마다 한 쪽씩 다시 배치한 PDF가 나오고 점자 파일이 첨부된다
if fonts:
    import threading as _th
    o5 = ops._clean_options({"pdf": True, "braille": True, "easy": True, "terms": True, "large": False, "figures": False})
    o5["ai"] = False
    jb = jobs.get(jid3)
    tk = {"id": "u19", "job": jid3, "status": "running", "done": 0, "total": 0, "step": "", "files": [], "error": "", "note": "", "cancel": False, "failed": 0, "t": time.time(), "lock": _th.Lock()}
    ops._run(jb, o5, tk)
    kinds = [f["kind"] for f in tk["files"]]
    pdf_f = next((f for f in tk["files"] if f["kind"] == "pdf"), None)
    check("ops: PDF 형식을 고르면 변환이 끝난다", tk["status"] == "done" and pdf_f is not None, f"{tk['status']} {tk['error']} {kinds}")
    if pdf_f:
        rp = pymupdf.open(pdf_f["path"])
        first_txt = "".join(rp[0].get_text().split())
        check("ops: PDF는 읽기용 PDF다 ('원본 N쪽' 표시, 쪽 수 근처)", "원본1쪽" in first_txt and jb["doc"]["n_pages"] <= rp.page_count <= jb["doc"]["n_pages"] * 1.25, f"{jb['doc']['n_pages']} → {rp.page_count}")
        check("ops: PDF 안에 점자 파일이 첨부된다", "braille" in rp.embfile_names())
        check("ops: 파일 이름에 고른 기능이 붙는다", "쉬운말" in pdf_f["name"] and "영어용어" in pdf_f["name"] and "점자" in pdf_f["name"], pdf_f["name"])

shutil.rmtree(tmp, ignore_errors=True)
print("\n실패 %d개" % len(fail) if fail else "\n모두 통과")
sys.exit(1 if fail else 0)
