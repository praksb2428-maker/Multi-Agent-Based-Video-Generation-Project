# ADR 0016: API 키 방식의 GUI 모의 연결

- **상태:** 모의 연결 구현·검증 후보. 실제 키 발급·외부 API 연결·실제 Codex 생성은 보류한다. 이번 독립 검토와 사용자 채택은 별도 기록한다.
- **배경:** 사용자는 기존 Python 구조로 Codex 기획·대본 생성과 API 키 연결 원리를 요청했다. API 과금과 추가 비용 없음의 충돌을 설명한 뒤 “API 연결 코드·모의 테스트부터 구현 — 요청한 API 키 구조를 준비하고, 실제 호출을 차단해 비용 없이 검증”을 선택했다.
- **선택지:** API 연결 모의 구현 / 보유 무료 크레딧 조건 확인 / ChatGPT 로그인 기반 Codex / 기존 로컬 모델 / 키 발급·요금 안내부터 확인. 사용자는 첫 번째를 선택했다.
- **선택과 이유:** 설치된 openai3.41.0/httpx0.28.1과 기존 src/openai_mock.py를 재사용한다. GUI openai_mock을 선택한 명시 생성만 Python SDK Responses 요청을 직렬화한다. 고정 dummy 자격 증명과 메모리 MockTransport를 사용하므로 실제 키·네트워크·추가 API 요금이 없다.
- **영향:** GUI → Python Workflow → 기존 SDK mock → 창작 JSON 검사 → 미승인 초안 저장 → 별도 기획 승인 → 가상 견적 → 별도 모의 제작 승인 → 명시 제작이다. 기본 템플릿·로컬 Qwen·양식·수정과 재승인·기존 파일을 유지한다. GUI SDK mock은 전역 잠금으로 직렬화해 pinned SDK의 일시적 환경 격리 복원 경합을 막는다. 이 잠금은 다른 프로세스나 앱 전체의 보안 격리가 아니다.
- **실패·복구:** 거부/미완료/손상 JSON/조건·앱 소유 값 위반은 새 job 저장 전에 거부한다. 기존 작업은 유지하고 자동 재시도·fallback·승인·제작을 하지 않는다. 화면은 입력 확인 후 명시적 새 생성 경로를 설명한다. live·endpoint·api_key·fixture 필드를 GUI 요청으로 추가해도 거부한다.
- **실제 연결 원리와 미정:** 향후 실제 API 연결을 승인한다면 본인이 OpenAI 계정에서 키를 발급하고 Python 서버 전용 비밀 설정으로 전달한다. 서버가 API 요청을 인증하고 응답의 JSON을 검증해 미승인 초안으로 저장하는 원리다. 키는 브라우저·Git·대화창에 넣지 않는다. 이번에는 키 발급·키 파일·환경 읽기·실제 통신 코드를 활성화하지 않는다. API 과금은 ChatGPT 구독과 별도이며 무료 크레딧·계정 권한·실제 사용 가능 모델은 확인하지 않았다. [공식 과금 안내](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)
- **Codex와 구분:** 이 단계는 OpenAI Python SDK의 합성 API 계약 검사다. Codex CLI·App Server·Codex SDK·ChatGPT 로그인 연결을 구현/호출한 것이 아니다. 기존 mock 모델 문자열 gpt-6.1-sol은 fixture의 요청 표기이며 실제 API 접근·가격·응답 품질의 증거가 아니다. [공식 인증 구분](https://learn.chatgpt.com/docs/auth)
- **범위·수리·보존:** 이번 M 수리 최초 실패 후 최대2회. 기존 SDK2/2+null예외1/1·J2/2+schema예외1/1·K 확대 HOLD를 보존한다. 기존 provider·CLI·승인/미디어 도메인·CSS·의존성·제안서·과거 증거는 변경하지 않는다. 새 설치/실제 모델 호출/결제/외부 전송/commit/push는 제외한다.
- **결정자:** 개인(사용자)의 위 선택 응답.
- **날짜:** 2026-11-16
- **관련:** [기존 SDK 모의](0006-sdk-mock.md), [GUI 안내](../shorts-production.md), Git 제외 workspace/api-key-mock-20261116의 계획·변경·검사·부모 UI/검토 기록.
