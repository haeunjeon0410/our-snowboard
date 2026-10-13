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
  // 버튼 아이콘: Phosphor 'magic-wand' (MIT, https://phosphoricons.com) — 현재 글자색을 따른다
  const ICON = '<svg viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="M48 64a8 8 0 0 1 8-8h16V40a8 8 0 0 1 16 0v16h16a8 8 0 0 1 0 16H88v16a8 8 0 0 1-16 0V72H56a8 8 0 0 1-8-8m136 128h-8v-8a8 8 0 0 0-16 0v8h-8a8 8 0 0 0 0 16h8v8a8 8 0 0 0 16 0v-8h8a8 8 0 0 0 0-16m56-48h-16v-16a8 8 0 0 0-16 0v16h-16a8 8 0 0 0 0 16h16v16a8 8 0 0 0 16 0v-16h16a8 8 0 0 0 0-16m-20.69-64L80 219.31a16 16 0 0 1-22.62 0l-20.7-20.68a16 16 0 0 1 0-22.63L176 36.69a16 16 0 0 1 22.63 0l20.68 20.68a16 16 0 0 1 0 22.63m-54.63 32L144 91.31l-96 96L68.68 208ZM208 68.69L187.31 48l-32 32L176 100.69Z"/></svg>';
  // PDF가 아닌 게 분명한 첨부(PPT·워드·한글·압축 등)에는 버튼을 붙이지 않는다. 이름만으로 알 수 없으면 붙이고, 누를 때 확인한다.
  const NOT_PDF = /\.(pptx?|docx?|xlsx?|hwpx?|zip|mp4|mp3|png|jpe?g)(?:[?#\s]|$)/i;
  const eligible = (a) => !NOT_PDF.test(a.textContent || '') && !NOT_PDF.test(a.getAttribute('href') || '');

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
    btn.innerHTML = ICON + '<span>맞춤 변환</span>';
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
  const observer = new MutationObserver(muts => { for (const m of muts) for (const n of m.addedNodes) if (n.nodeType === 1) { if (n.matches && n.matches(FILE_LINK)) addButton(n); scan(n); } });

  // 확장 프로그램 켜기/끄기 (팝업의 스위치). 끄면 버튼과 안내 띠를 모두 떼고, 켜면 다시 붙인다.
  let on = false;
  function apply(next) {
    if (next === on) return;
    on = next;
    if (on) {
      scan(); addBanner();
      observer.observe(document.body, { childList: true, subtree: true });
    } else {
      observer.disconnect();
      document.querySelectorAll('.osb-btn, #osb-banner').forEach(el => el.remove());
      document.querySelectorAll('[data-osb-done]').forEach(el => delete el.dataset[DONE]);
    }
  }
  const readEnabled = async () => { try { return store ? (await store.get('enabled')).enabled !== false : true; } catch (e) { return true; } };
  readEnabled().then(apply);
  const resync = () => { if (!document.hidden) readEnabled().then(apply); };
  document.addEventListener('visibilitychange', resync);
  window.addEventListener('focus', resync);
  try {
    if (chrome.storage && chrome.storage.onChanged) chrome.storage.onChanged.addListener((ch, area) => { if (area === 'sync' && ch.enabled) apply(ch.enabled.newValue !== false); });
  } catch (e) { /* 개발용 가짜 chrome에는 없다 */ }
})();
