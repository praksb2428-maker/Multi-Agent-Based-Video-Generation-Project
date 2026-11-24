---
name: project-docs
description: Update this short-video project's development documents after observed work or an explicit decision and record why each document changed; preserve proposal originals and distinguish executed, reused and unverified evidence.
---

# 프로젝트 문서 갱신

작업·검사·사용자의 결정이 문서에 반영돼야 할 때 사용한다.

## 입력

현재 요청, [프로젝트 규칙](../../../AGENTS.md), 이번 회차의 plan.md·change.md·checks.md·review.md, 실제 diff·로그와 관련 [결정 기록](../../../docs/decisions/README.md)을 읽는다. 기본 기록은 workspace 아래에 있고 새 회차 폴더는 계획을 따른다. 파일 이름만 보고 실행을 추측하지 않는다. 필요한 검토가 없으면 검토 대기로 표시하며 완료·통과를 만들지 않는다.

## 절차

1. README는 준비·실행·문서 탐색, 브리프는 목표·범위, workflow는 개발 역할, testing은 검사 방법·근거, ADR은 사용자의 중요한 결정을 담당하도록 유지한다. 구성 요소·흐름의 기준은 `docs/architecture.md`, HTML 구조 설명은 `docs/architecture.html`에 둔다.
2. 변경이 필요한 문서만 갱신하고 동일한 규칙·로그 전체를 여러 파일에 복제하지 않는다. 승인 규칙과 원본 제안서·기존 검증 자료를 보존한다.
3. 사실·가정·미정, 실제 실행·기존 근거 재사용·미검증을 구분한다. 실패·보류도 그대로 기록한다. 검사·검토 판정을 바꾸거나 새로운 결정을 사용자가 내렸다고 꾸미지 않는다.
4. Markdown·HTML 구조, 관련 링크·실제 경로를 확인한다. 구현 변경 시 `AGENTS.md` 또는 `docs/architecture.md` 동반 갱신과 HTML 파일 구조 요약을 대조한다. 스킬 파일이 생긴 것, 직접 읽어 수행한 것, 새 세션에서 자동 발견된 것을 따로 기록한다. 단순 결과 반영은 문서 검사로 끝내고, 완료 기준·권한·인계를 바꾸는 문서는 계획 및 영향을 받는 검증·독립 검토로 돌린다. 문서화 완료 후 필수 검사·검토·요구별 상태와 개인 확인 대기를 보고한다.
5. 회고는 확인된 선택·작업·검사·한계를 바탕으로 초안을 작성한다. 사용자의 감정·학습 경험·직접 수행을 대신 주장하지 않고 사용자 확인 전임을 표시한다.

## 산출물

기본 기록은 `workspace/docs-update.md`이며 새 회차 폴더를 정했다면 그 폴더에 docs-update.md를 쓴다. 갱신 파일·이유·후보·검사/검토 근거·남은 질문·개인 확인 대기를 담는다. [강의 하네스 보고서](../../../docs/course-harness-report.md)와 이전 실제 사용 기록은 해당 회차의 근거로 보존한다. 새 회차의 결과를 과거 실행 사실로 고쳐 쓰지 않는다. 원본 로그·비공개 자료는 workspace에 두고 공개용 문서로 통째로 복사하지 않는다.

## 중단 조건

원본과 결과가 충돌하거나 중요한 새 결정이 미확정이면 해당 내용을 확정하지 않는다. 코드·테스트 수정, 제작 승인, Git 커밋·푸시·배포, 실제 API·모델 실행은 이 스킬에서 수행하지 않는다.
