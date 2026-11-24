# HTTP 계약과 데이터·키 경계

현재 서버는 `127.0.0.1:8766`에서만 듣고 고정 경로만 처리한다. API가 작업 ID·파일명 외 임의 경로, 명령, 모델 또는 endpoint를 받지 않는다. [바인딩](../../storyboard_web.py#L44) · [경로 제한](../../storyboard_web.py#L79) · [라우팅](../../storyboard_web.py#L92)

| 메서드·경로 | 입력 → 결과 | 상태/외부 영향 |
| --- | --- | --- |
| `GET /api/bootstrap` | CSRF, 고정 모델명, FFmpeg 준비 여부, 출력 이미지 단가 참고값 | 조회만; 키 값 없음 |
| `POST /api/jobs` | `prompt`, `seconds`, 선택 `image_b64` → 서버 발급 ID·draft | 로컬 입력 저장; OpenAI 호출 없음 |
| `POST /api/jobs/{id}/plan` | 빈 JSON → 보강 프롬프트·구간 | 명시 GPT Responses 호출 |
| `POST /api/jobs/{id}/previews` | 빈 JSON → 각 구간 이미지 URL | 명시 OpenAI Images 호출; 여러 장 비용 가능 |
| `POST /api/jobs/{id}/decline` | 빈 JSON → declined | 로컬 상태 변경, 렌더 없음 |
| `POST /api/jobs/{id}/render` | 빈 JSON → ready·영상 URL | 승인 뒤 로컬 FFmpeg 실행; 추가 영상 API 없음 |
| `GET /api/jobs/{id}` | 작업 ID → 공개 가능한 현재 상태 | 재호출·승인 없음 |
| `GET /media/{id}/{고정 파일명}` | 원본·완성 예시·완성 MP4 | 파일 해시·단계 검사 후 반환 |

근거: [GET 구현](../../storyboard_web.py#L92), [POST 구현](../../storyboard_web.py#L119), [공개 상태](../../src/storyboard_flow.py#L103), [미디어 제한](../../src/storyboard_flow.py#L269).

## 데이터와 신뢰 경계

- **입력:** JSON 본문 한도, 필드 집합, 중복 키, 이미지 base64·서명/크기와 10·20·30초를 검사한다. [HTTP 검사](../../storyboard_web.py#L119) · [서비스 입력](../../src/storyboard_flow.py#L121)
- **브라우저 요청:** 정확한 localhost Host와 다른 Origin/교차 사이트 요청을 거부하고 POST에 서버 생성 CSRF 토큰을 요구한다. CSP·`no-store`·`nosniff`·`Referrer-Policy`를 응답에 둔다. 이것은 인터넷 공개 서비스의 사용자 인증을 제공하지 않는다. [경계](../../storyboard_web.py#L62) · [Host/Origin/CSRF](../../storyboard_web.py#L79)
- **키와 외부 전송:** 키는 서버 환경 `OPENAI_API_KEY` 또는 Git 제외 `.env`에서만 읽고 고정 `https://api.openai.com/v1`로 보낸다. 프롬프트와 선택 이미지는 명시 보강·예시 버튼에서 OpenAI로 전송된다. `.env` 크기·중복 키·형식을 검사한다. [키 읽기](../../src/storyboard_openai.py#L22) · [요청](../../src/storyboard_openai.py#L63)
- **저장과 출력:** 키는 `state.json`·브라우저 공개 상태에 포함하지 않는다. 원본·예시·결과는 로컬 작업 폴더에 남고, 해시와 고정 파일명으로 변경/경로 오류를 거부한다. 보존·삭제 기간은 아직 정하지 않았다. [상태 공개](../../src/storyboard_flow.py#L103) · [파일 확인](../../src/storyboard_flow.py#L55)

테스트는 CSRF 누락 거부와 정상 MIME/다운로드, 합성 키·모의 HTTP를 확인했다. 악성 Host/Origin 값과 모든 보안 헤더의 자동 assert, 실제 OpenAI 권한·과금·품질은 아직 미검증이다. [테스트](../../tests/test_storyboard.py#L139) · [검사 계획](../testing.md)
