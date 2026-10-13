// 확장 프로그램 아이콘을 누르면 뜨는 "맞춤 설정": 변환 창이 처음 열릴 때의 기본 선택을 정해 둔다 (변환 창과 같은 저장 위치를 쓴다).
const $ = (s) => document.querySelector(s);
const { DEFAULTS, OPTIONS } = window.OSBPanel;
let opts = { ...DEFAULTS };

// 체크는 바로 저장하지 않고 [저장]을 눌렀을 때 저장한다.
async function save() {
  const b = $('#save');
  b.disabled = true;
  await chrome.storage.sync.set({ opts });
  b.textContent = '저장했어요';
  setTimeout(() => window.close(), 700);
}

function row(def) {
  const input = document.createElement('input');
  input.type = 'checkbox'; input.checked = !!opts[def.key];
  const label = document.createElement('label'); label.className = 'opt';
  const l = document.createElement('span'); l.className = 'l'; l.textContent = def.label;
  const tag = document.createElement('span');
  if (def.ai) { tag.className = 'tag'; tag.textContent = 'AI'; }
  label.append(input, l);
  let sel = null;
  if (def.select) {
    sel = document.createElement('select'); sel.setAttribute('aria-label', '색각 유형');
    for (const [v, t] of [['deutan', '적록 색약·색맹'], ['tritan', '청황 색약·색맹']]) { const o = document.createElement('option'); o.value = v; o.textContent = t; sel.append(o); }
    sel.value = opts.colorType; sel.disabled = !input.checked;
    sel.addEventListener('change', () => { opts.colorType = sel.value; });
    const wrap = document.createElement('span'); wrap.className = 'sel'; wrap.append(sel); label.append(wrap);
  } else {
    label.append(tag);
  }
  input.addEventListener('change', () => { opts[def.key] = input.checked; if (sel) sel.disabled = !input.checked; });
  return label;
}

// 켜기/끄기: 누르는 즉시 적용된다 (아래 항목 저장과는 별개)
function showPower(on) {
  $('#power').setAttribute('aria-checked', String(on));
  $('#pw-s').textContent = on ? '스노우보드에 맞춤 변환 버튼을 보여 줘요' : '꺼져 있어요. 스노우보드에 버튼이 보이지 않아요';
  $('#main').classList.toggle('off', !on);
  $('#save').disabled = !on;
}
chrome.storage.sync.get('enabled').then((r) => showPower(!(r && r.enabled === false)));
$('#power').addEventListener('click', () => {
  const on = $('#power').getAttribute('aria-checked') !== 'true';
  showPower(on);
  chrome.storage.sync.set({ enabled: on });
});

chrome.storage.sync.get('opts').then((r) => {
  opts = { ...DEFAULTS, ...((r && r.opts) || {}) };
  $('#list').replaceChildren(...OPTIONS.map(row));
});

chrome.runtime.sendMessage({ type: 'health' }, (r) => {
  const on = r && r.ok;
  $('#st').textContent = on ? (r.ai ? '서버 연결됨 · AI 사용 가능' : r.codeRequired ? '서버 연결됨 · AI는 접속 코드가 필요해요' : '서버 연결됨 · AI 꺼짐') : '서버에 연결하지 못했어요';
});

$('#save').addEventListener('click', save);
$('#cancel').addEventListener('click', () => window.close());
