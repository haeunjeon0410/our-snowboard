/* 맞춤 변환 창 — 스노우보드 화면 위에 잠깐 떠서 변환 방식을 고르고 다운로드하는 작은 창.
   확장 프로그램(content script)과 홈 화면이 같은 코드를 쓴다. 화면 스타일은 Shadow DOM 안에 가둬서 사이트와 섞이지 않는다.
   사용: OSBPanel.open({ adapter })  /  OSBPanel.preview(container)  (adapter 모양은 아래 참고) */
(() => {
  if (window.OSBPanel) return;
  const FONT = "'OSB Pretendard','Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif";
  const ICON = {
    x: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>',
    file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7l-5-5z"/><path d="M14 2v5h5M9 13h6M9 17h6"/></svg>',
    down: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 11l5 5 5-5M5 20h14"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="M7.8 12.4l2.9 2.9 5.5-5.8"/></svg>',
    alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01"/></svg>'
  };
  const CHEV = "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%235a6b88' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")";

  const CSS = `
:host{all:initial}
*{box-sizing:border-box;font-family:${FONT}}
.scrim{position:fixed;inset:0;background:rgba(28,34,48,.26);-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px);animation:fade .16s ease-out}
.win:focus{outline:none}
.win{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(440px,calc(100vw - 24px));max-height:calc(100vh - 48px);display:flex;flex-direction:column;background:#fbfcfd;border-radius:12px;box-shadow:0 0 0 1px rgba(20,35,60,.14),0 28px 70px rgba(20,35,60,.32);overflow:hidden;color:#1c2230;font:400 14px/1.5 ${FONT};letter-spacing:-.01em;animation:pop .2s cubic-bezier(.2,.8,.2,1)}
:host(.inline) .win{position:relative;left:auto;top:auto;transform:none;width:100%;max-height:none;animation:none}
@keyframes fade{from{opacity:0}}@keyframes pop{from{opacity:0;transform:translate(-50%,calc(-50% + 8px)) scale(.985)}}
.bar{flex:none;height:42px;display:flex;align-items:center;justify-content:center;position:relative;background:#eceff4;border-bottom:1px solid rgba(20,35,60,.1);cursor:grab;user-select:none;-webkit-user-select:none;touch-action:none}
.bar.drag{cursor:grabbing}
.bar[hidden]{display:none}
.grip{position:absolute;right:0;bottom:0;width:20px;height:20px;cursor:nwse-resize;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'%3E%3Cg fill='%238a97ad'%3E%3Ccircle cx='13' cy='13' r='1.3'/%3E%3Ccircle cx='9' cy='13' r='1.3'/%3E%3Ccircle cx='13' cy='9' r='1.3'/%3E%3Ccircle cx='5' cy='13' r='1.3'/%3E%3Ccircle cx='9' cy='9' r='1.3'/%3E%3Ccircle cx='13' cy='5' r='1.3'/%3E%3C/g%3E%3C/svg%3E") no-repeat center/16px;opacity:.55;touch-action:none;z-index:5}
.grip:hover,.grip:focus-visible{opacity:1}.grip:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:-2px;border-radius:0 0 12px 0}
.win.flat{box-shadow:none;border-radius:0;background:transparent}.win.flat .file small{white-space:normal}.win.flat .body{padding:8px 4px 2px}.win.flat .foot{padding:8px 4px 2px}
.bar .t{font-size:13px;font-weight:600;color:#3a475d}
.x{all:unset;position:absolute;right:8px;top:8px;width:26px;height:26px;border-radius:7px;display:flex;align-items:center;justify-content:center;color:#5a6b88;cursor:pointer}
.x:hover{background:rgba(58,71,93,.13);color:#26344d}.x:focus-visible{outline:2px solid rgba(58,71,93,.55)}
.body{overflow-x:hidden;overflow-y:auto;scrollbar-width:thin;padding:12px 16px 4px;min-height:100px}
.file{display:flex;gap:9px;align-items:center;padding:0 2px 8px}
.file svg{width:18px;height:18px;color:#5a6b88;flex:none}
.file div{flex:1;min-width:0}
.file b{display:block;font-size:14px;font-weight:600;line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.file small{display:block;font-size:12px;color:#6b7689;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fmt{flex:none;appearance:none;-webkit-appearance:none;font:inherit;font-size:12.5px;font-weight:600;color:#3a475d;background:#eceff4 ${CHEV} no-repeat right 8px center/10px;border:0;border-radius:7px;padding:6px 26px 6px 10px;cursor:pointer}
.fmt:hover{background-color:#e4e9f1}.fmt:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:1px}
.lab{margin:6px 0 6px 2px;font-size:12.5px;font-weight:600;color:#6b7689}
.pres{margin-top:2px}
.pre{all:unset;box-sizing:border-box;display:grid;width:100%;grid-template-columns:20px 1fr;column-gap:11px;align-items:start;padding:8px 10px;border-radius:9px;cursor:pointer}
.pre:hover{background:#f0f3f7}.pre:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:1px}
.pre[aria-checked=true]{background:#eaeef4}
.pre .rd{width:18px;height:18px;margin-top:1px;border:1.5px solid #b3bdcd;border-radius:50%;background:#fff;display:grid;place-content:center}
.pre[aria-checked=true] .rd{background:#4a6794;border-color:#4a6794}
.pre[aria-checked=true] .rd::after{content:'';width:6px;height:6px;border-radius:50%;background:#fff}
.pre .l{font-size:14px;font-weight:600;line-height:1.4}
.pre .s{grid-column:2;font-size:12px;color:#6b7689;line-height:1.4}
.prew{position:relative}
.psel{position:absolute;right:10px;top:50%;transform:translateY(-50%)}
.psel select{appearance:none;-webkit-appearance:none;font:inherit;font-size:12.5px;font-weight:550;color:#3a475d;background:#eceff4 ${CHEV} no-repeat right 7px center/10px;border:0;border-radius:6px;padding:4px 22px 4px 9px;cursor:pointer}
.psel select:focus-visible{outline:2px solid rgba(58,71,93,.55)}
.pre[aria-disabled=true]{opacity:.5;cursor:not-allowed}
.opt.radio input{border-radius:50%}
.opt.radio input:checked::after{width:6px;height:6px;border:0;border-radius:50%;background:#fff;transform:none}
.opt.sub{margin:0}
.opts{padding-top:2px}.g2{display:grid;grid-template-columns:1fr 1fr;column-gap:10px}.g3{display:grid;grid-template-columns:repeat(3,auto);justify-content:start;column-gap:18px;margin-left:30px}
.sh3{margin:0 0 4px 2px;font-size:13px;font-weight:650;color:#3a475d}
.opts .opt{padding:8px 2px;align-items:start}.opts .opt+.opt{border-top:0}
.opts .tag{margin:0}
.sum{flex:1;min-width:0;margin-right:8px;font-size:12px;color:#6b7689;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.code{margin:12px 0 4px;padding:10px 12px;background:#eef1f5;border-radius:9px}
.code label{display:block;font-size:12.5px;font-weight:600;color:#3a475d;margin-bottom:6px}
.code .cr{display:flex;gap:6px}
.code input{flex:1;min-width:0;height:32px;padding:0 10px;border:1px solid #c4ccda;border-radius:7px;background:#fff;font:inherit;font-size:13px;color:#1c2230}
.code input:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:1px}
.code small{display:block;margin-top:6px;font-size:12px;color:#6b7689}
.code small.bad{color:#97662a}
.opt{display:grid;grid-template-columns:20px 1fr auto;column-gap:11px;align-items:start;padding:8px 2px;cursor:pointer}
.opt+.opt{border-top:1px solid rgba(20,35,60,.07)}
.opt input{appearance:none;-webkit-appearance:none;width:18px;height:18px;margin:2px 0 0;border:1.5px solid #b3bdcd;border-radius:5px;background:#fff;display:grid;place-content:center;cursor:pointer;transition:background .12s,border-color .12s}
.opt input:checked{background:#4a6794;border-color:#4a6794}
.opt input:checked::after{content:'';width:9px;height:5px;border:2px solid #fff;border-top:0;border-right:0;transform:rotate(-45deg) translate(1px,-1px)}
.opt input:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:2px}
.opt .l{font-size:14px;font-weight:550;line-height:1.4}
.opt .s{grid-column:2;font-size:12.5px;color:#6b7689;line-height:1.45;margin-top:1px}
.opt.off{opacity:.5;cursor:not-allowed}.opt.off input{cursor:not-allowed}
.tag{font-size:10.5px;font-weight:700;color:#5a6b88;background:#e4e9f1;border-radius:99px;padding:1px 7px;margin-top:2px}
.sel{grid-column:2;margin-top:5px}
.sel select{appearance:none;-webkit-appearance:none;font:inherit;font-size:12.5px;font-weight:550;color:#3a475d;background:#eceff4 ${CHEV} no-repeat right 7px center/10px;border:0;border-radius:6px;padding:4px 22px 4px 9px;cursor:pointer}
.sel select:disabled{opacity:.5;cursor:not-allowed}.sel select:focus-visible{outline:2px solid rgba(58,71,93,.55)}
.hint{margin:8px 2px 10px;font-size:12px;color:#6b7689}
.foot{flex:none;display:flex;justify-content:flex-end;align-items:center;gap:6px;padding:10px 16px 12px;border-top:1px solid rgba(20,35,60,.08)}
.btn{all:unset;box-sizing:border-box;height:32px;padding:0 14px;border-radius:8px;font:600 13.5px/1 ${FONT};display:inline-flex;align-items:center;gap:6px;cursor:pointer;color:#3a475d}
.btn:hover{background:#e4e9f1}.btn:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:2px}
.btn.pri{background:#3f5a86;color:#fff}.btn.pri:hover{background:#34496f}
.btn:disabled{opacity:.45;cursor:not-allowed}.btn.pri:disabled:hover{background:#3f5a86}
.state{display:flex;flex-direction:column;align-items:center;text-align:center;gap:6px;padding:22px 8px 14px}
.state svg{width:34px;height:34px}
.state.ok svg{color:#5d8a72}.state.bad svg{color:#97662a}
.state b{font-size:15px;font-weight:650}
.state p{font-size:13px;color:#6b7689;line-height:1.55;max-width:30em}
.state ul{list-style:none;margin:6px 0 0;padding:0;font-size:12.5px;color:#4a5262}
.state li,.prog .row span,.hint,.file b,.file small{overflow-wrap:anywhere}
.state ul.sum{width:100%;margin:6px 0 0;text-align:left}
.state ul.sum li{display:flex;gap:8px;padding:2px 0;line-height:1.45}
.state ul.sum li::before{content:'';flex:none;width:5px;height:5px;margin-top:8px;border-radius:50%;background:#4a6794}
.state ul.files{margin-top:8px;font-size:11.5px;color:#6b7689}
.lnk{all:unset;margin-top:10px;font-size:12.5px;font-weight:600;color:#4a6794;text-decoration:underline;text-underline-offset:3px;cursor:pointer;border-radius:4px}.lnk:hover{color:#34496f}.lnk:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:3px}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:10px;width:100%;margin-top:4px;text-align:left}
.cmp .c{overflow:hidden;overflow-wrap:anywhere;border-radius:9px;padding:10px 12px;font-size:13px;line-height:1.55;background:#f1f4f8;min-height:110px;min-width:0}
.cmp .c.af{background:#e6edf7}
.cmp small{display:block;font-size:11px;font-weight:650;color:#6b7689;margin-bottom:3px}
.cmp img{display:block;max-width:100%;max-height:150px;margin:0 auto;border-radius:5px}
.cmp .t{color:#1c2230}
.cmp .t.sm{font-size:11px;color:#5a6577}.cmp .t.lg{font-size:17px;line-height:1.45}
.cmp .c.hc{background:#000}.cmp .c.hc small{color:#fff}.cmp .c.hc .t{color:#ffe600}
.cmp+.cmp{margin-top:14px}.cmp .t.raw{word-break:break-all;color:#5a6577}
.prog{padding:20px 4px 14px}
.prog .row{display:flex;justify-content:space-between;gap:10px;font-size:13px;color:#4a5262;margin-bottom:8px}
.prog .row span:last-child{color:#6b7689;font-variant-numeric:tabular-nums}
.state img.m{width:92px;height:auto;margin-bottom:2px}
.course{position:relative;height:84px;margin-top:2px}
.band{position:absolute;left:0;right:0;top:54px;height:30px;clip-path:polygon(0 2px,100% 22px,100% 27px,0 7px);background:linear-gradient(to right,#4a6794 var(--p,0%),#dfe6f0 var(--p,0%));transition:background .6s linear}
.rider{position:absolute;width:0;height:0;transition:left .8s linear,top .8s linear;pointer-events:none}
.bob{position:absolute;left:-22px;top:0;width:44px;height:50px;transform-origin:50% 90%;animation:bob .7s ease-in-out infinite}
.bob img{display:block;height:50px;width:auto;margin:0 auto}.bob img.flip{transform:scaleX(-1)}
.rider.trick .bob{animation:trick .95s ease-in-out both;transform-origin:50% 100%}
@keyframes trick{0%{transform:translateY(0) rotate(5deg) scaleX(1)}14%{transform:translateY(-12px) rotate(5deg) scaleX(.62)}28%{transform:translateY(-26px) rotate(5deg) scaleX(.04)}42%{transform:translateY(-34px) rotate(5deg) scaleX(-.7)}56%{transform:translateY(-30px) rotate(5deg) scaleX(-1)}70%{transform:translateY(-18px) rotate(5deg) scaleX(-.5)}84%{transform:translateY(-5px) rotate(5deg) scaleX(.45)}94%{transform:translateY(0) rotate(5deg) scaleX(1) scaleY(.9)}100%{transform:translateY(0) rotate(5deg) scaleX(1) scaleY(1)}}
.lift{position:absolute;left:0;top:0;width:0;height:0;transition:transform .8s ease}
.rider.air .bob{animation:floaty 1.9s ease-in-out infinite}
.rider.air .bob img,.rider.air .pf{visibility:hidden}
.rider.air .spin{display:block}
@keyframes floaty{0%,100%{transform:translateY(0) rotate(5deg)}50%{transform:translateY(-4px) rotate(7deg)}}
.spin{display:none;position:absolute;left:50%;bottom:0;width:46px;height:60px;margin-left:-23px;background-repeat:no-repeat;background-size:800% 100%;pointer-events:none}
.pf{position:absolute;left:-4px;bottom:4px;width:5px;height:5px;border-radius:50%;background:#cfe0f7;opacity:0;animation:puff .9s ease-out infinite}
.pf:nth-of-type(2){animation-delay:.3s;bottom:7px}.pf:nth-of-type(3){animation-delay:.6s;bottom:1px}
.ind .rider{animation:lap 2.8s linear infinite}
@keyframes bob{0%,100%{transform:translateY(0) rotate(5deg)}50%{transform:translateY(-3px) rotate(9deg)}}
@keyframes puff{0%{opacity:.9;transform:translate(0,0) scale(1)}100%{opacity:0;transform:translate(-20px,-5px) scale(.3)}}
@keyframes lap{0%{left:5%;top:10px;opacity:0}12%{opacity:1}88%{opacity:1}100%{left:92%;top:28px;opacity:0}}
.meter{height:6px;border-radius:99px;background:#e4e9f1;overflow:hidden}
.meter i{display:block;height:100%;width:0;background:#4a6794;border-radius:99px;transition:width .45s ease}
.meter.ind i{width:38%;animation:slide 1.1s ease-in-out infinite}
@keyframes slide{0%{margin-left:-38%}100%{margin-left:100%}}
.sk{height:14px;border-radius:6px;background:#e8ecf2;margin:10px 0}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
`;

  // 고를 수 있는 항목. info(자료 요약)에 따라 해당 없는 것은 숨기거나 끈다.
  const DEFAULTS = { read: false, large: false, contrast: false, figures: false, easy: false, terms: false, color: false, colorType: 'deutan', pdf: true, readpdf: false, html: false, braille: false };
  const OPTIONS = [
    { key: 'braille', label: '점자 파일도 받기', sub: '점자 프린터·단말기용 파일(.brf)도 함께 받아요' },
    { key: 'figures', label: '그림·도식을 글로 설명', sub: '그림이 무엇을 보여 주는지 글로 풀어 써요', ai: true, needs: 'figures', none: '이 자료에는 그림이 없어요' },
    { key: 'color', label: '색 구분 돕기', sub: n => `색으로 칠한 도식 ${n}개에 보정과 무늬를 넣어요`, needs: 'colorFigures', hideIfNone: true, select: true },
    { key: 'easy', label: '어려운 단어 뜻', sub: '어려운 단어 뒤에 쉬운 말과 영어를 붙여요. 예: 용이하다(쉽다 · easy)', ai: true },
    { key: 'terms', label: '영어 용어 함께', sub: '전문 용어 뒤에 영어를 붙여요. 예: 알고리즘(algorithm)', ai: true },
    { key: 'contrast', label: '고대비', sub: '검정 바탕에 밝은 글씨로 바꿔요' },
    { key: 'large', web: true, label: '큰 글씨', sub: '글씨와 줄 간격을 키워요. 웹 문서로 받아요' },
    { key: 'read', web: true, label: '소리로 읽어 주기', sub: '문서 안에 읽어 주기 버튼이 생겨요. 웹 문서로 받아요' }
  ];
  const KEYS = ['pdf', 'readpdf', 'html', 'braille', 'figures', 'color', 'easy', 'terms', 'contrast', 'large', 'read'];
  const C = ['braille', 'figures', 'color', 'easy', 'terms', 'contrast', 'large', 'read'];     // 내용 항목 (받는 형식과 별개)
  // 대부분은 이 중 하나만 누르면 끝나도록. 받는 형식은 오른쪽 위 드롭다운. '직접 설정'은 고른 항목을 저장해 둔다.
  const PRESETS = [
    { id: 'read', label: '그림 읽기·점자', sub: '그림을 글로 설명하고 점자 파일도 받아요', set: { figures: true, braille: true }, ai: true },
    { id: 'low', label: '저시력', sub: '큰 글씨와 검정 바탕으로 바꾸고, 소리로 읽어 줘요', set: { large: true, contrast: true, read: true }, reflow: true },
    { id: 'color', label: '색각 이상', sub: '색이 칠해진 도식에 보정과 무늬를 넣어요', set: { color: true }, needs: 'colorFigures', none: '이 자료에는 색이 칠해진 도식이 없어요' },
    { id: 'easy', label: '교환학생', sub: '어려운 단어와 전문 용어에 쉬운 말·영어를 붙여요', set: { easy: true, terms: true }, ai: true, reflow: true },
    { id: 'custom', label: '직접 설정', custom: true }
  ];
  const SHORT = { read: '소리 읽기', large: '큰 글씨', contrast: '고대비', figures: '그림 설명', easy: '단어 뜻', terms: '영어 용어', color: '색 구분', pdf: 'PDF', readpdf: 'PDF', html: '웹 문서', braille: '점자' };
  // 예전에 저장된 설정(원본+웹 문서 같이 고르기 등)도 '원본 그대로 / 다시 정리' 둘 중 하나로 맞춘다.
  const normalize = (o) => { const r = { ...o }; if (r.pdf || !(r.readpdf || r.html)) { r.pdf = true; r.readpdf = false; r.html = false; } else { r.pdf = false; r.readpdf = false; r.html = true; } return r; };      // 받는 모양은 PDF / 웹 문서 둘뿐 (예전에 저장된 '읽기용 PDF'는 웹 문서로)

  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'html') e.innerHTML = v;
      else if (k === 'class') e.className = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
    return e;
  }

  /* adapter: {
       name, sub,                                   // 파일 이름, 부제(과목)
       prepare() → {job, info}                      // 자료를 올리고 요약을 받는다
       make(job, options) → taskId                  // 변환 시작
       status(taskId) → {status, done, total, step, files, error, note}
       cancel(taskId), save(files)                  // 다운로드
       loadOptions() → options|null, saveOptions(options)
  } */
  function open(cfg) {
    const { adapter } = cfg;
    const inline = !!cfg.container;
    const opener = document.activeElement;
    const host = h('div', { 'data-osb-panel': '' });
    host.style.cssText = inline ? 'display:block' : 'all:initial;position:fixed;inset:0;z-index:2147483000;';
    if (inline) host.className = 'inline';
    const root = host.attachShadow({ mode: 'open' });
    root.append(h('style', {}, CSS));
    const scrim = inline ? null : h('div', { class: 'scrim' });
    const win = h('div', { class: 'win' + (cfg.settings && inline ? ' flat' : ''), role: 'dialog', tabindex: '-1', 'aria-modal': inline ? null : 'true', 'aria-label': '맞춤 다운로드' });
    if (scrim) root.append(scrim);
    root.append(win);
    (cfg.container || document.body).append(host);

    let codeTried = false, state = 'loading', opts = { ...DEFAULTS }, job = null, info = null, task = null, msg = '', progress = null, files = [], timer = null, closed = false, result = null, cmpOpen = false, cmpIdx = 0;

    const baseTitle = cfg.settings ? '맞춤 설정' : '맞춤 다운로드';
    const titleEl = h('span', { class: 't' }, baseTitle);
    const bar = h('div', { class: 'bar', hidden: cfg.settings && inline ? '' : null }, titleEl,
      h('button', { class: 'x', type: 'button', 'aria-label': '닫기', html: ICON.x, onclick: () => close() }));
    const body = h('div', { class: 'body' });
    const foot = h('div', { class: 'foot' });
    win.append(bar, body, foot);

    // 오른쪽 아래 모서리를 끌면 창과 안의 글자·버튼이 함께 커진다 (잘 안 보이는 사람을 위해). 기본은 100%. 더블클릭하면 원래 크기.
    let scale = 1;
    const grip = h('div', { class: 'grip', role: 'slider', tabindex: '0', 'aria-label': '창 크기', 'aria-valuemin': '100', 'aria-valuemax': '200', 'aria-valuenow': '100', title: '끌어서 크기 조절 (두 번 누르면 원래 크기)' });
    const maxScale = () => Math.max(1, Math.min(2, (innerWidth - 24) / 440));      // 높이는 아래에서 화면에 맞추고, 모자라면 안쪽에서 스크롤한다
    function setScale(s, persist) {
      scale = Math.min(maxScale(), Math.max(1, Math.round(s * 100) / 100));
      win.style.zoom = scale; grip.setAttribute('aria-valuenow', String(Math.round(scale * 100)));
      win.style.maxHeight = `calc((100vh - 40px) / ${scale})`; win.style.width = `min(440px, calc((100vw - 24px) / ${scale}))`;      // 확대하면 이 길이들도 같이 커지므로 미리 나눠 둔다 (화면 밖으로 안 나가게)
      if (persist) { try { adapter.saveScale ? adapter.saveScale(scale) : localStorage.setItem('osb.scale', String(scale)); } catch (e) { /* 무시 */ } }
    }
    if (!inline) {
      win.append(grip);
      grip.addEventListener('pointerdown', (e) => {
        e.preventDefault(); e.stopPropagation(); grip.setPointerCapture(e.pointerId);
        const x0 = e.clientX, y0 = e.clientY, s0 = scale;
        const move = (ev) => setScale(s0 + ((ev.clientX - x0) + (ev.clientY - y0)) / 380, false);
        const up = () => { grip.removeEventListener('pointermove', move); grip.removeEventListener('pointerup', up); setScale(scale, true); };
        grip.addEventListener('pointermove', move); grip.addEventListener('pointerup', up);
      });
      grip.addEventListener('dblclick', () => setScale(1, true));
      grip.addEventListener('keydown', (e) => {
        const d = { ArrowRight: .1, ArrowUp: .1, ArrowLeft: -.1, ArrowDown: -.1 }[e.key];
        if (d) { e.preventDefault(); e.stopPropagation(); setScale(scale + d, true); }
      });
      (async () => { let s = 1; try { s = adapter.loadScale ? await adapter.loadScale() : parseFloat(localStorage.getItem('osb.scale')); } catch (e) { /* 무시 */ } if (s > 1) setScale(s, false); })();
    }

    function close() {
      if (closed) return;
      closed = true; clearInterval(timer);
      if (task && state === 'working') adapter.cancel && adapter.cancel(task);
      host.remove(); document.removeEventListener('keydown', onKey, true);
      try { opener && opener.focus && opener.focus(); } catch (e) { /* 무시 */ }
      cfg.onClose && cfg.onClose();
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.stopPropagation(); if (sheetOpen) sheetClose(false); else if (cmpOpen) { cmpOpen = false; render(); } else close(); return; }
      if (e.key !== 'Tab') return;
      const f = [...root.querySelectorAll('button,input,select')].filter(x => !x.disabled && x.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1], cur = root.activeElement;
      if (e.shiftKey && (cur === first || !cur)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && cur === last) { e.preventDefault(); first.focus(); }
    }
    if (!inline) document.addEventListener('keydown', onKey, true);

    // 제목줄을 잡고 옮기기
    bar.addEventListener('pointerdown', (e) => {
      if (inline || e.target.closest('.x')) return;
      const r = win.getBoundingClientRect(), dx = e.clientX - r.left, dy = e.clientY - r.top;
      const k = scale || 1;                                                   // 확대 중이면 left/top도 같이 커지므로 나눠서 넣는다
      win.style.transform = 'none'; win.style.left = r.left / k + 'px'; win.style.top = r.top / k + 'px'; bar.classList.add('drag');
      bar.setPointerCapture(e.pointerId);
      const move = (ev) => { win.style.left = Math.min(innerWidth - 80, Math.max(-r.width + 80, ev.clientX - dx)) / k + 'px'; win.style.top = Math.min(innerHeight - 42, Math.max(0, ev.clientY - dy)) / k + 'px'; };
      const up = () => { bar.classList.remove('drag'); bar.removeEventListener('pointermove', move); bar.removeEventListener('pointerup', up); };
      bar.addEventListener('pointermove', move); bar.addEventListener('pointerup', up);
    });

    const fileCard = (extra) => cfg.settings ? h('div', { class: 'file' }, h('div', {}, h('b', {}, '기본 변환 방식'), h('small', {}, '다운로드를 누르면 이 방식으로 바로 변환해요')), extra) : h('div', { class: 'file' }, h('span', { html: ICON.file, style: 'display:flex' }),
      h('div', {}, h('b', {}, adapter.name || '자료'), h('small', {}, [adapter.sub, info ? `${info.pages}쪽` : ''].filter(Boolean).join(' · ') || ' ')), extra);

    // 이 자료에는 쓸 수 없는 항목(그림이 없음, AI 키 없음). 저장된 내 선택(opts)은 건드리지 않고 보내는 값에서만 뺀다.
    const reflow = () => !opts.pdf;
    const unusable = (def) => !!(info && ((def.needs && info[def.needs] === 0) || (def.ai && !info.ai)));      // 개수를 아직 모르면(null) 막지 않는다
    const effective = () => { const o = { ...opts }; delete o.custom; for (const d of OPTIONS) if (unusable(d) || (d.web && !reflow())) o[d.key] = false; if (!(o.pdf || o.readpdf || o.html || o.braille)) o.pdf = true; return o; };
    const updaters = [];
    let sumEl = null, sheetOpen = false, sheetBefore = '';
    const summary = () => {
      const eff = effective();
      const on = KEYS.filter(k => eff[k]).map(k => SHORT[k]);
      return on.length ? on.join(' · ') : '선택 없음';
    };
    const syncAll = () => { updaters.forEach(f => f()); if (sumEl) sumEl.textContent = summary(); };

    function optionRow(def, extra) {
      if (def.hideIfNone && info && def.needs && !info[def.needs]) return null;
      const input = h('input', { type: 'checkbox' });
      let sel = null;
      if (def.select) {
        sel = h('select', { 'aria-label': '색각 유형' },
          h('option', { value: 'deutan' }, '적록'), h('option', { value: 'tritan' }, '청황'));
        sel.value = opts.colorType;
        sel.addEventListener('change', () => { opts.colorType = sel.value; syncAll(); });
      }
      const subEl = h('span', { class: 's' });
      const el = h('label', { class: 'opt' + (extra ? ' ' + extra : '') }, input, h('span', { class: 'l' }, def.label), def.ai ? h('span', { class: 'tag' }, 'AI') : h('span'),
        subEl, sel ? h('span', { class: 'sel' }, sel) : null);
      const update = () => {
        const off = unusable(def);
        input.disabled = off; input.checked = !off && !!opts[def.key] && !(def.web && !reflow()); el.classList.toggle('off', off);
        if (sel) { sel.disabled = off || !opts[def.key]; sel.value = opts.colorType; }
        el.title = subEl.textContent = (def.needs && info[def.needs] === 0) ? def.none : (def.ai && !info.ai) ? 'AI 키가 없어 쓸 수 없어요' : (typeof def.sub === 'function' ? def.sub(info[def.needs]) : def.sub);
      };
      input.addEventListener('change', () => {
        opts[def.key] = input.checked;
        if (def.web && input.checked && !reflow()) Object.assign(opts, { pdf: false, readpdf: false, html: true });   // 큰 글씨·소리 읽기는 다시 정리한 형식에서만
        syncAll();
      });
      updaters.push(update); update();
      return el;
    }

    const allOff = () => Object.fromEntries(C.map(k => [k, false]));
    const applyContent = (set) => Object.assign(opts, allOff(), set);
    const presetOff = (pr) => !!(info && ((pr.needs && info[pr.needs] === 0) || (pr.ai && !info.ai)));
    const customText = () => C.filter(k => opts.custom[k]).map(k => SHORT[k]).join(' · ') || '선택 없음';
    function selectedId() {
      const eff = effective();
      for (const pr of PRESETS) {
        if (pr.custom || presetOff(pr)) continue;
        const want = { ...allOff(), ...pr.set };
        if (C.every(k => !!eff[k] === !!want[k]) && (!pr.reflow || reflow())) return pr.id;
      }
      const can = (k) => { const d = OPTIONS.find(x => x.key === k); return !(d && (unusable(d) || (d.web && !reflow()))); };   // 이 자료·형식에서 실제로 쓰이는 항목만 비교
      return opts.custom && C.every(k => !!eff[k] === !!(opts.custom[k] && can(k))) ? 'custom' : '';
    }

    function presetRow(pr) {
      const noFig = !!(pr.needs && info[pr.needs] === 0);
      const off = presetOff(pr);
      let psel = null, pw = null;
      const subEl = h('span', { class: 's' });
      const el = h('button', { class: 'pre', type: 'button', role: 'radio', 'aria-checked': 'false', 'aria-disabled': off ? 'true' : null }, h('span', { class: 'rd' }), h('span', { class: 'l' }, pr.label), subEl);
      el.addEventListener('click', () => {
        if (off) return;
        if (pr.custom && (!opts.custom || selectedId() === 'custom')) { openSheet(); return; }
        const set = pr.custom ? opts.custom : pr.set, needReflow = pr.custom ? !!(opts.custom.large || opts.custom.read) : !!pr.reflow;
        applyContent(set);
        Object.assign(opts, needReflow ? { pdf: false, readpdf: false, html: true } : { pdf: true, readpdf: false, html: false });   // 웹 문서가 필요 없으면 기본(원본 PDF)으로
        syncAll();
      });
      updaters.push(() => {
        subEl.textContent = noFig ? pr.none : off ? 'AI 키가 없어 쓸 수 없어요' : pr.custom ? (opts.custom ? customText() + ' · 눌러서 바꾸기' : '원하는 항목을 직접 골라 저장해요') : pr.sub;
        el.setAttribute('aria-checked', String(!off && selectedId() === pr.id));
        if (psel) { psel.value = opts.colorType; pw.hidden = selectedId() !== 'color'; }
      });
      if (pr.id !== 'color' || off) return el;
      psel = h('select', { 'aria-label': '색각 유형' }, h('option', { value: 'deutan' }, '적록'), h('option', { value: 'tritan' }, '청황'));   // 색각 이상을 고른 때만 옆에 나타난다
      psel.addEventListener('change', () => { opts.colorType = psel.value; syncAll(); });
      pw = h('div', { class: 'psel' }, psel);
      return h('div', { class: 'prew' }, el, pw);
    }

    // '직접 설정': 설명까지 보면서 항목을 고르고 저장하면 프리셋처럼 다시 쓸 수 있다
    function openSheet() { sheetBefore = JSON.stringify(opts); sheetOpen = true; render(); }
    async function sheetClose(save) {
      if (save) {
        const picked = Object.fromEntries(C.map(k => [k, !!opts[k]]));
        if (C.some(k => picked[k])) opts.custom = picked; else delete opts.custom;
        try { await adapter.saveOptions(opts); } catch (e) { /* 저장 실패는 무시 */ }
      } else opts = JSON.parse(sheetBefore);
      sheetOpen = false; render();
    }
    function renderSheet() {
      body.replaceChildren(); foot.replaceChildren(); updaters.length = 0; sumEl = null;
      titleEl.textContent = '직접 설정';
      const O = (k) => OPTIONS.find(d => d.key === k);
      body.append(h('div', { class: 'sh3' }, '넣을 항목을 골라 저장해요'),
        h('div', { class: 'opts' }, ...['figures', 'easy', 'terms', 'contrast', 'color', 'braille', 'large', 'read'].map(k => optionRow(O(k)))));
      foot.append(h('button', { class: 'btn', type: 'button', onclick: () => sheetClose(false) }, '취소'), h('button', { class: 'btn pri', type: 'button', onclick: () => sheetClose(true) }, '저장'));
      syncAll();
      const f = root.querySelector('.opts input:not(:disabled)'); f && f.focus();
    }

    // 변환 중 화면은 진행 상황이 바뀔 때마다 다시 만들지 않고 값만 바꾼다 (움직임이 끊기지 않게)
    let work = null;
    // 스핀 점프 8프레임: 쪽이 끝날 때마다 공중에서 조금씩 돌고, 다 끝나면 한 바퀴를 마치고 착지한다. 프레임마다 떠 있는 높이가 다르다.
    const LIFT = [0, -10, -24, -32, -30, -22, -10, 0];
    function setSpin(f) {
      if (!work || !work.spin) return;
      work.frame = f; work.spin.style.backgroundPositionX = (f / 7 * 100) + '%'; work.lift.style.transform = `translateY(${LIFT[f]}px)`;
    }
    function updateWork() {
      const p = progress || { done: 0, total: 0, step: '준비하는 중' };
      const pct = p.total ? Math.round(100 * p.done / p.total) : 0;
      work.step.textContent = p.step; work.cnt.textContent = p.cnt != null ? p.cnt : (p.total ? `${p.done}/${p.total}쪽` : '');
      work.bar.setAttribute('aria-valuenow', String(pct));
      work.course.classList.toggle('ind', !p.total);
      if (work.band) work.band.style.setProperty('--p', pct + '%');
      if (work.rider && p.total) { work.rider.style.left = pct + '%'; work.rider.style.top = (10 + 20 * pct / 100) + 'px'; }
      if (work.fill) work.fill.style.width = pct + '%';
      if (work.meter) work.meter.classList.toggle('ind', !p.total);
      work.note.textContent = p.note || ''; work.note.hidden = !p.note;
    }

    function render() {
      if (state !== 'working') work = null;
      if (state === 'working' && work && work.root.isConnected) { updateWork(); const sr = body.querySelector('.sr'); if (sr && progress) sr.textContent = progress.step; return; }
      titleEl.textContent = baseTitle;
      if (state === 'done' && cmpOpen && result && (result.compare || []).length) {         // 원본과 변환 결과 비교 (글자를 눌렀을 때만, 고른 항목마다 한 장면씩)
        body.replaceChildren(); foot.replaceChildren(); titleEl.textContent = '원본과 비교';
        const side = (img, text, cls) => img ? h('img', { src: img, alt: '' }) : h('div', { class: 't ' + (cls || ''), 'aria-label': text }, text);
        const all = [].concat(result.compare); cmpIdx = Math.min(cmpIdx, all.length - 1);
        const c = all[cmpIdx], lg = c.style === 'large', hc = c.style === 'hc';      // 한 번에 한 장면씩 (스크롤 없이)
        body.append(h('div', { class: 'sh3' }, `${c.label}${c.page ? ` · ${c.page}쪽` : ''}`),
          h('div', { class: 'cmp' },
            h('div', { class: 'c' }, h('small', {}, '원본'), side(c.beforeImg, c.before, lg ? 'sm' : (c.label === '띄어쓰기' ? 'raw' : ''))),
            h('div', { class: 'c af' + (hc ? ' hc' : '') }, h('small', {}, '변환 후'), side(c.afterImg, c.after, lg ? 'lg' : ''))));
        if (all.length > 1) {
          const go = (d) => { cmpIdx = (cmpIdx + d + all.length) % all.length; render(); };
          foot.append(h('button', { class: 'btn', type: 'button', 'aria-label': '이전 항목', onclick: () => go(-1) }, '‹'),
            h('span', { class: 'sum', style: 'flex:none;margin:0 4px;font-variant-numeric:tabular-nums' }, `${cmpIdx + 1} / ${all.length}`),
            h('button', { class: 'btn', type: 'button', 'aria-label': '다음 항목', onclick: () => go(1) }, '›'), h('span', { style: 'flex:1' }));
        }
        foot.append(h('button', { class: 'btn pri', type: 'button', onclick: () => { cmpOpen = false; cmpIdx = 0; render(); } }, '확인'));
        return;
      }
      if (state === 'ready' && sheetOpen) return renderSheet();
      body.replaceChildren(); foot.replaceChildren();
      const cancel = h('button', { class: 'btn', type: 'button', onclick: () => close() }, state === 'done' ? '닫기' : '취소');
      if (state === 'loading') {
        body.append(fileCard(), h('div', { class: 'lab' }, '자료를 확인하고 있어요'), h('div', { class: 'sk' }), h('div', { class: 'sk', style: 'width:82%' }), h('div', { class: 'sk', style: 'width:64%' }));
        foot.append(cancel, h('button', { class: 'btn pri', type: 'button', disabled: '' }, h('span', { html: ICON.down, style: 'display:flex' }), '다운로드'));
      } else if (state === 'ready') {
        updaters.length = 0;
        const fmt = h('select', { class: 'fmt', 'aria-label': '받는 파일 형식', title: '받는 파일 형식' },
          h('option', { value: 'pdf' }, 'PDF'), h('option', { value: 'html' }, '웹 문서'));
        fmt.addEventListener('change', () => { Object.assign(opts, { pdf: fmt.value === 'pdf', html: fmt.value === 'html', readpdf: false }); syncAll(); });
        updaters.push(() => { fmt.value = opts.pdf ? 'pdf' : 'html'; });
        sumEl = h('span', { class: 'sum' }, summary());
        const O = (k) => OPTIONS.find(d => d.key === k);
        const pres = h('div', { class: 'pres', role: 'radiogroup', 'aria-label': '변환 방식' }, ...PRESETS.map(presetRow));
        body.append(fileCard(fmt), pres); syncAll();
        if (info.codeRequired && adapter.setCode) {          // 공개 서버: AI 항목은 접속 코드가 있어야 쓸 수 있다
          const inp = h('input', { type: 'password', id: 'osb-code', autocomplete: 'off', placeholder: '접속 코드' });
          const ok = h('button', { class: 'btn', type: 'button', onclick: async () => { codeTried = true; await adapter.setCode(inp.value); state = 'loading'; render(); load(); } }, '적용');
          inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') ok.click(); });
          body.append(h('div', { class: 'code' }, h('label', { for: 'osb-code' }, 'AI 접속 코드'), h('div', { class: 'cr' }, inp, ok),
            h('small', { class: codeTried ? 'bad' : '' }, codeTried ? '코드가 맞지 않아요. 다시 확인해 주세요.' : 'AI 항목(그림 설명 등)은 코드를 아는 사람만 써요. 다른 항목은 코드 없이 쓸 수 있어요.')));
        }
        if (cfg.settings) {                                  // 확장 프로그램 팝업: 다운로드 대신 기본 방식을 저장한다
          const sv = h('button', { class: 'btn pri', type: 'button', onclick: async () => { opts.profile = true; try { await adapter.saveOptions(opts); sv.textContent = '저장했어요'; if (!inline) setTimeout(close, 700); } catch (e) { sv.textContent = '저장하지 못했어요'; } setTimeout(() => { sv.textContent = '저장'; }, 1400); } }, '저장');
          foot.append(sumEl, sv);
        } else {
          const go = h('button', { class: 'btn pri', type: 'button', onclick: run }, h('span', { html: ICON.down, style: 'display:flex' }), '다운로드');
          foot.append(sumEl, cancel, go);
        }
      } else if (state === 'working') {
        const step = h('span', {}), cnt = h('span', {}), note = h('div', { class: 'hint', style: 'margin-top:10px', hidden: '' });
        let course = null, band = null, rider = null, meter = null, fill = null, bar, spin = null;
        if (cfg.mascot) {                                     // 눈 언덕을 보드를 타고 내려가며 진행을 보여 준다
          band = h('div', { class: 'band' });
          rider = h('div', { class: 'rider', style: 'left:0%;top:10px' }, h('div', { class: 'lift' }, h('div', { class: 'bob' }, h('img', { src: cfg.mascot.run || cfg.mascot.ride, alt: '', class: cfg.mascot.run ? '' : 'flip' }), h('i', { class: 'pf' }), h('i', { class: 'pf' }), h('i', { class: 'pf' }), spin = cfg.mascot.spin ? h('div', { class: 'spin', style: `background-image:url(${cfg.mascot.spin})` }) : null)));
          course = h('div', { class: 'course', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': '0', 'aria-label': '변환 진행' }, band, rider);
          bar = course;
        } else {
          fill = h('i', { style: 'width:0%' });
          meter = h('div', { class: 'meter', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': '0' }, fill);
          course = h('div', {}, meter); bar = meter;
        }
        const root_ = h('div', { class: 'prog' }, h('div', { class: 'row' }, step, cnt), course, note);
        body.append(fileCard(), root_);
        work = { root: root_, step, cnt, note, bar, course, band, rider, meter, fill, spin, lift: rider && rider.querySelector('.lift'), frame: -1 };
        updateWork();
        foot.append(cancel);
      } else if (state === 'done') {
        const cmp = result && [].concat(result.compare || []).length, sum = (result && result.summary) || [];
        const cmpEl = cmp ? h('button', { class: 'lnk', type: 'button', onclick: () => { cmpOpen = true; cmpIdx = 0; render(); } }, '원본과 비교해 보기') : null;
        body.append(h('div', { class: 'state ok' }, cfg.mascot ? h('img', { class: 'm', src: cfg.mascot.thumb, alt: '', style: null }) : h('span', { html: ICON.check, style: 'display:flex' }), h('b', {}, result && result.batch ? (result.batch.failed.length ? `${files.length}개 중 ${result.batch.ok}개를 다운로드했어요` : `${result.batch.ok}개를 다운로드했어요`) : '다운로드했어요'),
          sum.length ? h('ul', { class: 'sum' }, sum.map(t => h('li', {}, t))) : null, cmpEl,
          h('ul', { class: 'files' }, files.map(f => h('li', {}, f.name)))));
        foot.append(cancel);
      } else if (state === 'error') {
        body.append(h('div', { class: 'state bad' }, cfg.mascot ? h('img', { class: 'm', src: cfg.mascot.fall, alt: '' }) : h('span', { html: ICON.alert, style: 'display:flex' }), h('b', {}, '변환하지 못했어요'), h('p', {}, msg || '잠시 뒤에 다시 시도해 주세요.')));
        foot.append(cancel, job ? h('button', { class: 'btn pri', type: 'button', onclick: () => { state = 'ready'; render(); } }, '다시 시도') : null);
      }
      body.append(h('div', { class: 'sr', role: 'status', 'aria-live': 'polite' }, state === 'working' ? (progress ? progress.step : '') : state === 'done' ? '다운로드했어요' : state === 'error' ? msg : ''));
    }

    async function run() {
      state = 'working'; progress = { done: 0, total: 0, step: '변환을 시작하는 중' }; render();
      try { await adapter.saveOptions(opts); } catch (e) { /* 설정 저장 실패는 무시 */ }
      try {
        task = await adapter.make(job, effective());
        let busy = false, fails = 0;                       // 서버가 느려도 확인이 겹치지 않게 하고(같은 파일이 두 번 받아지지 않게), 한두 번 통신이 끊겨도 포기하지 않는다
        timer = setInterval(async () => {
          if (busy || closed) return;
          busy = true;
          try {
            const st = await adapter.status(task);
            fails = 0;
            if (closed) return;
            if (st.status === 'running') { progress = st; render(); }
            else if (st.status === 'done') {
              clearInterval(timer); progress = { ...st, step: '내려받는 중', done: st.total };
              render(); files = st.files; result = st; await Promise.all([adapter.save(files), trick()]); if (closed) return; state = 'done'; render();
            } else { clearInterval(timer); state = 'error'; msg = st.error || (st.status === 'cancelled' ? '취소했어요' : ''); render(); }
          } catch (e) {
            if (++fails >= 4) { clearInterval(timer); state = 'error'; msg = e.message; render(); }
          } finally { busy = false; }
        }, 800);
      } catch (e) { state = 'error'; msg = e.message; render(); }
    }

    // 여러 자료를 차례로 변환해 받는다 (주차 전체·강좌 전체). 한 파일이 실패해도 나머지는 계속한다.
    // 끝나기 직전에 결승선에서 한 바퀴 돌고 착지한다 (움직임 줄이기 설정이면 생략)
    async function trick() {
      if (!work || !work.rider || (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
      const sl = (ms) => new Promise(x => setTimeout(x, ms));
      work.course.classList.remove('ind'); work.band && work.band.style.setProperty('--p', '100%');
      work.rider.style.left = '94%'; work.rider.style.top = '30px';
      await sl(work.spin ? 600 : 850); if (closed || !work) return;
      if (work.spin) {                                                      // 비탈 끝에서 한 번, 빠르게 한 바퀴를 돌고 착지
        work.rider.classList.add('air');
        for (let f = 0; f <= 7 && !closed && work; f++) { setSpin(f); await sl(f === 7 ? 280 : 95); }
        return;
      }
      work.rider.classList.add('trick'); await sl(950);                      // 스핀 에셋이 없으면 납작하게 도는 연출
    }

    async function runBatch() {
      const items = cfg.batch.items, N = items.length, okNames = [], failed = [];
      state = 'working'; render();
      const how = summary();
      for (let i = 0; i < N && !closed; i++) {
        const it = items[i], head = `${i + 1}/${N} · ${it.label}`;
        progress = { done: i * 100, total: N * 100, step: head, cnt: `${i + 1}/${N}개`, note: `방식: ${how}` }; render();
        try {
          const r = await it.adapter.prepare({ light: true }); if (closed) return;
          if (r.info && r.info.codeRequired) throw new Error('AI 접속 코드가 필요해요');
          task = await it.adapter.make(r.job, effective());
          for (;;) {
            await new Promise(x => setTimeout(x, 800)); if (closed) return;
            const st = await it.adapter.status(task);
            if (st.status === 'running') { progress = { done: i * 100 + (st.total ? Math.round(100 * st.done / st.total) : 0), total: N * 100, step: head, cnt: `${i + 1}/${N}개`, note: `방식: ${how}` }; render(); continue; }
            if (st.status === 'done') { await it.adapter.save(st.files); okNames.push(...st.files.map(f => f.name)); break; }
            throw new Error(st.error || (st.status === 'cancelled' ? '취소했어요' : '변환하지 못했어요'));
          }
        } catch (e) { if (closed) return; failed.push({ label: it.label, msg: e.message }); }
      }
      if (closed) return;
      if (okNames.length) { progress = { done: N * 100, total: N * 100, step: '내려받는 중', cnt: `${N}/${N}개`, note: `방식: ${how}` }; render(); await trick(); if (closed) return; }
      files = okNames.map(n => ({ name: n }));
      result = { summary: failed.length ? failed.map(f => `${f.label}: ${f.msg}`).slice(0, 3) : [`방식: ${how}`], compare: [], batch: { ok: N - failed.length, failed } };
      state = okNames.length ? 'done' : 'error'; msg = failed.length ? `${failed[0].label}: ${failed[0].msg}` : ''; render();
    }

    async function load() {
      if (cfg.batch) { runBatch(); return; }
      if (cfg.settings) { job = 'settings'; info = { pages: 0, figures: 1, colorFigures: 1, ai: cfg.ai !== false, codeRequired: false }; state = 'ready'; render(); return; }
      const auto = !!(cfg.auto && opts.profile);          // 처음에 정해 둔 방식이 있으면 고르는 단계 없이 바로 변환한다
      if (auto) { state = 'working'; progress = { done: 0, total: 0, step: '자료를 살펴보는 중' }; render(); }
      try {
        let r = await adapter.prepare(auto ? { light: true } : undefined); if (closed) return;
        job = r.job; info = r.info;
        if (auto && !info.codeRequired) { run(); return; }
        if (auto) { r = await adapter.prepare(); if (closed) return; job = r.job; info = r.info; }      // 접속 코드가 필요하면 고르는 화면으로
        state = 'ready'; render();
        if (!inline && !codeTried) { win.focus(); }
      } catch (e) { if (!closed) { state = 'error'; msg = e.message; job = null; render(); } }
    }
    render();
    (async () => {
      const saved = await adapter.loadOptions().catch(() => null); if (saved) opts = normalize({ ...DEFAULTS, ...saved });
      load();
    })();
    return { close };
  }

  // 홈 화면 목업용: 실제 창과 똑같은 모양을 서버 없이 보여 준다.
  function preview(container, sample) {
    const adapter = {
      name: sample?.name || '2주차 학습자료', sub: sample?.sub || '경영정보시스템 (004)',
      prepare: async () => ({ job: 'demo', info: sample?.info || { pages: 15, figures: 5, colorFigures: 2, scanned: 0, ai: true } }),
      loadOptions: async () => null, saveOptions: async () => {}, make: async () => 'x', status: async () => ({ status: 'running' }), save: async () => {}
    };
    return open({ adapter, container });
  }

  window.OSBPanel = { open, preview, DEFAULTS, OPTIONS, SHORT };
})();
