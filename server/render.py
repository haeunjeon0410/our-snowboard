"""변환 결과 파일 만들기: 체크한 항목을 하나로 합친 웹 문서(.html)와 점자 파일(.brf)."""
import base64
import html as _html
import io
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from . import color, outputs

CSS = """
:root{--fs:__FS__;--bg:#fff;--fg:#1c2230;--mut:#6b7689;--line:#e1e6ee;--soft:#f2f4f8;--acc:#3f5a86;--mark:rgba(63,90,134,.14)}
[data-theme=dark]{--bg:#16181d;--fg:#eef1f6;--mut:#9aa5b8;--line:#2f3541;--soft:#222630;--acc:#9bb8e8;--mark:rgba(155,184,232,.2)}
[data-theme=hc]{--bg:#000;--fg:#ffe600;--mut:#fff;--line:#fff;--soft:#111;--acc:#fff;--mark:rgba(255,230,0,.28)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:400 var(--fs)/1.9 'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;letter-spacing:-.01em;word-break:keep-all;overflow-wrap:anywhere}
main{max-width:44em;margin:0 auto;padding:76px 24px 190px}
h1{font-size:1.3em;line-height:1.35;letter-spacing:-.03em;margin:0 0 .15em}
.meta{color:var(--mut);font-size:.62em;margin:0 0 1.6em}
h2,h3,h4{line-height:1.4;letter-spacing:-.025em;margin:1.3em 0 .3em}
h2{font-size:1.28em}h3{font-size:1.12em}h4{font-size:1.02em}
p{margin:.45em 0}ul{padding-left:1.2em;margin:.4em 0}li{margin:.25em 0}
.pg{margin:2.4em 0 .6em;padding-top:.8em;border-top:1px solid var(--line);color:var(--mut);font-size:.6em;font-weight:600;letter-spacing:0}
mark{background:var(--mark);color:inherit;font-weight:700;border-radius:4px;padding:0 .1em;box-shadow:inset 0 -.14em 0 var(--acc)}
.en{color:var(--mut);font-size:.82em}
.gl{color:var(--acc);font-size:.9em;font-weight:600}
.note{margin:0 0 1.4em;padding:.55em .9em;background:var(--soft);border-radius:10px;color:var(--mut);font-size:.62em}
.ai{display:inline-block;margin-left:.45em;padding:0 .5em;border-radius:99px;background:var(--soft);color:var(--mut);font-size:.5em;font-weight:700;letter-spacing:0;vertical-align:.2em;line-height:1.7}
figure{margin:1.2em 0;background:var(--soft);border-radius:14px;overflow:hidden}
figure img{display:block;max-width:100%;height:auto;margin:0 auto;background:#fff}
figcaption{padding:.8em 1.1em;font-size:.78em;line-height:1.75}
figcaption b{font-weight:650}
details{margin-top:.5em}summary{cursor:pointer;color:var(--acc);font-weight:600}
.leg{display:block;margin-top:.5em;color:var(--mut);font-size:.9em}
table{border-collapse:collapse;width:100%;font-size:.84em;margin:.8em 0}
th,td{border:1px solid var(--line);padding:.5em .7em;text-align:left;vertical-align:top}th{background:var(--soft)}
pre{background:#1d2230;color:#e6ebf4;padding:.9em 1.1em;border-radius:12px;overflow:auto;font:.78em/1.6 'SF Mono',Consolas,'D2Coding',monospace;word-break:normal}
.now{background:var(--mark);outline:3px solid var(--mark);border-radius:6px}
footer{margin-top:3em;padding-top:1em;border-top:1px solid var(--line);color:var(--mut);font-size:.6em}
.bar{position:fixed;top:12px;right:12px;display:flex;gap:2px;padding:3px;background:color-mix(in srgb,var(--bg) 84%,transparent);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);border:1px solid var(--line);border-radius:11px;z-index:10;font:600 14px/1 'Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif}
.bar button{all:unset;cursor:pointer;padding:9px 12px;border-radius:8px;color:var(--fg)}
.bar button:hover{background:var(--soft)}.bar button:focus-visible{outline:3px solid var(--acc)}
.now{transition:background .25s,outline-color .25s}
.pl{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);width:min(94vw,520px);padding:10px 14px 12px;background:color-mix(in srgb,var(--bg) 88%,transparent);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px);border:1px solid var(--line);border-radius:20px;box-shadow:0 10px 36px rgba(20,30,50,.2);z-index:20;font:600 14px/1 'Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif;animation:plin .28s ease}
.pl[hidden]{display:none}
@keyframes plin{from{opacity:0;transform:translate(-50%,16px)}}
.pl .trk{height:4px;border-radius:99px;background:var(--line);overflow:hidden;margin:0 2px 10px}
.pl .trk i{display:block;height:100%;width:0;background:var(--acc);border-radius:99px;transition:width .3s}
.pl .row{display:flex;align-items:center;gap:6px}
.pl button,.pl select{all:unset;cursor:pointer;box-sizing:border-box;color:var(--fg);border-radius:10px}
.pl button:focus-visible,.pl select:focus-visible{outline:3px solid var(--acc)}
.pl .ic{width:40px;height:40px;display:grid;place-items:center}
.pl .ic:hover,.pl .sm:hover,.pl select:hover{background:var(--soft)}
.pl .ic svg{width:20px;height:20px;fill:currentColor}
.pl .go{width:48px;height:48px;border-radius:99px;background:var(--acc);color:var(--bg)}
.pl .go:hover{background:var(--acc);filter:brightness(1.12)}
.pl .go svg{width:22px;height:22px}
.pl .cnt{flex:1;text-align:center;color:var(--mut);font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
.pl .sm{padding:10px;min-width:48px;text-align:center;font-size:13px}
.pl .vo{margin-top:8px;display:flex;align-items:center;gap:8px;color:var(--mut);font-size:12px;font-weight:500}
.pl select{flex:1;min-width:0;padding:7px 10px;border:1px solid var(--line);font-size:12px;font-weight:500;text-overflow:ellipsis}
.pl select option{color:#000}
.bar .on{background:var(--soft)}
@media (prefers-reduced-motion:reduce){.pl{animation:none}.pl .trk i,.now{transition:none}}
@media print{.bar,.pl{display:none}main{padding-top:0}}
"""

JS = r"""
(()=>{const R=document.documentElement,K='osb:';const g=k=>{try{return localStorage.getItem(K+k)}catch(e){return null}},s=(k,v)=>{try{localStorage.setItem(K+k,v)}catch(e){}};
const T=['light','dark','hc'];if(g('theme')&&T.includes(g('theme')))R.dataset.theme=g('theme');if(+g('fs'))R.style.setProperty('--fs',+g('fs')+'px');
const fs=()=>parseFloat(getComputedStyle(R).getPropertyValue('--fs'))||22;
const D=document,Q=x=>D.querySelector(x),syn=window.speechSynthesis,RATES=[.8,1,1.25,1.5];
let q=[],i=-1,st='idle',gen=0,voices=[],rate=RATES.includes(+g('rate'))?+g('rate'):1,vname=g('voice')||'';
const ICON={play:'<svg viewBox="0 0 24 24"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>',pause:'<svg viewBox="0 0 24 24"><rect x="6" y="5" width="4.2" height="14" rx="1.2"/><rect x="13.8" y="5" width="4.2" height="14" rx="1.2"/></svg>'};
D.addEventListener('click',e=>{const b=e.target.closest('[data-a]');
if(b){const a=b.dataset.a;
if(a==='bigger'||a==='smaller'){const v=Math.min(64,Math.max(14,fs()+(a==='bigger'?2:-2)));R.style.setProperty('--fs',v+'px');s('fs',v)}
if(a==='theme'){const n=T[(T.indexOf(R.dataset.theme||'light')+1)%3];R.dataset.theme=n;s('theme',n)}
if(a==='read')st==='idle'?open():close();
if(a==='close')close();
if(a==='play')st==='play'?pause():st==='pause'?resume():go(i<0?0:i);
if(a==='prev')go(Math.max(0,i-1));
if(a==='next')go(Math.min(q.length-1,i+1));
if(a==='rate'){rate=RATES[(RATES.indexOf(rate)+1)%RATES.length];s('rate',rate);ui();if(st==='play')go(i)}return}
const r=e.target.closest('.r');if(st!=='idle'&&r&&!e.target.closest('summary,a,button'))go(q.indexOf(r))});
D.addEventListener('change',e=>{if(e.target.id!=='vsel')return;vname=e.target.value;s('voice',vname);if(st==='play')go(i)});
D.addEventListener('keydown',e=>{if(e.key==='Escape'&&st!=='idle')close()});
function score(v){const n=v.name;return(/natural|online|neural/i.test(n)?40:0)+(/google/i.test(n)?25:0)+(/sun-?hi|yuna|injoon|seoyeon|heami|flo|sandy/i.test(n)?10:0)+(v.localService?0:5)}
function loadVoices(){if(!syn)return;voices=syn.getVoices().filter(v=>/^ko/i.test(v.lang)).sort((a,b)=>score(b)-score(a));const sel=Q('#vsel');if(!sel)return;
sel.innerHTML=voices.length?voices.map(v=>'<option value="'+v.name.replace(/"/g,'&quot;')+'">'+v.name.replace(/^Microsoft |\s*Online \(Natural\)|\s*- Korean \(Korea\)/g,'').trim()+(score(v)>=40?' · 자연스러운 목소리':'')+'</option>').join(''):'<option>기본 목소리</option>';
sel.disabled=!voices.length;if(voices.length)sel.value=voices.some(v=>v.name===vname)?vname:voices[0].name}
function pick(){return voices.find(v=>v.name===vname)||voices[0]}
function split(t){const out=[];let cur='';for(const p of t.replace(/\s+/g,' ').trim().split(/(?<=[.!?。…])\s+/)){if(cur&&(cur+p).length>110){out.push(cur);cur=p}else cur=cur?cur+' '+p:p}if(cur)out.push(cur);return out.length?out:[t]}
function clearNow(){D.querySelectorAll('.now').forEach(e=>e.classList.remove('now'))}
function ui(){const p=Q('[data-a=play]');if(!p)return;p.innerHTML=ICON[st==='play'?'pause':'play'];p.setAttribute('aria-label',st==='play'?'일시정지':'읽기');
Q('[data-a=rate]').textContent=rate+'배속';Q('.pl .cnt').textContent=q.length?(Math.max(i,0)+1)+' / '+q.length:'';Q('.pl .trk i').style.width=q.length?((Math.max(i,0)+1)/q.length*100)+'%':'0';
const b=Q('[data-a=read]');b.classList.toggle('on',st!=='idle');b.setAttribute('aria-expanded',st!=='idle')}
function open(){if(!syn){alert('이 브라우저는 읽어 주기를 지원하지 않아요.');return}q=[...D.querySelectorAll('.r')];if(!q.length)return;loadVoices();Q('.pl').hidden=false;
go(Math.max(0,q.findIndex(e=>e.getBoundingClientRect().top>60)))}
function close(){gen++;syn&&syn.cancel();st='idle';clearNow();Q('.pl').hidden=true;ui()}
function pause(){st='pause';syn.pause();ui()}
function resume(){st='play';syn.resume();ui()}
function go(n){gen++;syn.cancel();st='play';i=n;say()}
function say(){clearNow();if(i<0||i>=q.length){close();return}const el=q[i],my=gen,parts=split(el.dataset.s||el.innerText);let k=0;
el.classList.add('now');el.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});ui();
const next=()=>{if(my!==gen)return;if(k>=parts.length){i++;say();return}const u=new SpeechSynthesisUtterance(parts[k++]);u.lang='ko-KR';u.rate=rate;const v=pick();if(v)u.voice=v;u.onend=next;u.onerror=ev=>{if(ev.error!=='canceled'&&ev.error!=='interrupted')next()};syn.speak(u)};next()}
if(syn){loadVoices();syn.addEventListener&&syn.addEventListener('voiceschanged',loadVoices)}
window.addEventListener('beforeunload',()=>{syn&&syn.cancel()})})();
"""

CODE_SYM = [("==", " 같다 "), ("!=", " 같지 않다 "), ("<=", " 작거나 같다 "), (">=", " 크거나 같다 "), ("&&", " 그리고 "), ("||", " 또는 "),
            ("++", " 플러스 플러스 "), ("--", " 마이너스 마이너스 "), ("->", " 화살표 "), ("(", " 여는 괄호 "), (")", " 닫는 괄호 "),
            ("{", " 여는 중괄호 "), ("}", " 닫는 중괄호 "), ("[", " 여는 대괄호 "), ("]", " 닫는 대괄호 "), (";", " 세미콜론 "),
            ("=", " 는 "), ("+", " 더하기 "), ("-", " 빼기 "), ("*", " 곱하기 "), ("/", " 나누기 "), ("<", " 작다 "), (">", " 크다 "),
            ("!", " 부정 "), ("%", " 나머지 "), (",", " 쉼표 "), (":", " 콜론 "), ('"', " 큰따옴표 "), ("'", " 작은따옴표 "), ("_", " 밑줄 ")]


def _e(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


def _speak_code(raw: str) -> str:
    lines = [l for l in raw.split("\n")]
    out, prev = [f"코드 {len(lines)}줄 시작."], 0
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if not s:
            continue
        lvl = round(len(ln.replace("\t", "    ")) - len(ln.replace("\t", "    ").lstrip())) // 4
        for a, b in CODE_SYM:
            s = s.replace(a, b)
        out.append(f"{i}번째 줄." + (f" 들여쓰기 {lvl}단계." if lvl != prev else "") + " " + re.sub(r"\s+", " ", s))
        prev = lvl
    out.append("코드 끝.")
    return " ".join(out)


def _emph_html(text: str, phrases) -> str:
    """원본에서 색으로만 강조된 말을 <mark>로 (띄어쓰기가 바뀌어도 찾도록 글자 사이 공백 허용)"""
    ranges = []
    for ph in phrases or []:
        chars = list(re.sub(r"\s+", "", ph))
        if len(chars) < 2:
            continue
        m = re.search(r"\s*".join(re.escape(c) for c in chars), text)
        if m:
            ranges.append((m.start(), m.end()))
    ranges.sort()
    out, pos = [], 0
    for a, b in ranges:
        if a < pos:
            continue
        out.append(_e(text[pos:a]) + f"<mark>{_e(text[a:b])}</mark>")
        pos = b
    return "".join(out) + _e(text[pos:])


def _with_terms(html_s: str, terms, used: set) -> str:
    for t in terms or []:
        if t["ko"] in used or "we:" + t["ko"] in used:       # 단어 뜻에 이미 영어가 붙었으면 같은 영어를 한 번 더 붙이지 않는다
            continue
        ke = _e(t["ko"])
        i = html_s.find(ke)
        if i < 0 or html_s[i + len(ke):].startswith("("):
            continue
        used.add(t["ko"])
        html_s = html_s[:i + len(ke)] + f'<span class="en">({_e(t["en"])})</span>' + html_s[i + len(ke):]
    return html_s


def _with_words(html_s: str, words, used: set) -> str:
    """어려운 단어 바로 뒤에 쉬운 말을 괄호로 붙인다 (용이하다(쉽다)). 한 쪽에서 단어마다 처음 나온 곳에만."""
    for w in words or []:
        if not (isinstance(w, dict) and w.get("ko") and w.get("easy")):      # 비어 있거나 모양이 다른 항목은 건너뛴다
            continue
        key = "w:" + w["ko"]
        if key in used:
            continue
        ke = _e(w["ko"])
        i = html_s.find(ke)
        if i < 0 or html_s[i + len(ke):].startswith("("):
            continue
        used.add(key)
        if w.get("en"):
            used.add("we:" + w["ko"])
        html_s = html_s[:i + len(ke)] + f'<span class="gl">({_e(w["easy"])}{" · " + _e(w["en"]) if w.get("en") else ""})</span>' + html_s[i + len(ke):]
    return html_s


def _jpeg_b64(img: Image.Image, maxw=1100) -> str:
    img = img.convert("RGB")
    if img.width > maxw:
        img = img.resize((maxw, round(img.height * maxw / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _fix_all(doc, job_dir: Path, o) -> dict:
    """색 구분을 켰을 때, 모든 그림의 보정을 한꺼번에(병렬로) 계산해 둔다. numpy가 GIL을 놓아서 스레드로 빨라진다.
    같은 변환 안에서 형식(원본 PDF·읽기용 PDF·웹 문서·비교 장면)마다 다시 계산하지 않게 옵션 안에 한 번만 보관한다."""
    if o["color"] and (o.get("_fixed") or (None,))[0] == str(job_dir):
        return o["_fixed"][1]
    paths = {}
    for pg in doc["pages"]:
        for b in pg["blocks"]:
            if b["type"] == "figure" and not (pg.get("ocr_done") and b.get("fullpage")) and (job_dir / b["img"]).exists():
                paths[b["id"]] = job_dir / b["img"]
    if not o["color"] or not paths:
        return {}
    with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as ex:
        results = list(ex.map(lambda p: color.fix_image(p, o["colorType"]), paths.values()))
    out = dict(zip(paths.keys(), results))
    o["_fixed"] = (str(job_dir), out)
    return out


def _figure_html(b, pg, job_dir: Path, o, fixed=None) -> str:
    d = b.get("ai_desc") or {}
    desc = d.get("desc") or " ".join(x for x in (d.get("summary"), d.get("detail")) if x)   # 예전 형식도 읽는다
    scanned_text = pg.get("ocr_done") and b.get("fullpage")
    if scanned_text:
        return ""                                  # 스캔본은 읽어 낸 글이 이미 본문에 있으므로 쪽 이미지는 뺀다
    path = job_dir / b["img"]
    legend, img = "", None
    if o["color"] and path.exists():
        img, pal = (fixed or {}).get(b["id"]) or color.fix_image(path, o["colorType"])
        if pal:
            legend = '<span class="leg">색을 무늬로도 구분했어요: ' + ", ".join(f"{_e(g['name'])}={_e(g['pattern'])}" for g in pal[:6]) + "</span>"
    if img is None and path.exists():
        img = Image.open(path)
    tag = f'<img src="{_jpeg_b64(img)}" alt="{_e((desc or "그림")[:160])}">' if img is not None else ""
    if not o["figures"] or not desc:
        return f"<figure>{tag}</figure>" if tag else ""
    texts = [t for t in dict.fromkeys((b.get("inner_text") or []) + (d.get("texts") or [])) if t]
    note = f' <b>색 설명</b> {_e(d["color_note"])}' if d.get("color_note") else ""
    det = f"<details><summary>그림 속 글자 {len(texts)}개</summary><ul>" + "".join(f"<li>{_e(t)}</li>" for t in texts) + "</ul></details>" if texts else ""
    speak = _e("그림. " + desc + (" 색 설명. " + d["color_note"] if d.get("color_note") else ""))
    return (f'<figure class="r" data-s="{speak}">{tag}<figcaption><b>그림 설명</b><span class="ai" title="AI가 만든 설명이라 틀릴 수 있어요">AI</span> '
            f'{_e(desc)}{note}{legend}{det}</figcaption></figure>')


def to_html(doc: dict, job_dir: Path, o: dict, title: str = "") -> str:
    fs = "26px" if o["large"] else "19px"
    theme = "hc" if o["contrast"] else "light"
    parts = [f'<h1>{_e(title or doc.get("title", ""))}</h1>',
             f'<p class="meta">{_e((doc.get("course") + " · ") if doc.get("course") else "")}{doc["n_pages"]}쪽</p>']
    if o["easy"] and any(p.get("easy_words") for p in doc["pages"]):
        parts.append('<p class="note"><span class="ai" style="margin:0">AI</span> 어려운 단어 뒤에 쉬운 말과 영어를 괄호로 붙였어요. AI가 고른 풀이라 틀릴 수 있어요.</p>')
    fixed = _fix_all(doc, job_dir, o)
    prev_h = 1                                                    # 문서 제목이 h1이다
    for pg in doc["pages"]:
        words = pg.get("easy_words") if o["easy"] else None
        terms = pg.get("terms") if o["terms"] else None
        used: set = set()
        parts.append(f'<section aria-label="{pg["n"]}쪽"><p class="pg r" data-s="{pg["n"]}쪽">{pg["n"]}쪽</p>')

        def text_of(obj, key, tag_ai=True):
            h = _emph_html(obj["text"], obj.get("emph")) if obj.get("emph") else _e(obj["text"])
            return _with_terms(_with_words(h, words, used), terms, used)

        for b in pg["blocks"]:
            t = b["type"]
            if t == "heading":
                lv = min(b.get("level", 2) + 1, 4, prev_h + 1)        # 제목 단계를 건너뛰지 않는다 (스크린리더 제목 탐색용)
                prev_h = lv
                parts.append(f'<h{lv} class="r">{text_of(b, b["id"])}</h{lv}>')
            elif t == "paragraph":
                ocr = ' <span class="ai" title="스캔된 쪽에서 AI가 읽어 낸 글자예요">AI</span>' if "ocr" in (b.get("ai") or []) else ""
                parts.append(f'<p class="r">{text_of(b, b["id"])}{ocr}</p>')
            elif t == "list":
                parts.append("<ul>" + "".join(f'<li class="r">{text_of(it, f"{b["id"]}:{i}")}</li>' for i, it in enumerate(b["items"])) + "</ul>")
            elif t == "table":
                rows = b["rows"]
                sp = f"표입니다. 머리줄: {', '.join(rows[0])}. " + ". ".join(f"{i}행: " + ", ".join(f"{rows[0][j] if j < len(rows[0]) else ''} {c}" for j, c in enumerate(r)) for i, r in enumerate(rows[1:], 1))
                parts.append(f'<table class="r" data-s="{_e(sp)}"><thead><tr>' + "".join(f"<th scope=col>{_e(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"
                             + "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in rows[1:]) + "</tbody></table>")
            elif t == "code":
                parts.append(f'<pre class="r" data-s="{_e(_speak_code(b["text"]))}"><code>{_e(b["text"])}</code></pre>')
            elif t == "figure":
                parts.append(_figure_html(b, pg, job_dir, o, fixed))
        parts.append("</section>")
    parts.append("<footer>Our Snowboard로 변환했어요. <span class=\"ai\" style=\"margin:0\">AI</span> 표시가 있는 내용은 AI가 만들었고 틀릴 수 있어요.</footer>")
    bar = ('<div class="bar" role="toolbar" aria-label="보기 도구"><button data-a="smaller" aria-label="글씨 작게">가-</button>'
           '<button data-a="bigger" aria-label="글씨 크게">가+</button><button data-a="theme" aria-label="색 테마 바꾸기">테마</button>'
           '<button data-a="read" aria-controls="pl" aria-expanded="false">읽어 주기</button></div>'
           '<div class="pl" id="pl" role="region" aria-label="읽어 주기 도구" hidden><div class="trk"><i></i></div><div class="row">'
           '<button class="ic" data-a="prev" aria-label="이전 문단"><svg viewBox="0 0 24 24"><path d="M6 5h2v14H6zM9.5 12l9 6.5v-13z"/></svg></button>'
           '<button class="ic go" data-a="play" aria-label="읽기"></button>'
           '<button class="ic" data-a="next" aria-label="다음 문단"><svg viewBox="0 0 24 24"><path d="M16 5h2v14h-2zM14.5 12l-9 6.5v-13z"/></svg></button>'
           '<span class="cnt" aria-live="off"></span><button class="sm" data-a="rate" aria-label="읽는 속도 바꾸기">1배속</button>'
           '<button class="ic" data-a="close" aria-label="읽어 주기 닫기"><svg viewBox="0 0 24 24"><path d="M6.4 5l12.6 12.6-1.4 1.4L5 6.4zM17.6 5l1.4 1.4L6.4 19 5 17.6z"/></svg></button></div>'
           '<label class="vo">목소리<select id="vsel" aria-label="읽어 주는 목소리"></select></label></div>')
    return (f'<!doctype html><html lang="ko" data-theme="{theme}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_e(title or doc.get("title", ""))}</title><style>{CSS.replace("__FS__", fs)}</style></head>'
            f'<body>{bar}<main>{"".join(parts)}</main><script>{JS}</script></body></html>')


def brf_bytes(text: str) -> bytes:
    """점자 프린터용 BRF는 줄바꿈이 CR+LF가 표준이다. 파일로 받을 때와 PDF에 첨부할 때 같은 바이트가 되게 한곳에서 만든다."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def to_brf(doc: dict, o: dict) -> str:
    return outputs.to_braille_text(doc, 32, True, None, figures=o["figures"])
