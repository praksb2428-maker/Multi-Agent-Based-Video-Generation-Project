# 숏츠 제작 멀티 에이전트팀

이 저장소의 목표는 [제안서](Video_Production_Project.md)에 따라 사용자 주제 하나로 숏츠 한 편을 기획·제작·검토하는 흐름을 만드는 것입니다. 문제·대상 사용자·산출물·범위의 기준 정보는 [프로젝트 브리프](docs/project-brief.md)에 있습니다.

## 현재 범위

현재 구현은 **콘텐츠 기획과 기획 승인**까지입니다. 입력 조건을 검증하고 3장면짜리 `local_template` JSON 초안을 만든 뒤, 내용 해시와 승인 시각을 기록할 수 있습니다. 초안은 AI 생성물이 아닙니다. LLM, CrewAI, 영상 생성, TTS, 자막 생성, FFmpeg 조립은 아직 연결되지 않았습니다. `cost_estimate`는 `null`이며 기획 승인은 유료 제작 실행 허가가 아닙니다.

## 준비

확정한 환경은 Python 3.12, `venv` + `pip`입니다. 현재 [requirements.txt](requirements.txt)에는 외부 패키지가 없고 API 키도 필요하지 않습니다. PowerShell에서 저장소 루트에서 실행합니다.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index -r requirements.txt
```

첫 명령이 Python 3.12를 표시하는지 확인하세요. `.venv`, `.env` 계열 파일과 `workspace/` 출력은 Git에서 제외됩니다. 초기 검증에는 합성·공개 예제만 사용합니다.

## 실행

아래는 **현재 오프라인 기획 CLI의 실행 예시 초안**입니다. 출력 파일이 이미 있으면 덮어쓰지 않으므로 다른 경로를 사용하세요. **실행 절차와 출력의 최종 확인은 P4에서 실제 실행한 뒤 완성합니다.** 전체 영상 제작 명령은 미구성입니다.

```powershell
.\.venv\Scripts\python.exe shorts_cli.py draft examples/shorts_brief.json workspace/shorts_draft.json
.\.venv\Scripts\python.exe shorts_cli.py approve workspace/shorts_draft.json workspace/shorts_approved.json
```

## 검사

현재 단위·CLI 테스트 명령은 아래와 같습니다. 앞 단계에서 Python 3.12.7로 기존 테스트 5개가 통과했으며, P4의 실행·출력 확인은 아직 남아 있습니다. 전체 제작·미디어·외부 API 검사용 명령은 미구성입니다. 대상별 계획은 [테스트 계획](docs/testing.md)에 있습니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 문서 탐색

- [제안서 원본](Video_Production_Project.md) · [프로젝트 브리프](docs/project-brief.md): 목표와 범위
- [프로젝트 규칙](AGENTS.md) · [작업 흐름](docs/workflow.md): 작업·검토 방식
- [테스트 계획](docs/testing.md): 확인 대상과 현재/후속 검사
- [ADR 결정 기록](docs/decisions/README.md): 확정된 선택과 개인 확인 기준
- [초기 질문과 답변](docs/open-questions.md) · [첫 구현 요구사항](requirements.md): 결정 당시 문맥과 기존 구현 범위
