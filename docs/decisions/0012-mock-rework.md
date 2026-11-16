# ADR 0012: 수정 요청과 별도 재승인 모의 재제작

- 상태: 사용자 요청 범위 구현·로컬 검증, 독립 검토 별도
- 날짜: 2026-10-30
- 결정자: 프로젝트 사용자(명시 요청), 구현 담당(범위 내 JSON 연결)

## 배경과 선택

사용자는 “수정 요청을 기획 수정·재승인·모의 재제작까지 연결”하고 승인·무비용 경계를 유지하도록 요청했다. 기획안 §3의 수정 뒤 영향 단계 재검토를 기존 CLI에 연결한다. 자연어 AI 해석·자동 승인 대신 현재 source 여섯 입력·결과·검사·changes 확인과 사용자의 명시 교체 JSON을 받는 세 명령을 선택했다.

## 단계와 결속

`rework-plan-mock`는 기존 `revise_plan`으로 새 draft를 만들고 awaiting_plan_approval에서 멈춘다. 별도 기존 `approve` 후 `prepare-rework-mock`가 새 연출·프롬프트·모의 견적을 저장하며 awaiting_mock_production_approval에서 멈춘다. 별도 기존 `approve-production-mock` 후 명시적 `produce-rework-mock`만 로컬 합성과 실제 QA·새 inspection·receipt를 만든다. 통합 함수는 승인 함수를 호출하지 않는다.

각 schema1 handoff는 현재 원본·검토·명시 patch·새 draft/기획·견적 SHA-256에 결속한다. canonical은 UTF8, sorted keys, ensure_ascii=False, allow_nan=False, comma/colon 구분자다. 현재 원본은 매 단계 명시 인자로 다시 받고 실제 검사를 재수행한다. bundle은 고정 파일만 workspace 안에서 읽고 경로·명령을 저장해 실행하지 않는다. 해시는 변경 감지이며 신원 인증·서명 아님. 모든 출력은 새 폴더로 보존한다. 준비 뒤 변경이나 옛/만료/다른 승인은 재제작을 거부한다.

## 한계와 후속 확인

최종 기술 완료도 human_review_pending이며 issue 해결은 추론하지 않는다. 원 확인 기록은 그대로 두고 새 영상은 별도 사용자 확인을 받는다. 색상 카드·무음의 실제 로컬 시험이며 수정 대본은 SRT/장면 JSON에 반영한다. 실제 AI·TTS·비용·외부 서비스·framework·DB·자동반복은 추가하지 않는다. [ADR0005](0005-offline-services.md), [0010](0010-local-mock-media.md), [0011](0011-local-result-feedback.md)의 경계를 유지한다. 검사·미실행 범위는 [testing](../testing.md#수정-요청과-별도-재승인-모의-재제작)에 있다.
