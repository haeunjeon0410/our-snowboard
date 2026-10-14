"""시연 전에 AI 결과를 미리 만들어 둔다. 같은 자료를 같은 항목으로 다시 변환하면 AI를 부르지 않고 몇 초 만에 끝난다.
실행: python tools/warm_cache.py samples/제2장.pdf samples/MIS_Week02.pdf   (파일을 여러 개 줄 수 있다)
그림 설명·단어 뜻·영어 용어·띄어쓰기를 모두 한 번 채워 두므로, 시연에서 어떤 방식(저시력·색각 이상·교환학생…)을 골라도 빠르다.
AI 크레딧을 쓴다 (이미 해 둔 자료는 캐시라서 쓰지 않는다)."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import jobs, ops  # noqa: E402


def warm(path: Path) -> None:
    jid = jobs.create(path.read_bytes(), path.name, "", path.stem)
    job = jobs.get(jid)
    info = ops.analyze(job, True)
    o = dict(figures=True, easy=True, terms=True, color=True, contrast=False, large=False, pdf=True, readpdf=False, html=True, braille=True)
    t = time.time()
    tid = ops.start(job, o, True)
    while ops.TASKS[tid]["status"] == "running":
        time.sleep(0.3)
    st = ops.TASKS[tid]
    print(f"{path.name}: {st['status']} {time.time() - t:.1f}초 ({info['pages']}쪽, 그림 {info['figures']}개)" + (f" · {st['note']}" if st["note"] else ""))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        warm(Path(p))
