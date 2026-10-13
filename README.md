---
title: Our Snowboard
sdk: docker
app_port: 7860
pinned: false
---
<!-- 위 머리말은 Hugging Face Spaces 배포용입니다. 자세한 배포 방법은 docs/DEPLOY.md -->

# Our Snowboard

> 모든 사람이 스노우보드를 잘 이용할 수 있도록.

숙명여대 스노우보드의 PDF 자료 옆에 **맞춤 변환** 버튼이 생기는 크롬 확장 프로그램과, 내 컴퓨터에서 도는 변환 서버입니다.
버튼을 누르면 스노우보드 화면 위에 작은 창이 떠서, 변환 방식을 체크박스로 고르고 **다운로드**하면 바뀐 교재(웹 문서 `.html`, 선택하면 점자 `.brf`)가 내려옵니다. 새 탭이나 별도 웹사이트는 없습니다.

## 실행하기

1. `.env.example` 을 `.env` 로 복사하고 `GATEWAY_API_KEY=` 뒤에 학교 AI API 키를 넣는다. (BAZE → API Gateway → API 키 생성. 키는 채팅·코드·커밋에 남기지 않는다.)
2. `start_server.bat` 더블클릭 (처음에는 `pip install -r server/requirements.txt`). 서버 주소는 `http://localhost:8790`.
3. 크롬 → `chrome://extensions` → 개발자 모드 → **압축해제된 확장 프로그램 로드** → `extension` 폴더 선택.
4. 스노우보드 강좌 화면의 PDF 옆에 **맞춤 변환** 버튼이 생긴다. (확장 프로그램 없이도 `http://localhost:8790` 에서 PDF를 직접 올릴 수 있다. 보조 기능.)

## 변환 창에서 고르는 항목

| 항목 | AI | 설명 |
|---|---|---|
| 큰 글씨로 읽기 | - | 글씨를 키우고 줄 간격을 넓힘 |
| 고대비 | - | 검정 바탕 + 밝은 글씨 |
| 그림·도식을 글로 설명 | 사용 | 그림 설명 + 그림 속 글자 + 색 의미 (그림이 없으면 숨김/비활성) |
| 쉬운 한국어로 | 사용 | 어려운 문장을 짧고 쉽게 |
| 영어 용어 함께 | 사용 | 전문 용어 옆에 영어 병기 |
| 색 구분 돕기 | - | 색으로 칠해진 그림에 보정 + 같은 색에 같은 무늬 (해당 그림이 있을 때만 표시) |
| 점자 파일도 받기 | - | 한글 점자 `.brf` 파일을 함께 내려받음 |

항상 들어가는 것: 읽는 순서 정리, 제목·목록·표·코드 구분, 띄어쓰기 복원(사라진 쪽만), 원본에서 색으로만 강조된 말을 굵은 밑줄로, 스캔본(이미지 PDF)의 글자 읽기, 결과 문서 안의 도구(글씨 크기·테마·소리 내어 읽기).
체크한 항목에서만 AI를 부르므로, AI 항목을 끄면 크레딧이 들지 않는다.

## 구성

```
extension/     크롬 확장: 버튼·안내 띠(content.js), 변환 창(panel.js), 서버와의 통신·다운로드(background.js), 팝업
server/        FastAPI: extract(글자 추출) ops(필요한 AI 작업) render(결과 파일) braille_ko(점자) color(색 구분) enrich(AI 호출) llm jobs main
server/static/ 홈 화면, 품질 측정표, 변환 창(osb-panel.js), 스노우보드에 붙는 UI(osb-ui.css), 디자인 시스템(ds.css)
eval/          품질 측정 (python -m eval.run_eval → http://localhost:8790/quality), 서버 흐름 시험(e2e_api.py)
tools/         마스코트 이미지 만들기, 확장 프로그램 파일 동기화
docs/          화면 캡처 스크립트, 마스코트 원본
samples/ output/   (커밋 제외) 샘플 PDF와 변환 결과
```

흐름: `POST /api/prepare`(PDF 올리기: 글자 추출만, AI 없음) → `POST /api/jobs/{id}/make`(체크한 항목만 처리) → `GET /api/tasks/{id}`(진행) → `GET /api/tasks/{id}/file/{html|brf}`(받기).

## 시험

```
node extension/test_background.mjs     # 확장 프로그램 백그라운드의 올리기→변환→다운로드 흐름 (서버가 켜져 있어야 함)
python eval/e2e_api.py <PDF> [옵션JSON] # 서버의 전체 흐름
python -m eval.run_eval                # 변환 품질 측정표 (/quality)
python docs/make_shots.py              # 화면 캡처 (Edge를 화면 없이 실행)
```

개발 중에는 `http://localhost:8790/mock?ext=1` 에서 확장 프로그램 없이 버튼과 창을 눌러 볼 수 있다 (`dev-bg.js` 가 가짜 chrome API 역할).

## 디자인

- 글꼴 **Pretendard Variable** (SIL OFL, 서버·확장에 포함). 맥(macOS) 느낌의 차분한 회청색 톤, 얇은 실선, 평평한 면. 색·부품은 `ds.css`, 스노우보드에 붙는 버튼·안내 띠는 `osb-ui.css`, 변환 창은 `osb-panel.js` 안에 있다.
- 디자인을 고친 뒤에는 `python tools/sync_ext.py` 로 확장 프로그램 폴더에도 복사한다.
- 마스코트는 `docs/mascot-src/` 원본에서 `python tools/make_mascot_assets.py` 로 만든다. 사이트 톤에 맞게 색을 조정해서 쓴다.

## AI 사용

- 기본 모델은 가장 저렴한 `gpt-6-luna` (실패하면 `gemini-3.5-flash-lite`). `.env` 의 `TEXT_MODEL` `VISION_MODEL` 로 바꾼다.
- 같은 입력은 `server/.cache/llm` 에 저장해서 다시 호출하지 않는다. 사용량: `http://localhost:8790/api/usage`.
- 이 서버는 내 크레딧을 쓰므로 `localhost` 외 접속과 허용하지 않은 웹사이트의 쓰기 요청은 거부한다.

## 점자 규정

한글 점자는 국립국어원 「한글 점자 규정 해설」(2017 개정 한국 점자 규정)의 예시 59개와 대조해 모두 일치하도록 구현했다. 수식·화학식 같은 전문 점자는 범위 밖이다.
