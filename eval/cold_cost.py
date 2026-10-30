"""AI 캐시·변환 결과를 비운 임시 폴더에서 샘플 몇 개를 변환해, 파일 한 건에 드는 AI 토큰을 잰다. 실행: python -m eval.cold_cost 파일명..."""
import json
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="snow_cold_"))
import server.config as cfg  # noqa: E402
cfg.PORT = 8791
cfg.CACHE_DIR = tmp / "cache"
cfg.DATA_DIR = tmp / "output"
for d in (cfg.CACHE_DIR / "llm", cfg.DATA_DIR):
    d.mkdir(parents=True, exist_ok=True)
import uvicorn  # noqa: E402
from server.main import app  # noqa: E402

PORT = 8791
srv = uvicorn.Server(uvicorn.Config(app, port=PORT, log_level="warning"))
threading.Thread(target=srv.run, daemon=True).start()
time.sleep(5)
B = f"http://localhost:{PORT}"
USAGE = cfg.CACHE_DIR / "usage.jsonl"
P = {"gpt-6-luna": (0.1, 0.5), "gemini-3.5-flash-lite": (0.3, 2.5)}


def usage():
    rows = [json.loads(x) for x in USAGE.read_text(encoding="utf-8").splitlines() if x.strip()] if USAGE.exists() else []
    return sum(r["in"] for r in rows), sum(r["out"] for r in rows), sum(r["in"] / 1000 * P.get(r["model"], (0.3, 2.5))[0] + r["out"] / 1000 * P.get(r["model"], (0.3, 2.5))[1] for r in rows), len(rows)


out = []
for name in sys.argv[1:]:
    p = ROOT / "samples" / name
    u0 = usage(); t0 = time.time()
    q = urllib.parse.urlencode({"filename": p.name, "course": p.stem, "title": p.stem, "light": 1})
    r = json.load(urllib.request.urlopen(urllib.request.Request(f"{B}/api/prepare?{q}", data=p.read_bytes(), method="POST", headers={"Content-Type": "application/pdf"}), timeout=600))
    jid, pages = r["job"], r["info"]["pages"]
    tid = json.load(urllib.request.urlopen(urllib.request.Request(f"{B}/api/jobs/{jid}/make", data=json.dumps({"figures": True, "braille": True, "pdf": True}).encode(), method="POST", headers={"Content-Type": "application/json"}), timeout=60))["task"]
    while True:
        s = json.load(urllib.request.urlopen(f"{B}/api/tasks/{tid}", timeout=60))
        if s["status"] != "running":
            break
        time.sleep(2)
    u1 = usage()
    row = {"file": name, "status": s["status"], "pages": pages, "sec": round(time.time() - t0, 1), "calls": u1[3] - u0[3],
           "tokens_in": u1[0] - u0[0], "tokens_out": u1[1] - u0[1], "credits": round(u1[2] - u0[2], 2)}
    row["won"] = round(row["credits"] * 2, 1)
    print(row, flush=True)
    out.append(row)
(ROOT / "output" / "_eval" / "cold_cost.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
