# 인터넷에 올리기 (무료, Hugging Face Spaces)

올리면 사용자는 **확장 프로그램만 추가**하면 됩니다. (변환 서버를 켤 필요 없음)
서버는 `Dockerfile`로 돌아갑니다. 키와 접속 코드는 코드에 쓰지 않고 Spaces의 **Secrets**에만 넣습니다.

## 1. 한 번만 준비
1. https://huggingface.co 에 가입한다. (카드 필요 없음)
2. 오른쪽 위 프로필 → **New Space**
   - Space name: `our-snowboard`, SDK: **Docker** → **Blank**, Hardware: **CPU basic (free)**, Visibility: Public
3. 만들어진 Space → **Settings**
   - **Variables and secrets** → **New secret**
     - `GATEWAY_API_KEY` : 학교 AI API 키
     - `ACCESS_CODE` : AI 항목을 쓸 사람들에게만 알려 줄 코드 (아무 문자열)
   - **New variable**
     - `PUBLIC_URL` : `https://<아이디>-our-snowboard.hf.space` (Space 주소창에 보이는 주소, 마지막 `/` 없이)
     - 선택: `DAILY_AI_LIMIT` (하루 AI 호출 상한, 기본 300), `DATA_TTL_HOURS` (올린 자료 보관 시간, 기본 6)

## 2. 코드 올리기
Space 페이지의 **Files → Add file → Upload files** 로 이 프로젝트 폴더의 파일을 올린다.
**올리면 안 되는 것**: `.env`, `samples/`, `output/`, `server/.cache/` (`.dockerignore`가 막아 주지만 업로드할 때도 빼 둔다).
git으로 올릴 때는 Space의 안내(Clone repository)를 따른다.
처음 빌드는 몇 분 걸린다. 끝나면 `https://<아이디>-our-snowboard.hf.space` 가 홈페이지가 된다.

## 3. 확인
- 홈페이지가 열리고, 위쪽 설치 안내에 **설치 파일 받기** 버튼이 보인다 (`/extension.zip`).
- `https://…hf.space/health` 에서 `"public": true` 가 보인다.
- 설치 파일을 받아 크롬에 추가하면, 확장이 바로 이 서버로 연결된다. (서버 주소가 파일 안에 들어 있음)
- 변환 창에서 AI 항목을 쓰려면 **AI 접속 코드**를 한 번 넣는다. (코드는 크롬에 저장됨)

## 알아둘 것
- 무료 Space는 한동안 안 쓰면 잠들고, 다시 열 때 1분쯤 걸린다. 시연 직전에 한 번 열어 둔다.
- 올린 PDF는 `DATA_TTL_HOURS` 뒤에 서버에서 지워진다. 서버가 다시 시작돼도 파일이 사라질 수 있다 (정상).
- AI 크레딧은 하루 상한(`DAILY_AI_LIMIT`)에서 멈춘다. 코드가 새 나갔으면 `ACCESS_CODE`만 바꾸면 된다.
- 크롬 웹스토어에 올리면 개발자 모드 없이 "추가" 한 번으로 설치된다. (등록비 $5, 검수 며칠) 올리기 전에 `python tools/build_extension.py <서버주소>` 로 서버 주소가 들어간 폴더를 만든다.
