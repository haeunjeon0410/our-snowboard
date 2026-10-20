"""구조 태그 PDF 만들기 (OpenDataLoader PDF 사용, 선택 기능).
원본 PDF에 제목·목록·읽는 순서 같은 구조 태그를 자동으로 달고(Tagged PDF), 우리 AI 그림 설명을 그림의 대체 텍스트(Alt)로 넣는다.
Java 11 이상과 `pip install opendataloader-pdf`가 있을 때만 쓰이고, 없거나 실패하면 지금까지처럼 원본에 숨은 글자를 얹는다."""
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pymupdf

_lock = threading.Lock()
_java = {"tried": False, "home": None}
_PLACEHOLDER = re.compile(r"^\s*(image\s*\d*|figure\s*\d*)?\s*$", re.I)       # 'image 1' 같은 자리표시자나 빈 Alt는 덮어써도 된다
MATCH_IOU = 0.5


def _java_major(java_exe: str) -> int:
    try:
        out = subprocess.run([java_exe, "-version"], capture_output=True, text=True, timeout=15).stderr
        m = re.search(r'version "(\d+)(?:\.(\d+))?', out)
        if not m:
            return 0
        return int(m.group(2) or 0) if m.group(1) == "1" else int(m.group(1))
    except Exception:
        return 0


def _find_java_home() -> str | None:
    """Java 11 이상이 있는 폴더(JAVA_HOME). 환경 변수 → 사용자 .jdks → 일반 설치 위치 → PATH 순서."""
    if _java["tried"]:
        return _java["home"]
    cands = []
    if os.environ.get("JAVA_HOME"):
        cands.append(Path(os.environ["JAVA_HOME"]))
    for base in (Path.home() / ".jdks", Path("C:/Program Files/Java"), Path("C:/Program Files/Eclipse Adoptium"), Path("/usr/lib/jvm")):
        if base.is_dir():
            cands += sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    exe = "java.exe" if os.name == "nt" else "java"
    home = None
    for c in cands:
        if (c / "bin" / exe).exists() and _java_major(str(c / "bin" / exe)) >= 11:
            home = str(c)
            break
    if home is None and shutil.which("java") and _java_major(shutil.which("java")) >= 11:
        home = ""                                          # PATH의 java를 그대로 쓴다
    _java.update(tried=True, home=home)
    return home


def available() -> bool:
    if os.environ.get("OSB_TAGGING") == "0":
        return False
    try:
        import opendataloader_pdf  # noqa: F401
    except Exception:
        return False
    return _find_java_home() is not None


def tag(original: Path, work_dir: Path) -> Path | None:
    """원본 PDF에 구조 태그를 단 PDF를 work_dir/tagged.pdf로 만든다 (이미 있으면 그대로). 실패하면 None."""
    out = Path(work_dir) / "tagged.pdf"
    if out.exists():
        return out
    try:
        import opendataloader_pdf
        home = _find_java_home()
        tmp = Path(work_dir) / "_odl"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        with _lock:                                        # 환경 변수를 바꾸는 동안 다른 변환이 끼어들지 않게
            old = dict(os.environ)
            try:
                if home:
                    os.environ["JAVA_HOME"] = home
                    os.environ["PATH"] = str(Path(home) / "bin") + os.pathsep + os.environ.get("PATH", "")
                opendataloader_pdf.convert(input_path=str(original), output_dir=str(tmp), format="tagged-pdf", quiet=True)
            finally:
                os.environ.clear()
                os.environ.update(old)
        made = next(tmp.glob("*_tagged.pdf"), None)
        if made is None:
            return None
        made.replace(out)
        shutil.rmtree(tmp, ignore_errors=True)
        return out
    except Exception:
        return None


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def apply_alts(pdf: "pymupdf.Document", doc: dict, o: dict) -> set:
    """태그 PDF의 Figure 요소를 (쪽, 위치)로 우리 그림과 맞춰서 AI 그림 설명을 Alt로 넣는다. 맞춘 그림의 id 집합을 돌려준다."""
    pymupdf.TOOLS.mupdf_display_errors(False)               # 객체를 훑다가 나오는 무해한 경고(invalid key in dict)로 로그가 넘치지 않게
    try:
        return _apply_alts(pdf, doc, o)
    finally:
        pymupdf.TOOLS.mupdf_display_errors(True)


def _apply_alts(pdf, doc: dict, o: dict) -> set:
    done: set = set()
    page_of = {pdf.page_xref(i): i for i in range(len(pdf))}
    figs_by_page = {}
    for pg in doc["pages"]:
        figs_by_page[pg["n"] - 1] = [b for b in pg["blocks"] if b["type"] == "figure" and b.get("bbox") and not (b.get("fullpage") and pg.get("ocr_done"))]
    for x in range(1, pdf.xref_length()):
        try:
            if pdf.xref_get_key(x, "S")[1] != "/Figure":
                continue
            pgref = pdf.xref_get_key(x, "Pg")
            if pgref[0] != "xref":
                continue
            pi = page_of.get(int(pgref[1].split()[0]))
            bbox = pdf.xref_get_key(x, "A/BBox")
            if pi is None or bbox[0] == "null":
                continue
            x0, y0, x1, y1 = (float(v) for v in bbox[1].strip("[] ").split())
        except Exception:
            continue
        H = pdf[pi].rect.height
        box = (x0, H - y1, x1, H - y0)                       # PDF 좌표(아래가 0) → 우리 좌표(위가 0)
        best, best_iou = None, MATCH_IOU
        for b in figs_by_page.get(pi, []):
            v = _iou(box, tuple(b["bbox"]))
            if v >= best_iou:
                best, best_iou = b, v
        if best is None:
            continue
        d = best.get("ai_desc") or {}
        desc = d.get("desc") or ""
        if not desc:
            continue
        cur = pdf.xref_get_key(x, "Alt")
        if cur[0] != "null" and not _PLACEHOLDER.match(_alt_text(pdf, x)):
            done.add(best["id"])                             # 원본에 이미 쓸 만한 Alt가 있으면 그대로 둔다
            continue
        text = f"그림 설명. {desc}"
        if d.get("color_note"):
            text += f" 색 설명. {d['color_note']}"
        inner = [t for t in dict.fromkeys((best.get("inner_text") or []) + (d.get("texts") or [])) if t]
        if inner:
            text += " 그림 속 글자: " + ", ".join(inner)
        pdf.xref_set_key(x, "Alt", pymupdf.get_pdf_str(text[:2500]))
        done.add(best["id"])
    return done


def _alt_text(pdf, x) -> str:
    """Alt 값을 사람이 읽는 글로 (PDF 문자열이 16진수 UTF-16일 수도 있다)."""
    t, v = pdf.xref_get_key(x, "Alt")
    if t == "null":
        return ""
    v = v.strip()
    try:
        if v.startswith("<"):
            raw = bytes.fromhex(v.strip("<>"))
            return raw.decode("utf-16-be", "ignore").lstrip("\ufeff")
        if v.startswith("("):
            return v[1:-1]
    except Exception:
        pass
    return v
