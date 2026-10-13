// 확장 프로그램 백그라운드 흐름 시험 (크롬 없이): node extension/test_background.mjs
// 실제 변환 서버(localhost:8790)가 켜져 있어야 한다. chrome.* 는 가짜로 대신한다. AI는 쓰지 않는 항목만 시험한다.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const downloads = [];
let handler = null;
const chrome = {
  storage: { sync: { get: async () => ({}) } },
  runtime: { onMessage: { addListener: (f) => { handler = f; } } },
  downloads: { download: async (o) => { downloads.push(o); return 1; } },
};
const ctx = vm.createContext({ chrome, fetch, Blob, URL, Uint8Array, String, console, setTimeout, encodeURIComponent, decodeURIComponent, escape, JSON, Promise, Error });
vm.runInContext(readFileSync(new URL('./background.js', import.meta.url), 'utf8'), ctx);

const ask = (msg) => new Promise((res) => { const keep = handler(msg, {}, res); if (keep !== true) res(undefined); });
let fail = 0;
const check = (name, ok, extra = '') => { console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra ? '  ' + extra : '')); if (!ok) fail++; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const h = await ask({ type: 'health' });
check('서버 상태 확인', h && h.ok === true, JSON.stringify(h));

// 1) 파일 가져와서 올리기 → 자료 요약
const p = await ask({ type: 'prepare', url: 'http://localhost:8790/mock/file/0', name: '2주차 학습자료', course: '경영정보시스템 (004)' });
check('PDF를 가져와 올리고 자료 요약을 받음', p && p.ok && p.job && p.info && p.info.pages > 0, JSON.stringify(p && p.info));

// 2) 변환 (AI 없이 되는 항목만) → 진행 → 완료
const m = await ask({ type: 'make', job: p.job, options: { large: true, contrast: true, figures: false, easy: false, terms: false, color: false, braille: true } });
check('변환 시작', m && m.ok && m.task, JSON.stringify(m));
let st = null;
for (let i = 0; i < 60; i++) { st = (await ask({ type: 'task', id: m.task })).status; if (st.status !== 'running') break; await sleep(500); }
check('변환 완료 (웹 문서 + 점자 파일)', st && st.status === 'done' && st.files.length === 2, st && st.files.map(f => f.name).join(' / '));
check('파일 이름에 과목·자료 이름이 들어감', st && st.files[0].name.includes('경영정보시스템 (004)') && st.files[0].name.includes('2주차 학습자료'), st && st.files[0].name);

// 3) 다운로드
const d = await ask({ type: 'download', files: st.files });
check('다운로드 요청 2건', d && d.ok && downloads.length === 2 && downloads.every(x => x.url.startsWith('http://localhost:8790/api/tasks/')), downloads.map(x => x.filename).join(' / '));
const body = await (await fetch(downloads[0].url)).text();
check('받은 웹 문서에 고대비·큰 글씨가 적용됨', body.includes('data-theme="hc"') && body.includes('--fs:26px'));

// 4) 오류 처리
let r = await ask({ type: 'prepare', url: 'http://localhost:8790/health', name: '가짜', course: '' });
check('PDF가 아니면 친절한 오류', r && r.ok === false && r.error.includes('PDF'), r && r.error);
r = await ask({ type: 'prepare', url: 'http://localhost:8790/no-such-file', name: '없음', course: '' });
check('받기 실패(404)도 오류로', r && r.ok === false, r && r.error);

console.log(fail ? `\n${fail}개 실패` : '\n모두 통과');
setTimeout(() => process.exit(fail ? 1 : 0), 200);
