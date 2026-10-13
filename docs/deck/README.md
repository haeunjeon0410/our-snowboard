# 작품소개 PDF 소스 (16:9 슬라이드, 12장)
- `python build.py` → index.html 생성 (디자인·문구 전부 build.py 안에 있음)
- `python render.py` → Our-Snowboard_작품소개.pdf (Playwright Chromium, 1920x1080)
- assets/ : 마스코트, 맞춤 변환 창 캡처(panel.png), 실제 변환 예시 이미지(orig_p9, fig_p9, cb_orig/cb_sim/cb_fixed)
- slides_content.md : 슬라이드별 내용 텍스트
- 비어 있는 곳: 원본/변환본 비교 스크린샷은 현재 실제 변환 결과 이미지로 대체해 둠
- 글꼴은 Noto Sans CJK KR로 렌더링했음. 프로젝트의 Pretendard(extension/fonts)를 쓰려면 CSS font-family 앞에 추가하면 됨
