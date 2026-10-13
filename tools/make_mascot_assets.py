"""마스코트 원본 4장(흰 배경)에서 화면에 쓸 이미지를 만든다. 실행: python tools/make_mascot_assets.py <원본 폴더>
원본: 1.webp 컬러 전신, 2.webp·3.webp 선화 전신, 4.webp 선화 머리
결과: server/static/img/*.png, extension/icons/*.png"""
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "mascot-src"
OUT = ROOT / "server" / "static" / "img"
EXT = ROOT / "extension" / "icons"
OUT.mkdir(parents=True, exist_ok=True)
PRIMARY = (11, 99, 217)
TILE_TOP = (248, 250, 252)    # 타일 위쪽(눈 쌓인 하늘빛) → 아래쪽(사이트 파랑 쪽으로 살짝)
TILE_BOT = (212, 222, 236)      # 변환 창처럼 탁하고 연한 회청색
INK = (50, 96, 160)           # 마스코트 머리의 남색 (이미지에서 직접 잰 값, 색 채운 머리용)
ICON_INK = (107, 133, 175)    # 아이콘 선 색: 눈에 띄지 않는 탁한 회청색
LINE = (42, 89, 152)          # 윤곽선 (마스코트 윤곽선 색)
LENS = (146, 190, 242)        # 고글 렌즈·끈 (마스코트 렌즈 색)



def trim(im: Image.Image, pad_ratio=0.04) -> Image.Image:
    box = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    im = im.crop(box)
    pad = int(max(im.size) * pad_ratio)
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    out.paste(im, (pad, pad))
    return out


def fit(im: Image.Image, max_w=None, max_h=None) -> Image.Image:
    s = min((max_w or 10 ** 9) / im.width, (max_h or 10 ** 9) / im.height, 1)
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def remove_white_bg(path) -> Image.Image:
    """바깥쪽 흰 배경만 투명하게 한다 (얼굴 속 흰색처럼 선으로 둘러싸인 흰색은 남긴다)."""
    rgb = Image.open(path).convert("RGB")
    probe = rgb.copy()
    w, h = probe.size
    for pt in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        ImageDraw.floodfill(probe, pt, (255, 0, 255), thresh=18)
    a = np.asarray(probe).astype(int)
    bg = (a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255)
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8))
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))   # 흰 테두리 줄이고 가장자리 부드럽게
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def soften_color(im: Image.Image) -> Image.Image:
    """사이트의 차분한 톤에 맞게 색을 조정한다: 파랑은 사이트 강조색 쪽으로, 채도는 낮추고, 노란 포인트는 눌러 준다."""
    alpha = im.getchannel("A")
    hsv = np.asarray(im.convert("RGB").convert("HSV")).astype(float)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    target = 214 * 255 / 360                                  # 사이트 파랑의 색상
    blue = (h > 125) & (h < 190) & (s > 25)
    h = np.where(blue, h + (target - h) * 0.55, h)
    s = np.where(blue, s * 0.88, s)
    v = np.where(blue & (v < 150), v * 1.07 + 6, v)           # 너무 짙은 남색을 한 톤 올림
    yellow = (h > 14) & (h < 48) & (s > 90)
    s = np.where(yellow, s * 0.66, s)
    v = np.where(yellow, np.minimum(255, v * 1.03), v)
    out = Image.fromarray(np.stack([h, s, v], -1).clip(0, 255).astype(np.uint8), "HSV").convert("RGBA")
    out.putalpha(alpha)
    return out


def line_art(path, color=None, boost=1.0) -> Image.Image:
    """선화(연한 파랑 선 + 흰 배경) → 선만 남긴 투명 PNG. color 가 없으면 원래 선 색을 쓴다."""
    rgb = Image.open(path).convert("RGB")
    a = np.asarray(rgb).astype(float)
    r = a[..., 0]
    line_r = np.percentile(r[r < 200], 10)
    alpha = np.clip((255 - r) / (255 - line_r), 0, 1) * boost
    alpha = np.clip(alpha, 0, 1)
    alpha = np.where(alpha < 0.10, 0, alpha)        # 원본 압축 노이즈로 생긴 옅은 사각형 자국 제거
    if color is None:
        mask = alpha > 0.9
        color = tuple(int(a[..., c][mask].mean()) for c in range(3))
    out = Image.new("RGBA", rgb.size, color + (0,))
    out.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
    return out


def color_head(path) -> Image.Image:
    """머리 선화의 닫힌 칸을 색으로 칠한다: 머리카락=남색, 얼굴·고글 테두리=흰색, 렌즈·끈=옅은 파랑.
    선만 있는 그림보다 작은 크기에서 윤곽이 또렷하다."""
    base = trim(line_art(path, color=(0, 0, 0), boost=1.3), pad_ratio=0.02)
    a = np.asarray(base.getchannel("A")).astype(float) / 255
    line = a > 0.45
    lab, n = ndimage.label(~line)
    H, W = line.shape
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    out = np.zeros((H, W, 4), np.uint8)
    inside = ~np.isin(lab, list(border)) | line                 # 머리 모양(바깥 배경 제외)
    out[inside] = LINE + (255,)
    regions = []
    for i in range(1, n + 1):
        if i in border:
            continue
        ys, xs = np.where(lab == i)
        if len(ys) < 150:
            continue
        regions.append((i, len(ys), xs.mean() / W, ys.mean() / H))
    goggles = [r for r in regions if abs(r[2] - 0.5) < 0.12 and 0.33 < r[3] < 0.62 and r[1] > 10000]
    lens = max(goggles, key=lambda r: r[1])[0] if goggles else None
    face = max((r for r in regions if r[3] > 0.66), key=lambda r: r[1], default=(None,))[0]
    for i, size, cx, cy in regions:
        if i == face or (i in [g[0] for g in goggles] and i != lens):
            col = (255, 255, 255)
        elif i == lens or size < 6000:
            col = LENS
        else:
            col = INK
        out[lab == i] = col + (255,)
    img = Image.fromarray(out, "RGBA")
    # 바깥 가장자리를 부드럽게
    alpha = img.getchannel("A").filter(ImageFilter.GaussianBlur(1.2))
    img.putalpha(alpha)
    return img


def app_icon(head: Image.Image, size: int, thicken=0) -> Image.Image:
    """옅은 단색 타일 + 머리 선화(남색). 작은 크기는 선을 굵게 한다."""
    S = 1024
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.225), fill=255)
    yy, xx = np.mgrid[0:S, 0:S]
    t = np.clip((yy * 0.8 + xx * 0.2) / S, 0, 1)[..., None] ** 1.15      # 위→아래로, 약간 대각선으로
    grad = (np.array(TILE_TOP) * (1 - t) + np.array(TILE_BOT) * t).astype(np.uint8)
    grad = Image.fromarray(np.dstack([grad, np.full((S, S), 255, np.uint8)]), "RGBA")
    tile.paste(grad, (0, 0), mask)
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(5)))
    tile.paste(Image.new("RGBA", (S, S), (20, 35, 60, 40)), (0, 0), edge)
    al = head.getchannel("A")
    if thicken:                                     # 작은 크기에서는 선을 굵게
        al = al.filter(ImageFilter.MaxFilter(thicken))
    h = Image.new("RGBA", head.size, ICON_INK + (0,))
    h.putalpha(al)
    h = fit(h, max_w=int(S * 0.84), max_h=int(S * 0.84))
    pos = ((S - h.width) // 2, (S - h.height) // 2 + int(S * 0.01))
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow = Image.new("RGBA", h.size, (25, 50, 100, 0))
    shadow.putalpha(h.getchannel("A").point(lambda v: int(v * 0.10)))
    sh.alpha_composite(shadow, (pos[0], pos[1] + int(S * 0.025)))
    tile.alpha_composite(sh.filter(ImageFilter.GaussianBlur(S * 0.012)))                      # 머리 아래 부드러운 그림자
    tile.alpha_composite(h, pos)
    return tile.resize((size, size), Image.LANCZOS)


def main():
    color = trim(remove_white_bg(SRC / "1.webp"))
    fit(color, max_w=720).save(OUT / "mascot-original.png", optimize=True)      # 원본 색 (참고용)
    fit(soften_color(color), max_w=720).save(OUT / "mascot.png", optimize=True)  # 사이트에 쓰는 색
    for n, name in (("2", "mascot-line.png"), ("3", "mascot-line-2.png")):
        fit(trim(line_art(SRC / f"{n}.webp")), max_w=720).save(OUT / name, optimize=True)
    head = trim(line_art(SRC / "4.webp", color=PRIMARY, boost=1.25), pad_ratio=0.02)
    fit(head, max_w=600).save(OUT / "mascot-head.png", optimize=True)
    EXT.mkdir(parents=True, exist_ok=True)
    icon_head = trim(line_art(SRC / "4.webp", color=(255, 255, 255), boost=1.3), pad_ratio=0.02)   # 색을 채우지 않은 선화
    for size, thick in ((512, 3), (128, 3), (48, 5), (32, 7), (16, 9)):
        img = app_icon(icon_head, size, thicken=thick)
        img.save(OUT / f"app-icon-{size}.png", optimize=True)
        if size in (128, 48, 16):
            img.save(EXT / f"icon{size}.png", optimize=True)
    app_icon(icon_head, 48, thicken=5).save(OUT / "app-icon.png", optimize=True)
    for p in sorted(OUT.glob("*.png")):
        print(p.name, Image.open(p).size, p.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
