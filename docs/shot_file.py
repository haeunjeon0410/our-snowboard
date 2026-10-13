"""HTML 파일이나 주소 하나를 Edge(화면 없이)로 캡처한다. 실행: python docs/shot_file.py <파일 또는 주소> <저장.png> [가로 세로]"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

target, out = sys.argv[1], Path(sys.argv[2])
w, h = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1100, 1400)
url = target if "://" in target else Path(target).resolve().as_uri()
prof = tempfile.mkdtemp(prefix="osb_")
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
proc = subprocess.Popen([edge, "--headless=new", "--disable-gpu", f"--user-data-dir={prof}", f"--window-size={w},{h}",
                         "--virtual-time-budget=6000", f"--screenshot={out}", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    proc.wait(timeout=60)
except subprocess.TimeoutExpired:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
shutil.rmtree(prof, ignore_errors=True)
print(out, os.path.exists(out))
