---
name: project-ui-ux
description: Implement or verify the local short-video workroom's Korean interface and explicit approvals; excludes public websites, new frontend frameworks and automatic production.
---

# 로컬 작업실 화면

[GUI 안내](../../../docs/shorts-production.md)의 입력→기획→견적→제작→확인 흐름을 바꿀 때 사용한다.

- 사용자가 확인할 기획·장면·프롬프트·가상 견적을 해당 승인 버튼 앞에 보여준다. 기획 승인, 모의 제작 승인, 실제 모의 제작, 결과 확인은 각각 다른 명시 행동이다.
- 승인되지 않은 버튼은 비활성화하고 현재 해야 할 일을 옆에 설명한다. 로딩 동안 중복 실행을 막고 실패 후에는 원본 보존과 복구 방법을 제시한다.
- 한국어 label·semantic form·키보드 초점·상태 알림을 유지한다. 사용자가 입력한 문자열은 textContent 등 텍스트로 표시한다.
- 모바일·태블릿·데스크톱, 키보드·확대·긴 제목·빈 상태·오류·성공·수정 후 재승인을 실제 렌더에서 검사한다. 캡처에는 어떤 상태인지 적는다.
- 시스템 폰트와 프로젝트 로컬 자산만 쓴다. 서버 경로·CSRF·내부 함수명을 사용자의 작업 설명 대신 내보이지 않는다.

모의 영상/실제 모델 미연결 표시는 숨기지 않는다. 유료 호출·외부 공개·새 프레임워크는 이 스킬이 허가하지 않는다.
