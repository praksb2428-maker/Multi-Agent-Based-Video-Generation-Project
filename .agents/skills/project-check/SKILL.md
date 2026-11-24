---
name: project-check
description: Run scoped checks for this short-video project's environment or changed files and record commands, exits and evidence; never edit product code, tests or acceptance criteria to make a check pass.
---

# 프로젝트 검증과 실행 기록

환경 구성 또는 코드·문서 변경 후 실제 검사를 수행할 때 사용한다.

## 입력

[프로젝트 규칙](../../../AGENTS.md), [테스트 기준](../../../docs/testing.md), 이번 회차의 plan.md·change.md·정확 후보·변경 파일과 기존 실행 근거를 읽는다. 후보·입력·허용 범위가 맞지 않으면 계획 또는 작성 단계로 돌린다.

## 절차

1. 변경 파트와 영향을 받는 인터페이스의 검사 대상을 정한다. 구현되지 않은 기능은 검사 계획·미실행으로 표시한다.
2. 기존 Python 3.12 가상환경을 사용한다. 실제 명령은 저장소 루트에서 실행하고 명령·종료 코드·출력·환경을 기록한다. 새 의존성 설치나 키·비밀 환경 조회를 하지 않는다.
3. 실제 실행 근거가 필요한 시험 운영이고 유효한 기존 근거가 없을 때 초기 모듈 로딩 검사와 기존 핵심 검사를 실행한다. 다음은 해당 범위의 명령 예시다. 문서 설계만 변경되고 제품·검사 기준이 그대로면 구조·링크·보존 검사와 유효한 기존 결과를 사용하며 이 명령을 매번 반복하지 않는다.

   ```powershell
   .\.venv\Scripts\python.exe -X utf8 -c "import storyboard_web, src.storyboard_flow, src.storyboard_openai, src.storyboard_render; print('current modules loaded')"
   .\.venv\Scripts\python.exe -X utf8 -W error::ResourceWarning -m unittest discover -s tests -v
   ```

4. 나머지 기존 검사 근거는 해당 소스·입력·의존성·런타임·검사 정의·정상 종료·정리가 유효한지 비교하고 재사용으로 구분한다. 공통 경계 변경 또는 영향 불명 등 실제 근거가 있을 때만 전체 검사를 다시 실행한다. UI·미디어가 바뀌면 [테스트 기준](../../../docs/testing.md)의 실제 동작 검사도 수행한다.
5. 구현 파일이 바뀌면 회차 기준 ref로 `python scripts/check_architecture_sync.py --base <base>`를 실행한다. `AGENTS.md` 또는 `docs/architecture.md`의 동반 변경이 없으면 실패로 기록한다. 통과해도 설계의 의미가 맞는지는 별도 검토자가 확인한다. 구조가 바뀌었다면 `docs/architecture.html`의 파일 목록·계층·링크도 확인한다.
6. 통과·실패·미실행을 구분한다. 필수 검사 미실행은 보류로 인계하고 검사 실패는 작성자에게 돌린다. 필수 검사 통과·유효 재사용이 확인되면 같은 후보의 checks.md를 별도 검토자에게 넘긴다. 검증 담당의 검사 결과는 독립 검토의 판정이나 개인 채택을 대신하지 않는다. 모의 응답을 실제 모델 호출로, 로컬 MP4 기술 검사를 사람 수락으로, 파일 구조 검사를 스킬 자동 발견으로 표시하지 않는다.

## 산출물

기본 기록은 `workspace/checks.md`이며, 계획에서 새 회차 폴더를 정했다면 그 폴더에 checks.md를 쓴다. 같은 후보·입력 식별, 검사 범위, 실제 명령·종료 코드·출력·원본 로그, 재사용 근거, 미검증·복귀 대상과 남은 수리 횟수를 담는다. 초기 환경을 실제 실행한 경우에만 bootstrap-log.md에도 간결히 기록한다. 이전 기록을 덮어쓰지 않는다.

## 중단 조건과 권한

앱 코드·테스트·기준을 수정하지 않는다. 실행 불가·테스트 0개·실패를 통과로 쓰지 않는다. 실패를 작성자에게 넘기고, 최초 실패 후 추가 수리 최대 2회와 이전 소진 한도를 보존한다. 유료 API·실제 모델·서버 상주·자동 승인·자동 제작은 이 스킬의 동작이 아니다. 본인이 만든 임시물만 소유권·경로·필요성을 확인해 정리한다.
