"""올린 PDF 저장소. 올릴 때는 글자 추출만 하고, AI 작업은 변환할 때 체크한 항목에서만 한다 (ops.py)."""
import hashlib
import json
import shutil
import threading
import time
from pathlib import Path

from . import config
from .extract import VER as EXTRACT_VER, extract

_lock = threading.Lock()
_jobs: dict[str, dict] = {}   # id -> {"meta", "doc", "lock"}
_build_locks: dict[str, threading.Lock] = {}   # 같은 파일을 동시에 올려도 한 번만 만들게


def job_dir(jid: str) -> Path:
    return config.DATA_DIR / jid


def save(job):
    d = job_dir(job["meta"]["id"])
    with job["lock"]:
        for attempt in range(5):                                  # 다른 변환이 문서를 고치는 순간과 겹치면 직렬화가 한 번 실패할 수 있어서 다시 시도한다
            try:
                payload = json.dumps(job["doc"], ensure_ascii=False)
                break
            except RuntimeError:
                if attempt == 4:
                    raise
                time.sleep(0.05)
        tmp = d / "doc.json.tmp"
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(d / "doc.json")
        (d / "meta.json").write_text(json.dumps(job["meta"], ensure_ascii=False), encoding="utf-8")


def create(pdf_bytes: bytes, filename: str, course: str = "", title: str = "") -> str:
    """같은 파일이면 이미 처리한 것을 그대로 쓴다 (AI 결과도 함께 재사용)."""
    jid = hashlib.sha1(pdf_bytes).hexdigest()[:10]
    with _lock:
        j = _jobs.get(jid)
        if j and j["doc"].get("ver") != EXTRACT_VER:           # 예전 방식으로 뽑은 자료: 새로 뽑는다 (AI 응답은 그림이 같으면 저장해 둔 것을 쓰므로 크레딧은 거의 들지 않는다)
            _jobs.pop(jid, None)
            j = None
        if j:
            j["meta"]["created"] = time.time()          # 다시 올리면 보관 시간을 새로 센다
            changed = False
            for k, v in (("course", course), ("title", title)):
                if v and not j["meta"].get(k):                 # 이미 있는 과목명·제목은 다른 사람이 같은 파일을 올려도 덮어쓰지 않는다
                    j["meta"][k] = v
                    changed = True
            if changed:
                j["doc"]["course"] = j["meta"].get("course", "")
                save(j)
            return jid
    with _lock:
        build = _build_locks.setdefault(jid, threading.Lock())
    with build:
        with _lock:
            if jid in _jobs:                       # 기다리는 사이에 다른 요청이 이미 만들었다
                return jid
        d = job_dir(jid)
        d.mkdir(parents=True, exist_ok=True)
        (d / "original.pdf").write_bytes(pdf_bytes)
        doc = extract(d / "original.pdf", d)
        doc["course"] = course
        meta = {"id": jid, "filename": filename, "course": course, "title": title, "created": time.time(), "n_pages": doc["n_pages"]}
        job = {"meta": meta, "doc": doc, "lock": threading.Lock(), "run": threading.Lock()}
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


def start_cleanup_loop(ttl_hours: float, every_s: int = 600, also=None):
    """also: 같은 주기로 같이 부를 함수 (예: 끝난 작업 기록 지우기)"""
    if ttl_hours <= 0:
        return

    def loop():
        while True:
            try:
                cleanup(ttl_hours)
                if also:
                    also()
            except Exception:
                pass
            time.sleep(every_s)
    threading.Thread(target=loop, daemon=True).start()


def prune_outputs(days: float = 3.0) -> int:
    """오래된 변환 결과 파일(out/)과 PPT→PDF 보관본을 지운다 (내 컴퓨터에서 오래 쓰면 디스크가 계속 차는 것을 막는다). 올린 자료와 AI 결과는 지우지 않는다."""
    import shutil
    limit, n = time.time() - days * 86400, 0
    try:
        for d in config.DATA_DIR.iterdir():
            targets = [d / "out"] if not d.name.startswith("_") else ([d] if d.name == "_converted" else [])
            for t in targets:
                if not t.exists():
                    continue
                for item in (list(t.iterdir()) if t.is_dir() else []):
                    try:
                        if item.stat().st_mtime < (limit if d.name != "_converted" else time.time() - 14 * 86400):
                            shutil.rmtree(item) if item.is_dir() else item.unlink()
                            n += 1
                    except Exception:
                        pass
    except Exception:
        pass
    return n


def get(jid: str):
    with _lock:
        return _jobs.get(jid)


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
        _jobs[meta["id"]] = {"meta": meta, "doc": doc, "lock": threading.Lock(), "run": threading.Lock()}
