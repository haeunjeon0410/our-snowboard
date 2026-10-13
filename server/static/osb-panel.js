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
.win{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(440px,calc(100vw - 24px));max-height:calc(100vh - 48px);display:flex;flex-direction:column;background:#fbfcfd;border-radius:12px;box-shadow:0 0 0 1px rgba(20,35,60,.14),0 28px 70px rgba(20,35,60,.32);overflow:hidden;color:#1c2230;font:400 14px/1.5 ${FONT};letter-spacing:-.01em;animation:pop .2s cubic-bezier(.2,.8,.2,1)}
:host(.inline) .win{position:relative;left:auto;top:auto;transform:none;width:100%;max-height:none;animation:none}
@keyframes fade{from{opacity:0}}@keyframes pop{from{opacity:0;transform:translate(-50%,calc(-50% + 8px)) scale(.985)}}
.bar{flex:none;height:42px;display:flex;align-items:center;justify-content:center;position:relative;background:#eceff4;border-bottom:1px solid rgba(20,35,60,.1);cursor:grab;user-select:none;-webkit-user-select:none;touch-action:none}
.bar.drag{cursor:grabbing}
.bar .t{font-size:13px;font-weight:600;color:#3a475d}
.x{all:unset;position:absolute;right:8px;top:8px;width:26px;height:26px;border-radius:7px;display:flex;align-items:center;justify-content:center;color:#5a6b88;cursor:pointer}
.x:hover{background:rgba(58,71,93,.13);color:#26344d}.x:focus-visible{outline:2px solid rgba(58,71,93,.55)}
.body{overflow:auto;padding:16px 18px 6px;min-height:120px}
.file{display:flex;gap:11px;align-items:center;padding:10px 12px;background:#eef1f5;border-radius:9px}
.file svg{width:22px;height:22px;color:#5a6b88;flex:none}
.file div{min-width:0}
.file b{display:block;font-size:14px;font-weight:600;line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.file small{display:block;font-size:12.5px;color:#6b7689;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lab{margin:16px 0 4px;font-size:12.5px;font-weight:600;color:#6b7689}
.ohead{all:unset;box-sizing:border-box;width:100%;margin-top:12px;padding:9px 4px 9px 2px;display:flex;align-items:center;gap:10px;cursor:pointer;border-radius:8px}
.ohead:hover{background:#f0f3f7}.ohead:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:1px}
.ohead .ol{flex:none;font-size:13px;font-weight:650;color:#3a475d}
.ohead .os{flex:1;min-width:0;text-align:right;font-size:12.5px;color:#6b7689;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ohead .oc{flex:none;width:12px;height:12px;color:#6b7689;transition:transform .16s}
.ohead[aria-expanded=true] .oc{transform:rotate(180deg)}
.code{margin:12px 0 4px;padding:10px 12px;background:#eef1f5;border-radius:9px}
.code label{display:block;font-size:12.5px;font-weight:600;color:#3a475d;margin-bottom:6px}
.code .cr{display:flex;gap:6px}
.code input{flex:1;min-width:0;height:32px;padding:0 10px;border:1px solid #c4ccda;border-radius:7px;background:#fff;font:inherit;font-size:13px;color:#1c2230}
.code input:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:1px}
.code small{display:block;margin-top:6px;font-size:12px;color:#6b7689}
.code small.bad{color:#97662a}
.opts{border-top:1px solid rgba(20,35,60,.08)}
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
.foot{flex:none;display:flex;justify-content:flex-end;align-items:center;gap:6px;padding:12px 18px 14px;border-top:1px solid rgba(20,35,60,.08)}
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
.prog{padding:20px 4px 14px}
.prog .row{display:flex;justify-content:space-between;gap:10px;font-size:13px;color:#4a5262;margin-bottom:8px}
.prog .row span:last-child{color:#6b7689;font-variant-numeric:tabular-nums}
.meter{height:6px;border-radius:99px;background:#e4e9f1;overflow:hidden}
.meter i{display:block;height:100%;width:0;background:#4a6794;border-radius:99px;transition:width .45s ease}
.meter.ind i{width:38%;animation:slide 1.1s ease-in-out infinite}
@keyframes slide{0%{margin-left:-38%}100%{margin-left:100%}}
.sk{height:14px;border-radius:6px;background:#e8ecf2;margin:10px 0}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
`;

  // 고를 수 있는 항목. info(자료 요약)에 따라 해당 없는 것은 숨기거나 끈다.
  const DEFAULTS = { large: true, contrast: false, figures: true, easy: false, terms: false, color: false, colorType: 'deutan', pdf: true, html: false, braille: false };
  const OPTIONS = [
    // 받는 형식
    { key: 'pdf', group: '받는 형식', label: '원본 PDF', sub: '쪽 번호·배치 그대로, 접근성만 더해요' },
    { key: 'html', group: '받는 형식', label: '읽기용 웹 문서', sub: '큰 글씨·고대비·소리 읽기 (원본과 배치가 달라요)' },
    { key: 'braille', group: '받는 형식', label: '점자 파일', sub: '점자 프린터용 .brf 파일' },
    // 넣을 것 (PDF·웹 문서 모두에 들어간다)
    { key: 'figures', group: '넣을 것', label: '그림·도식을 글로 설명', sub: '그림이 무엇을 보여 주는지 풀어 써요', ai: true, needs: 'figures', none: '이 자료에는 그림이 없어요' },
    { key: 'color', group: '넣을 것', label: '색 구분 돕기', sub: n => `색이 칠해진 그림 ${n}개에 무늬를 넣어요`, needs: 'colorFigures', hideIfNone: true, select: true },
    // 읽기용 웹 문서에만 적용
    { key: 'large', group: '웹 문서 설정', web: true, label: '큰 글씨로 읽기', sub: '글씨를 키우고 줄 간격을 넓혀요' },
    { key: 'contrast', group: '웹 문서 설정', web: true, label: '고대비', sub: '검정 바탕에 밝은 글씨' },
    { key: 'easy', group: '웹 문서 설정', web: true, label: '쉬운 한국어로', sub: '어려운 문장을 짧고 쉽게 바꿔요', ai: true },
    { key: 'terms', group: '웹 문서 설정', web: true, label: '영어 용어 함께', sub: '전문 용어 옆에 영어를 붙여요', ai: true }
  ];

  const SHORT = { large: '큰 글씨', contrast: '고대비', figures: '그림 설명', easy: '쉬운 한국어', terms: '영어 용어', color: '색 구분', pdf: 'PDF', html: '웹 문서', braille: '점자' };

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
    const win = h('div', { class: 'win', role: 'dialog', 'aria-modal': inline ? null : 'true', 'aria-label': '맞춤 변환' });
    if (scrim) root.append(scrim);
    root.append(win);
    (cfg.container || document.body).append(host);

    let codeTried = false, state = 'loading', optOpen = true, opts = { ...DEFAULTS }, job = null, info = null, task = null, msg = '', progress = null, files = [], timer = null, closed = false;

    const bar = h('div', { class: 'bar' }, h('span', { class: 't' }, '맞춤 변환'),
      h('button', { class: 'x', type: 'button', 'aria-label': '닫기', html: ICON.x, onclick: () => close() }));
    const body = h('div', { class: 'body' });
    const foot = h('div', { class: 'foot' });
    win.append(bar, body, foot);

    function close() {
      if (closed) return;
      closed = true; clearInterval(timer);
      if (task && state === 'working') adapter.cancel && adapter.cancel(task);
      host.remove(); document.removeEventListener('keydown', onKey, true);
      try { opener && opener.focus && opener.focus(); } catch (e) { /* 무시 */ }
      cfg.onClose && cfg.onClose();
    }
    function onKey(e) {
      if (e.key === 'Escape') { e.stopPropagation(); close(); return; }
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
      win.style.transform = 'none'; win.style.left = r.left + 'px'; win.style.top = r.top + 'px'; bar.classList.add('drag');
      bar.setPointerCapture(e.pointerId);
      const move = (ev) => { win.style.left = Math.min(innerWidth - 80, Math.max(-r.width + 80, ev.clientX - dx)) + 'px'; win.style.top = Math.min(innerHeight - 42, Math.max(0, ev.clientY - dy)) + 'px'; };
      const up = () => { bar.classList.remove('drag'); bar.removeEventListener('pointermove', move); bar.removeEventListener('pointerup', up); };
      bar.addEventListener('pointermove', move); bar.addEventListener('pointerup', up);
    });

    const fileCard = () => h('div', { class: 'file' }, h('span', { html: ICON.file, style: 'display:flex' }),
      h('div', {}, h('b', {}, adapter.name || '자료'), h('small', {}, [adapter.sub, info ? `${info.pages}쪽` + (info.scanned ? ' · 스캔본은 글자를 자동으로 읽어요' : '') : ''].filter(Boolean).join(' · ') || ' ')));

    // 이 자료에는 쓸 수 없는 항목(그림이 없음, AI 키 없음). 저장된 내 선택(opts)은 건드리지 않고 보내는 값에서만 뺀다.
    const unusable = (def) => !!(info && ((def.needs && !info[def.needs]) || (def.ai && !info.ai))) || !!(def.web && !opts.html);
    const effective = () => { const o = { ...opts }; for (const d of OPTIONS) if (unusable(d)) o[d.key] = false; if (!(o.pdf || o.html || o.braille)) o.pdf = true; return o; };

    function optionRow(def) {
      const none = def.needs && !info[def.needs];
      const noAI = def.ai && info && !info.ai;
      const off = unusable(def);
      if (def.hideIfNone && none) return null;
      const input = h('input', { type: 'checkbox', disabled: off || null });
      input.checked = !off && !!opts[def.key];
      input.addEventListener('change', () => { opts[def.key] = input.checked; if (def.select) sel.disabled = !input.checked; if (def.key === 'html') { render(); return; } refreshHint(); });
      let sel = null;
      if (def.select) {
        sel = h('select', { 'aria-label': '색각 유형' },
          h('option', { value: 'deutan' }, '적록 색약·색맹'), h('option', { value: 'tritan' }, '청황 색약·색맹'));
        sel.value = opts.colorType; sel.disabled = !opts[def.key] || off;
        sel.addEventListener('change', () => { opts.colorType = sel.value; });
      }
      const sub = none ? def.none : (def.web && !opts.html) ? '‘읽기용 웹 문서’를 고르면 쓸 수 있어요' : noAI ? 'AI 키가 없어 쓸 수 없어요' : (typeof def.sub === 'function' ? def.sub(info[def.needs]) : def.sub);
      return h('label', { class: 'opt' + (off ? ' off' : '') }, input, h('span', { class: 'l' }, def.label), def.ai ? h('span', { class: 'tag' }, 'AI') : h('span'),
        h('span', { class: 's' }, sub), sel ? h('span', { class: 'sel' }, sel) : null);
    }

    const summary = () => {
      const eff = effective();
      const on = OPTIONS.filter(d => (!cfg.only || cfg.only.includes(d.key)) && eff[d.key]).map(d => SHORT[d.key]);
      return on.length ? on.join(' · ') : '선택 없음';
    };
    let sumEl = null;
    const refreshHint = () => { if (sumEl) sumEl.textContent = summary(); };

    function render() {
      body.replaceChildren(); foot.replaceChildren();
      const cancel = h('button', { class: 'btn', type: 'button', onclick: () => close() }, state === 'done' ? '닫기' : '취소');
      if (state === 'loading') {
        body.append(fileCard(), h('div', { class: 'lab' }, '자료를 확인하고 있어요'), h('div', { class: 'sk' }), h('div', { class: 'sk', style: 'width:82%' }), h('div', { class: 'sk', style: 'width:64%' }));
        foot.append(cancel, h('button', { class: 'btn pri', type: 'button', disabled: '' }, h('span', { html: ICON.down, style: 'display:flex' }), '다운로드'));
      } else if (state === 'ready') {
        const defs = cfg.only ? OPTIONS.filter(d => cfg.only.includes(d.key)) : OPTIONS;
        sumEl = h('span', { class: 'os' }, summary());
        const head = h('button', { class: 'ohead', type: 'button', 'aria-expanded': String(optOpen) }, h('span', { class: 'ol' }, '옵션'), sumEl,
          h('span', { class: 'oc', html: '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>' }));
        const rows = []; let lastGroup = '';
        for (const d of defs) { const row = optionRow(d); if (!row) continue; if (d.group && d.group !== lastGroup) { lastGroup = d.group; rows.push(h('div', { class: 'lab', style: rows.length ? 'margin:14px 0 2px' : 'margin:8px 0 2px' }, d.group)); } rows.push(row); }
        const list = h('div', { class: 'opts', id: 'osb-opts' }, ...rows);
        head.setAttribute('aria-controls', 'osb-opts');
        list.hidden = !optOpen;
        head.addEventListener('click', () => { optOpen = !optOpen; head.setAttribute('aria-expanded', String(optOpen)); list.hidden = !optOpen; });
        body.append(fileCard(), head, list); refreshHint();
        if (info.codeRequired && adapter.setCode) {          // 공개 서버: AI 항목은 접속 코드가 있어야 쓸 수 있다
          const inp = h('input', { type: 'password', id: 'osb-code', autocomplete: 'off', placeholder: '접속 코드' });
          const ok = h('button', { class: 'btn', type: 'button', onclick: async () => { codeTried = true; await adapter.setCode(inp.value); state = 'loading'; render(); load(); } }, '적용');
          inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') ok.click(); });
          body.append(h('div', { class: 'code' }, h('label', { for: 'osb-code' }, 'AI 접속 코드'), h('div', { class: 'cr' }, inp, ok),
            h('small', { class: codeTried ? 'bad' : '' }, codeTried ? '코드가 맞지 않아요. 다시 확인해 주세요.' : 'AI 항목(그림 설명 등)은 코드를 아는 사람만 써요. 다른 항목은 코드 없이 쓸 수 있어요.')));
        }
        const go = h('button', { class: 'btn pri', type: 'button', onclick: run }, h('span', { html: ICON.down, style: 'display:flex' }), '다운로드');
        foot.append(cancel, go);
      } else if (state === 'working') {
        const p = progress || { done: 0, total: 0, step: '준비하는 중' };
        const pct = p.total ? Math.round(100 * p.done / p.total) : 0;
        body.append(fileCard(), h('div', { class: 'prog' }, h('div', { class: 'row' }, h('span', {}, p.step), h('span', {}, p.total ? `${p.done}/${p.total}쪽` : '')),
          h('div', { class: 'meter' + (p.total ? '' : ' ind'), role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(pct) }, h('i', { style: `width:${pct}%` })),
          p.note ? h('div', { class: 'hint', style: 'margin-top:10px' }, p.note) : null));
        foot.append(cancel);
      } else if (state === 'done') {
        body.append(h('div', { class: 'state ok' }, h('span', { html: ICON.check, style: 'display:flex' }), h('b', {}, '다운로드했어요'),
          h('p', {}, '브라우저의 다운로드 폴더에 저장됐어요.'), h('ul', {}, files.map(f => h('li', {}, f.name)))));
        foot.append(cancel);
      } else if (state === 'error') {
        body.append(h('div', { class: 'state bad' }, h('span', { html: ICON.alert, style: 'display:flex' }), h('b', {}, '변환하지 못했어요'), h('p', {}, msg || '잠시 뒤에 다시 시도해 주세요.')));
        foot.append(cancel, job ? h('button', { class: 'btn pri', type: 'button', onclick: () => { state = 'ready'; render(); } }, '다시 시도') : null);
      }
      body.append(h('div', { class: 'sr', role: 'status', 'aria-live': 'polite' }, state === 'working' ? (progress ? progress.step : '') : state === 'done' ? '다운로드했어요' : state === 'error' ? msg : ''));
    }

    async function run() {
      state = 'working'; progress = { done: 0, total: 0, step: '변환을 시작하는 중' }; render();
      try { await adapter.saveOptions(opts); } catch (e) { /* 설정 저장 실패는 무시 */ }
      try {
        task = await adapter.make(job, effective());
        timer = setInterval(async () => {
          try {
            const st = await adapter.status(task);
            if (closed) return;
            if (st.status === 'running') { progress = st; render(); }
            else if (st.status === 'done') {
              clearInterval(timer); progress = { ...st, step: '내려받는 중', done: st.total };
              render(); files = st.files; await adapter.save(files); state = 'done'; render();
            } else { clearInterval(timer); state = 'error'; msg = st.error || (st.status === 'cancelled' ? '취소했어요' : ''); render(); }
          } catch (e) { clearInterval(timer); state = 'error'; msg = e.message; render(); }
        }, 800);
      } catch (e) { state = 'error'; msg = e.message; render(); }
    }

    async function load() {
      try {
        const r = await adapter.prepare(); if (closed) return;
        job = r.job; info = r.info; state = 'ready'; render();
        if (!inline && !codeTried) { const first = (optOpen && root.querySelector('.opt input:not(:disabled)')) || root.querySelector('.btn.pri'); first && first.focus(); }
      } catch (e) { if (!closed) { state = 'error'; msg = e.message; job = null; render(); } }
    }
    render();
    (async () => {
      const saved = await adapter.loadOptions().catch(() => null); if (saved) opts = { ...DEFAULTS, ...saved };
      optOpen = cfg.expanded != null ? !!cfg.expanded : !saved;       // 저장된 설정이 있으면 접어 두고 요약만 보여 준다
      load();
    })();
    return { close };
  }

  // 홈 화면 목업용: 실제 창과 똑같은 모양을 서버 없이 보여 준다.
  function preview(container, sample) {
    const adapter = {
      name: sample?.name || '2주차 학습자료', sub: sample?.sub || '경영정보시스템 (004)',
      prepare: async () => ({ job: 'demo', info: sample?.info || { pages: 15, figures: 5, colorFigures: 2, scanned: 0, ai: true } }),
      loadOptions: async () => ({ ...DEFAULTS, color: true }), saveOptions: async () => {}, make: async () => 'x', status: async () => ({ status: 'running' }), save: async () => {}
    };
    return open({ adapter, container, expanded: true, only: container ? ['pdf', 'figures', 'braille'] : null });
  }

  window.OSBPanel = { open, preview, DEFAULTS, OPTIONS, SHORT };
})();
