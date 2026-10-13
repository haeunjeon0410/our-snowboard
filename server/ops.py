"""변환 작업: 자료 분석, 체크한 항목에 필요한 AI 작업만 실행, 결과 파일(웹 문서·점자) 만들기."""
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from . import color, config, enrich, jobs, llm, pdf_out, render
from .extract import _needs_spacing

_POOL = ThreadPoolExecutor(max_workers=6)          # 쪽 단위 동시 처리
_FIG_POOL = ThreadPoolExecutor(max_workers=6)      # 한 쪽 안의 그림 설명 동시 처리 (쪽 풀과 분리해 서로 막지 않게)
TASKS: dict[str, dict] = {}

DEFAULTS = {"large": True, "contrast": False, "figures": True, "easy": False, "terms": False,
            "color": False, "colorType": "deutan", "braille": False,
            "pdf": True, "html": False,        # 받는 형식: 대부분의 학생은 PDF로 보므로 PDF가 기본
            "ai": True}   # 'ai'는 start()가 접속 코드를 확인해 정한다 (요청으로 받은 값은 쓰지 않는다)
TEXT_TYPES = ("paragraph", "heading", "list", "table")


# ───────────── 쪽 안의 내용 살피기 ─────────────
def _figures(pg):
    return [b for b in pg["blocks"] if b["type"] == "figure"]


def _scanned(pg):
    """글자가 없고 쪽 전체가 그림인 쪽 (스캔본)"""
    return not any(b["type"] in TEXT_TYPES for b in pg["blocks"]) and any(b.get("fullpage") for b in _figures(pg))


def _spacing_slots(pg):
    slots = []
    for b in pg["blocks"]:
        if b["type"] in ("paragraph", "heading") and b.get("spacing") == "restore":
            slots.append(b)
        elif b["type"] == "list":
            slots += [it for it in b["items"] if it.get("spacing") == "restore"]
    return slots


def _texts(pg):
    """(id, 글) 목록: 쉬운 한국어·영어 병기 대상"""
    out = []
    for b in pg["blocks"]:
        if b["type"] in ("paragraph", "heading"):
            out.append((b["id"], b["text"]))
        elif b["type"] == "list":
            out += [(f"{b['id']}:{i}", it["text"]) for i, it in enumerate(b["items"])]
    return out


def _color_count(job, b) -> int:
    """그림 안에 색으로 칠해진 영역이 몇 종류인지 (작게 줄여서 빠르게)"""
    if "colors" in b:
        return b["colors"]
    try:
        img = Image.open(jobs.job_dir(job["meta"]["id"]) / b["img"]).convert("RGB")
        img.thumbnail((420, 420))
        classes, _, _ = color.analyze(img, min_area=0.04)
        b["colors"] = len(classes)
        if b["colors"] >= 2:                         # 사진처럼 색이 번지는 그림은 '색이 칠해진 그림'으로 세지 않는다
            full = Image.open(jobs.job_dir(job["meta"]["id"]) / b["img"])
            if color.flat_fraction(full) < color.FLAT_MIN:
                b["colors"] = 0
    except Exception:
        b["colors"] = 0
    return b["colors"]


def analyze(job, ai_ok: bool | None = None) -> dict:
    """패널에 보여 줄 자료 요약. 해당 없는 항목은 패널에서 숨기거나 끄는 데 쓴다."""
    doc = job["doc"]
    figs = [b for pg in doc["pages"] for b in _figures(pg)]
    changed = any("colors" not in b for b in figs)
    todo = [b for b in figs if "colors" not in b]
    if len(todo) > 4:
        list(_FIG_POOL.map(lambda b: _color_count(job, b), todo))      # 그림이 많으면 색 종류 세기를 동시에
    colored = sum(1 for b in figs if _color_count(job, b) >= 2)
    if changed:
        jobs.save(job)
    return {"pages": doc["n_pages"], "figures": len(figs), "colorFigures": colored,
            "scanned": sum(1 for pg in doc["pages"] if _scanned(pg)),
            "ai": llm.available() if ai_ok is None else ai_ok,
            "codeRequired": bool(config.ACCESS_CODE) and llm.available() and not ai_ok}


# ───────────── 쪽 하나에 필요한 작업 ─────────────
def _needs_work(pg, o) -> bool:
    if _spacing_slots(pg):
        return True
    if _scanned(pg) and not pg.get("ocr_done"):
        return True
    if o["figures"] and any(not b.get("ai_desc") and not b.get("fullpage") for b in _figures(pg)):
        return True
    if o["easy"] and pg.get("easy") is None and _texts(pg):
        return True
    if o["terms"] and pg.get("terms") is None and _texts(pg):
        return True
    return False


def _work_page(job, pg, o) -> bool:
    """쪽 하나를 처리한다. AI 호출이 하나라도 실패하면 True (그 부분은 완료로 기록하지 않아 다음에 다시 시도된다)."""
    failed = False
    ai = o["ai"]
    d = jobs.job_dir(job["meta"]["id"])
    course = job["doc"].get("course", "")
    # 1) 띄어쓰기 (사라진 쪽만)
    slots = _spacing_slots(pg)
    if slots and ai:
        for obj, new in zip(slots, enrich.restore_spacing([s["text"] for s in slots])):
            if new is None:
                failed = True
                continue
            if new != obj["text"]:
                obj["raw_text"], obj["text"] = obj["text"], new
            obj["spacing"] = "done"
        for b in _figures(pg):
            if b.get("inner_text") and any(_needs_spacing(t) for t in b["inner_text"]):
                new = enrich.restore_spacing(b["inner_text"])
                failed |= None in new
                b["inner_text"] = [n if n is not None else t for n, t in zip(new, b["inner_text"])]
    if not ai:
        return failed
    # 2) 그림 설명 (체크했을 때, 또는 스캔본이라 글자를 읽어야 할 때)
    ctx = (f"[과목: {course}] " if course else "") + " ".join(b.get("text", "") for b in pg["blocks"] if b["type"] in ("heading", "paragraph"))
    scanned = _scanned(pg)
    if o["figures"] or scanned:
        todo = [b for b in _figures(pg) if not b.get("ai_desc") and not (b.get("fullpage") and not scanned)]
        results = list(_FIG_POOL.map(lambda b: enrich.describe_figure((d / b["img"]).read_bytes(), b.get("fig_kind", "image"), ctx, b.get("fullpage", False)), todo))
        for b, r in zip(todo, results):
            if "error" in r:
                failed = True
            else:
                b["ai_desc"], b["describe"] = r, "done"
        fig = next((b for b in _figures(pg) if b.get("fullpage") and b.get("ai_desc")), None)
        if scanned and fig and fig["ai_desc"].get("texts") and not pg.get("ocr_done"):
            idx = pg["blocks"].index(fig)
            pg["blocks"][idx:idx] = [{"type": "paragraph", "text": t, "ai": ["ocr"], "id": f"p{pg['n']}o{k + 1}"}
                                     for k, t in enumerate(fig["ai_desc"]["texts"]) if t.strip()]
            pg["ocr_done"] = True
    # 3) 쉬운 한국어 / 영어 병기
    items = _texts(pg)
    if o["easy"] and pg.get("easy") is None and items:
        res = enrich.easy_korean([t for _, t in items])
        if res is None:
            failed = True
        else:
            pg["easy"] = {i: r for (i, t), r in zip(items, res) if r != t}
    if o["terms"] and pg.get("terms") is None and items:
        res = enrich.english_terms([t for _, t in items])
        if res is None:
            failed = True
        else:
            pg["terms"] = res
    return failed


# ───────────── 작업 시작 / 진행 / 취소 ─────────────
def _clean_options(raw: dict) -> dict:
    o = dict(DEFAULTS)
    for k, v in (raw or {}).items():
        if k in o:
            o[k] = v if k == "colorType" else bool(v)
    if o["colorType"] not in ("deutan", "tritan"):
        o["colorType"] = "deutan"
    if not (o["pdf"] or o["html"] or o["braille"]):      # 받는 형식이 하나도 없으면 PDF
        o["pdf"] = True
    if not o["html"]:                                    # 쉬운 한국어·영어 병기는 웹 문서에만 들어가므로 AI도 부르지 않는다
        o["easy"] = o["terms"] = False
    return o


def start(job, raw_options: dict, ai_ok: bool | None = None) -> str:
    o = _clean_options(raw_options)
    o["ai"] = llm.available() if ai_ok is None else ai_ok       # 이 요청이 AI를 써도 되는가 (접속 코드 확인 결과)
    tid = uuid.uuid4().hex[:12]
    TASKS[tid] = {"id": tid, "job": job["meta"]["id"], "status": "running", "done": 0, "total": 0, "step": "자료를 살펴보는 중",
                  "files": [], "error": "", "note": "", "cancel": False, "failed": 0, "t": time.time(), "lock": threading.Lock()}
    threading.Thread(target=_run, args=(job, o, TASKS[tid]), daemon=True).start()
    return tid


def prune_tasks(max_age_s: float) -> int:
    """끝난 지 오래된 작업 기록을 지운다 (서버를 오래 켜 둬도 메모리가 계속 늘지 않게)."""
    old = [tid for tid, t in list(TASKS.items()) if t["status"] != "running" and time.time() - t["t"] > max_age_s]
    for tid in old:
        TASKS.pop(tid, None)
    return len(old)


def _safe_name(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', " ", s or "").strip()
    return re.sub(r"\s+", " ", s)[:80] or "교재"


def _run(job, o, task):
    try:
        doc = job["doc"]
        work = [pg for pg in doc["pages"] if _needs_work(pg, o)]
        task["total"] = len(work)
        if work:
            verbs = []
            if any(_spacing_slots(pg) for pg in work):
                verbs.append("글자를 정리하")
            if o["figures"] or any(_scanned(pg) for pg in work):
                verbs.append("그림을 살펴보")
            if o["easy"]:
                verbs.append("쉬운 한국어로 바꾸")
            if o["terms"]:
                verbs.append("영어 용어를 찾")
            task["step"] = ("고 ".join(verbs) + "는 중") if verbs else "자료를 정리하는 중"
            if not o["ai"]:
                task["note"] = "AI를 쓸 수 없어서 AI 항목은 건너뛰었어요"

            def one(pg):
                if task["cancel"]:
                    return
                try:
                    if _work_page(job, pg, o):
                        with task["lock"]:
                            task["failed"] += 1
                except Exception:                  # 한 쪽이 잘못돼도 나머지 쪽은 계속 처리한다
                    traceback.print_exc()
                    with task["lock"]:
                        task["failed"] += 1
                finally:
                    with task["lock"]:
                        task["done"] += 1
            list(_POOL.map(one, work))
            jobs.save(job)
            if task["failed"] and o["ai"]:
                task["note"] = f"{task['failed']}쪽은 AI가 응답하지 않아 건너뛰었어요. 다시 변환하면 그 부분만 이어서 해요"
        if task["cancel"]:
            task["status"] = "cancelled"
            return
        task["step"] = "파일을 만드는 중"
        meta = job["meta"]
        base = _safe_name(meta.get("title") or Path(meta["filename"]).stem)
        out_dir = jobs.job_dir(meta["id"]) / "out" / task["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        title = meta.get("title") or Path(meta["filename"]).stem
        files = []
        if o["pdf"] and not pdf_out.available():            # 서버에 한글 글꼴이 없으면 PDF 대신 웹 문서로
            o["pdf"], o["html"] = False, True
            task["note"] = (task["note"] + " / " if task["note"] else "") + "PDF를 만들 한글 글꼴이 없어 웹 문서로 만들었어요"
        if o["pdf"]:
            pdf_path = out_dir / f"{base} (맞춤).pdf"
            pdf_path.write_bytes(pdf_out.to_pdf(doc, jobs.job_dir(meta["id"]), o, title=title))
            files.append({"kind": "pdf", "name": pdf_path.name, "path": str(pdf_path)})
        if o["html"]:
            html_path = out_dir / f"{base} (맞춤).html"
            html_path.write_text(render.to_html(doc, jobs.job_dir(meta["id"]), o, title=title), encoding="utf-8")
            files.append({"kind": "html", "name": html_path.name, "path": str(html_path)})
        if o["braille"]:
            brf = out_dir / f"{base} (점자).brf"
            brf.write_text(render.to_brf(doc, o), encoding="utf-8")
            files.append({"kind": "brf", "name": brf.name, "path": str(brf)})
        task["files"] = files
        task["status"] = "done"
    except Exception as e:  # 화면에는 짧게, 자세한 것은 서버 창에
        traceback.print_exc()
        task["status"], task["error"] = "error", str(e)[:120]
