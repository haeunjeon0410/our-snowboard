import pathlib

CSS = """
@font-face{font-family:Pretendard;src:url(assets/fonts/PretendardVariable.woff2) format("woff2");font-weight:100 900}
@page { size: 1920px 1080px; margin: 0; }
:root{
  --band:#DCE6F4; --bg:#F1F5FA; --card:#FFFFFF; --panel:#E7EEF8;
  --navy:#3F5A86; --ink:#1C2230; --ink2:#5B6678; --ink3:#8793A6;
  --line:#DCE4EF; --chipbd:#BFD0E8; --nav-off:#7F93B2;
  --green-bg:#E1EBE5; --green:#2F6B4A; --grey-bg:#E6EAF0;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:var(--band)}
body{word-break:keep-all;font-family:Pretendard,'Noto Sans CJK KR','Noto Sans KR',sans-serif;color:var(--ink);-webkit-font-smoothing:antialiased}
.s{width:1920px;height:1080px;position:relative;overflow:hidden;background:var(--band);page-break-after:always;break-after:page}
.s:last-child{page-break-after:auto;break-after:auto}
.s.cover{background:var(--bg)}
.nav{position:absolute;left:112px;top:20px;display:flex;gap:64px;font-size:28px;font-weight:500;color:var(--nav-off);line-height:36px}
.nav span.on{color:var(--navy);font-weight:700}
.sheet{position:absolute;left:34px;right:34px;top:72px;bottom:24px;background:#fff;border-radius:44px}
.pn{position:absolute;right:76px;top:1004px;font-size:26px;font-weight:500;color:var(--ink2)}
.hl{position:absolute;left:0;right:0;top:96px;height:186px;display:flex;align-items:center;justify-content:center;text-align:center;font-size:50px;font-weight:700;line-height:1.5;letter-spacing:-1px;color:var(--ink)}
.hl .lab{font-size:50px;margin-bottom:2px}
.em{background:var(--navy);color:#fff;padding:0 12px;border-radius:6px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
.rule{position:absolute;left:112px;right:112px;top:290px;height:2px;background:var(--navy)}
.stmt{position:absolute;left:112px;right:112px;top:948px;text-align:center;font-size:38px;font-weight:700;color:var(--navy);letter-spacing:-.5px}
.abs{position:absolute}
.pill{display:inline-flex;align-items:center;height:56px;padding:0 28px;border-radius:14px;background:#EEF3FB;border:2px solid var(--navy);color:var(--navy);font-size:28px;font-weight:700}
.pill.plain{border-color:transparent;background:var(--panel);color:var(--ink)}
.tag{display:inline-flex;align-items:center;height:44px;padding:0 20px;border-radius:22px;font-size:24px;font-weight:700}
.tag.navy{background:var(--navy);color:#fff}
.tag.out{background:#F5F9FE;color:var(--navy);border:2px solid var(--chipbd)}
.tag.green{background:var(--green-bg);color:var(--green)}
.tag.grey{background:var(--grey-bg);color:var(--ink2)}
.chip{display:inline-flex;align-items:center;height:54px;padding:0 24px;border-radius:27px;background:var(--panel);color:var(--ink);font-size:26px;font-weight:500;white-space:nowrap}
.box{background:var(--bg);border-radius:28px}
.ph{background:#E3EAF4;color:var(--ink2);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-size:26px;font-weight:500;line-height:1.5}
.ph small{font-size:22px;color:var(--ink3);margin-top:8px}
.win{background:#fff;border-radius:20px;overflow:hidden;border:1.5px solid var(--line)}
.win .bar{height:48px;background:#EEF2F8;border-bottom:1.5px solid var(--line);display:flex;align-items:center;padding:0 18px;position:relative}
.win .bar i{width:12px;height:12px;border-radius:6px;background:#CBD5E4;margin-right:8px;display:block}
.win .bar b{position:absolute;left:0;right:0;text-align:center;font-size:20px;font-weight:500;color:var(--ink3)}
.num{width:56px;height:56px;border-radius:28px;background:var(--navy);color:#fff;font-size:30px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none}
.arrow{position:relative;height:3px;flex:1;background:var(--navy)}
.arrow:after{content:"";position:absolute;right:-2px;top:-9px;border-left:18px solid var(--navy);border-top:10px solid transparent;border-bottom:10px solid transparent}
.navy{background:var(--navy);color:#fff;border-radius:32px}
.chk{width:30px;height:30px;border-radius:8px;display:inline-block;position:relative;flex:none}
.chk.on{background:var(--navy)}
.chk.off{background:#E3EAF4}
.chk.on svg{position:absolute;left:6px;top:7px}
"""

CHECK = ''
GROUPS = ['문제', '해결', '개발', '결과']


def slide(n, g, head, body, stmt=None):
    nav = ''.join('<span class="%s">%s</span>' % ('on' if i == g else '', t) for i, t in enumerate(GROUPS))
    st = '<div class="stmt">%s</div>' % stmt if stmt else ''
    return ('<section class="s"><div class="nav">%s</div><div class="sheet"></div>'
            '<div class="hl"><div>%s</div></div><div class="rule"></div>%s%s<div class="pn">%s</div></section>\n'
            % (nav, head, body, st, n))


def thumb(label, added=False, navy=False):
    bar = ''
    if added:
        bar = '<div style="position:absolute;left:26px;bottom:18px;height:34px;padding:0 14px;border-radius:17px;background:var(--green-bg);color:var(--green);font-size:22px;font-weight:700;display:flex;align-items:center">접근성 추가</div>'
    return ('<div><div style="width:360px;height:216px;background:#fff;border:1.5px solid var(--line);border-radius:14px;padding:28px 30px;position:relative">'
            '<div style="width:180px;height:18px;border-radius:9px;background:var(--navy)"></div>'
            '<div style="margin-top:18px;width:230px;height:11px;border-radius:6px;background:#D5DEEC"></div>'
            '<div style="margin-top:11px;width:180px;height:11px;border-radius:6px;background:#D5DEEC"></div>'
            '<div style="margin-top:11px;width:200px;height:11px;border-radius:6px;background:#D5DEEC"></div>'
            '<div style="position:absolute;right:30px;top:66px;width:100px;height:90px;border-radius:10px;background:#C9D8EE"></div>'
            '<div style="position:absolute;right:16px;bottom:8px;font-size:22px;color:var(--ink3);font-weight:700">8</div>%s</div>'
            '<div style="margin-top:14px;font-size:30px;font-weight:700;text-align:center;color:%s">%s</div></div>'
            % (bar, 'var(--navy)' if navy else 'var(--ink)', label))


out = []

# ---------- 1 표지 ----------
out.append('''<section class="s cover">
  <div class="abs" style="left:1060px;top:0;width:860px;height:1080px;background:var(--panel)"></div>
  <img class="abs" src="assets/mascot_color.png" style="left:1190px;top:120px;height:840px">
  <div class="abs" style="left:120px;top:150px;font-size:30px;font-weight:700;color:var(--navy)">2026 SW MVP 경진대회</div>
  <div class="abs" style="left:112px;top:230px;font-size:164px;line-height:1.08;font-weight:900;letter-spacing:-5px;color:var(--ink)">Our<br>Snowboard</div>
  <div class="abs" style="left:120px;top:640px;font-size:46px;line-height:1.45;font-weight:500;color:var(--ink);letter-spacing:-1px">모든 사람이 디지털 자료를<br>잘 이용할 수 있도록.</div>
  <div class="abs" style="left:120px;top:830px;font-size:28px;line-height:1.5;color:var(--ink2)">스노우보드 강의자료를 내 방식으로 받는 크롬 확장 프로그램</div>
  <div class="abs" style="left:120px;top:940px;font-size:28px;font-weight:700;color:var(--ink)">전하은<span style="font-weight:400;color:var(--ink2)"> &nbsp;·&nbsp; 2412957 &nbsp;·&nbsp; 소프트웨어학부 컴퓨터과학전공</span></div>
</section>
''')

def win(x, y, w, title, inner, h=None):
    hh = 'height:%spx;' % h if h else ''
    return ('<div class="abs win" style="left:%spx;top:%spx;width:%spx;%s"><div class="bar"><i></i><i></i><i></i><b>%s</b></div>%s</div>' % (x, y, w, hh, title, inner))

def badge(n, x, y):
    return '<div class="num abs" style="left:%spx;top:%spx;width:44px;height:44px;border-radius:22px;font-size:26px;box-shadow:0 0 0 4px #fff">%s</div>' % (x, y, n)

# ---------- 2 문제 ----------
def prob(top, n, t, d):
    return ('<div class="abs" style="left:1180px;top:%spx;width:628px;display:flex;gap:22px;align-items:flex-start">'
            '<div class="num" style="width:48px;height:48px;border-radius:24px;font-size:26px">%s</div>'
            '<div><div style="font-size:36px;font-weight:700;line-height:1.3">%s</div>'
            '<div style="font-size:27px;line-height:1.5;color:var(--ink2);margin-top:6px">%s</div></div></div>' % (top, n, t, d))
b2 = (win(112, 322, 1000, '현대인의뇌질환 · 제7장 강의자료 9쪽', '<img src="assets/orig_p9.png" style="display:block;width:100%">') +
      badge(1, 290, 478) + badge(2, 800, 560) + badge(3, 748, 398) + badge(4, 596, 366) +
      prob(330, 1, '그림 안의 이름표', '이미지 속 글자라서 스크린리더가 건너뜁니다') +
      prob(488, 2, '빨강·초록으로만 구분', '색각 이상이면 두 경로가 같은 색으로 보입니다') +
      prob(646, 3, '빨간 글씨로만 강조', '색을 구분하지 못하면 강조가 사라집니다') +
      prob(804, 4, '전문 용어와 영어', '외국인 학생에게는 한국어 전문 용어가 벽입니다'))
out.append(slide(2, 0, '같은 PDF인데, <span class="em">모두에게 읽히지는</span> 않습니다', b2,
                 '스노우보드에서 학생이 직접 쓸 수 있는 변환 기능은 확인되지 않았습니다'))

# ---------- 3 대상 ----------
def trow3(who, pain, feat, last=False):
    b = '' if last else 'border-bottom:2px solid #fff;'
    c = 'height:88px;display:flex;align-items:center;font-size:28px;%s' % b
    return ('<div style="%spadding-left:32px;font-weight:700">%s</div><div style="%sline-height:1.4;padding-right:24px">%s</div>'
            '<div style="%scolor:var(--navy);font-weight:700;line-height:1.4">%s</div>' % (c, who, c, pain, c, feat))
h3 = lambda t, p='': '<div style="height:56px;display:flex;align-items:center;%sfont-size:24px;font-weight:700;color:var(--ink3)">%s</div>' % (p, t)
b3 = ('<div class="abs box" style="left:112px;top:322px;width:1696px;display:grid;grid-template-columns:350px 700px 1fr">' +
      h3('대상', 'padding-left:32px;') + h3('겪는 불편') + h3('만든 기능') +
      trow3('시각장애 · 스크린리더', '이미지 PDF가 읽히지 않고, 읽는 순서가 뒤섞이고, 그림이 건너뛰어짐', '읽는 순서 정리 · 그림 설명 · 스캔본 글자 읽기') +
      trow3('시각장애 · 점자', '점역에 2주~한 달이 걸림 <span style="color:var(--ink3);font-size:22px;margin-left:8px">뉴시스 2026.1</span>', '한글 점자 파일 변환') +
      trow3('저시력', '작은 글씨와 낮은 대비', '큰 글씨 · 고대비') +
      trow3('색각 이상', '색으로만 구분된 도표가 구분되지 않음', '색 보정 · 같은 색에 같은 무늬') +
      trow3('외국인 학생', '한국어 전문 용어와 긴 문장', '어려운 단어 뜻 · 영어 용어 함께') +
      trow3('모든 학생', '이동 중이거나 눈이 피로할 때 읽기 어려움', '소리 내어 읽기', True) + '</div>')
out.append(slide(3, 0, '<span class="em">누가</span> 불편한가, 무엇을 만들었나', b3,
                 '특정 집단을 정하지 않았습니다. 필요한 사람이 필요한 것만 골라 씁니다'))

# ---------- 4 해결 방식 ----------
def prow(top, n, t, d):
    return ('<div class="abs" style="left:790px;top:%spx;width:1018px;display:flex;gap:28px;align-items:flex-start">'
            '<div class="num">%s</div><div><div style="font-size:38px;font-weight:700">%s</div>'
            '<div style="font-size:28px;line-height:1.5;color:var(--ink2);margin-top:4px">%s</div></div></div>' % (top, n, t, d))
def fmt(x, t, d):
    return ('<div class="abs box" style="left:%spx;top:750px;width:326px;height:188px;padding:18px 26px"><div style="font-size:29px;font-weight:700;color:var(--navy)">%s</div>'
            '<div style="font-size:23px;line-height:1.45;color:var(--ink2);margin-top:6px">%s</div></div>' % (x, t, d))
b4 = ('<img class="abs" src="assets/panel.png" style="left:150px;top:326px;height:580px;border-radius:18px;border:1.5px solid var(--line)">' +
      prow(336, 1, '자료 옆 <b style="color:var(--navy)">다운로드</b> 버튼', '스노우보드 강의자료 옆에 생겨요. 화면 구석의 마스코트로도 열 수 있어요') +
      prow(466, 2, '필요한 방식 고르기', '그림 읽기·점자 · 저시력 · 색각 이상 · 교환학생') +
      prow(596, 3, '다운로드', '체크한 항목만 처리해서 받아요') +
      '<div class="abs" style="left:790px;top:706px;font-size:24px;font-weight:700;color:var(--ink3)">받는 모양 (PDF나 웹 문서 중 하나)</div>' +
      fmt(790, '원본 보존 PDF', '쪽 수·배치 그대로<br>필기도 그대로<br>설명은 보충 쪽으로') + fmt(1136, '웹 문서', '큰 글씨 · 고대비<br>소리 내어 읽기<br>설명이 글 사이에') + fmt(1482, '점자 파일 (선택)', '.brf · 점자 프린터용<br>점자 항목을 켜면<br>PDF 안에도 담김'))
out.append(slide(4, 1, '자료는 그대로 두고, <span class="em">받는 방식</span>을 고릅니다', b4,
                 '“8쪽 보세요” 하면 변환본에서도 8쪽이어야 해서, 원본을 그대로 둡니다'))

# ---------- 5 스크린리더 ----------
def tcard(x, w, lab, txt, navy=False, tag=None):
    cls = 'navy' if navy else 'box'
    lc = '#B9CBEA' if navy else 'var(--ink3)'
    tg = '<span class="tag" style="background:#fff;color:var(--navy);height:34px;font-size:20px;margin-left:12px">%s</span>' % tag if tag else ''
    return ('<div class="abs %s" style="left:%spx;top:326px;width:%spx;height:220px;padding:26px 34px;border-radius:28px">'
            '<div style="font-size:24px;font-weight:700;color:%s;display:flex;align-items:center">%s%s</div>'
            '<div style="font-size:29px;line-height:1.6;margin-top:12px;letter-spacing:-.3px;word-break:break-all">%s</div></div>' % (cls, x, w, lc, lab, tg, txt))
cap = ('뇌의 세로토닌 계(왼쪽)와 노르에피네프린 계(오른쪽)의 신경 경로를 비교한 그림이다. 양쪽 모두 신피질·시상·시상하부 등으로 신호가 뻗으며, '
       '뇌간의 봉선핵(솔기핵) 또는 청반에서 시작해 소뇌와 척수 방향으로도 연결된다. 화살표는 각 계의 신호가 뇌 여러 부위로 퍼지는 경로를 나타낸다.')
b5 = (tcard(112, 800, '원본에서 뽑은 글자', '신경관형성은복합적인과정으로각세포의삼차원적인구조의연속적변화와각각의세포들과주위세포의부착에의해좌우됨.') +
      '<div class="abs" style="left:928px;top:420px;width:56px;height:3px;background:var(--navy)"></div>'
      '<div class="abs" style="left:976px;top:411px;border-left:16px solid var(--navy);border-top:10px solid transparent;border-bottom:10px solid transparent"></div>' +
      tcard(1000, 808, '변환 후', '신경관 형성은 복합적인 과정으로 각 세포의 삼차원적인 구조의 연속적 변화와 각각의 세포들과 주위 세포의 부착에 의해 좌우됨.', True, 'AI 띄어쓰기 복원') +
      win(112, 584, 600, '원본 그림 (이미지)', '<img src="assets/fig_p9.png" style="display:block;width:100%">') +
      '<div class="abs box" style="left:760px;top:584px;width:1048px;height:340px;padding:26px 36px;border-radius:28px">'
      '<div style="font-size:24px;font-weight:700;color:var(--ink3);display:flex;align-items:center">변환 후 · 그림 설명<span class="tag out" style="height:34px;font-size:20px;margin-left:12px">AI</span></div>'
      '<div style="font-size:27px;line-height:1.6;margin-top:12px">%s</div>'
      '<div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap"><span class="chip" style="height:46px;font-size:23px">그림 속 글자 11개 함께 제공</span>'
      '<span class="chip" style="height:46px;font-size:23px">색 설명: 빨간색 = 세로토닌 계, 초록색 = 노르에피네프린 계</span></div></div>' % cap)
out.append(slide(5, 1, '스크린리더가 <span class="em">건너뛰던 것</span>을 읽게 합니다', b5,
                 '이미지 안의 이름표도, 붙어 있던 글자도 글로 읽힙니다'))

# ---------- 6 색각 이상 ----------
def cbp(x, title, img, cap, navy=False):
    col = 'var(--navy)' if navy else 'var(--ink)'
    return (win(x, 326, 540, title, '<img src="assets/%s" style="display:block;width:100%%">' % img) +
            '<div class="abs" style="left:%spx;top:726px;width:540px;text-align:center;font-size:27px;line-height:1.5;color:%s;font-weight:%s">%s</div>' % (x, col, 700 if navy else 500, cap))
b6 = (cbp(112, '원본', 'cb_orig.png', '일반 시각으로 본 모습') +
      cbp(690, '녹색약이 보는 원본', 'cb_sim.png', 'Differentiation과 Focus가<br>거의 같은 색으로 보여요') +
      cbp(1268, '변환본 · 녹색약이 보는 모습', 'cb_fixed.png', '색을 보정하고, 같은 색에는<br>같은 무늬를 얹어요', True) +
      '<div class="abs" style="left:112px;top:850px;display:flex;gap:12px"><span class="chip" style="height:50px;font-size:24px">AI 없이 규칙으로 처리</span>'
      '<span class="chip" style="height:50px;font-size:24px">사진처럼 색이 번지는 그림은 건드리지 않아요</span></div>')
out.append(slide(6, 1, '색으로만 구분된 도식을 <span class="em">구분되게</span> 바꿉니다', b6,
                 '녹색약 기준 구분 정도(ΔE) 색 도식이 있는 샘플 5개 평균 18.9 → 26.1 · 이 도식은 14.5 → 35.4'))

# ---------- 7 점자 ----------
SENT = '뇌간 망상계의 핵을 이루며 전뇌를 깨워 각성 상태를 유지하게 하는 역할을 함.'
BR = '⠉⠽⠫⠒⠀⠑⠶⠇⠶⠈⠌⠺⠀⠚⠗⠁⠮⠀⠕⠐⠍⠑⠱⠀⠨⠾⠉⠽⠐⠮⠀⠠⠈⠗⠏⠀⠫⠁⠠⠻⠀⠇⠶⠓⠗⠐⠮⠀⠩⠨⠕⠚⠈⠝⠀⠚⠉⠵⠀⠱⠁⠚⠂⠮⠀⠚⠢⠲'
def brow(top, h, lab, body, size, navy=False, tag=None):
    cls = 'navy' if navy else 'box'
    lc = '#B9CBEA' if navy else 'var(--ink3)'
    tg = '<span class="tag" style="background:#fff;color:var(--navy);height:36px;font-size:21px;margin-top:12px">%s</span>' % tag if tag else ''
    return ('<div class="abs %s" style="left:112px;top:%spx;width:1696px;height:%spx;border-radius:28px;display:flex;align-items:center;padding:0 40px">'
            '<div style="width:250px;flex:none"><div style="font-size:26px;font-weight:700;color:%s">%s</div>%s</div>'
            '<div style="font-size:%spx;line-height:1.55;letter-spacing:%s;flex:1;min-width:0;word-break:break-all">%s</div></div>' % (cls, top, h, lc, lab, tg, size, '3px' if size > 40 else '-.3px', body))
b7 = (brow(326, 132, '원문 (강의자료)', SENT, 32) +
      brow(478, 186, '점자', BR, 46, True) +
      brow(684, 132, '다시 글로 되돌림', SENT, 32, False, '원문과 일치') +
      '<div class="abs" style="left:112px;top:850px;display:flex;gap:12px"><span class="chip" style="height:50px;font-size:24px">규정 해설서 예시 59개 중 59개 일치</span>'
      '<span class="chip" style="height:50px;font-size:24px">샘플 8개 · 935문단을 점자로 바꿨다 되돌리면 글자까지 95.2% 일치</span>'
      '<span class="chip" style="height:50px;font-size:24px">.brf 파일로 받기</span></div>')
out.append(slide(7, 1, '점자 자료를 <span class="em">직접</span> 받을 수 있습니다', b7,
                 '점역에 2주~한 달이 걸린다고 보도됐습니다 (뉴시스 2026.1)'))

# ---------- 8 웹 문서 ----------
web_in = '<img src="assets/web_norm.png" style="display:block;width:100%">'
hc_in = '<img src="assets/web_hc.png" style="display:block;width:100%">'
def wf(top, t, d, tag=None):
    tg = '<span class="tag out" style="height:34px;font-size:20px;margin-left:12px">%s</span>' % tag if tag else ''
    return ('<div class="abs" style="left:1230px;top:%spx;width:578px"><div style="font-size:36px;font-weight:700;display:flex;align-items:center">%s%s</div>'
            '<div style="font-size:27px;line-height:1.5;color:var(--ink2);margin-top:6px">%s</div></div>' % (top, t, tg, d))
b8 = (win(112, 326, 1060, '읽기용 웹 문서 (실제 변환 결과)', web_in) +
      '<div class="abs" style="left:112px;top:612px;font-size:24px;font-weight:700;color:var(--ink3)">큰 글씨 · 고대비로 바꾸면</div>' +
      win(112, 650, 1060, '읽기용 웹 문서 · 고대비', hc_in) +
      wf(336, '어려운 단어 뜻', '어려운 단어 바로 뒤에 쉬운 말과 영어를 괄호로 붙여요', 'AI') +
      wf(520, '큰 글씨 · 고대비', '웹 문서에서 글씨를 키우고, 검정 바탕에 밝은 글씨로 바꿔요') +
      wf(704, '소리 내어 읽기', '문단 단위로 읽고, 속도를 조절할 수 있어요'))
out.append(slide(8, 1, '어려운 말과 작은 글씨도 <span class="em">내 방식으로</span>', b8,
                 '한국어가 낯선 학생도, 눈이 불편한 학생도 같은 자료를 읽습니다'))

# ---------- 9 기술 ----------
def node(w, t, sub, navy=False):
    cls = 'navy' if navy else 'box'
    sc = '#E7EEF8' if navy else 'var(--ink2)'
    return ('<div class="%s" style="width:%spx;height:112px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border-radius:24px"><div style="font-size:32px;font-weight:700">%s</div><div style="font-size:23px;color:%s;margin-top:4px">%s</div></div>' % (cls, w, t, sc, sub))
arr = '<div class="arrow" style="width:70px;flex:none"></div>'
def trow(f, t, why, last=False):
    b = '' if last else 'border-bottom:2px solid var(--line);'
    return ('<div style="padding:16px 0;font-size:28px;font-weight:700;%s">%s</div><div style="padding:16px 0;font-size:28px;%s">%s</div>'
            '<div style="padding:16px 0;font-size:26px;color:var(--ink2);line-height:1.4;%s">%s</div>' % (b, f, b, t, b, why))
b9 = ('<div class="abs" style="left:112px;top:316px;width:1696px;display:flex;align-items:center;justify-content:center">' +
      node(430, '크롬 확장', 'Manifest V3') + arr + node(500, '변환 서버', 'Python FastAPI · PyMuPDF', True) + arr + node(430, '학교 AI 게이트웨이', '체크한 항목에서만 호출') + '</div>'
      '<div class="abs" style="left:112px;top:452px;width:1696px;display:grid;grid-template-columns:360px 440px 1fr;column-gap:28px">' +
      trow('버튼 · 변환 창', '크롬 확장', '학교 서버를 고치지 않고 스노우보드 화면에만 얹음') +
      trow('글자·그림·표, 읽는 순서', 'PyMuPDF', '글자 위치를 알아야 읽는 순서를 바로잡을 수 있음') +
      trow('그림 설명 · 쉬운 말 · 띄어쓰기', 'AI (학교 게이트웨이)', 'AI가 글자를 바꾼 문장은 버리고 원문을 씀. 같은 입력은 저장해 재사용') +
      trow('점자 · 색 구분', '직접 구현 (AI 없이)', '규칙대로 같은 결과가 나오고 크레딧이 들지 않음') +
      trow('PowerPoint', '서버가 먼저 PDF로 변환', '두 형식을 하나의 처리 흐름으로') +
      trow('원본 보존 PDF', '원본 위에 글자·책갈피, 뒤에 보충 쪽', '보이는 모습은 그대로, 확대·복사도 그대로', True) + '</div>')
out.append(slide(9, 2, '<span class="em">어떤 기술</span>로 어떤 기능을 만들었는지', b9))

# ---------- 10 품질 ----------
def qrow(item, res, how, last=False):
    b = '' if last else 'border-bottom:2px solid #fff;'
    return ('<div style="padding-left:32px;height:84px;display:flex;align-items:center;font-size:30px;font-weight:700;%s">%s</div>'
            '<div style="height:84px;display:flex;align-items:center;font-size:30px;%s">%s</div>'
            '<div style="height:84px;display:flex;align-items:center;font-size:26px;line-height:1.4;color:var(--ink2);padding-right:24px;%s">%s</div>' % (b, item, b, res, b, how))
hd = lambda t, p='': '<div style="height:56px;display:flex;align-items:center;%sfont-size:24px;font-weight:700;color:var(--ink3)">%s</div>' % (p, t)
B = lambda t: '<b style="margin:0 8px">%s</b>' % t
b10 = ('<div class="abs box" style="left:112px;top:316px;width:1696px;display:grid;grid-template-columns:360px 540px 1fr">' +
       hd('항목', 'padding-left:32px;') + hd('결과') + hd('어떻게 쟀나') +
       qrow('띄어쓰기 복원', 'F1' + B('97.0%'), '띄어쓰기를 모두 지운 문장 95개를 AI가 복원 → 원문과 비교') +
       qrow('점자 · 규정 대조', '59/59' + B('일치'), '국립국어원 규정 해설서 예시 59개를 점역해 책의 점자와 비교') +
       qrow('점자 · 역점역', '글자까지' + B('95.2%') + '점자 동일' + B('98.2%'), '점자를 다시 글로 되돌려 원문과 비교 · 샘플 8개 · 935문단') +
       qrow('그림 설명 만들기', B('126/126') + '성공', '샘플 8개의 그림·도식 126개 중 설명을 만든 수 (실패 0)') +
       qrow('그림 속 글자', '재현율' + B('98.0%') + '(287/293)', '도식 안 글자를 설명·읽은 글이 얼마나 담는지 · 도식 글자가 있는 샘플 5개') +
       qrow('색 구분 (녹색약)', B('18.9 → 26.1'), '가장 비슷한 두 색의 색차(ΔE) 평균, 클수록 구분이 쉬움 · 색 도식이 있는 샘플 5개') +
       qrow('글자 추출 속도', '쪽당 평균' + B('0.28초'), 'AI 없는 단계 · 샘플 8개 136쪽 (쪽당 0.09~1.12초)', True) + '</div>'
       '<div class="abs" style="left:112px;top:944px;width:1696px;text-align:center;font-size:24px;color:var(--ink3)">샘플은 강의자료 8개(136쪽), 점자·색·글자 추출은 AI 없이 같은 결과가 나옵니다. 그림 설명의 사실 여부는 사람이 확인해야 합니다.</div>')
out.append(slide(10, 3, '품질은 <span class="em">숫자</span>로 확인했습니다', b10))

# ---------- 11 기대 효과 ----------
def eff(x, who, txt, sub):
    return ('<div class="abs box" style="left:%spx;top:370px;width:546px;height:500px;padding:56px 44px"><div style="font-size:30px;font-weight:700;color:var(--navy)">%s</div>'
            '<div style="font-size:40px;line-height:1.5;font-weight:700;margin-top:22px">%s</div>'
            '<div style="font-size:28px;line-height:1.55;color:var(--ink2);margin-top:26px">%s</div></div>' % (x, who, txt, sub))
b11 = (eff(112, '도움이 필요한 학생', '필요한 방식을<br>직접 골라 바로 받음', '스크린리더 · 점자 · 저시력 · 색각 이상 · 외국인 학생') +
       eff(687, '모든 학생', '이동 중에도,<br>눈이 피로해도', '소리 내어 읽기로 같은 자료를 듣고 따라갈 수 있음') +
       eff(1262, '교수 · 학교', '자료를 다시 만들지 않고<br>시스템도 고치지 않음', '학생 쪽 브라우저에서 보완하는 방식'))
out.append(slide(11, 3, '<span class="em">모두가</span> 디지털 자료를<br>불편함 없이 쓸 수 있도록', b11))

# ---------- 12 감사합니다 ----------
out.append('''<section class="s cover">
  <div class="abs" style="left:1060px;top:0;width:860px;height:1080px;background:var(--panel)"></div>
  <img class="abs" src="assets/mascot_line_a.png" style="left:1190px;top:190px;height:700px">
  <div class="abs" style="left:112px;top:360px;font-size:150px;line-height:1.15;font-weight:900;letter-spacing:-4px;color:var(--ink)">감사합니다</div>
  <div class="abs" style="left:120px;top:590px;font-size:44px;font-weight:500;color:var(--navy)">Our Snowboard</div>
  <div class="abs" style="left:120px;top:940px;font-size:28px;font-weight:700;color:var(--ink)">전하은<span style="font-weight:400;color:var(--ink2)"> &nbsp;·&nbsp; 2412957 &nbsp;·&nbsp; 소프트웨어학부 컴퓨터과학전공</span></div>
</section>
''')

html = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Our Snowboard</title><style>%s</style></head><body>\n%s</body></html>' % (CSS, ''.join(out))
(pathlib.Path(__file__).parent / 'index.html').write_text(html, encoding='utf-8')
print('ok', len(out))
