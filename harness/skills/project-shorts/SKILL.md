---
name: project-shorts
description: Coordinate this project's existing offline short-video flow through separate plan and mock-production approvals, explicit reviews and versioned rework; excludes paid generation and live agent-team dispatch.
---

# 숏폼 제작 흐름

[역할과 아키텍처](../../../docs/architecture.md), [실행 안내](../../../docs/shorts-production.md)를 따른다. 이 문서는 프로젝트 한정 호출 지침이며 글로벌 팀의 설치나 실행 계약이 아니다.

1. 주제·길이·비율·스타일·시청자·금지 요소·가상 예산을 확인하고 미승인 초안을 만든다. 참고 자료가 없으면 예시 큐레이션을 생략한다. 현재 GUI는 자료 수집을 하지 않는다.
2. **기획 승인에서 멈춘다.** 사용자 명시 승인 뒤 액션/비주얼 로컬 연출→범용 프롬프트→가상 견적을 만든다.
3. **제작 승인에서 멈춘다.** 새 입력·견적별 모의 승인 후에도 별도 제작 행동을 기다린다. 승인 1회에 새 결과 폴더를 하나만 만든다.
4. 색상 카드·무음·SRT를 만들고 기술 검사한다. 사용자가 영상·자막을 확인해 accept 또는 request_changes를 직접 기록한다.
5. 수정 요청은 직접 제공한 교체값으로만 새 초안을 만든다. 영향 후속 자료를 다시 만들고 두 승인을 새로 받는다. 문제 해결이나 수락은 추론하지 않는다.

기획/예시/액션/비주얼/프롬프트/운영/제작/검토의 8개 책임은 설계 역할이다. 현재는 고정 Python 함수와 모의 transport가 처리하며 8개 LLM 팀 호출을 수행하지 않는다. 실패·승인 만료·입력 변조·알 수 없는 상태는 자동 재시도·fallback 없이 중단한다. 과금·게시·키 사용은 범위 밖이다.
