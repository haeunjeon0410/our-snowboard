"""서버 화면의 디자인 파일을 확장 프로그램 폴더로 복사한다. (디자인을 고친 뒤 실행: python tools/sync_ext.py)"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
css = (root / "server/static/ds.css").read_text(encoding="utf-8").replace("url('/static/fonts/PretendardVariable.woff2')", "url('fonts/PretendardVariable.woff2')")
(root / "extension/ds.css").write_text(css, encoding="utf-8")
shutil.copy(root / "server/static/icons.svg", root / "extension/icons.svg")
shutil.copy(root / "server/static/fonts/PretendardVariable.woff2", root / "extension/fonts/PretendardVariable.woff2")
shutil.copy(root / "server/static/osb-panel.js", root / "extension/panel.js")   # 맞춤 변환 창 (홈 화면과 같은 코드)

# 스노우보드 화면에 붙는 UI(버튼·안내 띠): 홈 화면 목업과 똑같은 CSS(osb-ui.css) + 확장 프로그램용 폰트 선언
font_face = (
    "@font-face{font-family:'OSB Pretendard';font-weight:45 920;font-display:swap;"
    "src:url('chrome-extension://__MSG_@@extension_id__/fonts/PretendardVariable.woff2') format('woff2-variations')}\n"
)
ui = (root / "server/static/osb-ui.css").read_text(encoding="utf-8")
(root / "extension/content.css").write_text(font_face + ui, encoding="utf-8")
from PIL import Image   # 첫 방문 안내에 쓰는 마스코트 (작게 줄여서)
mascot = Image.open(root / "server/static/img/mascot.png")
mascot.thumbnail((260, 348))
mascot.save(root / "extension/icons/mascot.png", optimize=True)
peek_src = root / "server/static/img/mascot-peek.png"      # 접혀 있을 때 화면 오른쪽 끝에서 머리만 내미는 모습
if peek_src.exists():
    peek = Image.open(peek_src)
    peek.thumbnail((240, 240))
    peek.save(root / "extension/icons/mascot-peek.png", optimize=True)
spin_src = root / "server/static/img/mascot-spin.png"      # 360도 스핀 점프 프레임 (한 줄 이미지는 줄이지 않고 그대로)
if spin_src.exists():
    shutil.copy(spin_src, root / "extension/icons/mascot-spin.png")
for name in ("mascot-ride", "mascot-thumb", "mascot-fall", "mascot-run"):      # 변환 중·완료·오류 화면용 (작게)
    f = root / f"server/static/img/{name}.png"
    if f.exists():
        im = Image.open(f); im.thumbnail((240, 240)); im.save(root / f"extension/icons/{name}.png", optimize=True)
print("확장 프로그램 디자인 파일을 동기화했습니다.")
