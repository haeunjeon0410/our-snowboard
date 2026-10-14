"""마스코트가 접혀 있다가 나와서 말풍선을 고르고 다시 접히는 움직임을 GIF로 만든다. 서버가 켜져 있어야 한다.
실행: python tools/make_mascot_gif.py [저장경로]   (기본 assets/mascot.gif)"""
import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "assets" / "mascot.gif")
W, H = 900, 600
CLIP = {"x": 630, "y": 245, "width": 270, "height": 290}
frames = []   # (이미지, 찍은 시각)


def shoot(page, seconds):
    end = time.time() + seconds
    while time.time() < end:
        png = page.screenshot(clip=CLIP, type="jpeg", quality=92)
        frames.append((Image.open(io.BytesIO(png)).convert("RGB"), time.time()))


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
    page.goto("http://localhost:8790/mock?ext=1")
    page.evaluate("localStorage.setItem('dev:onboarded', 'true')")
    page.reload()
    page.add_style_tag(content="h2,ul{visibility:hidden}body{background:#fff}")
    page.wait_for_timeout(400)
    page.reload(); page.add_style_tag(content="h2,ul{visibility:hidden}body{background:#fff}")
    shoot(page, 1.0)                                   # 접힌 채 머리만 내밀고 있음
    page.mouse.move(W - 20, H - 150); shoot(page, 0.5)
    page.mouse.click(W - 20, H - 150); shoot(page, 1.4)   # 눌러서 마스코트가 나온다
    for label in ("점자", "색 구분"):
        page.locator(f".chip:has-text('{label}')").first.click(); shoot(page, 0.7)
    shoot(page, 0.6)
    page.locator("button:has-text('저장')").first.click(); shoot(page, 1.6)   # 접힘
    b.close()

# 찍힌 시각이 고르지 않으므로 일정한 간격(FPS)의 격자에 가장 가까운 프레임을 골라 끊기지 않게 한다
FPS = 20
t0, t1 = frames[0][1], frames[-1][1]
grid, j = [], 0
for k in range(int((t1 - t0) * FPS) + 1):
    t = t0 + k / FPS
    while j + 1 < len(frames) and abs(frames[j + 1][1] - t) <= abs(frames[j][1] - t):
        j += 1
    grid.append(frames[j][0])
size = (grid[0].width * 3 // 4, grid[0].height * 3 // 4)
grid = [g.resize(size, Image.LANCZOS) for g in grid]
# 모든 프레임이 같은 색 팔레트를 쓰게 해서 색이 깜빡이지 않게 한다
sheet = Image.new("RGB", (size[0], size[1] * len(grid[::6])))
for i, g in enumerate(grid[::6]):
    sheet.paste(g, (0, i * size[1]))
pal = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
out = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in grid]
dur = [1000 // FPS] * len(out)
dur[0] = 900      # 접힌 모습에서 잠깐 멈춤
dur[-1] = 1500    # 다시 접힌 모습에서 잠깐 멈춤
out[0].save(OUT, save_all=True, append_images=out[1:], duration=dur, loop=0, optimize=False, disposal=1)
print(OUT, len(out), "frames", round(sum(dur) / 1000, 1), "s", OUT.stat().st_size // 1024, "KB; 찍힌 프레임", len(frames), f"({len(frames)/(t1-t0):.1f}fps)")
