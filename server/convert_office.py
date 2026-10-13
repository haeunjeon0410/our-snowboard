"""PowerPoint(.ppt/.pptx)를 PDF로 바꾼다. 바꾼 뒤에는 PDF와 똑같이 처리한다.

- Windows에 PowerPoint가 있으면 PowerPoint로 내보낸다 (슬라이드 모습 그대로, 가장 정확하다).
- 없으면 LibreOffice(soffice)가 있을 때 그것으로 바꾼다.
- 둘 다 없으면 Unsupported 를 일으킨다 (화면에는 친절한 안내가 나간다).
한 번 바꾼 파일은 보관해 두고 다시 바꾸지 않는다."""
import hashlib
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from . import config

_LOCK = threading.Lock()                 # PowerPoint는 한 번에 하나씩만 다룬다
_CACHE = config.DATA_DIR / "_converted"


TIMEOUT_S = 90


class Unsupported(Exception):
    pass


def kind(head: bytes, filename: str = "") -> str:
    """올라온 파일이 어떤 종류인지: 'pdf' / 'pptx' / 'ppt' / ''"""
    ext = Path(filename or "").suffix.lower()
    if head[:5] == b"%PDF-":
        return "pdf"
    if head[:4] == b"PK\x03\x04" and ext in (".pptx", ".pptm", ".ppsx", ""):
        return "pptx"
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and ext in (".ppt", ".pps"):
        return "ppt"
    return ""


def _powerpoint(src: Path, dst: Path, state: dict):
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    app = None
    started_here = False
    try:
        try:
            app = win32com.client.GetActiveObject("PowerPoint.Application")      # 사용자가 이미 켜 둔 PowerPoint는 건드리지 않고 그대로 쓴다
        except Exception:
            app = win32com.client.DispatchEx("PowerPoint.Application")
            started_here = state["started"] = True
        pres = app.Presentations.Open(str(src), True, False, False)             # 읽기 전용, 제목 없음 아님, 창 없이
        try:
            pres.SaveAs(str(dst), 32)                                          # 32 = PDF
        finally:
            pres.Close()
    finally:
        try:
            if app is not None and started_here and app.Presentations.Count == 0:
                app.Quit()
        except Exception:
            pass
        pythoncom.CoUninitialize()


def _soffice(src: Path, outdir: Path) -> Path:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise Unsupported("PowerPoint 파일을 PDF로 바꿀 프로그램이 이 컴퓨터에 없어요")
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(src)], check=True, timeout=180,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return outdir / (src.stem + ".pdf")


def to_pdf(data: bytes, ext: str = ".pptx") -> bytes:
    """PowerPoint 파일 내용 → PDF 내용. 같은 파일이면 보관해 둔 것을 쓴다."""
    key = hashlib.sha1(data).hexdigest()[:16]
    _CACHE.mkdir(parents=True, exist_ok=True)
    cached = _CACHE / f"{key}.pdf"
    if cached.exists():
        return cached.read_bytes()
    with _LOCK:
        if cached.exists():
            return cached.read_bytes()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            src = Path(td) / f"slides{ext if ext in ('.ppt', '.pptx', '.pps', '.ppsx', '.pptm') else '.pptx'}"
            src.write_bytes(data)
            out = Path(td) / "slides.pdf"
            err = None
            state = {"started": False, "error": None}

            def work():
                try:
                    _powerpoint(src, out, state)
                except BaseException as e:                                  # PowerPoint가 없거나 파일을 열지 못함
                    state["error"] = e
            th = threading.Thread(target=work, daemon=True)
            th.start()
            th.join(TIMEOUT_S)
            if th.is_alive():                                              # 암호·보호된 보기 창 때문에 멈춘 경우
                if state["started"]:                                       # 우리가 띄운 PowerPoint만 닫는다 (사용자가 켜 둔 것은 건드리지 않는다)
                    subprocess.run(["taskkill", "/F", "/IM", "POWERPNT.EXE"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                raise Unsupported("PowerPoint가 응답하지 않아요. 암호가 걸린 파일이면 변환할 수 없어요")
            err = state["error"]
            if isinstance(err, ImportError):
                err = Unsupported("PowerPoint 파일을 PDF로 바꿀 프로그램이 이 컴퓨터에 없어요")
            if not out.exists():
                try:
                    out = _soffice(src, Path(td))
                except Unsupported:
                    raise err if isinstance(err, Unsupported) else Unsupported("이 PowerPoint 파일을 PDF로 바꾸지 못했어요")
                except Exception:
                    raise Unsupported("이 PowerPoint 파일을 PDF로 바꾸지 못했어요")
            if not out.exists():
                raise Unsupported("이 PowerPoint 파일을 PDF로 바꾸지 못했어요")
            pdf = out.read_bytes()
            cached.write_bytes(pdf)
            return pdf
