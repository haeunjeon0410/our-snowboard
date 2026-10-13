// Our Snowboard — 백그라운드: 로그인된 브라우저로 강의 파일을 받아 변환 서버에 맡기고, 결과 파일을 다운로드한다.
// 패널(content script)은 아래 메시지만 보낸다: prepare / make / task / cancel / download / health / setcode
const DEFAULT_SERVER = 'http://localhost:8790';
const server = async () => (await chrome.storage.sync.get('server')).server || DEFAULT_SERVER;
// AI 접속 코드 (공개 서버에서 AI 항목을 쓸 때만 필요). 이 컴퓨터의 크롬 설정에 저장한다.
const codeHeader = async () => { const c = (await chrome.storage.sync.get('code')).code; return c ? { 'X-OSB-Code': c } : {}; };

function fileNameFrom(resp, fallback) {
  const cd = resp.headers.get('content-disposition') || '';
  let m = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  if (m) { try { return decodeURIComponent(m[1]); } catch (e) { /* 다음 방법 */ } }
  m = /filename="?([^";]+)"?/i.exec(cd);
  if (m) { try { return decodeURIComponent(escape(m[1])); } catch (e) { return m[1]; } }
  // 헤더에 이름이 없으면 이동한 뒤의 주소에서 (예: .../pluginfile.php/.../제7장.pdf?...)
  try {
    const base = decodeURIComponent(new URL(resp.url).pathname.split('/').pop());
    if (/\.pdf$/i.test(base)) return base;
  } catch (e) { /* 다음 방법 */ }
  return fallback || 'lecture.pdf';
}

async function alive(base) {
  try { return (await fetch(base + '/health', { cache: 'no-store' })).ok; } catch (e) { return false; }
}

// 1) 강의 파일을 가져와서 서버에 올리고, 자료 요약을 받는다 (AI는 아직 쓰지 않는다)
async function prepare({ url, name, course, light }) {
  const base = await server();
  if (!(await alive(base))) return { ok: false, error: '변환 서버에 연결하지 못했어요. 잠시 뒤 다시 시도해 주세요. (내 컴퓨터에서 서버를 켜 쓰는 중이라면 start_server.bat 을 먼저 실행해 주세요)' };
  let resp;
  try { resp = await fetch(url, { credentials: 'include', redirect: 'follow' }); }
  catch (e) { return { ok: false, error: '파일을 가져오지 못했어요. 스노우보드에 로그인되어 있는지 확인해 주세요.' }; }
  if (!resp.ok) return { ok: false, error: `파일을 가져오지 못했어요 (${resp.status})` };
  const blob = await resp.blob();
  const head = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
  const isPdf = String.fromCharCode(...head.slice(0, 5)) === '%PDF-', isZip = head[0] === 0x50 && head[1] === 0x4b, isOle = head[0] === 0xd0 && head[1] === 0xcf && head[2] === 0x11 && head[3] === 0xe0;      // PDF / PPTX / PPT
  if (!isPdf && !isZip && !isOle) return { ok: false, error: 'PDF나 PowerPoint 파일이 아니라서 변환할 수 없어요.' };
  const ext = isPdf ? '.pdf' : isOle ? '.ppt' : '.pptx';
  const fname = fileNameFrom(resp, name ? name.replace(/[\\/:*?"<>|]/g, '_') + ext : 'lecture' + ext);
  const title = [course, name].filter(Boolean).join(' · ');
  let r;
  try {
    r = await fetch(`${base}/api/prepare?filename=${encodeURIComponent(fname)}&course=${encodeURIComponent(course || '')}&title=${encodeURIComponent(title)}${light ? '&light=1' : ''}`,
      { method: 'POST', headers: { 'Content-Type': 'application/pdf', ...(await codeHeader()) }, body: blob });
  } catch (e) { return { ok: false, error: '변환 서버에 연결하지 못했어요.' }; }
  if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) { /* 무시 */ } return { ok: false, error: d || `자료를 확인하지 못했어요 (${r.status})` }; }
  return { ok: true, ...(await r.json()) };
}

async function call(path, method, body) {
  const base = await server();
  const r = await fetch(base + path, { method, headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(await codeHeader()) }, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) { /* 무시 */ } throw new Error(d || `요청에 실패했어요 (${r.status})`); }
  return r.json();
}

const handlers = {
  prepare,
  make: async ({ job, options }) => ({ ok: true, task: (await call(`/api/jobs/${job}/make`, 'POST', options || {})).task }),
  task: async ({ id }) => ({ ok: true, status: await call(`/api/tasks/${id}`, 'GET') }),
  cancel: async ({ id }) => { try { await call(`/api/tasks/${id}/cancel`, 'POST'); } catch (e) { /* 무시 */ } return { ok: true }; },
  download: async ({ files }) => {
    const base = await server();
    for (const f of files) await chrome.downloads.download({ url: base + f.url, filename: f.name, saveAs: false, conflictAction: 'uniquify' });
    return { ok: true };
  },
  setcode: async ({ code }) => { await chrome.storage.sync.set({ code: String(code || '').trim() }); return { ok: true }; },
  health: async () => {
    const base = await server();
    try { const j = await (await fetch(base + '/health', { cache: 'no-store', headers: await codeHeader() })).json(); return { ok: true, ...j, server: base }; }
    catch (e) { return { ok: false, server: base }; }
  }
};

// 툴바 아이콘 표시: 꺼져 있으면 'OFF'
async function showBadge() {
  try {
    const off = (await chrome.storage.sync.get('enabled')).enabled === false;
    await chrome.action.setBadgeText({ text: off ? 'OFF' : '' });
    if (off) await chrome.action.setBadgeBackgroundColor({ color: '#7a8699' });
  } catch (e) { /* 시험용 가짜 chrome에는 없다 */ }
}
try {
  showBadge();
  if (chrome.storage && chrome.storage.onChanged) chrome.storage.onChanged.addListener((ch, area) => { if (area === 'sync' && ch.enabled) showBadge(); });
} catch (e) { /* 무시 */ }

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const fn = msg && handlers[msg.type];
  if (!fn) return;
  fn(msg).then(sendResponse).catch(e => sendResponse({ ok: false, error: String((e && e.message) || e) }));
  return true;   // 비동기 응답
});
