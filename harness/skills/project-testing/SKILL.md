---
name: project-testing
description: Verify an affected offline planning, approval, GUI, mock-media or rework part and record reproducible results; excludes live API tests and repeated full runs without changed baselines.
---

# 파트별 검사와 테스트 기록

코드 변경 후 [테스트 기준](../../../docs/testing.md)과 현재 작업 기록의 요구 ID를 확인할 때 사용한다.

1. 파트와 공유 인터페이스의 변경 영향을 정한다. 신규 GUI는 실제 HTTP와 브라우저, 미디어는 FFprobe/전체 디코드/SRT, 승인 변경은 현재 입력·만료·변조·재승인 거부를 검사한다.
2. 구현 중에는 좁은 진단을 쓰고 파트가 완성되면 관련 검사를 묶는다. 전체 회귀는 공통 경계 변경이나 영향 불명 등 명시적 이유가 있을 때 수행한다.
3. 통과 결과를 재사용할 때 source·입력·의존성·런타임·정의·로그·정상 종료·정리가 같은지 확인하고 기존 실행 ID를 유지한다. 새 채팅만으로 다시 실행하지 않는다.
4. 실제 실행 명령·종료·통과 수·경고·미실행 범위를 기존 기록에 남긴다. 합성 입력은 합성이라고 표시한다.
5. 최초 실패 뒤 가설을 바꾼 수리는 최대 두 번이다. 같은 실패를 반복하거나 새 이름으로 횟수를 초기화하지 않는다. 소진·권한 거부·결과 불명은 영향 작업을 멈추고 보고한다.

테스트 소유 임시 폴더·서버는 끝나면 소유권과 절대 경로를 확인해 정리한다. 필요한 실패·검증 증거는 보존한다. 모의 단가/호출자 표기는 실제 결제나 신원 검증이 아니다.
