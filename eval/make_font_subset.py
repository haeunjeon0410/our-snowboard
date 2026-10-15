"""웹 문서에 넣는 Pretendard 부분 글꼴(server/static/fonts/PretendardKS.woff2)을 만든다.

KS X 1001 한글 2,350자 + 영문·숫자·기호 + 자주 쓰는 문장부호만 남긴다 (약 440KB).
글자를 고르는 데 1분 넘게 걸려서 변환할 때마다 하지 않고, 이 스크립트로 한 번만 만들어 저장소에 둔다.
글꼴을 바꿨거나 글자를 더하고 싶을 때만 다시 실행: python -m eval.make_font_subset  (brotli 필요)
"""
import io
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

STATIC = Path(__file__).resolve().parent.parent / "server" / "static" / "fonts"
EXTRA = "·…“”‘’–—→←↑↓×÷≤≥≠≈○●■□▲△▶◀※ⅠⅡⅢⅣⅤ①②③④⑤"


def chars() -> set[str]:
    out = {chr(c) for c in range(0x20, 0x7F)} | set(EXTRA)
    for hi in range(0xB0, 0xC9):                       # KS X 1001 한글 영역
        for lo in range(0xA1, 0xFF):
            try:
                out.add(bytes([hi, lo]).decode("euc_kr"))
            except UnicodeDecodeError:
                pass
    return out


def main():
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    font = TTFont(STATIC / "PretendardVariable.woff2")
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars())))
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    (STATIC / "PretendardKS.woff2").write_bytes(buf.getvalue())
    print("저장:", STATIC / "PretendardKS.woff2", len(buf.getvalue()) // 1024, "KB")


if __name__ == "__main__":
    main()
