# GPT 스토리보드 영상 작업실

프롬프트와 선택적 기준 이미지로 10·20·30초 숏폼의 10초 구간을 설계합니다. GPT API는 프롬프트를 보강하고 장면별 대표 이미지 묘사와 카메라 이동을 정합니다. OpenAI 이미지 API로 만든 예시를 프롬프트와 함께 검토한 뒤, 사용자가 최종 승인하면 로컬 FFmpeg가 **무음 MP4**를 합성해 다운로드할 수 있게 합니다. 정지 이미지의 확대·이동 효과이며 피사체의 연속 동작을 생성하는 AI 영상은 아닙니다.

## 준비

- Python 3.12, `venv`·`pip`, FFmpeg와 FFprobe가 필요합니다. API 요청에는 `httpx==0.28.1`을 사용합니다.
- 서버 환경 변수 `OPENAI_API_KEY` 또는 Git 제외 루트 `.env`에 기존 OpenAI 키를 둡니다. [openai.env.example](openai.env.example)을 참고하세요. 키·개인 이미지를 Git에 넣지 마세요.
- FFmpeg와 FFprobe가 `PATH`에 없으면 둘이 있는 폴더를 `FFMPEG_BIN`으로 지정합니다. 아래는 이 PC에서 확인한 경로입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FFMPEG_BIN = 'C:\Users\Administer\anaconda3\envs\llm\Library\bin'
```

## 실행

```powershell
.\.venv\Scripts\python.exe -X utf8 storyboard_web.py
```

[로컬 작업실](http://127.0.0.1:8766)에서 프롬프트 보강 → 10초 구간 확인 → 예시 이미지 비용 확인·생성 → 이미지와 프롬프트 검토 → 영상 미생성 또는 최종 승인 → MP4 다운로드 순서로 진행합니다. 기준 이미지는 프롬프트 해석과 예시 이미지 생성 요청에 전달됩니다. 예시는 최종 영상의 9:16 기본 구도로 표시되며 이동 중 가장자리가 더 잘릴 수 있습니다.

보강 버튼은 `gpt-6.1-sol`, 예시 생성 버튼은 `gpt-image-2` API를 호출해 비용이 발생할 수 있습니다. 화면의 이미지 출력 단가 참고값은 입력·보강 비용을 포함한 총액이나 상한이 아닙니다. 최종 MP4는 추가 영상 API 호출 없이 로컬에서 만듭니다. 실패 시 자동 재시도·공급자 전환은 없습니다. 실제 OpenAI 계정·과금·결과 품질은 아직 검증하지 않았습니다.

## 검사와 문서

```powershell
$env:FFMPEG_BIN = 'C:\Users\Administer\anaconda3\envs\llm\Library\bin'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/check_architecture_sync.py --base HEAD
```

[프로젝트 브리프](docs/project-brief.md) · [아키텍처](docs/architecture.md) · [역공학 설계 문서](docs/reverse-engineering/README.md) · [HTML 구조도](docs/architecture.html) · [테스트 범위](docs/testing.md) · [작업 흐름](docs/workflow.md) · [결정 기록](docs/decisions/README.md)

제안서 원본, [처음 구상한 하네스](docs/harness.md)와 [참고 스킬](harness/skills/project-bootstrap/SKILL.md), 과거 결정·보고서는 개발 이력으로 보존했습니다. 이 문서들의 이전 명령은 현재 앱에서 실행되지 않을 수 있습니다. 2026-11-24 사용자 결정에 따라 이전 8765 GUI·CLI·모의 제작 **코드와 전용 테스트·예제**는 제거했습니다. [제거한 파일 44개](docs/removed-legacy-files.md) · [제거 결정](docs/decisions/0021-remove-legacy-runtime.md)
