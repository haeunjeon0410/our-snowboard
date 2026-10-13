"""색각 이상 지원: 시뮬레이션, 색 보정(daltonize), 색으로만 구분된 영역에 무늬 덧씌우기, 색 이름."""
import colorsys
import io

import numpy as np
from PIL import Image

# Machado et al. (2009), 심한 정도 1.0, 선형 RGB 기준
SIM = {
    "protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}
# 구분하기 어려운 색 차이를 잘 보이는 채널로 옮기는 행렬
SHIFT = {
    "protan": [[0, 0, 0], [0.7, 1, 0], [0.7, 0, 1]],
    "deutan": [[0, 0, 0], [0.7, 1, 0], [0.7, 0, 1]],
    "tritan": [[1, 0, 0.7], [0, 1, 0.7], [0, 0, 0]],
}
MODE_KO = {"protan": "적색약·적색맹(제1형)", "deutan": "녹색약·녹색맹(제2형)", "tritan": "청황색약(제3형)"}


def _to_linear(a):
    a = a / 255.0
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055) * 255.0


def simulate(img: Image.Image, mode: str) -> Image.Image:
    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    lin = _to_linear(arr)
    out = lin @ np.array(SIM[mode]).T
    return Image.fromarray(_to_srgb(out).round().astype(np.uint8))


def daltonize(img: Image.Image, mode: str, gain: float = 1.0) -> Image.Image:
    """보정: 색각 이상으로 사라지는 차이를 계산해서 보이는 색 방향으로 옮겨 준다. gain: 옮기는 세기"""
    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    lin = _to_linear(arr)
    sim = lin @ np.array(SIM[mode]).T
    err = lin - sim
    out = lin + gain * (err @ np.array(SHIFT[mode]).T)
    return Image.fromarray(_to_srgb(out).round().astype(np.uint8))


# ───── 색 이름 / 픽셀에서 색 영역 찾기 ─────
HUE_EDGES = [15, 40, 68, 95, 165, 200, 225, 255, 295, 345]
HUE_LABELS = ["빨강", "주황", "노랑", "연두", "초록", "청록", "하늘색", "파랑", "보라", "분홍", "빨강"]


def _name(h, s, v):
    if v < 0.18:
        return "검정"
    if s < 0.12:
        return "흰색" if v > 0.9 else "회색"
    idx = next((i for i, e in enumerate(HUE_EDGES) if h < e), len(HUE_EDGES))
    base = HUE_LABELS[idx]
    if 15 <= h < 40 and v < 0.6:
        base = "갈색"
    tone = "연한 " if (s < 0.4 and v > 0.8) else ("진한 " if v < 0.45 else "")
    return tone + base


def color_name(hexc: str) -> str:
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return _name(h * 360, s, v)


PATTERNS = ["사선(/)", "사선(\\)", "가로줄", "세로줄", "점", "격자", "빗금(X)", "굵은 사선"]
BLOCK = 6


def _hsv(arr):
    a = arr / 255.0
    mx, mn = a.max(2), a.min(2)
    d = mx - mn
    v = mx
    s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.zeros_like(mx)
    m = d > 1e-9
    rc = m & (mx == r)
    gc = m & (mx == g) & ~rc
    bc = m & ~rc & ~gc
    h[rc] = ((g - b)[rc] / d[rc]) % 6
    h[gc] = (b - r)[gc] / d[gc] + 2
    h[bc] = (r - g)[bc] / d[bc] + 4
    return h * 60, s, v


def analyze(img, min_area=0.004, max_classes=8):
    """색으로 칠해진 영역을 찾는다. 반환: (분류 목록, 분류별 칸 단위 마스크)"""
    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    H, W = arr.shape[:2]
    h, s, v = _hsv(arr)
    colored = (s > 0.30) & (v > 0.18)
    hue_idx = np.digitize(h, HUE_EDGES)
    hue_idx = np.where(hue_idx >= 10, 0, hue_idx)      # 345도 이상은 빨강
    tone = np.where(v < 0.45, 0, np.where((s < 0.4) & (v > 0.8), 2, 1))
    brown = (h >= 15) & (h < 40) & (v < 0.6)
    cls = np.where(brown, 100, hue_idx * 3 + tone)
    cls = np.where(colored, cls, -1)
    bh, bw = H // BLOCK, W // BLOCK
    cls_b = cls[:bh * BLOCK, :bw * BLOCK].reshape(bh, BLOCK, bw, BLOCK).transpose(0, 2, 1, 3).reshape(bh, bw, -1)
    out_cls, masks = [], {}
    for c in np.unique(cls):
        if c < 0:
            continue
        mask = (cls_b == c).mean(2) >= 0.75
        if mask.sum() < min_area * bh * bw:
            continue
        mean = arr[cls == c].mean(0)
        hx = "#%02x%02x%02x" % tuple(int(round(x)) for x in mean)
        out_cls.append({"cid": int(c), "hex": hx, "name": color_name(hx), "area": float(mask.sum()) / (bh * bw)})
        masks[int(c)] = mask
    out_cls.sort(key=lambda g: -g["area"])
    out_cls = out_cls[:max_classes]
    for i, g in enumerate(out_cls):
        g["pattern"] = PATTERNS[i]
        g["pattern_id"] = i
        g["pct"] = round(100 * g["area"], 1)
    return out_cls, masks, cls


def _pattern(pid, H, W, scale):
    y, x = np.mgrid[0:H, 0:W]
    p = max(8, int(round(12 * scale)))
    t = max(2, int(round(3 * scale)))
    if pid == 0:
        return ((x + y) % p) < t
    if pid == 1:
        return ((x - y) % p) < t
    if pid == 2:
        return (y % p) < t
    if pid == 3:
        return (x % p) < t
    if pid == 4:
        return ((x % p - p // 2) ** 2 + (y % p - p // 2) ** 2) < (t * 1.6) ** 2
    if pid == 5:
        return ((x % (p + 2)) < max(1, t - 1)) | ((y % (p + 2)) < max(1, t - 1))
    if pid == 6:
        return ((x + y) % (p + 4) < max(1, t - 1)) | ((x - y) % (p + 4) < max(1, t - 1))
    return ((x + y) % (2 * p)) < 2 * t + 1


def apply_hatch(img, classes, masks, cls):
    arr = np.asarray(img.convert("RGB"), dtype=np.float64)
    H, W = arr.shape[:2]
    scale = W / 1500.0
    out = arr.copy()
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255
    target = np.where((lum < 0.5)[..., None], 255.0, 0.0)
    for g in classes:
        m = np.kron(masks[g["cid"]], np.ones((BLOCK, BLOCK), dtype=bool))
        full = np.zeros((H, W), dtype=bool)
        full[:m.shape[0], :m.shape[1]] = m
        pat = _pattern(g["pattern_id"], H, W, scale) & full & (cls == g["cid"])   # 글자 픽셀은 건드리지 않음
        out = np.where(pat[..., None], out * 0.35 + target * 0.65, out)
    return Image.fromarray(out.round().astype(np.uint8))


def render_page(png_path, page, mode="normal", correct=False, hatch=False):
    """원본 쪽 이미지에 보정/시뮬레이션/무늬를 적용한다. 반환: (PNG 바이트, 색 분류 목록)"""
    img = Image.open(png_path).convert("RGB")
    classes, masks, cls = analyze(img)
    work = img
    gain = 1.0
    if mode in SIM:
        if correct:
            gain = best_gain([g["hex"] for g in classes], mode)
            work = daltonize(img, mode, gain) if gain > 0 else img
        else:
            work = simulate(img, mode)
    if hatch and classes:
        work = apply_hatch(work, classes, masks, cls)
    buf = io.BytesIO()
    work.save(buf, "PNG")
    return buf.getvalue(), [{k: v for k, v in g.items() if k != "cid"} for g in classes]


def page_palette(png_path):
    classes, _, _ = analyze(Image.open(png_path).convert("RGB"))
    return [{k: v for k, v in g.items() if k != "cid"} for g in classes]


# ───── 색 구분 정도 측정 (CIE76 색차) ─────
def _lab(rgb):
    """rgb: (N,3) 0~255 → CIELAB"""
    lin = _to_linear(rgb.astype(np.float64))
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


GAINS = [0.0, 0.7, 1.0, 1.5, 2.2, 3.0]


def best_gain(hexes, mode):
    """이 쪽의 색들이 가장 잘 구분되는 보정 세기를 고른다. (보정이 오히려 나쁘면 0 = 보정 없음)"""
    if len(hexes) < 2:
        return 1.0
    scores = [(min_confusion(hexes, mode, True, g), -g) for g in GAINS]
    return -max(scores)[1]


def min_confusion(hexes, mode=None, correct=False, gain=1.0):
    """색 목록에서 가장 비슷해 보이는 두 색의 색차(ΔE). 작을수록 구분이 어렵다. 3 이하면 거의 같은 색으로 보인다.
    mode: 색각 유형(없으면 일반 시각), correct: 보정한 색을 보여 준 경우"""
    arr = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in hexes], dtype=np.uint8).reshape(1, -1, 3)
    img = Image.fromarray(arr)
    if mode:
        if correct:
            img = daltonize(img, mode, gain)
        img = simulate(img, mode)
    lab = _lab(np.asarray(img, dtype=np.float64).reshape(-1, 3))
    best = 1e9
    for i in range(len(lab)):
        for j in range(i + 1, len(lab)):
            best = min(best, float(np.linalg.norm(lab[i] - lab[j])))
    return best


def fix_image(png_path, mode="deutan"):
    """색으로만 구분된 그림을 구분하기 쉽게: 색 보정(쪽마다 가장 잘 보이는 세기) + 같은 색에 같은 무늬.
    반환: (RGB 이미지, 범례 목록). 색이 2종류 미만이면 원본 그대로."""
    img = Image.open(png_path).convert("RGB")
    classes, masks, cls = analyze(img)
    if len(classes) < 2:
        return img, []
    gain = best_gain([g["hex"] for g in classes], mode)
    work = daltonize(img, mode, gain) if gain > 0 else img
    work = apply_hatch(work, classes, masks, cls)
    return work, [{k: v for k, v in g.items() if k != "cid"} for g in classes]
