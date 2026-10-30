"""AI 프롬프트 틀이 모두 오류 없이 채워지는지 점검 (AI 호출 없음). 실행: python -m eval.test_prompts
프롬프트를 고칠 때 자리표시자({payload} 등)가 어긋나면 해당 기능이 조용히 실패한 채 지나가므로, 고친 뒤에는 이 점검을 돌린다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import enrich as E  # noqa: E402

CASES = {
    "띄어쓰기": lambda: E.SPACING_PROMPT.format(payload='["x"]'),
    "그림 설명": lambda: E.FIG_PROMPT.format(kind="그림", page_note="", context="없음"),
    "단어 뜻": lambda: E.EASYWORD_PROMPT.format(domain=E._domain("민법총칙"), payload='["x"]'),
    "영어 용어": lambda: E.TERMS_PROMPT.format(domain="", payload='["x"]'),
    "단어 뜻+영어 용어": lambda: E.BOTH_PROMPT.format(domain=E._domain(""), payload='["x"]'),
    "의미 점검(검토)": lambda: E.SEM_VERIFY_PROMPT.format(desc="설명", labels="a | b"),
    "의미 점검(수정)": lambda: E.SEM_REVISE_PROMPT.format(desc="설명", crit="- 지적"),
}

if __name__ == "__main__":
    bad = 0
    for name, make in CASES.items():
        try:
            text = make()
            print(f"OK   {name} ({len(text)}자)")
        except Exception as e:
            bad += 1
            print(f"FAIL {name}: {type(e).__name__}({e})")
    sys.exit(1 if bad else 0)
