"""샘플 전체를 실제 서버로 변환해 성공률·시간·AI 사용량을 잰다. 실행: 서버를 켠 뒤 python -m eval.stress_run [설정이름]
설정: read(그림 읽기·점자, 기본) / low(저시력, AI 없음). 결과는 output/_eval/stress_<설정>.json"""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = "http://localhost:8790"
PRESETS = {"read": {"figures": True, "braille": True, "pdf": True}, "low": {"large": True, "contrast": True, "read": True, "html": True, "pdf": False}}
USAGE = ROOT / "server" / ".cache" / "usage.jsonl"


def _usage():
    n = tin = tout = 0
    if USAGE.exists():
        for line in USAGE.read_text(encoding="utf-8").splitlines():
            r = json.loads(line); n += 1; tin += r["in"]; tout += r["out"]
    return n, tin, tout


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "read"
    opts = PRESETS[name]
    seen, rows = set(), []
    for p in sorted((ROOT / "samples").glob("*.pdf")):
        h = hashlib.sha1(p.read_bytes()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        u0 = _usage(); t0 = time.time()
        row = {"file": p.name, "status": "error", "error": ""}
        try:
            q = urllib.parse.urlencode({"filename": p.name, "course": p.stem, "title": p.stem, "light": 1})
            r = json.load(urllib.request.urlopen(urllib.request.Request(f"{B}/api/prepare?{q}", data=p.read_bytes(), method="POST", headers={"Content-Type": "application/pdf"}), timeout=600))
            jid, pages = r["job"], r["info"]["pages"]
            tid = json.load(urllib.request.urlopen(urllib.request.Request(f"{B}/api/jobs/{jid}/make", data=json.dumps(opts).encode(), method="POST", headers={"Content-Type": "application/json"}), timeout=60))["task"]
            while True:
                s = json.load(urllib.request.urlopen(f"{B}/api/tasks/{tid}", timeout=60))
                if s["status"] != "running":
                    break
                time.sleep(2)
            row.update(status=s["status"], error=s["error"], note=s["note"], pages=pages, files=[f["name"] for f in s["files"]])
        except Exception as e:
            row["error"] = str(e)[:120]
        u1 = _usage()
        row.update(sec=round(time.time() - t0, 1), calls=u1[0] - u0[0], tokens_in=u1[1] - u0[1], tokens_out=u1[2] - u0[2])
        rows.append(row)
        print(f"{p.name[:30]:30} {row['status']:6} {row.get('pages', 0):3}쪽 {row['sec']:6}초 AI호출 {row['calls']:3} 토큰 {row['tokens_in']}/{row['tokens_out']} {row['error'] or row.get('note', '')[:50]}", flush=True)
    ok = [r for r in rows if r["status"] == "done"]
    pages = sum(r.get("pages", 0) for r in ok)
    out = {"preset": name, "files": len(rows), "ok": len(ok), "pages": pages, "seconds": round(sum(r["sec"] for r in ok), 1),
           "calls": sum(r["calls"] for r in rows), "tokens_in": sum(r["tokens_in"] for r in rows), "tokens_out": sum(r["tokens_out"] for r in rows), "rows": rows}
    (ROOT / "output" / "_eval" / f"stress_{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n성공 {out['ok']}/{out['files']} · {out['pages']}쪽 · 쪽당 {out['seconds'] / max(1, pages):.2f}초 · AI 호출 {out['calls']} · 토큰 {out['tokens_in']:,}/{out['tokens_out']:,}")


if __name__ == "__main__":
    main()
