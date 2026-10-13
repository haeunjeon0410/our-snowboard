/* 개발용: 크롬 확장 프로그램 없이 모의 강좌 화면(/mock?ext=1)에서 패널을 시험하기 위한 가짜 chrome.* 입니다.
   실제 extension/background.js 와 같은 일을 합니다(서버에 올리기·변환·진행·다운로드). 배포에는 쓰이지 않습니다. */
(() => {
  const ls = (k, v) => { try { return v === undefined ? JSON.parse(localStorage.getItem('dev:' + k) || 'null') : localStorage.setItem('dev:' + k, JSON.stringify(v)); } catch (e) { return null; } };
  const call = async (path, method, body) => {
    const r = await fetch(path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
    if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) {} throw new Error(d || '요청에 실패했어요 (' + r.status + ')'); }
    return r.json();
  };
  const handlers = {
    async prepare({ url, name, course }) {
      const blob = await (await fetch(url)).blob();
      const r = await fetch(`/api/prepare?filename=${encodeURIComponent(name + '.pdf')}&course=${encodeURIComponent(course || '')}&title=${encodeURIComponent([course, name].filter(Boolean).join(' · '))}`, { method: 'POST', headers: { 'Content-Type': 'application/pdf' }, body: blob });
      if (!r.ok) throw new Error((await r.json()).detail || '자료를 확인하지 못했어요');
      return { ok: true, ...(await r.json()) };
    },
    async make({ job, options }) { return { ok: true, task: (await call(`/api/jobs/${job}/make`, 'POST', options)).task }; },
    async task({ id }) { return { ok: true, status: await call(`/api/tasks/${id}`, 'GET') }; },
    async setcode() { return { ok: true }; },
    async cancel({ id }) { await call(`/api/tasks/${id}/cancel`, 'POST'); return { ok: true }; },
    async download({ files }) {
      for (const f of files) { const a = document.createElement('a'); a.href = f.url; a.download = f.name; document.body.append(a); a.click(); a.remove(); await new Promise(r => setTimeout(r, 400)); }
      return { ok: true };
    }
  };
  const listeners = [];
  window.chrome = {
    runtime: { sendMessage: async (msg) => { try { return await handlers[msg.type](msg); } catch (e) { return { ok: false, error: e.message }; } }, onMessage: { addListener() {} } },
    storage: {
      sync: { get: async (k) => ({ [k]: ls(k) }), set: async (o) => { const ch = {}; for (const k in o) { ch[k] = { oldValue: ls(k), newValue: o[k] }; ls(k, o[k]); } listeners.forEach(f => f(ch, 'sync')); } },
      onChanged: { addListener: (f) => listeners.push(f) }
    }
  };
})();
