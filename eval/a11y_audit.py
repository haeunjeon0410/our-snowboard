"""현재 강의자료(원본 PDF)의 접근성 실태. 실행: python -m eval.a11y_audit  (AI 호출 없음)
samples/ 의 PDF에서 ① 구조 태그가 있는지 ② 그림(Figure)에 대체 텍스트(Alt)가 있는지 ③ 쪽에 들어 있는 그림 수를 센다."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pymupdf  # noqa: E402

pymupdf.TOOLS.mupdf_display_errors(False)


def audit(path: Path) -> dict:
    d = pymupdf.open(str(path))
    cat = d.pdf_catalog()
    tagged = d.xref_get_key(cat, "StructTreeRoot")[0] != "null"
    figs = alts = 0
    for x in range(1, d.xref_length()):
        try:
            if d.xref_get_key(x, "S")[1] == "/Figure":
                figs += 1
                alt = d.xref_get_key(x, "Alt")
                if alt[0] != "null" and alt[1].strip("() <>") not in ("", "FEFF"):
                    alts += 1
        except Exception:
            continue
    images = sum(len(p.get_images(full=True)) for p in d)
    return {"file": path.name, "pages": len(d), "tagged": tagged, "figure_tags": figs, "figure_alts": alts, "images": images}


def main():
    seen, rows = set(), []
    for p in sorted((ROOT / "samples").glob("*.pdf")):
        h = hashlib.sha1(p.read_bytes()).hexdigest()
        if h in seen:                                          # 같은 파일을 복사해 둔 것은 한 번만
            continue
        seen.add(h)
        rows.append(audit(p))
    tot = lambda k: sum(r[k] for r in rows)
    out = {"files": len(rows), "pages": tot("pages"), "tagged_files": sum(r["tagged"] for r in rows),
           "figure_tags": tot("figure_alts") and tot("figure_tags") or tot("figure_tags"), "figure_alts": tot("figure_alts"), "images": tot("images"), "rows": rows}
    (ROOT / "output" / "_eval").mkdir(parents=True, exist_ok=True)
    (ROOT / "output" / "_eval" / "a11y_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"PDF {out['files']}개 {out['pages']}쪽: 구조 태그가 있는 파일 {out['tagged_files']}개, 쪽에 삽입된 이미지 {out['images']}개")
    print(f"태그된 파일 안의 Figure 요소 {out['figure_tags']}개 중 Alt가 있는 것 {out['figure_alts']}개")
    for r in rows:
        print(f"  {r['file'][:34]:34} {r['pages']:3}쪽 태그={'O' if r['tagged'] else 'X'} 이미지 {r['images']:3} Figure {r['figure_tags']:3} Alt {r['figure_alts']}")


if __name__ == "__main__":
    main()
