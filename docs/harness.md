# TXT 제작 요구사항과 현재 범위

이 문서는 강의 메모에서 프로젝트에 필요한 제작 요구를 골라 기존 코드와 연결한 기준이다. 제안서 원본은 보존한다. 초기 로컬 모델 모의 준비 이후 사용자 후속 승인에 따라 Ollama portable·Qwen3.5 4B를 설치하고 명시 CLI에 이어 GUI의 기획 방식 선택에도 실제 기획·대본 생성을 연결했다. 기본은 규칙 템플릿이며, 생성된 내용의 사실성·사용자 채택은 별도다. [GUI 연결 결정](decisions/0015-gui-local-planning.md)

## 필요한 제작물

| 요구 | 재사용·새 제작 | 완료를 확인하는 방법 |
| --- | --- | --- |
| 제안서 기반 에이전트 규칙 | [AGENTS](../AGENTS.md)에 8개 설계 책임·입출력·작성 범위·중단·두 승인 규칙 반영 | 현재 코드·역할 표·링크 비교 |
| 기능별 필요·제외 체크리스트 | 이 표와 아래 제외 범위 | 구현·검증·보류 구분 |
| 스킬·오케스트레이션 | [프로젝트 스킬](#프로젝트-스킬)과 `src/gui_workflow.py` | 파일 구조와 실제 GUI/API 순서·거부 검사 |
| 아키텍처 그림·숏폼 MD | [아키텍처](architecture.md)·[제작 안내](shorts-production.md) | SVG 렌더·내용·문서 링크 |
| 문서화·테스트 기록부 | 기존 [testing](testing.md)와 작업별 RUN | 실제 명령·환경·로그·영향 범위 기록 |
| Python 서비스·localhost GUI | `shorts_web.py`·`web/` | 실제 HTTP·브라우저 입력부터 수정 재제작까지 |
| 로컬 경량 모델 | `src/local_model_mock.py` 보존, `src/local_ollama.py`·명시 draft-local·GUI 실제 기획 선택 | 고정 loopback/버전/digest·실제 한글 기획 JSON·미승인 경계 검사. GUI 생성 외 조회/승인/수정 호출0과 내용 확인 대기 |
| 중간보고서 시연 캡처 | [시연 순서](shorts-production.md#중간보고서-시연)와 작업별 대표 PNG | 실제 실행 화면·상태와 캡처 일치 |
| 저장소 기능·소개 화면 | GUI의 프로젝트 소개·아래 재사용 목록 | 기존 기능과 새 기능을 화면에서 확인 |

## 그대로 활용하는 코드

- `src/shorts.py`: 입력 조건·초안·명시 수정·기획 승인과 내용 결속.
- `src/direction.py`: 액션/비주얼의 로컬 규칙 연출·프롬프트. 별도 LLM 연출팀은 아니다.
- `src/mock_production.py`: 가상 견적·예산 비교·별도 모의 승인·1시간 테스트 만료.
- `src/mock_media.py`: 실제 FFmpeg 합성·FFprobe·전체 디코드·무음·SRT 검사.
- `src/quality_feedback.py`: 별도 기술 검사보고·사용자의 확인/수정 요청·현재성 재검증.
- `src/mock_rework.py`: 수정 원본 결속·정확 수정본의 재승인·새 견적/승인·새 결과.
- `shorts_cli.py`: 기존 명령을 유지한다. GUI는 셸로 CLI 문자열을 만들지 않고 같은 함수를 호출한다.

## 프로젝트 스킬

강의 P3·P5의 기본 개발 스킬은 다음 세 개다. 실제 수행·제출 정리는 [강의 하네스 보고서](course-harness-report.md)에 있다. 기존 다섯 참고 절차는 삭제하지 않고 아래에 보존하며 같은 검사를 중복 실행하지 않는다.

| 강의용 스킬 | 책임 |
| --- | --- |
| [project-plan](../.agents/skills/project-plan/SKILL.md) | 제안서·기존 결정에 맞춰 범위·검사·미정을 계획 |
| [project-check](../.agents/skills/project-check/SKILL.md) | 실제 검사와 종료 코드·재사용·미실행 기록, 코드·테스트 수정 금지 |
| [project-docs](../.agents/skills/project-docs/SKILL.md) | 확인된 결과의 문서 반영·회고 초안, 승인·실행 사실 발명 금지 |

`.agents/skills/`는 프로젝트용 경로이며 전역 설치를 하지 않는다. 새 세션에서 자동 발견되는지는 별도 확인 대상이다.

### 기존 참고 절차

| 스킬 | 사용할 때 |
| --- | --- |
| [project-bootstrap](../harness/skills/project-bootstrap/SKILL.md) | 기존 환경에서 시작·재개·임시 서버 종료 |
| [project-documentation](../harness/skills/project-documentation/SKILL.md) | 현재 결과·제약·검사 근거 문서화 |
| [project-testing](../harness/skills/project-testing/SKILL.md) | 파트별 검사·근거 재사용·수리 한도 |
| [project-ui-ux](../harness/skills/project-ui-ux/SKILL.md) | 승인·상태·접근성·반응형 화면 |
| [project-shorts](../harness/skills/project-shorts/SKILL.md) | 명시 승인과 수정·재제작 흐름 |

모두 이 저장소에서 명시적으로 읽어 사용하는 프로젝트 문서다. Codex 전역에 등록·설치하지 않았고 자동 발견이나 글로벌 팀 실행을 검증한 결과가 아니다.

## 이번에 하지 않는 것

승인된 Ollama 0.40.16·qwen3.5:4b-q4_K_M 이외의 다운로드/설치, 유료 API·실제 영상 모델·TTS·API 키·외부 자료 업로드·자동 게시·계정 연결·새 패키지·RAG·벡터 DB는 제외한다. 참고 자료를 다루는 큐레이션은 설계 책임만 남기고 현재 실행에서는 정상적으로 생략한다. 대규모 전문팀 분할과 LLM 독립 내용 검토도 실제로 구현한 기능처럼 표시하지 않는다.

TXT의 면접 관련 메모는 이 제작 요구와 관계가 없어 제외했다. 소개 화면은 프로젝트와 실제 제공 기능을 설명하며 개인의 이름·경력·학번을 임의로 넣지 않는다.
