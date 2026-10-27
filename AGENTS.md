# Codex 프로젝트 규칙

## 목적과 현재 범위

- 제안서 원본은 [`Video_Production_Project.md`](Video_Production_Project.md)이다. 목표는 주제 하나로 숏츠 한 편을 기획·제작·검토하는 흐름이며, 상세 요구와 현재 구현의 차이는 [`docs/project-brief.md`](docs/project-brief.md)에 있다.
- 현재 하네스는 **기존 로컬 템플릿 기반 콘텐츠 기획·승인**을 오프라인으로 다룬다. 이번 문서 단계에서 앱 기능을 추가하지 않는다. CrewAI, 실제 모델·영상 API, TTS, FFmpeg 제작 연결은 미구성이다.
- 확정 환경은 Python 3.12, `venv` + `pip`, 명시적 [`requirements.txt`](requirements.txt), VS Code, Git/GitHub다. 합성·공개 예제만 사용하고 유료 API 호출은 별도 결정 전까지 하지 않는다. 근거는 [`docs/decisions/README.md`](docs/decisions/README.md)에 있다.

## 파일별 역할과 수정 범위

| 경로 | 역할과 수정 원칙 |
| --- | --- |
| `Video_Production_Project.md` | 확정한 제안서 원본. 요청된 변경 없이 해석만으로 수정하지 않는다. |
| `README.md`, `docs/` | 사용 안내, 브리프, 작업 흐름, 검사 계획, 결정 기록. 사실·제안·미정을 구분하고 코드 변경에 맞춰 갱신한다. |
| `src/`, `shorts_cli.py`, `demo.py` | 기존 앱 코드·CLI. 승인된 구현 범위에서만 수정한다. 이번 문서 작업 범위에서는 수정하지 않는다. |
| `tests/`, `examples/` | 검증 코드와 합성 예제. 실제 개인 자료·음성·영상·키를 넣지 않는다. |
| `requirements.txt`, `.gitignore` | 의존성·로컬 파일 제외 규칙. 패키지·외부 연결·키 취급 변경은 결정 기준을 먼저 확인한다. |
| `.venv/`, `workspace/`, `.env`, `.env.*`, `.envrc` | 로컬 환경·출력·비밀 값. Git에 올리지 않는다. |

## 작업과 완료 기준

- 개인이 흐름을 관리하고 한 CLI에서 작성자와 검토자 역할을 순서대로 전환한다. 범위를 확인하고 작은 변경을 적용한 뒤 검토한다. 상세 단계와 실패 시 중단 규칙은 [`docs/workflow.md`](docs/workflow.md)를 따른다.
- 중요 결정은 기술 스택·데이터/저장·비용·외부 서비스·범위가 바뀌기 **전** 개인에게 선택지와 영향을 제시한다. 사소한 파일 정리는 승인 대상이 아니다. 기준과 기록 형식은 [`docs/decisions/README.md`](docs/decisions/README.md)를 따른다.
- 변경 범위에 맞는 검사를 실행하고 결과를 보고한다. 문서만 바뀌면 경로·링크·상태 표기와 `git diff --check`를 확인한다. 코드가 바뀌면 관련 기존 테스트를 실행한다. 실행하지 않은 검사는 통과했다고 쓰지 않는다. 검사 전략과 현재 명령은 [`docs/testing.md`](docs/testing.md)에 있다.
- 완료 보고에는 변경 파일, 확인한 명령과 결과, 미실행·실패 항목, 남은 결정과 개인 채택 필요 여부를 적는다. 전체 영상 제작·API·미디어 검사용 명령은 **미구성**이다. README의 실행 절차는 P4에서 실제 확인한 뒤 확정한다.

## 문서 지도

- [README](README.md) · [프로젝트 개요](docs/project-brief.md) · [workflow](docs/workflow.md) · [테스트 계획](docs/testing.md) · [결정 기록](docs/decisions/README.md)
