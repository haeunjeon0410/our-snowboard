// Our Snowboard — 숙명여대 스노우보드 화면에서 PDF 자료 옆에 "맞춤 변환" 버튼을 붙인다.
// 누르면 화면 위에 작은 창(osb-panel.js)이 떠서 변환 방식을 고르고 다운로드한다. 학교 서버나 사이트 내용은 바꾸지 않는다.
(() => {
  const FILE_LINK = [
    'a[href*="/mod/ubfile/view.php"]',                 // 강좌 자료 파일 (스노우보드의 기본 자료 형태)
    'a[href*="/mod/resource/view.php"]',
    'a[href*="/pluginfile.php/"][href*=".pdf"]',       // 게시판·과제 등에 붙은 PDF 첨부
    'a[href*="/mock/file/"]'                           // 개발용 모의 화면
  ].join(',');
  const DONE = 'osbDone';
  // PDF가 아닌 게 분명한 첨부(PPT·워드·한글·압축 등)에는 버튼을 붙이지 않는다. 이름만으로 알 수 없으면 붙이고, 누를 때 확인한다.
  const NOT_PDF = /\.(pptx?|docx?|xlsx?|hwpx?|zip|mp4|mp3|png|jpe?g)(?:[?#\s]|$)/i;
  const eligible = (a) => !NOT_PDF.test(a.textContent || '') && !NOT_PDF.test(a.getAttribute('href') || '');
  const GOGGLES = '<svg viewBox="0 0 24 24" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 9.6c0-1.5 1.2-2.7 2.7-2.7h12.2c1.5 0 2.7 1.2 2.7 2.7v3c0 2.3-1.9 4.2-4.2 4.2h-.9c-1 0-1.9-.5-2.4-1.3-.4-.6-1-.9-1.7-.9h-.2c-.7 0-1.3.3-1.7.9-.5.8-1.4 1.3-2.4 1.3h-.9c-2.3 0-4.2-1.9-4.2-4.2z"/><path d="M3.2 10.2H1.6M20.8 10.2h1.6"/><path d="M7.4 10.4l1.8-1.8M11 10.4l1.8-1.8" opacity=".5"/></g></svg>';

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
      prepare: () => send({ type: 'prepare', url, name, course }),
      make: (job, options) => send({ type: 'make', job, options }).then((r) => r.task),
      status: (id) => send({ type: 'task', id }).then((r) => r.status),
      cancel: (id) => send({ type: 'cancel', id }).catch(() => {}),
      setCode: (code) => send({ type: 'setcode', code }).catch(() => {}),
      save: (files) => send({ type: 'download', files }),
      loadOptions: async () => { try { return store ? ((await store.get('opts')).opts || null) : null; } catch (e) { return null; } },
      saveOptions: async (o) => { try { if (store) await store.set({ opts: o }); } catch (e) { /* 무시 */ } }
    };
  }

  function addButton(a) {
    if (a.dataset[DONE]) return;
    a.dataset[DONE] = '1';
    if (!eligible(a)) return;
    const label = cleanLabel(a.textContent);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'osb-btn';
    btn.innerHTML = GOGGLES + '<span>맞춤 변환</span>';
    btn.setAttribute('aria-label', `${label} 파일을 내 방식으로 변환`);
    btn.title = '큰 글씨·그림 설명·점자 등 내게 맞는 형태로 바꿔 받아요';
    a.insertAdjacentElement('afterend', btn);
    btn.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      if (!window.OSBPanel) return;
      window.OSBPanel.open({ adapter: adapterFor(a.href, label, courseName()) });
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

  function scan(root = document) { root.querySelectorAll(FILE_LINK).forEach(addButton); }
  scan();
  addBanner();
  new MutationObserver(muts => { for (const m of muts) for (const n of m.addedNodes) if (n.nodeType === 1) { if (n.matches && n.matches(FILE_LINK)) addButton(n); scan(n); } })
    .observe(document.body, { childList: true, subtree: true });
})();
