// Our Snowboard — 숙명여대 스노우보드 화면에서 PDF 자료 옆에 "다운로드" 버튼을 붙인다.
// 누르면 화면 위에 작은 창(osb-panel.js)이 떠서 변환 방식을 고르고 다운로드한다. 학교 서버나 사이트 내용은 바꾸지 않는다.
(() => {
  const FILE_LINK = [
    'a[href*="/mod/ubfile/view.php"]',                 // 강좌 자료 파일 (스노우보드의 기본 자료 형태)
    'a[href*="/mod/resource/view.php"]',
    'a[href*="/pluginfile.php/"][href*=".pdf"]',       // 게시판·과제 등에 붙은 PDF 첨부
    'a[href*="/mock/file/"]'                           // 개발용 모의 화면
  ].join(',');
  const DONE = 'osbDone';
  // 버튼 아이콘: Phosphor 'magic-wand' (MIT, https://phosphoricons.com) — 현재 글자색을 따른다
  const ICON = '<svg viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="M48 64a8 8 0 0 1 8-8h16V40a8 8 0 0 1 16 0v16h16a8 8 0 0 1 0 16H88v16a8 8 0 0 1-16 0V72H56a8 8 0 0 1-8-8m136 128h-8v-8a8 8 0 0 0-16 0v8h-8a8 8 0 0 0 0 16h8v8a8 8 0 0 0 16 0v-8h8a8 8 0 0 0 0-16m56-48h-16v-16a8 8 0 0 0-16 0v16h-16a8 8 0 0 0 0 16h16v16a8 8 0 0 0 16 0v-16h16a8 8 0 0 0 0-16m-20.69-64L80 219.31a16 16 0 0 1-22.62 0l-20.7-20.68a16 16 0 0 1 0-22.63L176 36.69a16 16 0 0 1 22.63 0l20.68 20.68a16 16 0 0 1 0 22.63m-54.63 32L144 91.31l-96 96L68.68 208ZM208 68.69L187.31 48l-32 32L176 100.69Z"/></svg>';
  // PDF가 아닌 게 분명한 첨부(PPT·워드·한글·압축 등)에는 버튼을 붙이지 않는다. 이름만으로 알 수 없으면 붙이고, 누를 때 확인한다.
  const NOT_PDF = /\.(docx?|xlsx?|hwpx?|zip|mp4|mp3|png|jpe?g)(?:[?#\s]|$)/i;
  // 스노우보드는 파일 앞 아이콘 주소에 종류를 담는다 (…/f/pdf-24, …/f/powerpoint-24). 종류를 알 수 있으면 PDF에만 붙이고, 모르면 이름으로 가린다.
  const iconKind = (a) => { const im = a.querySelector('img.activityicon, img'); const m = im && /\/f\/([a-z0-9]+)-\d+/i.exec(im.getAttribute('src') || ''); return m ? m[1].toLowerCase() : ''; };
  const eligible = (a) => { const k = iconKind(a); if (k) return k === 'pdf' || k === 'powerpoint'; return !NOT_PDF.test(a.textContent || '') && !NOT_PDF.test(a.getAttribute('href') || ''); };

  // 과목 이름: 강좌 화면의 제목 (예: "경영정보시스템 (004)"), 다른 화면에서는 위쪽 경로 표시에서 찾는다.
  function courseName() {
    if (/\/course\/view\.php|^\/mock/.test(location.pathname)) {
      const t = (document.title || '').replace(/\s*[-|·:]\s*(SnowBoard|스노우보드).*$/i, '').trim();
      if (t && !/^snowboard$/i.test(t)) return t.slice(0, 60);
    }
    const bc = document.querySelector('.breadcrumb a[href*="/course/view.php"], nav[aria-label] a[href*="/course/view.php"]');
    return bc ? bc.textContent.replace(/\s+/g, ' ').trim().slice(0, 60) : '';
  }
  const cleanLabel = (t) => (t || '').replace(/\s+/g, ' ').replace(/\s*파일$/, '').trim().slice(0, 60) || '자료';

  // 패널이 쓰는 연결: 백그라운드(서버와 이야기하는 쪽)에 메시지를 보낸다
  const send = (msg) => chrome.runtime.sendMessage(msg).then((r) => { if (!r || r.ok === false) throw new Error((r && r.error) || '요청에 실패했어요'); return r; });
  const store = (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.sync) ? chrome.storage.sync : null;
  function adapterFor(url, name, course) {
    return {
      name, sub: course,
      prepare: (o) => send({ type: 'prepare', url, name, course, light: !!(o && o.light) }),
      make: (job, options) => send({ type: 'make', job, options }).then((r) => r.task),
      status: (id) => send({ type: 'task', id }).then((r) => r.status),
      cancel: (id) => send({ type: 'cancel', id }).catch(() => {}),
      setCode: (code) => send({ type: 'setcode', code }).catch(() => {}),
      save: (files) => send({ type: 'download', files }),
      loadScale: async () => { try { return store ? ((await store.get('uiScale')).uiScale || 1) : 1; } catch (e) { return 1; } },
      saveScale: (s) => { try { if (store) store.set({ uiScale: s }); } catch (e) { /* 무시 */ } },
      loadOptions: async () => { try { return store ? ((await store.get('opts')).opts || null) : null; } catch (e) { return null; } },
      saveOptions: async (o) => { try { if (store) await store.set({ opts: o }); } catch (e) { /* 무시 */ } }
    };
  }

  // 확장 프로그램을 새로고침·업데이트하면 이미 열려 있던 스노우보드 탭의 옛 스크립트는 연결이 끊긴다. 오류 대신 새로고침을 안내한다.
  const alive = () => { try { return !!(chrome.runtime && (chrome.runtime.id || typeof chrome.runtime.getURL !== 'function')); } catch (e) { return false; } };      // (개발용 가짜 chrome에는 getURL이 없다)
  function staleNotice() {
    if (document.getElementById('osb-stale')) return;
    const h = document.createElement('div'); h.id = 'osb-stale';
    h.style.cssText = 'all:initial;position:fixed;z-index:2147483000;left:50%;bottom:28px;transform:translateX(-50%)';
    const r = h.attachShadow({ mode: 'open' });
    r.innerHTML = `<style>*{box-sizing:border-box;font-family:'Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif}
.t{display:flex;align-items:center;gap:12px;background:#fbfcfd;border-radius:10px;box-shadow:0 0 0 1px rgba(20,35,60,.14),0 14px 40px rgba(20,35,60,.24);padding:10px 12px 10px 16px;font-size:13px;color:#1c2230}
button{all:unset;cursor:pointer;height:28px;padding:0 12px;border-radius:8px;background:#3f5a86;color:#fff;font:600 12.5px/28px 'Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif}
button:hover{background:#34496f}button.x{background:none;color:#6b7689;padding:0 8px}</style>
<div class="t"><span>확장 프로그램이 새로 설정되었어요. 페이지를 새로고침해 주세요.</span><button id="r" type="button">새로고침</button><button class="x" id="c" type="button">닫기</button></div>`;
    r.getElementById('r').onclick = () => location.reload();
    r.getElementById('c').onclick = () => h.remove();
    document.body.append(h);
  }

  // 변환 중·완료·오류 화면에 쓰는 마스코트 (달리기·엄지 척·넘어짐)
  const mascotUrls = () => {
    const u = (n) => (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL) ? chrome.runtime.getURL(`icons/mascot-${n}.png`) : `/static/img/mascot-${n}.png`;
    return { ride: u('ride'), run: u('run'), spin: u('spin'), thumb: u('thumb'), fall: u('fall') };
  };

  function addButton(a) {
    if (a.dataset[DONE]) return;
    a.dataset[DONE] = '1';
    if (!eligible(a)) return;
    const label = cleanLabel(a.textContent);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'osb-btn';
    btn.innerHTML = ICON + '<span>다운로드</span>';
    btn.setAttribute('aria-label', `${label} 파일을 내 방식으로 변환해 다운로드`);
    btn.title = '내게 맞는 형태(큰 글씨·그림 설명·점자 등)로 바꿔서 다운로드해요';
    a.insertAdjacentElement('afterend', btn);
    btn.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      if (!alive()) { staleNotice(); return; }
      if (!window.OSBPanel) return;
      window.OSBPanel.open({ adapter: adapterFor(a.href, label, courseName()), auto: true, mascot: mascotUrls() });
    });
  }

  // 강좌 화면 위쪽 안내 띠: 이 강좌에서 바꿔 받을 수 있는 PDF가 몇 개인지
  function addBanner() {
    if (document.getElementById('osb-banner') || !/\/course\/view\.php|\/mock/.test(location.pathname)) return;
    const n = [...document.querySelectorAll(FILE_LINK)].filter(eligible).length;
    if (!n) return;
    const host = document.querySelector('#region-main, [role="main"], .course-content') || document.body.firstElementChild;
    if (!host) return;
    const bar = document.createElement('div');
    bar.id = 'osb-banner';
    bar.className = 'osb-banner';
    const logo = (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.getURL) ? chrome.runtime.getURL('icons/icon48.png') : '/static/img/app-icon-48.png';
    bar.innerHTML = '<img class="osb-logo" alt="" src="' + logo + '"><div class="osb-bt"></div>';
    bar.querySelector('.osb-bt').textContent = `자료 ${n}개를 내 방식으로 바꿔 받을 수 있어요`;
    host.insertAdjacentElement('afterbegin', bar);
  }


  // 떠 있는 마스코트: 처음에는 보드를 타고 들어와 방식을 묻고, 그 뒤에는 작은 버튼으로 남아 언제든 방식을 바꿀 수 있다.
  // 자세한 설정은 확장 프로그램 팝업에서 한다.
  const PROFILE = [      // 패널의 프리셋과 같은 이름·구성. 하나만 고르면 끝나게 하고, 하나씩 고르는 것은 세부 설정에서 한다.
    { id: 'low', label: '저시력', set: { large: true, contrast: true, read: true } },
    { id: 'read', label: '그림 읽기·점자', set: { figures: true, braille: true } },
    { id: 'color', label: '색각 이상', set: { color: true } },
    { id: 'easy', label: '교환학생', set: { easy: true, terms: true } }
  ];
  const FONT = "'OSB Pretendard','Pretendard Variable',Pretendard,'Malgun Gothic',sans-serif";
  const FL_CSS = `*{box-sizing:border-box;font-family:${FONT}}
.wrap{position:fixed;right:8px;bottom:86px;display:flex;flex-direction:column;align-items:flex-end}
.wrap [hidden]{display:none!important}
.bub{position:relative;width:228px;margin:0 6px -2px 0;background:#fbfcfd;border-radius:12px;box-shadow:0 0 0 1px rgba(20,35,60,.14),0 14px 40px rgba(20,35,60,.24);color:#1c2230;font:400 14px/1.5 ${FONT};letter-spacing:-.01em;padding:14px 14px 9px;opacity:0;transform:translateY(6px);animation:bub .25s .4s ease-out forwards}
.first .bub{animation-delay:.75s}
.bub::after{content:'';position:absolute;right:46px;bottom:-6px;width:12px;height:12px;background:#fbfcfd;transform:rotate(45deg);box-shadow:3px 3px 4px rgba(20,35,60,.1)}
.bub b{display:block;font-size:13px;font-weight:650;line-height:1.35;margin-bottom:11px;word-break:keep-all}
.chips{display:grid;grid-template-columns:1fr 1fr;gap:7px}
.chip{all:unset;box-sizing:border-box;text-align:center;padding:5px 2px;border-radius:99px;background:#eceff4;color:#3a475d;font:550 12px/1.2 ${FONT};cursor:pointer}
.chip:hover{background:#e0e6ef}.chip[aria-pressed=true]{background:#4a6794;color:#fff}.chip:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:2px}
.ft{display:flex;align-items:center;justify-content:flex-end;gap:2px;margin-top:10px}.ft .sp{flex:1}
.btn{all:unset;box-sizing:border-box;white-space:nowrap;flex:none;height:24px;padding:0 9px;border-radius:7px;font:600 12px/1 ${FONT};display:inline-flex;align-items:center;cursor:pointer;color:#3a475d}
.btn:hover{background:#e4e9f1}.btn:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:2px}
.btn.pri{background:#3f5a86;color:#fff}.btn.pri:hover{background:#34496f}.btn:disabled{opacity:.45;cursor:not-allowed}
.csel{appearance:none;-webkit-appearance:none;flex:none;height:24px;margin-left:2px;font:550 12px/1 ${FONT};color:#3a475d;background:#e4e9f1 url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%235a6b88' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E") no-repeat right 6px center/9px;border:0;border-radius:99px;padding:0 18px 0 9px;cursor:pointer}
.csel:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:2px}.csel.off{visibility:hidden}
.btn.more{color:#6b7689;font-weight:550;padding:0 5px;margin-left:-5px}
.mas{width:104px;height:auto;display:block;margin-right:4px;filter:drop-shadow(0 6px 8px rgba(20,35,60,.18));transform-origin:right bottom;animation:pop .55s cubic-bezier(.2,.9,.3,1.15) both;cursor:pointer}
.first .mas{animation:ride .9s cubic-bezier(.16,.8,.3,1) both}
.out .mas{animation:fold .4s cubic-bezier(.5,0,.9,.5) forwards}.out .bub{animation:none;opacity:0;transition:opacity .15s}
.grip{position:absolute;left:0;top:0;width:20px;height:20px;cursor:nwse-resize;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'%3E%3Cg fill='%238a97ad'%3E%3Ccircle cx='13' cy='13' r='1.3'/%3E%3Ccircle cx='9' cy='13' r='1.3'/%3E%3Ccircle cx='13' cy='9' r='1.3'/%3E%3Ccircle cx='5' cy='13' r='1.3'/%3E%3Ccircle cx='9' cy='9' r='1.3'/%3E%3Ccircle cx='13' cy='5' r='1.3'/%3E%3C/g%3E%3C/svg%3E") no-repeat center/16px;transform:rotate(180deg);opacity:.5;touch-action:none;border-radius:12px 0 0 0}
.grip:hover,.grip:focus-visible{opacity:1}.grip:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:-2px}
.peek{all:unset;box-sizing:border-box;position:fixed;right:0;bottom:96px;cursor:pointer;animation:peek .5s ease-out;transition:transform .18s;transform-origin:right center}
.peek[hidden]{display:none!important}
.peek img{display:block;height:92px;width:auto;filter:drop-shadow(-2px 2px 4px rgba(20,35,60,.2))}
.peek:hover,.peek:focus-visible{transform:scale(1.07)}.peek:focus-visible{outline:2px solid rgba(58,71,93,.55);outline-offset:2px;border-radius:12px 0 0 12px}
@keyframes ride{from{transform:translateX(260px) rotate(8deg);opacity:0}30%{opacity:1}to{transform:none;opacity:1}}
@keyframes pop{from{transform:translateX(44px) scale(.55);opacity:0}30%{opacity:1}to{transform:none;opacity:1}}
@keyframes fold{to{transform:translateX(44px) scale(.55);opacity:0}}
@keyframes bub{to{opacity:1;transform:none}}@keyframes peek{from{transform:translateX(100%)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}.bub{opacity:1;transform:none}.out .mas{opacity:0}}`;
  let fl = null, settingsOpen = false;
  function removeFloat() { if (fl) { fl.host.remove(); document.removeEventListener('keydown', fl.onKey, true); document.removeEventListener('pointerdown', fl.onOut, true); fl = null; } }
  // open=true: 마스코트가 보드를 타고 나와 말풍선이 뜬다. open=false: 화면 오른쪽 끝에 머리만 내민 채 접혀 있다.
  async function showFloat(open) {
    if (fl || !store || !window.OSBPanel) return;
    let saved = {};
    try { saved = await store.get(['opts', 'profileIds', 'uiScale']); } catch (e) { /* 무시 */ }
    if (fl) return;
    const D = window.OSBPanel.DEFAULTS, picked = new Set(saved.profileIds || []);
    const host = document.createElement('div');
    host.style.cssText = 'all:initial;position:fixed;z-index:2147482999;right:0;bottom:0';
    const root = host.attachShadow({ mode: 'open' });
    const url = (n) => (chrome.runtime && chrome.runtime.getURL) ? chrome.runtime.getURL('icons/' + n) : '/ext/icons/' + n;
    const el = (t, a = {}, ...k) => { const e = document.createElement(t); for (const [n, v] of Object.entries(a)) e.setAttribute(n, v); e.append(...k); return e; };
    const save = el('button', { class: 'btn pri', type: 'button' }, '저장');
    const skip = el('button', { class: 'btn', type: 'button' }, '닫기');
    const more = el('button', { class: 'btn more', type: 'button' }, '세부 설정');
    // 색각 유형: 색 구분을 고르면 아래 줄 가운데에 나타난다. 자리는 항상 잡아 두어서 말풍선 모양이 바뀌지 않는다.
    const csel = el('select', { class: 'csel off', 'aria-label': '색각 유형' }, el('option', { value: 'deutan' }, '녹색약'), el('option', { value: 'protan' }, '적색약'), el('option', { value: 'tritan' }, '청황색약'));
    csel.value = (saved.opts && saved.opts.colorType) || 'deutan';
    const showType = () => csel.classList.toggle('off', !picked.has('color'));
    showType();
    const chips = PROFILE.map(p => {
      const c = el('button', { class: 'chip', type: 'button', 'aria-pressed': String(picked.has(p.id)) }, p.label);
      c.addEventListener('click', () => { picked.has(p.id) ? picked.delete(p.id) : picked.add(p.id); c.setAttribute('aria-pressed', String(picked.has(p.id))); showType(); if (fl && fl.first) save.disabled = !picked.size; });
      return c;
    });
    const bub = el('div', { class: 'bub', role: 'dialog', 'aria-label': '변환 방식 선택' }, el('b', {}, '어떤 도움이 필요하세요?'),
      el('div', { class: 'chips', role: 'group' }, ...chips), el('div', { class: 'ft' }, more, csel, el('span', { class: 'sp' }), skip, save));
    const peek = el('button', { class: 'peek', type: 'button', 'aria-label': '변환 방식 열기', 'aria-expanded': 'false', title: '변환 방식' }, el('img', { src: url('mascot-peek.png'), alt: '' }));
    const grip = el('div', { class: 'grip', role: 'slider', tabindex: '0', 'aria-label': '말풍선 크기', 'aria-valuemin': '100', 'aria-valuemax': '220', 'aria-valuenow': '100', title: '끌어서 크기 조절 (두 번 누르면 원래 크기)' });
    bub.append(grip);
    const wrap = el('div', { class: 'wrap' }, bub);
    root.append(el('style', {}, FL_CSS), wrap, peek);
    document.body.append(host);

    // 왼쪽 위 모서리를 끌면 말풍선과 마스코트가 함께 커진다 (기본 100%, 두 번 누르면 원래 크기)
    let scale = 1;
    const setScale = (s, persist) => {
      scale = Math.min(2.2, Math.max(1, Math.round(s * 100) / 100));
      wrap.style.zoom = scale; grip.setAttribute('aria-valuenow', String(Math.round(scale * 100)));
      if (persist) { try { store.set({ uiScale: scale }); } catch (e) { /* 무시 */ } }
    };
    if (saved.uiScale > 1) setScale(saved.uiScale, false);
    grip.addEventListener('pointerdown', (e) => {
      e.preventDefault(); e.stopPropagation(); grip.setPointerCapture(e.pointerId);
      const x0 = e.clientX, y0 = e.clientY, s0 = scale;
      const move = (ev) => setScale(s0 + ((x0 - ev.clientX) + (y0 - ev.clientY)) / 340, false);
      const up = () => { grip.removeEventListener('pointermove', move); grip.removeEventListener('pointerup', up); setScale(scale, true); };
      grip.addEventListener('pointermove', move); grip.addEventListener('pointerup', up);
    });
    grip.addEventListener('dblclick', () => setScale(1, true));
    grip.addEventListener('keydown', (e) => {
      const d = { ArrowRight: -.1, ArrowUp: .1, ArrowLeft: .1, ArrowDown: -.1 }[e.key];
      if (d) { e.preventDefault(); e.stopPropagation(); setScale(scale + d, true); }
    });

    const state = { host, first: !!open, open: false, mas: null, busy: false };
    fl = state;
    const sync = () => { for (let i = 0; i < chips.length; i++) chips[i].setAttribute('aria-pressed', String(picked.has(PROFILE[i].id))); showType(); };
    function openIt() {                          // 접힘 → 마스코트가 나온다
      if (state.open || state.busy) return;
      if (!alive()) { staleNotice(); return; }
      state.open = true; sync();
      save.disabled = state.first && !picked.size;
      peek.hidden = true; peek.setAttribute('aria-expanded', 'true');
      wrap.classList.toggle('first', state.first);      // 처음 안내만 멀리서 보드를 타고 들어온다
      state.mas = el('img', { class: 'mas', src: url('mascot-ride.png'), alt: '', title: '접기' });
      state.mas.addEventListener('click', () => { if (!state.first) closeIt(); });      // 캐릭터를 누르면 접힌다
      wrap.append(state.mas); bub.hidden = false;
      bub.style.animation = 'none'; void bub.offsetWidth; bub.style.animation = '';
      const f = root.querySelector('.chip'); f && !state.first && f.focus({ preventScroll: true });
    }
    function closeIt() {                         // 마스코트가 달려 나가고 머리만 내민 모습으로 접힌다
      if (!state.open || state.busy) return;
      state.busy = true; wrap.classList.add('out'); skip.disabled = save.disabled = true;      // 접힌 자리로 쏙 들어간다
      setTimeout(() => {
        if (fl !== state) return;
        state.mas && state.mas.remove(); state.mas = null; wrap.classList.remove('out'); bub.hidden = true;
        peek.hidden = false; peek.setAttribute('aria-expanded', 'false'); skip.disabled = false; state.open = false; state.busy = false; state.first = false;
      }, 420);
    }
    state.closeIt = closeIt;
    const onKey = (e) => { if (e.key === 'Escape' && state.open && !state.first) { e.stopPropagation(); closeIt(); } };
    const onOut = (e) => { if (state.open && !state.first && !e.composedPath().includes(host)) closeIt(); };
    state.onKey = onKey; state.onOut = onOut;
    document.addEventListener('keydown', onKey, true); document.addEventListener('pointerdown', onOut, true);
    peek.addEventListener('click', openIt);
    skip.addEventListener('click', async () => { if (state.first) { try { await store.set({ onboarded: true }); } catch (e) { /* 무시 */ } } closeIt(); });
    more.addEventListener('click', async () => {      // 세부 설정: 확장 프로그램 설정과 같은 내용을 페이지 위 창으로 연다 (이미 열려 있으면 다시 열지 않는다)
      if (settingsOpen) return;
      settingsOpen = true;
      let ai = true;
      try { ai = !!(await chrome.runtime.sendMessage({ type: 'health' })).ai; } catch (e) { /* 무시 */ }
      closeIt();
      window.OSBPanel.open({ settings: true, ai, onClose: () => { settingsOpen = false; }, adapter: {
        loadScale: async () => { try { return (await store.get('uiScale')).uiScale || 1; } catch (e) { return 1; } },
        saveScale: (v) => { try { store.set({ uiScale: v }); } catch (e) { /* 무시 */ } },
        loadOptions: async () => { try { return (await store.get('opts')).opts || null; } catch (e) { return null; } },
        saveOptions: async (o) => { await store.set({ opts: o, onboarded: true }); }
      } });
    });
    save.addEventListener('click', async () => {
      if (!alive()) { staleNotice(); return; }
      const o = { ...D, ...(saved.opts || {}), pdf: true, readpdf: false, html: false, large: false, read: false, contrast: false, figures: false, color: false, easy: false, terms: false, braille: false, profile: true };
      for (const p of PROFILE) if (picked.has(p.id)) Object.assign(o, p.set);
      if (o.read) Object.assign(o, { pdf: false, html: true });          // 큰 글씨·소리 읽기는 웹 문서에서만 (나머지는 원본 PDF에서도 된다)
      o.colorType = csel.value;
      saved.opts = o;
      try { await store.set({ opts: o, onboarded: true, profileIds: [...picked] }); } catch (e) { /* 무시 */ }
      closeIt();
    });
    if (open) openIt(); else { bub.hidden = true; }
    peek.hidden = open;
  }
  // 주소 끝에 ?osbIntro=1 (또는 &osbIntro=1)을 붙이면 처음 안내를 다시 볼 수 있다 (시연·영상 촬영용)
  async function maybeFloat() { try { if (store) showFloat(/[?&]osbIntro=1/.test(location.search) || !(await store.get('onboarded')).onboarded); } catch (e) { /* 무시 */ } }

  // 주차 제목 옆에 그 주차의 자료를 한꺼번에 받는 '전체 다운로드' 링크를 붙인다 (자료가 2개 이상인 주차만).
  function batchItems(scope) {
    const seen = new Set();
    return [...scope.querySelectorAll(FILE_LINK)].filter(eligible).filter(a => !seen.has(a.href) && seen.add(a.href))
      .map(a => { const label = cleanLabel(a.textContent); return { label, adapter: adapterFor(a.href, label, courseName()) }; });
  }
  function addAllButton(host, scope, text, quiet) {
    if (!host || host.querySelector(':scope > .osb-all')) return;
    const n = batchItems(scope).length;
    if (quiet ? n < 2 : !n) return;                    // 주차에 자료가 하나뿐이면 그 파일의 버튼과 겹치므로 붙이지 않는다
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = quiet ? 'osb-link osb-all' : 'osb-btn osb-all';
    btn.innerHTML = quiet ? `<span>${text} (${n})</span>` : ICON + `<span>${text} (${n})</span>`;
    btn.setAttribute('aria-label', `${text}: 자료 ${n}개를 내 방식으로 한꺼번에 변환`);
    btn.title = `자료 ${n}개를 정해 둔 방식으로 차례로 변환해 받아요`;
    host.append(btn);
    btn.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      if (!alive()) { staleNotice(); return; }
      if (!window.OSBPanel) return;
      const items = batchItems(scope);
      window.OSBPanel.open({ batch: { items }, adapter: items[0].adapter, mascot: mascotUrls() });
    });
  }
  function addBatchButtons(root = document) {
    document.querySelectorAll('li.section').forEach(sec => addAllButton(sec.querySelector('h3.sectionname'), sec, '전체 다운로드', true));      // 자료가 2개 이상인 주차에만, 눈에 덜 띄는 글자 링크로
  }

  function scan(root = document) { root.querySelectorAll(FILE_LINK).forEach(addButton); addBatchButtons(); }
  // 화면이 바뀔 때마다 바로 훑지 않고, 한 프레임에 한 번만 (페이지가 자주 바뀌어도 느려지지 않게)
  let scanQueued = false;
  const observer = new MutationObserver(() => {
    if (scanQueued) return;
    scanQueued = true;
    requestAnimationFrame(() => { scanQueued = false; if (on) scan(); });
  });

  // 확장 프로그램 켜기/끄기 (팝업의 스위치). 끄면 버튼과 안내 띠를 모두 떼고, 켜면 다시 붙인다.
  let on = false;
  function apply(next) {
    if (next === on) return;
    on = next;
    if (on) {
      scan(); addBanner(); maybeFloat();
      observer.observe(document.body, { childList: true, subtree: true });
    } else {
      observer.disconnect(); removeFloat();
      document.querySelectorAll('.osb-btn, .osb-link, #osb-banner').forEach(el => el.remove());
      document.querySelectorAll('[data-osb-done]').forEach(el => delete el.dataset[DONE]);
    }
  }
  const readEnabled = async () => { try { return store ? (await store.get('enabled')).enabled !== false : true; } catch (e) { return true; } };
  readEnabled().then(apply);
  const resync = () => { if (!document.hidden) readEnabled().then(apply); };
  document.addEventListener('visibilitychange', resync);
  window.addEventListener('focus', resync);
  try {
    if (chrome.storage && chrome.storage.onChanged) chrome.storage.onChanged.addListener((ch, area) => { if (area !== 'sync') return; if (ch.enabled) apply(ch.enabled.newValue !== false); if (ch.onboarded) { if (ch.onboarded.newValue) fl && fl.first && fl.closeIt(); else if (on) { removeFloat(); showFloat(true); } } });
  } catch (e) { /* 개발용 가짜 chrome에는 없다 */ }
})();
