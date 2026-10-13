// 확장 프로그램 아이콘을 누르면 뜨는 작은 창: 켜기/끄기, 기본 변환 방식(변환 창과 같은 선택 화면), 서버 상태.
const $ = (s) => document.querySelector(s);

function showPower(on) {
  $('#power').setAttribute('aria-checked', String(on));
  $('#pw-s').textContent = on ? '스노우보드에 다운로드 버튼을 보여 줘요' : '꺼져 있어요. 스노우보드에 버튼이 보이지 않아요';
  $('#main').classList.toggle('off', !on);
}
chrome.storage.sync.get('enabled').then((r) => showPower(!(r && r.enabled === false)));
$('#power').addEventListener('click', () => {
  const on = $('#power').getAttribute('aria-checked') !== 'true';
  showPower(on);
  chrome.storage.sync.set({ enabled: on });
});

const adapter = {
  loadOptions: async () => { try { return (await chrome.storage.sync.get('opts')).opts || null; } catch (e) { return null; } },
  saveOptions: async (o) => { await chrome.storage.sync.set({ opts: o, onboarded: true }); }
};
chrome.runtime.sendMessage({ type: 'health' }, (r) => {
  const ok = r && r.ok;
  if (!ok) { $('#st').textContent = '서버에 연결하지 못했어요'; $('#st').hidden = false; }      // 연결될 때는 아무것도 보여 주지 않는다
  window.OSBPanel.open({ adapter, container: $('#settings'), settings: true, ai: !!(ok && r.ai) });
});
