"""그림 설명 자기검증의 효과 측정. 실행: python -m eval.verify_eval  (결과는 output/_eval/verify.json)
PDF 안에 글자로 들어 있는 그림 속 라벨이 3개 이상인 그림만 대상으로, 첫 시도의 라벨 재현율과 검증(재시도) 뒤 재현율을 비교한다.
같은 입력은 캐시되므로 다시 돌려도 크레딧이 들지 않는다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import enrich, jobs, llm  # noqa: E402


def main():
    if not llm.available():
        sys.exit("AI 키가 없어 측정할 수 없습니다 (.env의 GATEWAY_API_KEY)")
    jobs.load_existing()
    rows, done = [], set()
    for p in sorted((ROOT / "samples").glob("*.pdf")):
        jid = jobs.create(p.read_bytes(), p.name, "", p.stem)
        if jid in done:                                    # 같은 파일을 복사해 둔 것은 한 번만
            continue
        done.add(jid)
        job = jobs.get(jid)
        d = jobs.job_dir(jid)
        for pg in job["doc"]["pages"]:
            ctx = " ".join(b.get("text", "") for b in pg["blocks"] if b["type"] in ("heading", "paragraph"))
            for b in pg["blocks"]:
                if b["type"] != "figure" or b.get("fullpage") or len(enrich._truth_labels(b.get("inner_text"))) < enrich.VERIFY_MIN_LABELS:
                    continue
                r = enrich.describe_checked((d / b["img"]).read_bytes(), b.get("fig_kind", "image"), ctx, False, b.get("inner_text"))
                v = r.get("verify")
                if v:
                    rows.append({"file": p.name, "page": pg["n"], "id": b["id"], **v})
                    print(f"{p.stem[:28]:28} p{pg['n']:<3} 라벨 {v['n']:>2}개  첫 시도 {v['first']:.0%} → 검증 후 {v['recall']:.0%}" + ("  (재시도)" if v["retried"] else "") + ("  ※확인 필요" if v["flag"] else ""))
    n = len(rows)
    if not n:
        sys.exit("검증할 수 있는 그림이 없습니다")
    first = sum(r["first"] * r["n"] for r in rows) / sum(r["n"] for r in rows)
    final = sum(r["recall"] * r["n"] for r in rows) / sum(r["n"] for r in rows)
    out = {"figures": n, "labels": sum(r["n"] for r in rows), "first_recall": round(first, 4), "final_recall": round(final, 4),
           "retried": sum(r["retried"] for r in rows), "flagged": sum(r["flag"] for r in rows),
           "below_pass_first": sum(r["first"] < enrich.VERIFY_PASS for r in rows), "rows": rows}
    (ROOT / "output" / "_eval").mkdir(parents=True, exist_ok=True)
    (ROOT / "output" / "_eval" / "verify.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n그림 {n}개 · 라벨 {out['labels']}개: 첫 시도 {first:.1%} → 검증 후 {final:.1%} "
          f"(기준 {enrich.VERIFY_PASS:.0%} 미달 {out['below_pass_first']}개 → 재시도 {out['retried']}개 → 끝내 확인 필요 {out['flagged']}개)")


if __name__ == "__main__":
    main()
