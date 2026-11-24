---
name: project-test-design
description: Design and write focused tests for approved changes in this short-video project; use before project-check runs independent verification, not as a substitute for it.
---

# 프로젝트 테스트 설계·작성

기능을 구현하거나 계약을 바꿀 때 작성자 역할에서 사용한다. 검사 실행·판정·`checks.md`는 [project-check](../project-check/SKILL.md)의 책임이다.

1. 이번 회차의 `plan.md`, 실제 변경 후보, [아키텍처](../../../docs/architecture.md), [테스트 기준](../../../docs/testing.md)을 비교한다. 성공 경로뿐 아니라 승인 전 차단, 변경·만료·변조, 파일 보존, 오류 복구, 외부 호출 금지 중 영향받는 계약을 고른다.
2. `tests/`에 합성 입력으로 관찰 가능한 행동을 검증한다. 구현 코드를 그대로 복사한 단언이나 현재 미구현 기능의 가짜 통과 테스트를 만들지 않는다. 실제 API·키·모델·유료 사용은 이 스킬의 권한이 아니다. 외부 경계는 명시적 모의로 검사한다.
3. 새 테스트와 기존 관련 테스트가 왜 필요한지 `change.md`에 요구·파일·검사 명령으로 연결한다. 작성 중 좁은 테스트를 실행할 수 있지만 최종 검증 결과는 독립 `project-check`가 같은 후보에서 기록한다.
4. 테스트가 제품 설계·입출력 계약을 바꾸면 [설계 동기화](../project-architecture-report/SKILL.md)와 개인 결정 기준을 먼저 적용한다. 통과를 위해 요구·승인 기준을 낮추지 않는다.

실패 후 추가 수정은 [workflow](../../../docs/workflow.md)의 회차 누계 최대 2회를 따른다. 테스트 설계만으로 실제 영상 품질이나 개인의 결과 채택을 증명하지 않는다.
