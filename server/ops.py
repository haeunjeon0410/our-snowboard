"""변환 작업: 자료 분석, 체크한 항목에 필요한 AI 작업만 실행, 결과 파일(웹 문서·점자) 만들기."""
import json
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from . import color, config, enrich, jobs, llm, pdf_out, pdf_read, render
from .extract import _needs_spacing

_POOL = ThreadPoolExecutor(max_workers=12)         # 쪽 단위 동시 처리 (AI 서버는 동시 32개까지 오류 없이 받았다)
_FIG_POOL = ThreadPoolExecutor(max_workers=20)     # 한 쪽 안의 그림 설명·글 풀이 동시 처리 (쪽 풀과 분리해 서로 막지 않게)
TASKS: dict[str, dict] = {}

DEFAULTS = {"read": False, "large": True, "contrast": False, "figures": True, "easy": False, "terms": False,
            "color": False, "colorType": "deutan", "braille": False,
            "pdf": True, "readpdf": False, "html": False,   # 받는 형식: 원본 PDF(기본) / 읽기용 PDF / 읽기용 웹 문서 / 점자
            "ai": True}   # 'ai'는 start()가 접속 코드를 확인해 정한다 (요청으로 받은 값은 쓰지 않는다)
_FILE_TAGS = [("large", "큰글씨"), ("read", "소리읽기"), ("contrast", "고대비"), ("figures", "그림설명"),
              ("easy", "쉬운말"), ("terms", "영어용어"), ("color", "색각이상"), ("braille", "점자")]


def _file_tag(o) -> str:
    """파일 이름 끝에 붙일 말: 고른 기능을 가운데 점(·)으로 이어 쓴다. 프리셋과 같으면 프리셋 이름."""
    web = o["html"] or o["readpdf"]
    on = [n for k, n in _FILE_TAGS if o.get(k) and (web or k not in ("large", "read"))]
    if set(on) == {"큰글씨", "고대비", "소리읽기"}:
        return "저시력"
    if set(on) == {"쉬운말", "영어용어"}:
        return "교환학생"
    return "·".join(on) or "원본"


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


def analyze(job, ai_ok: bool | None = None, light: bool = False) -> dict:
    """패널에 보여 줄 자료 요약. 해당 없는 항목은 패널에서 숨기거나 끄는 데 쓴다."""
    doc = job["doc"]
    figs = [b for pg in doc["pages"] for b in _figures(pg)]
    if light:        # 바로 변환할 때는 항목 표시용 색 도식 수를 세지 않는다 (기다리는 시간 단축)
        return {"pages": doc["n_pages"], "figures": len(figs), "colorFigures": None,
                "scanned": sum(1 for pg in doc["pages"] if _scanned(pg)),
                "ai": llm.available() if ai_ok is None else ai_ok,
                "codeRequired": bool(config.ACCESS_CODE) and llm.available() and not ai_ok}
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
    if o["easy"] and pg.get("easy_words") is None and _texts(pg):
        return True
    if o["terms"] and pg.get("terms") is None and _texts(pg):
        return True
    return False


MIN_TEXT_FOR_AI = 25          # 한 쪽의 글이 이보다 짧으면 단어 뜻·영어 용어는 AI 없이 건너뛴다
MAX_AI_FIGURES = 150          # 한 번의 변환에서 AI가 설명할 그림의 상한 (아주 큰 자료 하나가 크레딧을 한꺼번에 쓰지 않게)


def _start_text_jobs(pg, o) -> dict:
    """쪽의 글을 풀이하는 AI 호출(단어 뜻, 영어 용어)을 동시에 시작하고 {결과 키: 진행 중인 작업}을 돌려준다."""
    items = _texts(pg)
    if items and sum(len(t) for _, t in items) < MIN_TEXT_FOR_AI:        # 제목만 있는 쪽 등은 풀이할 것이 없으니 AI를 부르지 않는다 (크레딧 절약)
        for key, want in (("easy_words", o["easy"]), ("terms", o["terms"])):
            if want and pg.get(key) is None:
                pg[key] = []
        items = []
    texts = [t for _, t in items]
    running = {}
    want_easy = o["easy"] and pg.get("easy_words") is None and items
    want_terms = o["terms"] and pg.get("terms") is None and items
    if want_easy and want_terms:                            # 둘 다 필요하면 같은 글을 두 번 보내지 않고 한 번에 묻는다
        running["both"] = _FIG_POOL.submit(enrich.words_and_terms, texts)
    elif want_easy:
        running["easy_words"] = _FIG_POOL.submit(enrich.easy_words, texts)
    elif want_terms:
        running["terms"] = _FIG_POOL.submit(enrich.english_terms, texts)
    return running


def _work_page(job, pg, o, budget: dict | None = None) -> bool:
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
    early = None if scanned else _start_text_jobs(pg, o)        # 단어 뜻·영어 용어는 그림 설명을 기다리지 않고 동시에 시작한다 (스캔본은 읽어 낸 글이 생긴 뒤에)
    if o["figures"] or scanned:
        todo = [b for b in _figures(pg) if not b.get("ai_desc") and not (b.get("fullpage") and not scanned)]
        if budget is not None and todo:                     # 남은 그림 수만큼만 설명한다
            with budget["lock"]:
                take = max(0, min(len(todo), budget["figs"]))
                budget["figs"] -= take
                if take < len(todo):
                    budget["cut"] = True
            todo = todo[:take]
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
    if early is None:
        early = _start_text_jobs(pg, o)
    for key, fut in early.items():
        res = fut.result()
        if key == "both":
            for k, v in zip(("easy_words", "terms"), res):
                if v is None:
                    failed = True
                else:
                    pg[k] = v
            continue
        if res is None:
            failed = True
        else:
            pg[key] = res
    return failed


# ───────────── 작업 시작 / 진행 / 취소 ─────────────
def _clean_options(raw: dict) -> dict:
    o = dict(DEFAULTS)
    for k, v in (raw or {}).items():
        if k in o:
            o[k] = v if k == "colorType" else bool(v)
    if o["colorType"] not in ("deutan", "tritan"):
        o["colorType"] = "deutan"
    if not (o["pdf"] or o["readpdf"] or o["html"] or o["braille"]):      # 받는 형식이 하나도 없으면 원본 PDF
        o["pdf"] = True
    return o


_START_LOCK = threading.Lock()


def start(job, raw_options: dict, ai_ok: bool | None = None) -> str:
    o = _clean_options(raw_options)
    o["ai"] = llm.available() if ai_ok is None else ai_ok       # 이 요청이 AI를 써도 되는가 (접속 코드 확인 결과)
    sig = json.dumps(o, sort_keys=True)
    with _START_LOCK:
        prune_tasks(6 * 3600)                                   # 끝난 지 오래된 작업 기록은 치운다 (로컬에서는 따로 치우는 곳이 없어 메모리가 계속 늘었다)
        for t in TASKS.values():                                # 같은 자료를 같은 항목으로 이미 변환 중이면(더블 클릭·재시도) 새로 시작하지 않고 그 작업에 이어 붙는다
            if t["status"] == "running" and t["job"] == job["meta"]["id"] and t.get("sig") == sig:
                return t["id"]
        tid = uuid.uuid4().hex[:12]
        TASKS[tid] = {"id": tid, "job": job["meta"]["id"], "sig": sig, "status": "running", "done": 0, "total": 0, "step": "자료를 살펴보는 중",
                      "files": [], "error": "", "note": "", "cancel": False, "failed": 0, "t": time.time(), "lock": threading.Lock()}
    threading.Thread(target=_run, args=(job, o, TASKS[tid]), daemon=True).start()
    return tid


def prune_tasks(max_age_s: float) -> int:
    """끝난 지 오래된 작업 기록을 지운다 (서버를 오래 켜 둬도 메모리가 계속 늘지 않게)."""
    old = [tid for tid, t in list(TASKS.items()) if t["status"] != "running" and time.time() - t["t"] > max_age_s]
    for tid in old:
        TASKS.pop(tid, None)
    return len(old)


def _ensure_colors(job, o):
    """'바로 변환'에서는 색 도식 수를 세지 않으므로, 요약·비교가 그 값을 쓰기 전에 빠진 것만 채운다 (색 구분을 골랐을 때만)."""
    if not o["color"]:
        return
    todo = [b for pg in job["doc"]["pages"] for b in _figures(pg) if "colors" not in b]
    if todo:
        list(_FIG_POOL.map(lambda b: _color_count(job, b), todo))
        jobs.save(job)


def _summary(job, o) -> list[str]:
    """이번 변환에서 사용자가 고른 항목의 결과만 짧게 (센 값만 쓴다). 고르지 않은 일은 적지 않고, 원본 PDF의 글자에 적용되지 않는 일도 적지 않는다."""
    doc = job["doc"]
    reflow = o["html"] or o["readpdf"] or o["braille"]
    figs = [b for pg in doc["pages"] for b in _figures(pg) if b.get("ai_desc") and not b.get("fullpage")]
    restored = sum(1 for pg in doc["pages"] for b in pg["blocks"] if b["type"] in ("paragraph", "heading") and b.get("raw_text") and b["raw_text"] != b["text"])
    ocr = sum(1 for pg in doc["pages"] if pg.get("ocr_done"))
    easy = sum(len(pg.get("easy_words") or []) for pg in doc["pages"])
    terms = sum(len(pg.get("terms") or []) for pg in doc["pages"])
    colored = sum(1 for pg in doc["pages"] for b in _figures(pg) if b.get("colors", 0) >= 2)
    nfig = sum(len(_figures(pg)) for pg in doc["pages"])
    out = []
    if restored and reflow:
        out.append(f"사라진 띄어쓰기를 {restored}개 문단에서 바로잡았어요")
    if ocr:
        out.append(f"스캔된 {ocr}쪽의 글자를 읽어 냈어요")
    if o["figures"]:
        out.append(f"그림 {len(figs)}개에 설명을 붙였어요" if figs else ("설명을 붙일 그림이 없었어요" if not nfig else "그림 설명은 AI를 쓸 수 없어 건너뛰었어요"))
    if o["color"]:
        out.append(f"색으로 칠한 도식 {colored}개를 구분하기 쉽게 바꿨어요" if colored else "색으로 구분된 도식이 없어서 바꾼 곳은 없어요")
    if o["easy"]:
        out.append(f"어려운 단어 {easy}개에 쉬운 말을 붙였어요" if easy else "풀이를 붙일 어려운 단어가 없었어요")
    if o["terms"]:
        out.append(f"전문 용어 {terms}개에 영어를 붙였어요" if terms else "영어를 붙일 전문 용어가 없었어요")
    if o["braille"]:
        out.append(f"{doc['n_pages']}쪽을 한글 점자로 옮겼어요")
    if o["contrast"]:
        out.append("검정 바탕의 고대비로 바꿨어요")
    if o["large"] and (o["html"] or o["readpdf"]):
        out.append("큰 글씨로 다시 정리했어요")
    if o.get("read") and o["html"]:
        out.append("문서 안에 소리로 읽어 주기를 넣었어요")
    if not out:
        out.append("고른 항목이 없어서 원본 그대로 받았어요")
    return out[:7]


def _compares(job, o) -> list[dict]:
    """고른 항목마다 원본과 달라진 대표 장면 하나씩 (실제 변환 결과에서 뽑는다)."""
    import base64
    import io
    from . import braille_ko as B
    doc = job["doc"]
    d = jobs.job_dir(job["meta"]["id"])
    out = []

    def thumb(img, size=(220, 150)):
        im = img.convert("RGB")
        im.thumbnail(size)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=74)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    def sample():
        for pg in doc["pages"]:
            for b in pg["blocks"]:
                if b["type"] == "paragraph" and 24 <= len(b["text"]) <= 160:
                    return pg["n"], b["text"]
        for pg in doc["pages"]:                                        # 짧은 슬라이드 문장도 허용
            for b in pg["blocks"]:
                if b["type"] in ("paragraph", "heading") and 10 <= len(b["text"]) <= 160:
                    return pg["n"], b["text"]
        return None, ""

    def add(label, **kw):
        out.append({"label": label, **kw})

    reflow = o["html"] or o["readpdf"] or o["braille"]
    try:
        if o["figures"]:                                            # 그림 → 그림 설명
            for pg in doc["pages"]:
                for b in _figures(pg):
                    desc = (b.get("ai_desc") or {}).get("desc")
                    if desc and not b.get("fullpage"):
                        add("그림 설명", page=pg["n"], beforeImg=thumb(Image.open(d / b["img"])), after=desc[:130])
                        raise StopIteration
    except StopIteration:
        pass
    try:
        if o["color"]:                                              # 색 도식 → 보정·무늬
            for pg in doc["pages"]:
                for b in _figures(pg):
                    if b.get("colors", 0) >= 2:
                        res = render._fix_all(doc, d, o).get(b["id"])         # 파일을 만들 때 계산해 둔 보정본을 쓴다
                        if res and res[1]:
                            add("색 구분", page=pg["n"], beforeImg=thumb(Image.open(d / b["img"])), afterImg=thumb(res[0]))
                            raise StopIteration
    except StopIteration:
        pass
    except Exception:
        traceback.print_exc()
    if reflow:                                                      # 붙은 글자 → 띄어쓰기
        for pg in doc["pages"]:
            hit = next((b for b in pg["blocks"] if b["type"] in ("paragraph", "heading") and b.get("raw_text") and b["raw_text"] != b["text"] and len(b["text"]) >= 14), None)
            if hit:
                add("띄어쓰기", page=pg["n"], before=hit["raw_text"][:70], after=hit["text"][:70])
                break
    if o["easy"]:                                                   # 어려운 단어 → 단어(쉬운 말)
        for pg in doc["pages"]:
            words = pg.get("easy_words") or []
            hit = next(((t, w) for _, t in _texts(pg) for w in words if w["ko"] in t), None)
            if hit:
                t, w = hit
                i = t.find(w["ko"]) + len(w["ko"])
                lo = max(0, i - 30)
                add("단어 뜻", page=pg["n"], before=t[lo:i + 20], after=t[lo:i] + f"({w['easy']})" + t[i:i + 20])
                break
    if o["terms"]:                                                  # 용어 → 용어(영어)
        for pg in doc["pages"]:
            hit = next(((t, tm) for _, t in _texts(pg) for tm in (pg.get("terms") or []) if tm["ko"] in t), None)
            if hit:
                t, tm = hit
                i = t.find(tm["ko"]) + len(tm["ko"])
                lo = max(0, i - 30)
                add("영어 용어", page=pg["n"], before=t[lo:i + 20], after=t[lo:i] + f"({tm['en']})" + t[i:i + 20])
                break
    n, text = sample()
    if text:
        if o["braille"]:                                            # 글 → 점자
            add("점자", page=n, before=text[:36], after=B.encode(text[:36]))
        if o["contrast"]:                                           # 보통 → 고대비
            add("고대비", page=n, before=text[:60], after=text[:60], style="hc")
        if o["large"] and (o["html"] or o["readpdf"]):              # 보통 → 큰 글씨
            add("큰 글씨", page=n, before=text[:50], after=text[:50], style="large")
    try:
        scan = next((b for pg in doc["pages"] if pg.get("ocr_done") for b in _figures(pg) if b.get("fullpage") and (b.get("ai_desc") or {}).get("texts")), None)
        if scan:                                                    # 스캔 그림 → 읽어 낸 글자
            add("스캔본 글자 읽기", beforeImg=thumb(Image.open(d / scan["img"])), after=" ".join(scan["ai_desc"]["texts"])[:130])
    except Exception:
        pass
    return out


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

            budget = {"figs": MAX_AI_FIGURES, "lock": threading.Lock(), "cut": False}

            def one(pg):
                if task["cancel"]:
                    return
                try:
                    if _work_page(job, pg, o, budget):
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
            if budget["cut"]:
                task["note"] = (task["note"] + " / " if task["note"] else "") + f"그림이 많아서 앞쪽 {MAX_AI_FIGURES}개만 설명했어요"
            if task["failed"] and o["ai"]:
                task["note"] = (task["note"] + " / " if task["note"] else "") + f"{task['failed']}쪽은 AI가 응답하지 않아 건너뛰었어요. 다시 변환하면 그 부분만 이어서 해요"
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
        if (o["pdf"] or o["readpdf"]) and not pdf_out.available():            # 서버에 한글 글꼴이 없으면 PDF 대신 웹 문서로
            o["pdf"], o["readpdf"], o["html"] = False, False, True
            task["note"] = (task["note"] + " / " if task["note"] else "") + "PDF를 만들 한글 글꼴이 없어 웹 문서로 만들었어요"
        brf_text = render.to_brf(doc, o) if o["braille"] else None
        tag = _file_tag(o)
        if o["pdf"]:
            pdf_path = out_dir / f"{base} ({tag}).pdf"
            brf_att = (f"{base} (점자).brf", brf_text) if brf_text else None       # PDF 한 파일에도 점자가 들어 있게
            pdf_path.write_bytes(pdf_out.to_pdf(doc, jobs.job_dir(meta["id"]), o, title=title, brf=brf_att))
            files.append({"kind": "pdf", "name": pdf_path.name, "path": str(pdf_path)})
        if o["readpdf"]:
            rp = out_dir / f"{base} ({tag}).pdf"
            rp.write_bytes(pdf_read.to_read_pdf(doc, jobs.job_dir(meta["id"]), o, title=title))
            files.append({"kind": "readpdf", "name": rp.name, "path": str(rp)})
        if o["html"]:
            html_path = out_dir / f"{base} ({tag}).html"
            html_path.write_text(render.to_html(doc, jobs.job_dir(meta["id"]), o, title=title), encoding="utf-8")
            files.append({"kind": "html", "name": html_path.name, "path": str(html_path)})
        if o["braille"]:
            brf = out_dir / f"{base} (점자).brf"
            brf.write_bytes(render.brf_bytes(brf_text))
            files.append({"kind": "brf", "name": brf.name, "path": str(brf)})
        task["files"] = files
        try:
            _ensure_colors(job, o)
            task["summary"], task["compare"] = _summary(job, o), _compares(job, o)
            if task.get("note"):                                    # AI가 응답하지 않아 건너뛴 일 등은 숨기지 않고 알린다
                task["summary"] = (task["summary"] + [task["note"]])[:8]
        except Exception:
            traceback.print_exc()
        task["status"] = "done"
    except Exception as e:  # 화면에는 짧게, 자세한 것은 서버 창에
        traceback.print_exc()
        msg = str(e)
        task["status"], task["error"] = "error", (msg[:120] if re.search("[가-힣]", msg) else "변환 중 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요")
