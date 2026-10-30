"""전공 용어 영어 병기 정확도. 실행: python -m eval.terms_eval  (결과는 output/_eval/terms.json)
법학·생물·의학·경영/보안 용어 문장에 표준 영어 표기를 정답지로 두고, 과목 정보를 넣었을 때와 뺐을 때의 영어 병기를 비교한다.
정답지는 개발자가 직접 만든 소규모 목록(약 40개)이라 일반화된 정확도가 아니라 '전공 용어를 맞게 짝짓는가'의 점검용이다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import enrich, llm  # noqa: E402

# (과목, [(문장, 용어, 인정하는 영어 표기들)])
GOLD = [
    ("민법총칙", [
        ("선의의 제3자에게는 대항하지 못한다.", "선의", ["good faith", "bona fide"]),
        ("채권자는 채무자에게 이행을 청구할 수 있다.", "채권자", ["creditor"]),
        ("채권자는 채무자에게 이행을 청구할 수 있다.", "채무자", ["debtor", "obligor"]),
        ("불법행위로 인한 손해배상책임이 성립한다.", "불법행위", ["tort", "wrongful act"]),
        ("소멸시효가 완성되면 권리는 소멸한다.", "소멸시효", ["extinctive prescription", "statute of limitations", "limitation"]),
        ("물권은 물건을 직접 지배하는 권리이다.", "물권", ["real right", "right in rem", "property right", "in rem"]),
        ("가처분을 신청하여 임시의 지위를 정한다.", "가처분", ["provisional", "preliminary injunction", "interim"]),
        ("법인의 대표자가 직무에 관하여 타인에게 손해를 가하였다.", "법인", ["juridical person", "juristic person", "legal entity", "legal person", "corporation"]),
        ("고의 또는 과실로 타인에게 손해를 가한 경우에 배상한다.", "과실", ["negligence"]),
        ("고의 또는 과실로 타인에게 손해를 가한 경우에 배상한다.", "고의", ["intent", "willful", "deliberate"]),
    ]),
    ("헌법·형사법", [
        ("무죄추정의 원칙이 피고인에게 적용된다.", "무죄추정", ["presumption of innocence"]),
        ("항소심 법원은 원심판결을 파기하였다.", "항소", ["appeal"]),
        ("위헌법률심판을 제청하였다.", "위헌법률심판", ["constitutional review", "judicial review", "constitutionality"]),
        ("상법상 주주의 유한책임이 인정된다.", "유한책임", ["limited liability"]),
        ("상법상 주주의 유한책임이 인정된다.", "주주", ["shareholder", "stockholder"]),
    ]),
    ("일반생물학", [
        ("광합성은 엽록체에서 일어난다.", "광합성", ["photosynthesis"]),
        ("광합성은 엽록체에서 일어난다.", "엽록체", ["chloroplast"]),
        ("미토콘드리아는 ATP를 합성한다.", "미토콘드리아", ["mitochondri"]),
        ("감수분열 과정에서 상동 염색체가 분리된다.", "감수분열", ["meiosis"]),
        ("감수분열 과정에서 상동 염색체가 분리된다.", "상동 염색체", ["homologous chromosome"]),
        ("삼투 현상에 의해 물이 이동한다.", "삼투", ["osmosis", "osmotic"]),
        ("전사 과정에서 mRNA가 합성된다.", "전사", ["transcription"]),
        ("효소는 활성화 에너지를 낮춘다.", "효소", ["enzyme"]),
        ("효소는 활성화 에너지를 낮춘다.", "활성화 에너지", ["activation energy"]),
    ]),
    ("현대인의 뇌질환", [
        ("봉선핵에서 세로토닌 신경이 시작된다.", "봉선핵", ["raphe"]),
        ("시상하부는 항상성 유지에 관여한다.", "시상하부", ["hypothalamus"]),
        ("시상하부는 항상성 유지에 관여한다.", "항상성", ["homeostasis"]),
        ("신경관 형성은 복합적인 과정이다.", "신경관", ["neural tube"]),
        ("기저핵의 도파민 신경세포가 소실된다.", "기저핵", ["basal ganglia", "basal nuclei"]),
        ("혈액뇌장벽은 물질의 이동을 선택적으로 제한한다.", "혈액뇌장벽", ["blood-brain barrier", "blood brain barrier"]),
    ]),
    ("경영정보시스템 · 정보보호", [
        ("공급망 관리는 기업의 경쟁우위를 높인다.", "공급망 관리", ["supply chain management"]),
        ("공급망 관리는 기업의 경쟁우위를 높인다.", "경쟁우위", ["competitive advantage"]),
        ("대칭키 암호는 같은 키로 암호화와 복호화를 한다.", "대칭키", ["symmetric"]),
        ("대칭키 암호는 같은 키로 암호화와 복호화를 한다.", "복호화", ["decrypt"]),
        ("방화벽은 허가되지 않은 접근을 차단한다.", "방화벽", ["firewall"]),
        ("거래비용이 낮아지면 기업의 경계가 변한다.", "거래비용", ["transaction cost"]),
    ]),
]


def run(course_on: bool):
    chosen = right = total = 0
    wrong = []
    for course, items in GOLD:
        texts = list(dict.fromkeys(s for s, _, _ in items))
        got = enrich.english_terms(texts, course if course_on else "")
        if got is None:
            continue
        for sent, ko, ok in items:
            total += 1
            m = [g for g in got if ko.replace(" ", "") in g["ko"].replace(" ", "") or g["ko"].replace(" ", "") in ko.replace(" ", "")]
            if not m:
                continue
            chosen += 1
            if any(any(v in g["en"].lower() for v in ok) for g in m):
                right += 1
            else:
                wrong.append({"ko": ko, "got": [g["en"] for g in m], "expected": ok})
    return {"gold": total, "chosen": chosen, "right": right, "wrong": wrong}


def main():
    if not llm.available():
        sys.exit("AI 키가 없어 측정할 수 없습니다 (.env의 GATEWAY_API_KEY)")
    res = {"with_course": run(True), "without_course": run(False)}
    d = ROOT / "output" / "_eval"
    d.mkdir(parents=True, exist_ok=True)
    (d / "terms.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(f"{k}: 용어 {v['gold']}개 중 골라 냄 {v['chosen']}개 · 영어가 맞음 {v['right']}개 (고른 것 중 {v['right'] / max(1, v['chosen']):.0%})")
        for w in v["wrong"]:
            print("   틀림:", w["ko"], "→", w["got"], "(정답 후보", w["expected"], ")")


if __name__ == "__main__":
    main()
