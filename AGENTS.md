# Codex 프로젝트 규칙

## 목적과 현재 범위

- 제안서 원본은 [`Video_Production_Project.md`](Video_Production_Project.md)이다. 목표는 주제 하나로 숏츠 한 편을 기획·제작·검토하는 흐름이며, 상세 요구와 현재 구현의 차이는 [`docs/project-brief.md`](docs/project-brief.md)에 있다.
- 현재 하네스는 로컬 기획·명시 수정·기획 승인·연출/프롬프트·가상 견적·별도 제작 승인·합성 제작/검사·결과 확인·재승인 재제작을 다룬다. CLI와 Python localhost GUI는 같은 기존 함수 계약을 쓴다. 명시 CLI draft-local과 GUI의 ‘로컬 AI 실제 생성’ 선택·생성 버튼은 승인된 Ollama 0.40.16·qwen3.5:4b-q4_K_M으로 기획·대본만 실제 생성한다. 기본 GUI 모드는 템플릿이며 실제 영상 API·TTS·CrewAI 실행은 연결하지 않는다.
- 확정 환경은 Python 3.12, `venv` + `pip`, 명시적 [`requirements.txt`](requirements.txt), VS Code, Git/GitHub다. 합성·공개 예제만 사용하고 유료 API 호출은 별도 결정 전까지 하지 않는다. 근거는 [`docs/decisions/README.md`](docs/decisions/README.md)에 있다.

## 파일별 역할과 수정 범위

| 경로 | 역할과 수정 원칙 |
| --- | --- |
| `Video_Production_Project.md` | 확정한 제안서 원본. 요청된 변경 없이 해석만으로 수정하지 않는다. |
| `README.md`, `docs/` | 사용 안내, 브리프, 작업 흐름, 검사 계획, 결정 기록. 사실·제안·미정을 구분하고 코드 변경에 맞춰 갱신한다. |
| `src/`, `shorts_cli.py`, `shorts_web.py`, `web/` | 승인된 기능의 CLI·GUI·순차 처리. 기존 승인·해시·파일 보존 계약을 유지한다. 새 프레임워크·실제 모델 연결은 별도 선택이 필요하다. |
| `.agents/skills/` | 강의용 계획·검증·문서화 스킬의 프로젝트 경로. 실제 사용 방식과 자동 발견 확인 여부를 구분해 기록한다. |
| `harness/skills/` | 기존 참고 절차를 보존한다. 기본 개발 절차는 `.agents/skills/`의 3개 스킬을 우선 사용하고 같은 작업을 중복 실행하지 않는다. |
| `tests/`, `examples/` | 검증 코드와 합성 예제. 실제 개인 자료·음성·영상·키를 넣지 않는다. |
| `requirements.txt`, `.gitignore` | 의존성·로컬 파일 제외 규칙. 패키지·외부 연결·키 취급 변경은 결정 기준을 먼저 확인한다. |
| `.venv/`, `workspace/`, `.env`, `.env.*`, `.envrc` | 로컬 환경·출력·비밀 값. Git에 올리지 않는다. |

## 작업과 완료 기준

- 범위·파트 책임·인터페이스·완료 기준·검사를 기존 작업 기록에 먼저 적는다. 한 파일 집합은 한 명만 작성하고, 중요한 구현은 fresh 읽기 전용 검토를 거친다. 단계·최초 실패 후 최대 두 번의 수리 한도는 [`docs/workflow.md`](docs/workflow.md)를 따른다.
- 개발 역할은 계획·작성·검증·검토·문서화로 구분한다. 진행 담당자는 같은 회차의 plan/change/checks/review/docs-update와 정확 후보를 확인해 연결한다. 검증과 검토는 소스·테스트를 수정하지 않고 자신의 보고서만 남긴다. 작성·검토 역할을 추가했다는 이유로 새로운 실행 권한이나 실제 에이전트 호출 성공을 주장하지 않는다.
- 중요 결정은 기술 스택·데이터/저장·비용·외부 서비스·범위가 바뀌기 **전** 개인에게 선택지와 영향을 제시한다. 사소한 파일 정리는 승인 대상이 아니다. 기준과 기록 형식은 [`docs/decisions/README.md`](docs/decisions/README.md)를 따른다.
- 변경 범위에 맞는 검사를 실행하고 결과를 보고한다. 문서만 바뀌면 경로·링크·상태 표기와 `git diff --check`를 확인한다. 코드가 바뀌면 관련 기존 테스트를 실행한다. 실행하지 않은 검사는 통과했다고 쓰지 않는다. 검사 전략과 현재 명령은 [`docs/testing.md`](docs/testing.md)에 있다.
- 완료 보고에는 변경 파트, 실제 실행·유효 증거 재사용·미검증, 수리 누계와 사용자 확인 대기를 구분한다. 로컬 미디어 검사는 존재하며 실제 AI·유료 API 검증은 범위 밖이다. 유효한 검사를 새 채팅이나 문서 편집만으로 반복하지 않는다.

## 역할·진행 경계

8개 책임의 입출력과 현재 구현은 [아키텍처](docs/architecture.md)에 있다. 콘텐츠 기획 → 사용자 기획 승인 → 액션/비주얼 연출 → 프롬프트 → 운영의 가상 견적 → 사용자 별도 모의 제작 승인 → 명시 제작 → 기술 검사와 사용자 결과 확인 순서다. 예시 큐레이터는 자료가 없으면 생략한다. 설계 역할을 실제 8개 LLM 전문팀 호출로 표시하지 않는다.

- 기획 초안 생성·연출 준비·조회·새로고침·재시작에서 승인 함수를 호출하지 않는다. 승인 함수는 해당 명시 사용자 행동에만 연결한다.
- 제작 내용·견적·입력이 달라지면 기존 승인을 재사용하지 않는다. 수정본은 새 버전으로 저장하고 기획과 제작을 다시 승인받는다.
- 승인된 로컬 기획 범위를 제외한 실제 모델, 유료 API·키/비밀 환경·외부 자료 전송·자동 게시·새 의존성/모델 설치·전역 자산 변경은 진행하지 않는다. 이전 mock-only 선택에 대한 사용자 후속 승인으로 정확한 portable·모델 설치와 명시 draft-local, 이후 명시 요청으로 GUI의 로컬 AI 생성 선택을 허용한다. 고정 loopback·버전·모델 digest를 확인하며 자동 pull·재시도·fallback·서버 상주/자동 시작은 하지 않는다. 실제 출력은 미승인 초안이며 내용의 사실성과 적절성은 사용자 확인 전이다.
- 실패·만료·파일 변조·미완료 출력·알 수 없는 상태는 해당 작업을 중단한다. 자동 재시도나 공급자 fallback을 하지 않는다. 사용자에게 새 작업/수정/재검사 경로를 설명한다.
- GUI는 127.0.0.1 전용이다. 임의 요청 경로·명령·외부 URL·live 옵션을 실행하지 않는다. 작업 ID와 고정 파일만 서버에서 결정한다.
- 규칙·스킬 문서와 해시는 권한·신원 인증·실제 실행 성공을 증명하지 않는다. 기술 검사와 사용자의 시청·수락을 분리한다.

## 프로젝트 스킬과 정리

개발 요청은 [project-plan](.agents/skills/project-plan/SKILL.md)으로 범위·검사를 계획하고, 작성자가 허용된 후보와 change.md를 남긴 뒤 [project-check](.agents/skills/project-check/SKILL.md)로 검증한다. 별도 검토자의 review.md 판정 후 [project-docs](.agents/skills/project-docs/SKILL.md)로 관련 문서와 기록을 갱신하고 개인이 최종 확인한다. 다섯 역할과 세 스킬의 인계·실패 복귀는 [workflow](docs/workflow.md)를 따른다. 계획 스킬은 코드 작성, 검증 스킬은 코드·테스트 수정, 문서화 스킬은 제작 승인을 하지 않는다. [사용 기록과 과제 정리](docs/course-harness-report.md)는 해당 회차의 수행 근거이며 변경된 설계의 자동 실행 증거가 아니다.

기존 [부트스트랩](harness/skills/project-bootstrap/SKILL.md), [문서화 참고](harness/skills/project-documentation/SKILL.md), [테스트 참고](harness/skills/project-testing/SKILL.md), [UI/UX](harness/skills/project-ui-ux/SKILL.md), [숏폼 제작](harness/skills/project-shorts/SKILL.md)은 보존한다. 동일 작업은 기본 3개 스킬과 중복 수행하지 않는다. 모든 작업에서 스킬 전부를 로드하지 않는다.

실행 중 필요한 서버만 시작하고 PID·시각·포트·종료를 기존 기록에 남긴다. 검증 후 소유 임시물만 절대 경로·필요성·소유권을 확인해 정리한다. 기존/필수 증거와 원본은 임시물로 취급하지 않는다. 루틴 전체 폴더 백업·전역 변경·새 자동 감시를 하지 않는다. 최종 소스·고정 의존성·가이드·핵심 증거만 필요에 따라 보존하며 commit/push 권한은 별도다.

## 문서 지도

- [README](README.md) · [프로젝트 개요](docs/project-brief.md) · [workflow](docs/workflow.md) · [테스트 계획](docs/testing.md) · [결정 기록](docs/decisions/README.md)
