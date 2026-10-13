"""PDF → 구조화 문서. AI 없이 되는 부분: 글자 추출, 읽는 순서, 제목·목록·표, 그림 위치, 띄어쓰기 문제 감지."""
import re
from collections import Counter
from pathlib import Path

import pymupdf

BULLET_RE = re.compile(r"^\s*([•▪■●○◦·\-–—*▶▷◆◇※]|\d{1,2}[.)]|[가-하][.)]|\(\d{1,2}\))\s*")
SENT_END_RE = re.compile(r"[.!?。…]$|[다요임음함됨]\.?$")
MONO_RE = re.compile(r"mono|consol|courier|menlo|code|d2coding", re.I)
HANGUL_RE = re.compile(r"[가-힣]")
PAGE_SCALE_WIDTH = 1500  # 원본 쪽 이미지 가로 픽셀


def _collapse_letterspacing(text: str):
    """'P O R T E R' 처럼 글자 사이가 벌어진 부분을 붙이고, 띄어쓰기 복원 대상으로 표시한다. (줄 일부만 그래도 처리)"""
    toks = text.split(" ")
    out, run, changed = [], [], False

    def flush():
        nonlocal changed
        if len(run) >= 4 and sum(len(t) for t in run) / len(run) <= 2.2:
            out.append("".join(run)); changed = True
        else:
            out.extend(run)
        run.clear()

    for t in toks:
        if re.fullmatch(r"[A-Za-z0-9&]{1,3}", t):
            run.append(t)
        else:
            flush(); out.append(t)
    flush()
    return " ".join(out), changed


def _needs_spacing(text: str) -> bool:
    k = len(HANGUL_RE.findall(text))
    if k < 5:
        return False
    if k < 8:                       # 짧은 제목: 띄어쓰기가 전혀 없을 때만
        return text.count(" ") == 0
    return text.count(" ") / k < 0.09


def _area(r):
    return max(0, r[2] - r[0]) * max(0, r[3] - r[1])


def _inside(inner, outer, tol=2):
    return inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol


def _center_in(r, outer):
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3]


def _read_lines(page):
    """쪽의 글줄 목록. 각 줄: text, bbox, size, bold, mono, block_no"""
    lines = []
    for bi, b in enumerate(page.get_text("dict")["blocks"]):
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            spans = [s for s in l["spans"] if s["text"].strip() or s["text"] == " "]
            text = "".join(s["text"] for s in spans).strip()
            if not text:
                continue
            n = sum(len(s["text"]) for s in spans) or 1
            main = max(spans, key=lambda s: len(s["text"].strip()))
            bold_chars = sum(len(s["text"]) for s in spans if (s["flags"] & 16) or "bold" in s["font"].lower() or "black" in s["font"].lower())
            mono_chars = sum(len(s["text"]) for s in spans if MONO_RE.search(s["font"]))
            emph, run, n_col = [], "", 0
            for sp in spans:
                if _is_colored(sp.get("color", 0)) and sp["text"].strip():
                    run += sp["text"]
                    n_col += len(sp["text"].strip())
                else:
                    if len(run.strip()) >= 2:
                        emph.append(run.strip())
                    run = ""
            if len(run.strip()) >= 2:
                emph.append(run.strip())
            lines.append({
                "text": text, "bbox": tuple(l["bbox"]), "size": round(main["size"], 1),
                "bold": bold_chars / n > 0.5, "mono": mono_chars / n > 0.6, "block": bi,
                "color": main.get("color", 0), "emph": emph, "n_col": n_col, "n_chars": len(text.replace(" ", "")) or 1,
            })
    return lines


def _is_colored(color_int: int) -> bool:
    """글자색이 '색으로 강조'로 볼 만큼 선명한가 (검정·회색·흰색은 제외)"""
    r, g, b = ((color_int >> 16) & 255) / 255, ((color_int >> 8) & 255) / 255, (color_int & 255) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    return mx > 0.35 and (mx - mn) / max(mx, 1e-9) > 0.45


def _diagram_regions(page, drawings, table_boxes, line_boxes):
    """도식(박스와 화살표로 된 그림) 후보 영역. 배경 같은 큰 도형은 빼고 묶는다."""
    W, H = page.rect.width, page.rect.height
    kept = [d for d in drawings if d.get("rect") is not None and 0 < _area(d["rect"]) < 0.55 * W * H]
    if len(kept) < 5:
        return []
    try:
        clusters = page.cluster_drawings(drawings=kept, x_tolerance=6, y_tolerance=6)
    except Exception:
        return []
    regions = []
    for c in clusters:
        c = tuple(c)
        if _area(c) < 0.05 * W * H:
            continue
        n_draw = sum(1 for d in kept if _inside(tuple(d["rect"]), c, 3))
        n_text = sum(1 for lb in line_boxes if _center_in(lb, c))
        if n_draw >= 5 and n_text >= 3:
            if any(_inside(t, c, 3) or _inside(c, t, 3) for t in table_boxes):
                continue
            regions.append(c)
    return regions[:6]


def _merge_wrapped(items):
    """줄바꿈으로 쪼개진 같은 문단을 다시 합친다 (글 크기가 같고 줄 간격이 좁은 경우)."""
    items = sorted(items, key=lambda it: (it["bbox"][0] // 40, it["bbox"][1]))
    out = []
    for it in items:
        merged = False
        if it["kind"] in ("paragraph", "listitem", "heading") and not it.get("collapsed"):
            for prev in reversed(out[-6:]):
                if prev["kind"] != it["kind"] and not (prev["kind"] == "listitem" and it["kind"] == "paragraph"):
                    continue
                if abs(prev["size"] - it["size"]) > 0.6 or prev["bold"] != it["bold"]:
                    continue
                gap = it["bbox"][1] - prev["bbox"][3]
                dx = it["bbox"][0] - prev["bbox"][0]
                tight = -2 <= gap < 0.28 * it["size"]
                loose = (it["kind"] != "heading" and -2 <= gap < 0.9 * it["size"]
                         and not prev["text"].rstrip().endswith((".", "!", "?", "…", "。", ":", "”", '"')))
                if (tight or loose) and -4 <= dx <= 30:
                    glue = "" if _needs_spacing(prev["text"] + " " + it["text"]) else " "
                    prev["text"] = prev["text"] + glue + it["text"]
                    prev["bbox"] = (min(prev["bbox"][0], it["bbox"][0]), prev["bbox"][1],
                                    max(prev["bbox"][2], it["bbox"][2]), it["bbox"][3])
                    if it.get("spacing"):
                        prev["spacing"] = "restore"
                    if it.get("emph"):
                        prev["emph"] = prev.get("emph", []) + it["emph"]
                    merged = True
                    break
        if not merged:
            out.append(it)
    return out


def _order(items, W):
    """읽는 순서: 위→아래. 좌우 두 단이면 왼쪽 단을 먼저 읽고 오른쪽 단을 읽는다."""
    def width(it):
        return it["bbox"][2] - it["bbox"][0]

    items = sorted(items, key=lambda it: (it["bbox"][1], it["bbox"][0]))
    out, buf = [], []

    def flush():
        if not buf:
            return
        left = [i for i in buf if (i["bbox"][0] + i["bbox"][2]) / 2 < W / 2]
        right = [i for i in buf if i not in left]
        if left and right and len(buf) >= 2:
            out.extend(sorted(left, key=lambda i: i["bbox"][1]))
            out.extend(sorted(right, key=lambda i: i["bbox"][1]))
        else:
            out.extend(sorted(buf, key=lambda i: (i["bbox"][1], i["bbox"][0])))
        buf.clear()

    for it in items:
        if width(it) > 0.7 * W:
            flush()
            out.append(it)
        else:
            buf.append(it)
    flush()
    return out


def render_page_png(pdf_path: Path, out_png: Path, page_no: int) -> Path:
    """쪽 전체 그림 (측정표의 색 분석용). 변환에는 쓰이지 않아서 필요할 때만 만든다."""
    if not Path(out_png).exists():
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(str(pdf_path)) as pdf:
            page = pdf[page_no - 1]
            sc = PAGE_SCALE_WIDTH / page.rect.width
            _save_png(page.get_pixmap(matrix=pymupdf.Matrix(sc, sc)), out_png)
    return Path(out_png)


def _save_png(pix, path):
    """pymupdf 기본 PNG 저장은 압축이 무거워 그림이 많은 자료에서 가장 오래 걸린다. 가볍게 압축해 3~5배 빠르게 저장한다."""
    try:
        if pix.n == 3 and not pix.alpha:
            from PIL import Image
            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(str(path), "PNG", compress_level=1)
            return
    except Exception:
        pass
    pix.save(str(path))


def extract(pdf_path: Path, out_dir: Path, progress=None) -> dict:
    out_dir = Path(out_dir)
    (out_dir / "figs").mkdir(parents=True, exist_ok=True)
    pdf = pymupdf.open(str(pdf_path))
    n_pages = len(pdf)

    # 1차: 본문 글자 크기(가장 많이 쓰인 크기)와 반복되는 장식 이미지 파악
    size_chars = Counter()
    xref_pages = Counter()
    page_lines = []
    for p in pdf:
        ls = _read_lines(p)
        page_lines.append(ls)
        for l in ls:
            size_chars[round(l["size"])] += len(l["text"])
        for info in p.get_image_info(xrefs=True):
            xref_pages[info["xref"]] += 1
    body = size_chars.most_common(1)[0][0] if size_chars else 10
    deco_xrefs = {x for x, c in xref_pages.items() if n_pages >= 4 and c >= max(3, 0.35 * n_pages)}

    head_sizes = sorted({round(l["size"] * 2) / 2 for ls in page_lines for l in ls if l["size"] >= body * 1.25}, reverse=True)

    def heading_level(size):
        s = round(size * 2) / 2
        if s in head_sizes:
            return min(head_sizes.index(s) + 1, 3)
        return None

    pages = []
    for pn, page in enumerate(pdf):
        W, H = page.rect.width, page.rect.height
        lines = page_lines[pn]
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []
        items = []   # {kind, bbox, ...}

        # 표
        table_boxes = []
        try:
            for t in (page.find_tables().tables if len(drawings) >= 4 else []):
                if t.row_count >= 2 and t.col_count >= 2:
                    rows = [[(c or "").replace("\n", " ").strip() for c in r] for r in t.extract()]
                    if sum(1 for r in rows for c in r if c) >= 4:
                        table_boxes.append(tuple(t.bbox))
                        items.append({"kind": "table", "bbox": tuple(t.bbox), "rows": rows})
        except Exception:
            pass

        # 그림 (이미지 + 도식)
        fig_boxes = []
        for info in page.get_image_info(xrefs=True):
            r = pymupdf.Rect(info["bbox"]) & page.rect
            if r.is_empty or info["xref"] in deco_xrefs:
                continue
            if r.width < 40 or r.height < 40 or _area(r) < 0.012 * W * H:
                continue
            fig_boxes.append((tuple(r), "image", _area(r) > 0.6 * W * H))
        diag = _diagram_regions(page, drawings, table_boxes, [l["bbox"] for l in lines])
        for c in diag:
            if not any(_inside(c, fb[0], 6) for fb in fig_boxes):
                fig_boxes.append((c, "diagram", False))
        for fi, (bb, fkind, fullpage) in enumerate(fig_boxes):
            clip = pymupdf.Rect(bb)
            sc = min(2.2, 1400 / max(clip.width, 1))
            fname = f"p{pn + 1}_f{fi + 1}.png"
            _save_png(page.get_pixmap(matrix=pymupdf.Matrix(sc, sc), clip=clip), out_dir / "figs" / fname)
            inner = [l for l in lines if _center_in(l["bbox"], bb)]
            items.append({"kind": "figure", "bbox": tuple(bb), "img": f"figs/{fname}", "fig_kind": fkind,
                          "fullpage": fullpage, "inner": inner})

        # 글 줄 → 문단/목록/제목/코드
        used = set()
        for it in items:
            if it["kind"] == "table":
                used.update(i for i, l in enumerate(lines) if _center_in(l["bbox"], it["bbox"]))
            elif it["kind"] == "figure":
                used.update(i for i, l in enumerate(lines) if _center_in(l["bbox"], it["bbox"]))
        rest = [(i, l) for i, l in enumerate(lines) if i not in used]
        text_items = []
        groups = {}
        for i, l in rest:
            groups.setdefault(l["block"], []).append(l)

        for bno, ls in groups.items():
            paras = []  # 한 블록 안에서 글머리 기호마다 새 문단
            for l in ls:
                is_b = bool(BULLET_RE.match(l["text"])) and not l["mono"]
                if is_b or not paras:
                    paras.append({"lines": [l], "bullet": is_b})
                else:
                    paras[-1]["lines"].append(l)
            for p_ in paras:
                pl = p_["lines"]
                joined_sp = " ".join(x["text"] for x in pl)
                # 띄어쓰기가 사라진 슬라이드는 줄바꿈 자리가 낱말 중간일 수 있어 공백 없이 잇고 AI가 복원하게 한다
                text = "".join(x["text"] for x in pl) if _needs_spacing(joined_sp) else joined_sp
                bbox = (min(x["bbox"][0] for x in pl), min(x["bbox"][1] for x in pl),
                        max(x["bbox"][2] for x in pl), max(x["bbox"][3] for x in pl))
                size = max(x["size"] for x in pl)
                bold = all(x["bold"] for x in pl)
                mono = all(x["mono"] for x in pl)
                if p_["bullet"]:
                    text = BULLET_RE.sub("", text, count=1).strip()
                    if not text:
                        continue
                text, collapsed = _collapse_letterspacing(text)
                kind, extra = "paragraph", {}
                if collapsed:
                    pass
                elif mono:
                    kind = "code"
                    text = "\n".join(x["text"] for x in pl)
                elif p_["bullet"]:
                    kind = "listitem"
                else:
                    lvl = heading_level(size)
                    short = len(text) <= 60 and len(pl) <= 2 and not SENT_END_RE.search(text)
                    if lvl and short:
                        kind, extra = "heading", {"level": lvl}
                    elif bold and size >= body and len(pl) == 1 and len(text) <= 45 and not SENT_END_RE.search(text) \
                            and bbox[1] < 0.22 * H:
                        kind, extra = "heading", {"level": 3}
                col_chars = sum(x["n_col"] for x in pl)
                all_chars = sum(x["n_chars"] for x in pl)
                emph = [e for x in pl for e in x["emph"]] if (col_chars / all_chars) < 0.6 else []
                it = {"kind": kind, "bbox": bbox, "text": text, "bold": bold, "size": size, **extra}
                if emph:
                    it["emph"] = emph
                if kind in ("paragraph", "listitem", "heading") and (collapsed or _needs_spacing(text)):
                    it["spacing"] = "restore"
                text_items.append(it)

        items.extend(_merge_wrapped(text_items))

        # 읽는 순서
        ordered = _order(items, W)

        # 연속된 목록 항목 묶기, id 부여
        blocks = []
        for it in ordered:
            k = it["kind"]
            if k == "listitem":
                if blocks and blocks[-1]["type"] == "list":
                    blocks[-1]["items"].append({"text": it["text"], **({"spacing": "restore"} if it.get("spacing") else {}), **({"emph": it["emph"]} if it.get("emph") else {})})
                else:
                    blocks.append({"type": "list", "items": [{"text": it["text"], **({"spacing": "restore"} if it.get("spacing") else {}), **({"emph": it["emph"]} if it.get("emph") else {})}]})
            elif k == "paragraph":
                b = {"type": "paragraph", "text": it["text"]}
                if it.get("bold"):
                    b["bold"] = True
                if it.get("spacing"):
                    b["spacing"] = "restore"
                if it.get("emph"):
                    b["emph"] = it["emph"]
                blocks.append(b)
            elif k == "heading":
                b = {"type": "heading", "level": it["level"], "text": it["text"]}
                if it.get("spacing"):
                    b["spacing"] = "restore"
                blocks.append(b)
            elif k == "code":
                blocks.append({"type": "code", "text": it["text"]})
            elif k == "table":
                blocks.append({"type": "table", "rows": it["rows"]})
            elif k == "figure":
                inner_txt = [x["text"] for x in sorted(it["inner"], key=lambda x: (round(x["bbox"][1] / 6), x["bbox"][0]))]
                blocks.append({"type": "figure", "img": it["img"], "fig_kind": it["fig_kind"], "fullpage": it["fullpage"],
                               "inner_text": inner_txt, "bbox": [round(v, 1) for v in it["bbox"]]})
        for bi, b in enumerate(blocks):
            b["id"] = f"p{pn + 1}b{bi + 1}"

        text_all = " ".join(l["text"] for l in lines)
        ko = len(HANGUL_RE.findall(text_all))
        lang = "ko" if ko >= 0.3 * max(1, len(re.findall(r"[A-Za-z가-힣]", text_all))) else "en"
        pages.append({
            "n": pn + 1, "width": W, "height": H, "lang": lang,
            "blocks": blocks,
            "status": "extracted",
        })
        if progress:
            progress(pn + 1, n_pages)

    title = ""
    for pg in pages:
        for b in pg["blocks"]:
            if b["type"] == "heading":
                title = b["text"]
                break
        if title:
            break
    return {"title": title or Path(pdf_path).stem, "body_size": body, "n_pages": n_pages, "pages": pages}
