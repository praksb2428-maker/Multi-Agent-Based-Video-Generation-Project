---
name: project-bootstrap
description: Prepare or resume this short-video project's existing Python offline CLI and local GUI; excludes package installation, global Codex setup, and paid model connections.
---

# 프로젝트 시작·재개

이 프로젝트의 준비와 실행 환경 확인에만 사용한다. [프로젝트 규칙](../../../AGENTS.md)과 [실행 안내](../../../README.md)를 먼저 읽는다.

1. 기존 `.venv`의 Python 버전과 고정 requirements를 확인한다. 파일이 있다는 이유로 설치 성공을 주장하지 않는다.
2. 실행할 작업과 관련된 최근 기록·입력·출력·승인 상태를 읽는다. 오래된 모의 승인은 새 제작에 사용하지 않는다.
3. CLI 검증은 필요한 명령만, GUI 검증은 `python -X utf8 shorts_web.py`로 시작한다. 자동 설치·모델 다운로드·환경변수의 키 조회를 하지 않는다.
4. 서버가 필요한 때만 시작하고 PID·시작 시각·cwd·포트·소비자·종료 방법을 기존 작업 기록에 남긴다. 다른 작업의 프로세스를 종료하지 않는다.
5. GUI 접속은 정확한 `http://127.0.0.1:8765`를 사용한다. 새로고침·재시작은 기획/제작 승인을 만들거나 실행하지 않는다.

준비 결과에는 실행 가능한 명령, 실제 확인한 환경, 없는 도구와 중단 지점만 적는다. 필수 도구가 없거나 현재 파일이 변경됐으면 해당 실행을 중단한다. 설치·실제 모델·유료 연결은 사용자 선택과 런타임 권한 없이 진행하지 않는다.
