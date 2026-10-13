"""서버의 '올리기 → 변환 → 파일 받기' 전체 흐름을 시험한다. 실행: python eval/e2e_api.py <PDF 경로> [옵션 JSON]
서버(localhost:8790)가 켜져 있어야 한다."""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://localhost:8790"
pdf = sys.argv[1]
options = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {"large": True, "figures": True, "easy": True, "terms": True, "color": True, "braille": True}


def call(path, data=None, method=None, raw=False):
    req = urllib.request.Request(BASE + path, data=data, method=method or ("POST" if data is not None else "GET"))
    if data is not None and not raw:
        req.add_header("Content-Type", "application/json")
    elif raw:
        req.add_header("Content-Type", "application/pdf")
    return urllib.request.urlopen(req, timeout=120)


t0 = time.time()
r = json.load(call("/api/prepare?filename=test.pdf&course=" + urllib.parse.quote("경영정보시스템 (004)") + "&title=" + urllib.parse.quote("시험 자료"), open(pdf, "rb").read(), raw=True))
print("요약:", r["info"], f"({time.time() - t0:.1f}s)")
task = json.load(call(f"/api/jobs/{r['job']}/make", json.dumps(options).encode()))["task"]
while True:
    st = json.load(call(f"/api/tasks/{task}"))
    print(f"  {st['status']} {st['done']}/{st['total']} {st['step']} {st['note']}")
    if st["status"] in ("done", "error", "cancelled"):
        break
    time.sleep(1.5)
print("결과:", st["status"], st["error"], f"({time.time() - t0:.1f}s)")
for f in st["files"]:
    data = call(f["url"]).read()
    print(" 파일:", f["name"], f"{len(data) / 1024:.0f}KB")
    open(f"e2e_{f['kind']}.out", "wb").write(data)
