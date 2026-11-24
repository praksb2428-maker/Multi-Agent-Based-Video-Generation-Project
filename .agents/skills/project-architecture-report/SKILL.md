---
name: project-architecture-report
description: Reconcile short-video implementation changes with AGENTS.md or docs/architecture.md and explain the changed file structure in a standalone HTML architecture report.
---

# 구현·설계 동기화와 HTML 구조 보고

구현 파일 또는 프로젝트 스킬이 바뀐 회차에 사용한다. `docs/architecture.md`는 구성 요소·데이터/승인 흐름의 기준이며 `AGENTS.md`는 오래 유지할 작업 규칙의 기준이다. HTML은 사람이 읽는 현재 구조와 이번 파일 변경 요약이다.

1. 같은 후보의 `plan.md`·`change.md`와 `git diff --name-status <base>` 및 untracked 목록을 확인한다. 실제 만든 파일과 수정한 파일을 구분하고, `rg --files`로 관련 호출·저장 경로만 확인한다. `.env`, `workspace/`의 비밀·사용자 결과를 보고서에 복사하지 않는다.
2. 변경된 컴포넌트의 책임·입출력·의존·승인 경계·미구현 영역을 [아키텍처](../../../docs/architecture.md)에 반영한다. 팀의 지속 규칙이나 권한 경계가 바뀌면 [AGENTS](../../../AGENTS.md)를 갱신한다. 설계 영향이 없더라도 어떤 파일과 계약을 확인했는지 아키텍처 문서에 간결히 기록한다.
3. `docs/architecture.html`을 외부 네트워크 없이 열리는 HTML로 작성한다. 실제 코드에 근거한 상위 계층 다이어그램(인라인 SVG 또는 의미 있는 HTML), 폴더별 책임, **이번 회차에 생성/수정한 파일**, 현재 구현/미구현, 설계 근거 링크를 포함한다. HTML의 파일 목록은 Git 상태에서 만들고 기존 파일을 새 파일이라 부르지 않는다. 반응형 화면과 텍스트 대체 설명을 제공한다.
4. `python scripts/check_architecture_sync.py --base <base>`로 설계 문서 동반 변경을 확인하고, HTML 상대 경로·문서 구조·보기를 검사한다. 이 가드는 문서가 바뀐 **존재**만 확인한다. 작성자와 별도 검토자가 실제 코드·Markdown·HTML의 의미 일치를 읽어 판정한다.
5. 변경 파일, 다이어그램의 근거, 가드·HTML 검사 결과와 미정 사항을 `change.md` 및 문서화 회차 기록에 연결한다. 검증·검토가 없으면 완료나 자동 발견 성공으로 표시하지 않는다.

이 스킬은 전역 자산을 설치하거나 서비스 기능을 추가하지 않는다. HTML 출력은 설계 설명이며 기획·제작 승인이나 배포 권한이 아니다.
