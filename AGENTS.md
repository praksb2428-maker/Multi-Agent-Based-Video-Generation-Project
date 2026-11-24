# Codex 프로젝트 규칙

## 목적과 범위

[제안서](Video_Production_Project.md)의 숏폼 제작 목표 중 현재 구현은 **GPT 스토리보드 → 예시 이미지 검토 → 사용자 최종 승인 → 로컬 무음 MP4**다. `storyboard_web.py`가 127.0.0.1:8766에서 실행된다. 사용자는 10·20·30초와 선택적 기준 이미지를 입력한다. GPT API는 10초 구간별 프롬프트·카메라 이동을 제안하고, OpenAI 이미지 API는 대표 이미지를 만든다. FFmpeg는 승인된 이미지를 이동·확대해 MP4로 합성한다. 피사체의 연속 동작을 생성하는 영상 모델로 표시하지 않는다. [현재 구조](docs/architecture.md) · [선택 ADR 0020](docs/decisions/0020-gpt-storyboard-local-mp4.md)

환경은 Python 3.12, `venv`+`pip`, `httpx==0.28.1`, 로컬 FFmpeg/FFprobe, VS Code, Git/GitHub다. `gpt-6.1-sol`·`gpt-image-2`와 OpenAI HTTPS endpoint는 서버에 고정한다. 키는 서버의 `OPENAI_API_KEY` 또는 Git 제외 `.env`에서만 읽는다. 실제 유료 API 호출·결과 품질은 아직 검증하지 않았다. 이전 8765 GUI·CLI·모의 제작 코드는 [ADR 0021](docs/decisions/0021-remove-legacy-runtime.md)에 따라 제거했다. **처음 구상한 하네스**와 제안서·과거 ADR·보고서는 이력으로 남긴다.

## 경로와 수정 범위

| 경로 | 역할 |
| --- | --- |
| `Video_Production_Project.md` | 제안서 원본. 명시 요청 없이 바꾸지 않는다. |
| `storyboard_web.py`, `web/storyboard.*` | localhost 서버와 간결한 입력·검토·다운로드 UI. 임의 경로·명령·모델·키를 요청에서 받지 않는다. |
| `src/storyboard_flow.py` | 작업 상태, 서버 발급 ID, 단계별 승인, 원본·예시·결과 변경 감지. |
| `src/storyboard_openai.py` | 서버 전용 키, 고정 GPT/이미지 API. 명시 버튼에서만 외부 호출한다. |
| `src/storyboard_render.py` | 승인된 이미지의 로컬 FFmpeg 합성과 FFprobe 검사. |
| `tests/`, `scripts/`, `.agents/skills/` | 합성 계약 검사, 설계 동기화 가드, 프로젝트 개발 절차. |
| `harness/skills/`, `docs/harness.md`, `docs/shorts-production.md`, `requirements.md` | 초기 구상 하네스와 당시 안내의 보존본. 현재 앱 실행 명령의 기준은 README다. |
| `README.md`, `docs/` | 사용 안내·브리프·아키텍처·작업 흐름·검사·결정·이력. 코드와 사실을 맞춘다. |
| `workspace/`, `.venv/`, `.env*` | 로컬 결과·환경·비밀. Git에 넣지 않고, 소유권 확인 없이 삭제하지 않는다. |

## 작업과 완료 기준

- 새 개발 요청은 [workflow](docs/workflow.md)의 계획 → 작성 → 검사 → 별도 읽기 검토 → 문서화 → 개인 채택 순서로 진행한다. 한 파일 집합은 한 명이 작성한다. 최초 실패 뒤 추가 수리는 최대 2회다. 설계 규칙만으로 도구 권한이나 에이전트 호출이 강제되지는 않는다.
- 구현을 바꾸면 같은 후보에서 `docs/architecture.md`(구조·흐름) 또는 이 파일(지속 규칙)을 갱신한다. 구조가 바뀌면 [HTML 구조도](docs/architecture.html)도 맞춘다. `python scripts/check_architecture_sync.py --base HEAD`는 **문서 변경 여부만** 확인하며 의미의 정확성은 검토자가 판단한다.
- 기술 스택, 데이터·저장·키 취급, 비용, 외부 서비스, 목표 범위·승인 지점의 변경은 적용 전에 개인의 결정을 받는다. [ADR 기준](docs/decisions/README.md)을 따른다. 승인된 현재 OpenAI 경로 밖의 유료 서비스·실제 모델·외부 전송·공개 배포를 임의로 추가하지 않는다. 사소한 파일 정리는 별도 승인 대상이 아니다.
- 프롬프트 보강, 예시 이미지 생성, 최종 렌더는 각각 명시 사용자 동작에서만 수행한다. 예시 전체를 검토한 뒤에만 최종 승인한다. 거절·실패·변조·알 수 없는 상태는 중단하며 자동 재시도나 공급자 전환을 하지 않는다. 해시는 변경 감지용이며 인증이 아니다.
- 실제 키·개인 이미지·사용자 결과를 테스트/예제/Git에 넣지 않는다. 검사는 합성 데이터와 모의 HTTP로 진행한다. 완료 보고에는 실제 실행, 유효한 결과 재사용, 미검증, 수리 누계, 독립 검토와 사용자 채택 대기를 구분한다. 실행하지 않은 API·검사를 통과했다고 쓰지 않는다.

## 문서 지도

[README](README.md) · [프로젝트 브리프](docs/project-brief.md) · [아키텍처](docs/architecture.md) · [역공학 설계 문서](docs/reverse-engineering/README.md) · [HTML 구조도](docs/architecture.html) · [workflow](docs/workflow.md) · [테스트 계획](docs/testing.md) · [결정 기록](docs/decisions/README.md)
