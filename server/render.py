"""변환 결과 파일 만들기: 체크한 항목을 하나로 합친 웹 문서(.html)와 점자 파일(.brf)."""
import base64
import hashlib
import html as _html
import io
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from . import color, config, outputs, tts

CSS = """
:root{--fs:__FS__;--bg:#fff;--fg:#1c2230;--mut:#6b7689;--line:#e1e6ee;--soft:#f2f4f8;--acc:#0b63d9;--mark:rgba(11,99,217,.12);
--sf:#fff;--sf2:#eef1f5;--sf3:#e3e8ee;--mat:rgba(250,251,253,.78);--bd:rgba(20,35,60,.11);--bd2:rgba(20,35,60,.2);--pri:#0b63d9;--prih:#0a54b8;--pris:rgba(11,99,217,.09);--prik:#0a4fb0;--onp:#fff;--sh:0 6px 20px rgba(20,35,60,.1),0 1px 3px rgba(20,35,60,.07);--sh1:0 .5px 1px rgba(20,35,60,.08)}
[data-theme=dark]{--bg:#16181d;--fg:#eef1f6;--mut:#9aa5b8;--line:#2f3541;--soft:#222630;--acc:#4d9bff;--mark:rgba(77,155,255,.2);
--sf:#202329;--sf2:#2a2e36;--sf3:#363b45;--mat:rgba(32,35,41,.78);--bd:rgba(255,255,255,.1);--bd2:rgba(255,255,255,.2);--pri:#4d9bff;--prih:#74b1ff;--pris:rgba(77,155,255,.16);--prik:#8cc0ff;--onp:#06182f;--sh:0 8px 24px rgba(0,0,0,.45);--sh1:0 .5px 1px rgba(0,0,0,.5)}
[data-theme=hc]{--bg:#000;--fg:#ffe600;--mut:#fff;--line:#fff;--soft:#111;--acc:#fff;--mark:rgba(255,230,0,.28);
--sf:#000;--sf2:#141414;--sf3:#222;--mat:#000;--bd:#fff;--bd2:#fff;--pri:#ffe14d;--prih:#fff08a;--pris:#1d1a00;--prik:#ffe14d;--onp:#000;--sh:none;--sh1:none}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:400 var(--fs)/1.9 'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;letter-spacing:-.01em;word-break:keep-all;overflow-wrap:anywhere}
main{max-width:44em;margin:0 auto;padding:32px 24px 64px}
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
.now{transition:background .25s,outline-color .25s}
.bar{position:sticky;top:0;z-index:10;background:var(--mat);-webkit-backdrop-filter:saturate(1.6) blur(18px);backdrop-filter:saturate(1.6) blur(18px);border-bottom:1px solid var(--bd);font:550 14px/1 'Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif}
.bar .in{max-width:44em;margin:0 auto;padding:6px 24px;display:flex;align-items:center;gap:14px}
.bar .ttl{flex:1 1 0;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--mut);font-size:13px;font-weight:600}
.bar .tools{display:flex;align-items:center;gap:4px;flex:none}
.bar .g{position:relative;display:flex;align-items:center;gap:4px}
.bar .cap{padding:0 2px 0 6px;color:var(--mut);font-size:12px;font-weight:600}
.bar .sp{width:1px;height:22px;margin:0 6px;background:var(--bd2);opacity:.6}
.bar button{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:40px;padding:0 14px;border:1px solid var(--bd2);border-radius:10px;background:var(--sf);color:var(--fg);box-shadow:var(--sh1);cursor:pointer;white-space:nowrap;transition:background .12s,border-color .12s}
.bar button:hover{background:var(--sf2)}
.bar button:active{background:var(--sf3)}
.bar button:focus-visible,.pl button:focus-visible{outline:3px solid color-mix(in srgb,var(--pri) 70%,transparent);outline-offset:2px}
.bar .rd svg{width:17px;height:17px}
.bar .on{background:var(--pris);border-color:color-mix(in srgb,var(--pri) 45%,transparent);color:var(--prik)}
.pl{position:absolute;top:calc(100% + 10px);right:0;z-index:30;padding:6px 8px;background:var(--sf);border:1px solid var(--bd2);border-radius:14px;box-shadow:var(--sh);font:550 14px/1.4 'Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif;animation:plin .16s ease-out}
.pl[hidden]{display:none}
.pl.open{width:268px}
@keyframes plin{from{opacity:0;transform:translateY(-6px)}}
.pl .pr{display:flex;align-items:center;justify-content:center;gap:2px}
.pl button{all:unset;box-sizing:border-box;display:inline-grid;place-items:center;cursor:pointer;color:var(--fg);transition:background .12s,transform .08s}
.pl button:focus-visible,.pl select:focus-visible,.pl input:focus-visible{outline:3px solid color-mix(in srgb,var(--pri) 70%,transparent);outline-offset:2px}
.pl .ic{width:32px;height:32px;border-radius:50%}
.pl .ic:hover{background:var(--sf2)}.pl .ic:active{background:var(--sf3);transform:scale(.94)}
.pl .ic svg{width:15px;height:15px;fill:currentColor}
.pl .go{width:36px;height:36px;border-radius:50%;background:var(--pri);color:var(--onp);box-shadow:inset 0 1px 0 rgba(255,255,255,.2)}
.pl .go:hover{background:var(--prih)}.pl .go:active{transform:scale(.95)}
.pl .go svg{width:17px;height:17px}
.pl .cnt{min-width:42px;text-align:center;color:var(--mut);font-size:12.5px;font-variant-numeric:tabular-nums;white-space:nowrap}
.pl .mini{width:28px;height:28px;border-radius:50%;color:var(--mut)}
.pl .mini:hover{background:var(--sf2);color:var(--fg)}
.pl .mini[aria-expanded=true]{background:var(--pris);color:var(--prik)}
.pl .mini svg{width:15px;height:15px}
.pl .set{display:none;flex-direction:column;gap:12px;margin-top:6px;padding:10px 4px 6px;border-top:1px solid var(--bd)}
.pl.open .set{display:flex}
.pl .fr{display:flex;align-items:center;gap:10px}
.pl .fl{flex:none;width:40px;color:var(--mut);font-size:12.5px;font-weight:600}
.pl input[type=range]{-webkit-appearance:none;appearance:none;flex:1;min-width:0;height:4px;margin:0;border-radius:99px;background:linear-gradient(to right,var(--pri) var(--p,0%),var(--sf3) var(--p,0%));cursor:pointer}
.pl input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;background:#fff;border:1px solid var(--bd2);box-shadow:0 1px 4px rgba(0,0,0,.3)}
.pl input[type=range]::-moz-range-thumb{width:15px;height:15px;border-radius:50%;background:#fff;border:1px solid var(--bd2);box-shadow:0 1px 4px rgba(0,0,0,.3)}
.pl .vs{-webkit-appearance:none;appearance:none;flex:1;min-width:0;height:34px;padding:0 30px 0 12px;border:1px solid var(--bd2);border-radius:9px;background:var(--sf) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%23808a9c' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") no-repeat right 11px center;color:var(--fg);box-shadow:var(--sh1);font:550 13px/1 inherit;font-family:inherit;cursor:pointer}
.pl .vs:hover{background-color:var(--sf2)}
.pl .vs option{color:#000}
.pl .spv{flex:none;min-width:52px;text-align:right;color:var(--fg);font-size:12.5px;font-variant-numeric:tabular-nums}
.pl .nt{margin:0;color:var(--mut);font-size:12px;font-weight:500}
@media (max-width:560px){.bar .in{padding:8px 12px}.bar .ttl{display:none}.bar .tools{flex:1;justify-content:space-between}.bar .cap{display:none}.bar .sp{margin:0 2px}.bar button{padding:0 10px}main{padding:24px 16px 64px}}
@media (prefers-reduced-motion:reduce){.pl{animation:none}.pl .trk i,.now,.bar button,.pl button{transition:none}}
@media print{.bar,.pl{display:none}main{padding-top:0}}
"""

JS = r"""
(()=>{const R=document.documentElement,K='osb:';const g=k=>{try{return localStorage.getItem(K+k)}catch(e){return null}},s=(k,v)=>{try{localStorage.setItem(K+k,v)}catch(e){}};
const T=['light','dark','hc'];if(g('theme')&&T.includes(g('theme')))R.dataset.theme=g('theme');if(+g('fs'))R.style.setProperty('--fs',+g('fs')+'px');
const fs=()=>parseFloat(getComputedStyle(R).getPropertyValue('--fs'))||22;
const AIV=__AIV__,TTS=location.protocol.indexOf('http')===0?'':'__TTS__',D=document,Q=x=>D.querySelector(x),syn=window.speechSynthesis,clampR=x=>Math.min(1.5,Math.max(.8,+x||1));
let q=[],i=-1,st='idle',gen=0,voices=[],au=null,aiFail=false,redo=false,bad=0,rate=clampR(g('rate')),vname='ai:'+(AIV.some(v=>v[0]===g('voice'))?g('voice'):AIV[0][0]);
const ICON={play:'<svg viewBox="0 0 24 24"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/></svg>',pause:'<svg viewBox="0 0 24 24"><rect x="6" y="5" width="4.2" height="14" rx="1.2"/><rect x="13.8" y="5" width="4.2" height="14" rx="1.2"/></svg>'};
const TN={light:'기본',dark:'어둡게',hc:'고대비'};function thl(){const b=Q('#thb'),n=R.dataset.theme||'light';if(b){b.textContent=TN[n];b.setAttribute('aria-label','화면 대비 바꾸기, 지금은 '+TN[n])}}thl();
D.addEventListener('click',e=>{const b=e.target.closest('[data-a]');
if(b){const a=b.dataset.a;
if(a==='bigger'||a==='smaller'){const v=Math.min(64,Math.max(14,fs()+(a==='bigger'?2:-2)));R.style.setProperty('--fs',v+'px');s('fs',v)}
if(a==='theme'){const n=T[(T.indexOf(R.dataset.theme||'light')+1)%3];R.dataset.theme=n;s('theme',n);thl()}
if(a==='read')st==='idle'?open():Q('.pl').hidden?unfold():fold();
if(a==='more'){const pl=Q('.pl'),o=!pl.classList.contains('open');pl.classList.toggle('open',o);b.setAttribute('aria-expanded',o);s('more',o?1:0)}
if(a==='play')st==='play'?pause():st==='pause'?(redo?go(i):resume()):go(i<0?0:i);
if(a==='prev')go(Math.max(0,i-1));
if(a==='next')go(Math.min(q.length-1,i+1));
return}
const r=e.target.closest('.r');if(st!=='idle'&&!Q('.pl').hidden&&r&&!e.target.closest('summary,a,button'))go(q.indexOf(r))});
D.addEventListener('input',e=>{if(e.target.id!=='rng')return;rate=clampR(e.target.value);s('rate',rate);ui();if(au)au.playbackRate=rate});
D.addEventListener('change',e=>{if(e.target.id==='rng'){if(st==='play'&&!au)go(i);return}if(e.target.id!=='vsel')return;vname='ai:'+e.target.value;s('voice',e.target.value);aiFail=false;bad=0;note('');if(st!=='idle'){gen++;stopAu();syn&&syn.cancel();st='pause';redo=true;ui()}});
D.addEventListener('keydown',e=>{if(e.key==='Escape'&&st!=='idle'&&!Q('.pl').hidden)fold()});
function score(v){const n=v.name;return(/natural|online|neural/i.test(n)?40:0)+(/google/i.test(n)?25:0)+(/sun-?hi|yuna|injoon|seoyeon|heami|flo|sandy/i.test(n)?10:0)+(v.localService?0:5)}
function loadVoices(){voices=(syn?syn.getVoices():[]).filter(v=>/^ko/i.test(v.lang)).sort((a,b)=>score(b)-score(a))}
function useAi(){return vname.indexOf('ai:')===0&&!aiFail}
function aiUrl(t){return TTS+'/api/tts?v='+vname.slice(3)+'&t='+encodeURIComponent(t)}
function stopAu(){if(au){au.onended=au.onerror=null;au.pause();au=null}}
function note(m){const n=Q('.pl .nt');if(n){n.textContent=m;n.hidden=!m}}
function pick(){return voices[0]}
function split(t){const out=[];let cur='';for(const p of t.replace(/\s+/g,' ').trim().split(/(?<=[.!?。…])\s+/)){if(cur&&(cur+p).length>110){out.push(cur);cur=p}else cur=cur?cur+' '+p:p}if(cur)out.push(cur);
return out.flatMap(x=>{const r=[];while(x.length>160){let k=Math.max(x.lastIndexOf(', ',160),x.lastIndexOf(' ',160));if(k<40)k=160;r.push(x.slice(0,k+1).trim());x=x.slice(k+1)}r.push(x);return r}).filter(x=>/[0-9A-Za-z가-힣]/.test(x))}
function clearNow(){D.querySelectorAll('.now').forEach(e=>e.classList.remove('now'))}
function ui(){const p=Q('[data-a=play]');if(!p)return;p.innerHTML=ICON[st==='play'?'pause':'play'];p.setAttribute('aria-label',st==='play'?'일시정지':'읽기');
const rg=Q('#rng');rg.value=rate;rg.style.setProperty('--p',(rate-.8)/.7*100+'%');Q('.spv').textContent=(+rate.toFixed(2))+'배속';const vs=Q('#vsel');if(vs.value!==vname.slice(3))vs.value=vname.slice(3);Q('.pl .cnt').textContent=q.length?(Math.max(i,0)+1)+' / '+q.length:'';
const b=Q('[data-a=read]');const ex=st!=='idle'&&!Q('.pl').hidden;b.classList.toggle('on',ex);b.setAttribute('aria-expanded',ex)}
function open(){note('');{const op=g('more')==='1';Q('.pl').classList.toggle('open',op);Q('[data-a=more]').setAttribute('aria-expanded',op)}q=[...D.querySelectorAll('.r')];if(!q.length)return;loadVoices();Q('.pl').hidden=false;
go(Math.max(0,q.findIndex(e=>e.getBoundingClientRect().top>60)))}
function close(){redo=false;gen++;stopAu();syn&&syn.cancel();st='idle';clearNow();Q('.pl').hidden=true;ui()}
function fold(){Q('.pl').hidden=true;if(st==='play')pause();ui()}
function unfold(){Q('.pl').hidden=false;if(st==='pause')redo?go(i):resume();ui()}
function pause(){st='pause';au?au.pause():syn.pause();ui()}
function resume(){st='play';au?au.play():syn.resume();ui()}
function go(n){redo=false;gen++;stopAu();syn&&syn.cancel();st='play';i=n;say()}
function reveal(el){const br=Q('.bar'),pl=Q('.pl'),t=Math.max(br?br.getBoundingClientRect().bottom:0,pl&&!pl.hidden?pl.getBoundingClientRect().bottom:0)+12,b=innerHeight-16,r=el.getBoundingClientRect();
if(r.top>=t&&r.bottom<=b)return;const room=b-t,y=r.height>=room?r.top-t:r.top-t-(room-r.height)/2;scrollBy({top:y,behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'})}
function say(){clearNow();if(i<0||i>=q.length){close();return}const el=q[i],my=gen,parts=split(el.dataset.s||el.innerText);let k=0;
el.classList.add('now');reveal(el);ui();
const dev=t=>{if(!syn){next();return}const u=new SpeechSynthesisUtterance(t);u.lang='ko-KR';u.rate=rate;const v=pick();if(v)u.voice=v;u.onend=next;u.onerror=ev=>{if(ev.error!=='canceled'&&ev.error!=='interrupted')next()};syn.speak(u)};
const next=()=>{if(my!==gen)return;if(k>=parts.length){i++;say();return}const t=parts[k++];
if(useAi()){const nx=parts[k]||(q[i+1]&&split(q[i+1].dataset.s||q[i+1].innerText)[0]);if(nx)fetch(aiUrl(nx),{mode:'no-cors'}).catch(()=>{});
const a=au=new Audio(aiUrl(t));a.playbackRate=rate;a.onplaying=()=>{bad=0};a.onended=next;a.onerror=()=>{if(my!==gen)return;au=null;if(++bad>=3){aiFail=true;note('AI 목소리 서버에 연결되지 않아 이 기기 목소리로 읽어요')}dev(t)};a.play().catch(()=>{});return}
dev(t)};
next()}
loadVoices();if(syn&&syn.addEventListener)syn.addEventListener('voiceschanged',loadVoices)
window.addEventListener('beforeunload',()=>{stopAu();syn&&syn.cancel()})})();
"""

CODE_SYM = [("==", " 같다 "), ("!=", " 같지 않다 "), ("<=", " 작거나 같다 "), (">=", " 크거나 같다 "), ("&&", " 그리고 "), ("||", " 또는 "),
            ("++", " 플러스 플러스 "), ("--", " 마이너스 마이너스 "), ("->", " 화살표 "), ("(", " 여는 괄호 "), (")", " 닫는 괄호 "),
            ("{", " 여는 중괄호 "), ("}", " 닫는 중괄호 "), ("[", " 여는 대괄호 "), ("]", " 닫는 대괄호 "), (";", " 세미콜론 "),
            ("=", " 는 "), ("+", " 더하기 "), ("-", " 빼기 "), ("*", " 곱하기 "), ("/", " 나누기 "), ("<", " 작다 "), (">", " 크다 "),
            ("!", " 부정 "), ("%", " 나머지 "), (",", " 쉼표 "), (":", " 콜론 "), ('"', " 큰따옴표 "), ("'", " 작은따옴표 "), ("_", " 밑줄 ")]


def _font_css(text: str) -> str:
    """Pretendard를 문서 안에 넣는다. 이 문서에 쓰인 글자만 남겨서 용량을 줄이고, 실패하면 기기에 있는 글꼴로 대신한다."""
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
        chars = set(re.sub(r"<[^>]+>", " ", _html.unescape(text))) | {chr(c) for c in range(0x20, 0x7F)} | set("·…“”‘’–—→←↑↓×÷≤≥≠≈○●■□▲△▶◀※")
        key = hashlib.sha256("".join(sorted(chars)).encode("utf-8")).hexdigest()[:24]
        cached = config.CACHE_DIR / "font" / (key + ".css")                 # 같은 글자 구성이면 다시 만들지 않는다 (만드는 데 몇 초 걸린다)
        if cached.exists():
            return cached.read_text(encoding="utf-8")
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]
        font = TTFont(config.STATIC_DIR / "fonts" / "PretendardVariable.woff2")
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(chars)))
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff2"
        font.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        css = "@font-face{font-family:'Pretendard Variable';font-weight:45 920;font-display:swap;src:url(data:font/woff2;base64," + b64 + ") format('woff2')}"
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(css, encoding="utf-8")
        return css
    except Exception:
        return ""


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
        if t["ko"] in used:
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
        html_s = html_s[:i + len(ke)] + f'<span class="gl">({_e(w["easy"])})</span>' + html_s[i + len(ke):]
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
        parts.append('<p class="note"><span class="ai" style="margin:0">AI</span> 어려운 단어 뒤에 쉬운 말을 괄호로 붙였어요. AI가 고른 풀이라 틀릴 수 있어요.</p>')
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
    js = (JS.replace("__AIV__", json.dumps([[k, v] for k, v in tts.VOICES.items()], ensure_ascii=False))
          .replace("__TTS__", config.PUBLIC_URL or f"http://localhost:{config.PORT}"))   # 내려받아 파일로 열어도 서버가 켜져 있으면 AI 목소리를 쓴다
    # 고른 기능의 도구만 문서에 둔다 (큰 글씨만 골랐으면 글씨 크기 버튼만, 고대비만 골랐으면 대비 버튼만, 소리 읽기를 골랐을 때만 읽어 주기)
    groups = []
    if o["large"]:
        groups.append('<div class="g" role="group" aria-label="글씨 크기"><span class="cap">글씨</span><button data-a="smaller" aria-label="글씨 작게">가-</button><button data-a="bigger" aria-label="글씨 크게">가+</button></div>')
    if o["contrast"]:
        groups.append('<div class="g" role="group" aria-label="화면 대비"><span class="cap">대비</span><button data-a="theme" id="thb">기본</button></div>')
    if o.get("read"):
        groups.append('<div class="g" role="group" aria-label="읽어 주기"><button class="rd" data-a="read" aria-controls="pl" aria-expanded="false">'
                      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5zM15 8.5a5 5 0 0 1 0 7M17.5 6a8.5 8.5 0 0 1 0 12" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>읽어 주기</button></div>')
    player = ""
    if o.get("read"):
        player = ('<div class="pl" id="pl" role="region" aria-label="읽어 주기 도구" hidden><div class="pr">'
                  '<button class="ic" data-a="prev" aria-label="이전 문단"><svg viewBox="0 0 24 24"><path d="M6 5h2v14H6zM9.5 12l9 6.5v-13z"/></svg></button>'
                  '<button class="go" data-a="play" aria-label="읽기"></button>'
                  '<button class="ic" data-a="next" aria-label="다음 문단"><svg viewBox="0 0 24 24"><path d="M16 5h2v14h-2zM14.5 12l-9 6.5v-13z"/></svg></button>'
                  '<span class="cnt" aria-live="off"></span>'
                  '<button class="mini" data-a="more" aria-expanded="false" aria-label="목소리와 속도 설정"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M4 7h8M18 7h2M4 17h2M12 17h8"/><circle cx="15" cy="7" r="2.6"/><circle cx="9" cy="17" r="2.6"/></svg></button></div>'
                  '<div class="set">'
                  f'<label class="fr"><span class="fl">목소리</span><select class="vs" id="vsel">{"".join(f"<option value={chr(34)}{k}{chr(34)}>{_e(v)}</option>" for k, v in tts.VOICES.items())}</select></label>'
                  '<label class="fr"><span class="fl">속도</span><input id="rng" type="range" min="0.8" max="1.5" step="0.05" value="1"><span class="spv">1배속</span></label>'
                  '<p class="nt" hidden></p></div></div>')
    if player:                                        # 읽어 주기 버튼 바로 아래에 붙는다
        groups[-1] = groups[-1][:-len('</div>')] + player + '</div>'
    bar = (f'<header class="bar" role="toolbar" aria-label="보기 도구"><div class="in"><span class="ttl">{_e(title or doc.get("title", ""))}</span><div class="tools">'
           + '<i class="sp"></i>'.join(groups) + '</div></div></header>') if groups else ""
    body_html = "".join(parts)
    return (f'<!doctype html><html lang="ko" data-theme="{theme}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_e(title or doc.get("title", ""))}</title><style>{_font_css(body_html + bar + js + ''.join(tts.VOICES.values()))}{CSS.replace("__FS__", fs)}</style></head>'
            f'<body>{bar}<main>{body_html}</main><script>{js}</script></body></html>')


def brf_bytes(text: str) -> bytes:
    """점자 프린터용 BRF는 줄바꿈이 CR+LF가 표준이다. 파일로 받을 때와 PDF에 첨부할 때 같은 바이트가 되게 한곳에서 만든다."""
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def to_brf(doc: dict, o: dict) -> str:
    return outputs.to_braille_text(doc, 32, True, None, figures=o["figures"])
