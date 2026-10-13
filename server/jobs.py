"""올린 PDF 저장소. 올릴 때는 글자 추출만 하고, AI 작업은 변환할 때 체크한 항목에서만 한다 (ops.py)."""
import hashlib
import json
import shutil
import threading
import time
from pathlib import Path

from . import config
from .extract import extract

_lock = threading.Lock()
_jobs: dict[str, dict] = {}   # id -> {"meta", "doc", "lock"}


def job_dir(jid: str) -> Path:
    return config.DATA_DIR / jid


def save(job):
    d = job_dir(job["meta"]["id"])
    with job["lock"]:
        tmp = d / "doc.json.tmp"
        tmp.write_text(json.dumps(job["doc"], ensure_ascii=False), encoding="utf-8")
        tmp.replace(d / "doc.json")
        (d / "meta.json").write_text(json.dumps(job["meta"], ensure_ascii=False), encoding="utf-8")


def create(pdf_bytes: bytes, filename: str, course: str = "", title: str = "") -> str:
    """같은 파일이면 이미 처리한 것을 그대로 쓴다 (AI 결과도 함께 재사용)."""
    jid = hashlib.sha1(pdf_bytes).hexdigest()[:10]
    with _lock:
        j = _jobs.get(jid)
        if j:
            j["meta"]["created"] = time.time()          # 다시 올리면 보관 시간을 새로 센다
            changed = False
            for k, v in (("course", course), ("title", title)):
                if v and j["meta"].get(k) != v:
                    j["meta"][k] = v
                    changed = True
            if changed:
                j["doc"]["course"] = j["meta"].get("course", "")
                save(j)
            return jid
    d = job_dir(jid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "original.pdf").write_bytes(pdf_bytes)
    doc = extract(d / "original.pdf", d)
    doc["course"] = course
    meta = {"id": jid, "filename": filename, "course": course, "title": title, "created": time.time(), "n_pages": doc["n_pages"]}
    job = {"meta": meta, "doc": doc, "lock": threading.Lock()}
    with _lock:
        _jobs[jid] = job
    save(job)
    return jid


def cleanup(ttl_hours: float) -> int:
    """올린 지 ttl_hours가 지난 자료(원본·변환 결과)를 지운다. 공개 서버에서 남의 강의 파일을 오래 들고 있지 않기 위해."""
    if ttl_hours <= 0:
        return 0
    limit = time.time() - ttl_hours * 3600
    with _lock:
        old = [jid for jid, j in _jobs.items() if j["meta"].get("created", 0) < limit]
        for jid in old:
            del _jobs[jid]
    for jid in old:
        shutil.rmtree(job_dir(jid), ignore_errors=True)
    return len(old)


def start_cleanup_loop(ttl_hours: float, every_s: int = 600):
    if ttl_hours <= 0:
        return

    def loop():
        while True:
            try:
                cleanup(ttl_hours)
            except Exception:
                pass
            time.sleep(every_s)
    threading.Thread(target=loop, daemon=True).start()


def get(jid: str):
    with _lock:
        return _jobs.get(jid)


def listing():
    with _lock:
        items = [j["meta"] for j in _jobs.values()]
    return sorted(items, key=lambda m: -m["created"])


def load_existing():
    """서버를 다시 켰을 때 이전에 올린 자료를 불러온다."""
    for d in config.DATA_DIR.iterdir():
        mp, dp = d / "meta.json", d / "doc.json"
        if d.name.startswith("_") or not (mp.exists() and dp.exists()):
            continue
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
            doc = json.loads(dp.read_text(encoding="utf-8"))
        except Exception:
            continue
        _jobs[meta["id"]] = {"meta": meta, "doc": doc, "lock": threading.Lock()}
