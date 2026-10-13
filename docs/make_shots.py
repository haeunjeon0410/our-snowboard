"""소개자료·시연용 화면 캡처를 만든다 (Edge를 화면 없이 실행). 서버가 켜져 있어야 한다.
실행: python docs/make_shots.py [이름 일부]"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://localhost:8790"

SHOTS = [
    ("01_home", "/", 1280, 2300),
    ("02_home_panel", "/?demo=1", 1280, 900),
    ("03_mock_course", "/mock?ext=1", 900, 260),
    ("04_quality", "/quality", 1280, 1700),
    ("05_popup", "/ext/popup.html", 340, 300),
    ("06_mobile_home", ("iframe", "/", 390, 844), 700, 880),
]
only = sys.argv[1:]
for name, path, w, h in SHOTS:
    if only and not any(o in name for o in only):
        continue
    out = OUT / f"{name}.png"
    if isinstance(path, tuple):    # 실제 390px 폭을 재현하려고 iframe 안에서 연다
        _, src, fw, fh = path
        page = OUT / f"_{name}.html"
        page.write_text(f"<body style='margin:0;background:#cfd6e4;display:flex;justify-content:center'><iframe src='{BASE}{src}' width='{fw}' height='{fh}' style='border:0;background:#fff'></iframe></body>", encoding="utf-8")
        target = page.as_uri()
    else:
        target = BASE + path
    # 캡처용 임시 프로필로 따로 띄우고, 시간이 넘으면 '내가 띄운 프로세스'만 종료한다 (사용자가 쓰는 Edge는 건드리지 않음)
    prof = tempfile.mkdtemp(prefix="osb_shot_")
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}", f"--window-size={w},{h}",
           "--virtual-time-budget=9000", f"--screenshot={out}", target]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(prof, ignore_errors=True)
    print(name, "OK" if out.exists() else "FAIL")
for p in OUT.glob("_*.html"):
    p.unlink()
