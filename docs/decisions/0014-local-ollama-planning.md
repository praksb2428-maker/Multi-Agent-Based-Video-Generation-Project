# ADR 0014: 승인된 로컬 모델의 실제 기획·대본 생성

- **상태:** 사용자 선택에 따른 로컬 구현·실행 검증. 독립 검토와 사용자 최종 채택은 별도다.
- **배경:** 기존 모의 흐름 뒤 실제 기획·대본 생성을 연결하려는 요청이다. CPU i7-12700F, RAM31.8GiB, RTX3060 12GiB를 확인했다. 당시 사용 가능한 RAM6.6GiB·GPU메모리 약5GiB를 고려해 우선 4B급을 선정했다. 이 값은 조회 시점의 스냅샷이며 성능 보장이 아니다.
- **선택지:** PC 사양 후 로컬 모델 선정 / 이미 쓰는 로컬 모델 / OpenAI 코드만 준비 / 실제 모델 보류 / 우선순위 재정리. 사용자는 첫 선택 뒤 다시 설치·다운로드·연결을 승인했다.
- **선택과 이유:** 사용자 원문 “추천 구성 설치·다운로드 후 연결 (추천) — API 요금 없이 로컬 생성과 검사까지 진행하고, 자동 시작은 등록하지 않아.” 정확 구성은 Ollama0.40.16 portable·qwen3.5:4b-q4_K_M이며 프로젝트 workspace/local-model 아래에 둔다. 기존 GUI는 모의 모드를 유지하고 CLI draft-local부터 연결한다.
- **영향:** 명시 CLI만 고정 127.0.0.1:11434·runtime버전·모델 digest를 검사해 creative 필드만 받아 미승인 기획을 저장한다. 외부 URL·cloud모델·자동 pull·retry·fallback·자동 승인/제작은 없다. 자식 프로세스 전용 환경·private-home·모델 폴더를 쓰며 전역 환경/PATH/자동 시작 등록을 바꾸지 않았다. 로컬 API 통신·모델 설치가 새 승인 범위이고 유료 API·실제 영상/TTS·계정 연결은 아니다.
- **수리·예외:** J2/2를 소진한 뒤 실제 최초 요청이 items:false schema 변환 HTTP400으로 실패했다. 사용자 원문 “이 문제만 추가 수정 1회 허용 (추천) — 장면 목록 규격을 호환되는 형태로 바꾸고 실제 생성까지 재검증해.”에 따라 그 문제만 object items(anyOf)로 수정하고 영향62개·실제생성1회로 재검증했다. J2/2+schema예외1/1을 보존하며 추가 제품 수리/생성을 하지 않는다.
- **결과·한계:** 실제 한글 기획 JSON 생성은 36.703초·종료0, 미승인3장면·목표30초·입력보존이었다. 내용에는 분류/통 색상/벌금의 확인되지 않은 단정이 있어 사실성·금지 의도 준수·내용 품질은 수락하지 않았다. 기술 연결과 JSON 성공은 사용 가능한 대본이나 사람 채택의 근거가 아니다. 실제 사용자 확인과 자동 사실/의도 검토, GUI 실제 모델 모드·AI 연출/영상/TTS는 이번 범위에서 검증하지 않았다.
- **보존:** 원본 제안서·모의 경로·GUI·스킬/workflow·이전 H/I/G 기록은 변경하지 않는다. 현재 생성물의 기획/제작 승인과 사용자 채택은 대기다. 소유 서버/runner는 검증 후 종료하고 설치파일·모델·유일한 근거는 보존한다.
- **공식 출처:** [고정 배포](https://github.com/ollama/ollama/releases/tag/v0.40.16), [정확 모델](https://ollama.com/library/qwen3.5:4b-q4_K_M), [Chat API](https://docs.ollama.com/api/chat), [JSON schema](https://docs.ollama.com/capabilities/structured-outputs). ZIP SHA256 `50fcf5ad54277f2fa5d173ebfc93bcb017adbc0c9ef2314daabc96ca9e6aa64e`, 모델 manifest SHA256 `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`를 검증했다.
- **결정자:** 개인(사용자)의 위 명시 선택·예외 답변. 배포/연결/검사 결과는 실행 기록에 근거한다.
- **날짜:** 2026-11-16
- **관련:** [이전 모의 준비](0013-local-gui-harness.md), [검사](../testing.md), [실행](../../README.md), Git 제외 workspace/local-ollama-planning-20261116 기록.
