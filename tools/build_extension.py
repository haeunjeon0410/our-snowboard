"""서버 주소가 들어간 확장 프로그램 폴더·zip을 만든다 (크롬 웹스토어 제출용).
사용: python tools/build_extension.py https://아이디-our-snowboard.hf.space"""
import json
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
    sys.exit("사용법: python tools/build_extension.py https://서버주소")
base = sys.argv[1].rstrip("/")
out = root / "dist" / "our-snowboard-extension"
shutil.rmtree(out, ignore_errors=True)
shutil.copytree(root / "extension", out, ignore=shutil.ignore_patterns("test_*", "__pycache__"))

bg = out / "background.js"
bg.write_text(bg.read_text(encoding="utf-8").replace("const DEFAULT_SERVER = 'http://localhost:8790';", f"const DEFAULT_SERVER = '{base}';"), encoding="utf-8")
mf = out / "manifest.json"
m = json.loads(mf.read_text(encoding="utf-8"))
m["host_permissions"] = sorted(set(m["host_permissions"]) | {base + "/*"})
for cs in m["content_scripts"]:
    if cs["js"] == ["mark.js"]:
        cs["matches"] = sorted(set(cs["matches"]) | {base + "/*"})
m["web_accessible_resources"][0]["matches"] = sorted(set(m["web_accessible_resources"][0]["matches"]) | {base + "/*"})
mf.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
zip_path = shutil.make_archive(str(root / "dist" / "our-snowboard-extension"), "zip", out.parent, out.name)
print("만들었어요:", zip_path)
