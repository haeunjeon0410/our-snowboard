"""변환 품질 측정. 실행: python -m eval.run_eval  (샘플은 samples/ 에 둔다, 결과는 output/_eval/results.json)
측정하지 못하는 것(읽는 순서, 그림 설명의 의미 정확도)은 억지로 숫자를 만들지 않고 '사람 확인 필요'로 남긴다."""
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import braille_ko as B, color, config, enrich, extract, jobs, ops, outputs  # noqa: E402
from eval.braille_examples import EXAMPLES, to_unicode  # noqa: E402

WS = re.compile(r"\s+")
M = {}   # 요약 카드(KPI)용 숫자


def load_docs():
    """저장된 자료를 불러오고, 측정에 필요한 AI 결과(띄어쓰기·그림 설명)가 없는 쪽만 채운다 (이미 한 것은 캐시)."""
    jobs.load_existing()
    docs = {}
    o = dict(ops.DEFAULTS, figures=True)
    only = [x for x in os.environ.get("OSB_EVAL_ONLY", "").split(",") if x]   # 크레딧을 아끼려고 일부 파일만 잴 때: 파일 이름(확장자 제외)을 쉼표로
    for p in sorted((ROOT / "samples").glob("*.pdf")):                 # 측정 대상: samples/ 의 파일만 (같은 파일이면 이미 처리한 것을 그대로 쓴다)
        if only and p.stem not in only:
            continue
        jid = jobs.create(p.read_bytes(), p.name, "", p.stem)
        j = jobs.get(jid)
        todo = [pg for pg in j["doc"]["pages"] if ops._needs_work(pg, o)]
        for pg in todo:
            ops._work_page(j, pg, o)
        if todo:
            jobs.save(j)
        docs[p.name] = (jid, j["doc"])
    return docs


def norm(s):
    return WS.sub("", s)


def overview(docs):
    rows = []
    for name, (jid, doc) in docs.items():
        t = time.time()
        extract.extract(config.DATA_DIR / jid / "original.pdf", config.DATA_DIR / "_eval" / ("tmp_" + jid))
        sec = time.time() - t
        c = {"heading": 0, "paragraph": 0, "list": 0, "table": 0, "figure": 0, "code": 0}
        emph_pages = 0
        for pg in doc["pages"]:
            has = False
            for b in pg["blocks"]:
                c[b["type"]] += 1
                has |= bool(b.get("emph")) or any(i.get("emph") for i in b.get("items", []))
            emph_pages += has
        rows.append([name, doc["n_pages"], c["heading"], c["paragraph"], c["list"], c["table"], c["figure"], emph_pages, f"{sec:.1f}초 ({sec / doc['n_pages']:.2f}초/쪽)"])
    return {"title": "1. 변환 개요 (AI를 쓰지 않는 추출 단계)",
            "note": "글자 추출·읽는 순서 정리·제목/목록/표/그림 구분에 걸린 시간입니다. ‘색 강조 쪽’은 원본에서 색으로만 강조된 말이 있어 굵은 밑줄로 바꿔 준 쪽 수입니다.",
            "head": ["파일", "쪽 수", "제목", "문단", "목록", "표", "그림·도식", "색 강조 쪽", "추출 시간"], "rows": rows}


def spacing_eval(docs):
    """정답 띄어쓰기가 있는 문서로: 띄어쓰기를 지운 뒤 AI가 복원하게 하고 위치를 비교한다."""
    src = next((d for n, d in docs.items() if n.startswith("MIS")), None)
    if not src:
        return None
    texts = []
    for pg in src[1]["pages"]:
        for b in pg["blocks"]:
            cand = [b["text"]] if b["type"] in ("paragraph", "heading") else [i["text"] for i in b.get("items", [])] if b["type"] == "list" else []
            for t in cand:
                if 25 <= len(t) <= 260 and t.count(" ") >= 4 and len(re.findall(r"[가-힣]", t)) >= 15 and "ai" not in b:
                    texts.append(t)
    texts = texts[:100]
    stripped = [norm(t) for t in texts]
    restored = enrich.restore_spacing(stripped)
    tp = fp = fn = exact = accepted = 0
    for gold, s_in, out in zip(texts, stripped, restored):
        out = s_in if out is None else out
        accepted += out != s_in
        gset = set(); k = 0
        for ch in gold:
            if ch == " ":
                gset.add(k)
            else:
                k += 1
        pset = set(); k = 0
        for ch in out:
            if ch == " ":
                pset.add(k)
            else:
                k += 1
        tp += len(gset & pset); fp += len(pset - gset); fn += len(gset - pset)
        exact += out.strip() == gold.strip()
    p = tp / max(1, tp + fp); r = tp / max(1, tp + fn)
    f1 = 2 * p * r / max(1e-9, p + r)
    M["spacing_f1"] = f1; M["spacing_n"] = len(texts)
    ktp = kfp = kfn = kexact = 0                                     # 같은 문장으로 Kiwi(AI 없이)도 잰다: AI를 쓸 수 없을 때의 대체 수단
    for gold, s_in in zip(texts, stripped):
        kout = enrich.kiwi_space(s_in) or s_in
        kg, kp = set(), set(); k = 0
        for ch in gold:
            kg.add(k) if ch == " " else None
            k += ch != " "
        k = 0
        for ch in kout:
            kp.add(k) if ch == " " else None
            k += ch != " "
        ktp += len(kg & kp); kfp += len(kp - kg); kfn += len(kg - kp); kexact += kout.strip() == gold.strip()
    kprec = ktp / max(1, ktp + kfp); krec = ktp / max(1, ktp + kfn)
    kf1 = 2 * kprec * krec / max(1e-9, kprec + krec)
    M["spacing_kiwi_f1"] = kf1
    return {"title": "2. 띄어쓰기 복원 정확도 (뇌질환 자료처럼 띄어쓰기가 사라진 글 대비)",
            "note": "정답이 있는 MIS 문서의 문장 %d개에서 띄어쓰기를 모두 지운 뒤 AI에게 복원하게 하고, 원문의 띄어쓰기 위치와 비교했습니다. AI가 글자를 하나라도 바꾸면 그 문장은 버리고 원문을 씁니다." % len(texts),
            "head": ["지표", "값"],
            "rows": [["평가한 문장 수", len(texts)], ["띄어쓰기 위치 정밀도", f"{100 * p:.1f}%"], ["띄어쓰기 위치 재현율", f"{100 * r:.1f}%"],
                     ["띄어쓰기 위치 F1", f"{100 * f1:.1f}%"], ["문장 전체가 정답과 똑같은 비율", f"{100 * exact / len(texts):.1f}%"],
                     ["글자가 바뀌어 거부된 문장(원문 유지)", f"{len(texts) - accepted}개"],
                     ["(비교) Kiwi로 AI 없이 복원한 F1", f"{100 * kf1:.1f}%  · 문장 전체 일치 {100 * kexact / len(texts):.1f}%"]]}


def braille_eval(docs):
    rows = []
    tot = ok_s = ok_c = 0
    unm = {}
    for name, (jid, doc) in docs.items():
        pages, st = outputs.braille_pages(doc)
        segs = [s for p in pages for s in p["segs"]]
        a = sum(s["match"] for s in segs); b = sum(s["cells_same"] for s in segs)
        tot += len(segs); ok_s += a; ok_c += b
        for k, v in st["unmapped"].items():
            unm[k] = unm.get(k, 0) + v
        rows.append([name, len(segs), f"{100 * a / len(segs):.1f}%", f"{100 * b / len(segs):.1f}%", st["chars"]])
    rows.append(["합계", tot, f"{100 * ok_s / tot:.1f}%", f"{100 * ok_c / tot:.1f}%", ""])
    good = 0
    bad = []
    for ko, asc in EXAMPLES:
        got = B.encode(ko)
        exp = to_unicode(asc, B._ASCII_BRAILLE)
        if got == exp:
            good += 1
        else:
            bad.append(ko)
    un = " ".join(f"{k}×{v}" for k, v in sorted(unm.items(), key=lambda x: -x[1])[:10]) or "없음"
    M["b_examples"] = (good, len(EXAMPLES)); M["b_strict"] = ok_s / tot; M["b_cells"] = ok_c / tot; M["b_n"] = tot
    return [{"title": "3-1. 한글 점자: 규정 해설서 예시 대조",
             "note": "국립국어원 「한글 점자 규정 해설」(2017 개정 한국 점자 규정)에 실린 예시 낱말·문장을 그대로 점역해서 책에 적힌 점자와 비교했습니다.",
             "head": ["지표", "값"], "rows": [["대조한 예시 수", len(EXAMPLES)], ["책의 점자와 똑같이 나온 예시", f"{good}개 ({100 * good / len(EXAMPLES):.1f}%)"], ["다르게 나온 예시", ", ".join(bad) or "없음"]]},
            {"title": "3-2. 한글 점자: 역점역 일치율 (샘플 자료 전체)",
             "note": "변환한 점자를 같은 규칙표로 다시 글로 되돌려 원문과 비교했습니다. ‘글자까지 일치’는 되돌린 글이 원문과 똑같은 비율, ‘점자는 동일’은 규정상 같은 점자로 적히는 낱말(예: ‘가?’와 ‘같’은 점형이 같음)을 같은 것으로 본 비율입니다. 점역하지 못한 글자(수식·특수기호): " + un,
             "head": ["파일", "문단 수", "글자까지 일치", "점자는 동일", "점역한 글자 수"], "rows": rows}]


def figure_eval(docs):
    rows = []
    for name, (jid, doc) in docs.items():
        figs = [b for pg in doc["pages"] for b in pg["blocks"] if b["type"] == "figure"]
        done = [b for b in figs if b.get("ai_desc")]
        err = [b for b in figs if b.get("describe") == "error"]
        # PDF 안에 글자로 들어 있던 그림 속 글자를 AI가 얼마나 다시 읽어 냈는가
        have = tot = hit = 0
        for b in done:
            truth = [norm(t) for t in (b.get("inner_text_raw") or b.get("inner_text") or []) if len(norm(t)) >= 2]
            if not truth:
                continue
            have += 1
            blob = norm(" ".join((b["ai_desc"].get("texts") or []) + [b["ai_desc"].get("desc", ""), b["ai_desc"].get("summary", ""), b["ai_desc"].get("detail", "")]))
            for t in truth:
                tot += 1
                hit += t in blob
        avg = sum(len(b["ai_desc"].get("desc", "") or (b["ai_desc"].get("summary", "") + b["ai_desc"].get("detail", ""))) for b in done) / max(1, len(done))
        rows.append([name, len(figs), len(done), len(err), f"{avg:.0f}자", have, f"{100 * hit / tot:.1f}% ({hit}/{tot})" if tot else "-"])
        M["fig_total"] = M.get("fig_total", 0) + len(figs); M["fig_done"] = M.get("fig_done", 0) + len(done); M["fig_err"] = M.get("fig_err", 0) + len(err)
        M["fig_hit"] = M.get("fig_hit", 0) + hit; M["fig_tot"] = M.get("fig_tot", 0) + tot
    return {"title": "4. 그림·도식 설명",
            "note": "‘글자 재현율’은 PDF 안에 글자로 들어 있던 그림 속 문구(도식 안의 라벨)를 AI의 설명과 읽어낸 글자가 얼마나 다시 담았는지 잰 값입니다. 설명이 사실과 맞는지(의미 정확도)는 자동으로 잴 수 없어 사람 확인이 필요합니다.",
            "head": ["파일", "그림·도식", "설명 생성", "실패", "평균 설명 길이", "글자 검증 가능한 그림", "그림 속 글자 재현율"], "rows": rows}


def color_eval(docs):
    rows = []
    for name, (jid, doc) in docs.items():
        n_pg = 0
        per = {m: ([], []) for m in ("deutan", "protan", "tritan")}
        normal = []
        for pg in doc["pages"]:
            png = extract.render_page_png(config.DATA_DIR / jid / "original.pdf", config.DATA_DIR / jid / "pages" / f"p{pg['n']}.png", pg["n"])
            pal = color.page_palette(png)
            if len(pal) < 2:
                continue
            n_pg += 1
            hexes = [g["hex"] for g in pal]
            normal.append(color.min_confusion(hexes))
            for m in per:
                per[m][0].append(color.min_confusion(hexes, m, False))
                per[m][1].append(color.min_confusion(hexes, m, True, color.best_gain(hexes, m)))
        if not n_pg:
            rows.append([name, 0, "-", "-", "-", "-"])
            continue
        avg = lambda xs: sum(xs) / len(xs)
        M.setdefault("color", []).append((name, avg(per["deutan"][0]), avg(per["deutan"][1])))
        rows.append([name, n_pg, f"{avg(normal):.1f}", f"{avg(per['deutan'][0]):.1f} → {avg(per['deutan'][1]):.1f}",
                     f"{avg(per['protan'][0]):.1f} → {avg(per['protan'][1]):.1f}", f"{avg(per['tritan'][0]):.1f} → {avg(per['tritan'][1]):.1f}"])
    return {"title": "5. 색각 이상 지원 (색 구분 정도)",
            "note": "색이 2종류 이상 칠해진 쪽에서, 가장 비슷해 보이는 두 색의 색차(CIE76 ΔE)를 평균 냈습니다. 값이 클수록 구분이 쉽고 3 이하면 거의 같은 색으로 보입니다. ‘A → B’는 보정 전 → 보정 후입니다(보정 세기는 쪽마다 가장 잘 구분되는 값을 고르고, 보정이 오히려 나쁘면 보정하지 않습니다). 보정으로도 부족한 경우를 위해 같은 색에 같은 무늬를 덧씌우는 기능을 함께 제공합니다.",
            "head": ["파일", "측정한 쪽 수", "일반 시각", "녹색약(2형) 보정 전→후", "적색약(1형) 보정 전→후", "청황색약(3형) 보정 전→후"], "rows": rows}


def usage_eval():
    p = config.CACHE_DIR / "usage.jsonl"
    calls = tin = tout = 0
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(l); calls += 1; tin += r["in"]; tout += r["out"]
    return {"title": "6. AI 사용량 (개발 중 누적)", "note": "같은 입력은 디스크에 저장해 두고 다시 호출하지 않습니다(캐시).",
            "head": ["지표", "값"], "rows": [["AI 호출 수", calls], ["입력 토큰", f"{tin:,}"], ["출력 토큰", f"{tout:,}"]]}


def main():
    docs = load_docs()
    if not docs:
        print("output/ 에 변환된 문서가 없습니다. 먼저 samples 의 PDF를 변환하세요."); return
    secs = [overview(docs)]
    s = spacing_eval(docs)
    if s:
        secs.append(s)
    secs += braille_eval(docs)
    secs.append(figure_eval(docs))
    secs.append(color_eval(docs))
    secs.append(usage_eval())
    secs.append({"title": "측정하지 못한 것 (사람 확인 필요)", "note": "아래 항목은 자동으로 정확도를 잴 수 없어 숫자를 만들지 않았습니다. 변환이 끝난 화면의 ‘원본과 비교’로 사람이 직접 확인합니다.",
                 "head": ["항목", "이유"], "rows": [["읽는 순서가 올바른지", "정답 순서가 없음"], ["그림 설명이 사실과 맞는지", "의미 판단이 필요함"], ["단어 뜻(쉬운 말·영어)이 알맞은지", "의미 판단이 필요함"]]})
    kpis = []
    if "b_examples" in M:
        g, n = M["b_examples"]
        kpis.append({"label": "점자: 규정 예시 일치", "value": f"{g}/{n}", "caption": "국립국어원 「한글 점자 규정 해설」 예시를 그대로 점역해 책의 점자와 대조", "tone": "ok"})
        kpis.append({"label": "점자: 역점역 글자 일치", "value": f"{100 * M['b_strict']:.1f}%", "caption": f"샘플 {M['b_n']}문단을 점자로 바꿨다가 다시 글로 되돌려 원문과 비교 (점자는 동일 {100 * M['b_cells']:.1f}%)", "tone": "ok"})
    if "spacing_f1" in M:
        kpis.append({"label": "띄어쓰기 복원 F1", "value": f"{100 * M['spacing_f1']:.1f}%", "caption": f"정답 있는 문장 {M['spacing_n']}개의 띄어쓰기를 지운 뒤 복원시켜 위치를 비교", "tone": "primary"})
    if M.get("fig_tot"):
        kpis.append({"label": "도식 속 글자 재현율", "value": f"{100 * M['fig_hit'] / M['fig_tot']:.1f}%", "caption": f"PDF 안의 도식 라벨 {M['fig_tot']}개 중 AI 설명이 다시 담은 비율", "tone": "ai"})
    if M.get("fig_total"):
        kpis.append({"label": "그림·도식 설명 생성", "value": f"{M['fig_done']}/{M['fig_total']}", "caption": f"샘플의 그림·도식 {M['fig_total']}개 중 설명을 만든 수 (실패 {M.get('fig_err', 0)}개)", "tone": "ai"})
    if M.get("color"):
        n = len(M["color"])                       # 색이 칠해진 도식이 있는 샘플 전체의 평균 (가장 나쁜 샘플 하나만 보여 주지 않는다)
        a = sum(x[1] for x in M["color"]) / n
        b = sum(x[2] for x in M["color"]) / n
        kpis.append({"label": "색 구분 (녹색약 기준 ΔE)", "value": f"{a:.1f} → {b:.1f}", "caption": f"색 도식이 있는 샘플 {n}개 평균, 가장 헷갈리는 두 색의 색차 보정 전 → 후 (클수록 구분이 쉬움)", "tone": "primary"})
    out = {"when": datetime.now().strftime("%Y-%m-%d %H:%M"), "samples": list(docs.keys()), "kpis": kpis, "sections": secs}
    d = config.DATA_DIR / "_eval"
    d.mkdir(exist_ok=True)
    (d / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # 사람이 읽는 요약
    md = [f"# 변환 품질 측정 결과 ({out['when']})", ""]
    for s in secs:
        md += [f"## {s['title']}", s.get("note", ""), "", "| " + " | ".join(s["head"]) + " |", "|" + "---|" * len(s["head"])]
        md += ["| " + " | ".join(str(c) for c in r) + " |" for r in s["rows"]] + [""]
    (d / "results.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
