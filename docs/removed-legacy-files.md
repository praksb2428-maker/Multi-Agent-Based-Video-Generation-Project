# 이전 실행 기능 파일 정리 — 2026-11-24

사용자가 새 8766 스토리보드 작업실에 맞춰 **이전 기능 전체 제거**를 선택했다. 아래는 현재 Git 작업본에서 제거한 추적 파일 **44개**다. 새 런타임의 유일한 옛 의존이던 키 읽기 함수를 `src/storyboard_openai.py`로 옮긴 뒤 삭제했다. [ADR 0021](decisions/0021-remove-legacy-runtime.md)

| 묶음 | 제거한 파일 | 이유 |
| --- | --- | --- |
| 이전 진입 3 | `shorts_cli.py`, `shorts_web.py`, `demo.py` | 이전 기획·모의 제작 CLI/8765 GUI 전용 |
| 이전 소스 12 | `src/shorts.py`, `src/direction.py`, `src/gui_workflow.py`, `src/research_mock.py`, `src/openai_api.py`, `src/openai_mock.py`, `src/local_ollama.py`, `src/local_model_mock.py`, `src/mock_production.py`, `src/mock_media.py`, `src/mock_rework.py`, `src/quality_feedback.py` | 새 `storyboard_*` 경로에서 호출하지 않는 이전 기획·조사·모의 제작·검토 |
| 이전 웹 4 | `web/index.html`, `web/app.js`, `web/app.css`, `web/architecture.svg` | 이전 8765 화면과 당시 구조 그림 |
| 이전 테스트 16 | `tests/test_direction.py`, `tests/test_gui_local_model.py`, `tests/test_gui_openai_mock.py`, `tests/test_local_model_mock.py`, `tests/test_local_ollama.py`, `tests/test_mock_media.py`, `tests/test_mock_production.py`, `tests/test_mock_rework.py`, `tests/test_openai_api.py`, `tests/test_openai_mock.py`, `tests/test_plan_revision.py`, `tests/test_quality_feedback.py`, `tests/test_research_mock.py`, `tests/test_shorts.py`, `tests/test_ui_contract.py`, `tests/test_web.py` | 삭제한 기능 전용 계약 |
| 이전 fixture 2 | `tests/fixtures/legacy_plan_without_research_v1.json`, `tests/fixtures/ui_contract_v1.json` | 이전 JSON/UI 테스트 입력 |
| 이전 예제 7 | `examples/shorts_brief.json`, `examples/rework_revision.json`, `examples/result_changes.json`, `examples/result_accept.json`, `examples/plan_revision.json`, `examples/mock_refusal.json`, `examples/mock_pricing.json` | 이전 CLI·모의 기능 전용 입력 |

**보존:** 처음 구상한 하네스의 `harness/skills/` 5개 스킬과 `docs/harness.md`, `docs/shorts-production.md`, `requirements.md`는 사용자 후속 지시에 따라 Git 원본 그대로 복원했다. `.agents/skills/`의 현재 개발 스킬, 제안서·과거 ADR·보고서·증빙 이미지, Git 제외 `workspace/`·`.venv/`·`.env`도 유지한다. 보존된 옛 안내의 실행 명령은 현재 앱에서 동작하지 않을 수 있다. 실행 기준은 [README](../README.md)다.

삭제는 Git 작업본의 파일 변경이며 아직 커밋·푸시하지 않았다. 추적 파일의 과거 내용은 Git 이력에서 확인할 수 있다. 새 런타임 import·현재 15개 검사와 문서 링크 검사는 [테스트 기록](testing.md)과 작업 기록에 구분해 남긴다.
