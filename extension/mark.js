// 변환 서버의 홈페이지에서 "확장 프로그램이 설치돼 있어요"를 알려 주는 표시만 남긴다. (페이지 내용은 읽거나 바꾸지 않는다)
document.documentElement.dataset.osbExt = chrome.runtime.getManifest().version;
