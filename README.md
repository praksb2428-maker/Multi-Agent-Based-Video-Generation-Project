# 숏츠 제작 멀티 에이전트팀

이 저장소의 목표는 [제안서](Video_Production_Project.md)에 따라 사용자 주제 하나로 숏츠 한 편을 기획·제작·검토하는 흐름을 만드는 것입니다. 문제·대상 사용자·산출물·범위의 기준 정보는 [프로젝트 브리프](docs/project-brief.md)에 있습니다.

[중간보고서 수정본](mid-report-v2.md)과 함께 공유하는 **2026-11-16 개발 진행본**입니다. 보고서의 GitHub·로컬 상태 설명은 작성 당시의 기준이며, 이 공유본에는 이후 로컬에서 진행한 소스·GUI·테스트·문서를 포함합니다. 실제 AI 영상·TTS·인터넷 검색·Codex 생성은 연결하지 않았고, GUI의 브라우저 자체 200% 확대 검증과 사용자 내용 확인은 남아 있습니다. 로컬 모델 파일·가상환경·실행 상태는 저장소에 포함하지 않습니다.
## 현재 범위

명시 CLI `draft-local`과 GUI의 **로컬 AI 실제 생성** 선택에서 **Ollama 0.40.16 + qwen3.5:4b-q4_K_M**으로 기획·대본을 생성합니다. GUI 기본 선택은 기존 템플릿이며 실제 생성은 해당 방식 선택 후 **기획 초안 만들기**를 누를 때만 실행합니다. Ollama 모델 서버는 아래 안내에 따라 별도로 시작해야 합니다. [GUI 연결 범위](docs/decisions/0015-gui-local-planning.md)

2026-11-16 J의 실제 한글 CLI 주제 생성은 36.703초에 미승인 3장면 JSON을 저장했습니다. 샘플의 분류·배출통 색상·벌금 표현은 사실 확인이 안 된 단정이므로 내용 품질은 미수락이며, JSON 검사 통과를 대본 채택으로 보지 않습니다. [모델 설정과 결정](docs/decisions/0014-local-ollama-planning.md)

강의 과제의 개발 하네스는 **계획 → 작성 → 검증 → 검토 → 문서화 → 개인 최종 확인**으로 설계했습니다. `.agents/skills/`의 project-plan·project-check·project-docs는 각각 계획·검증·문서화 절차이며, 작성자·검토자는 [기존 양식을 유지한 역할·인계 규칙](docs/workflow.md)을 따릅니다. 이전 회차의 파일 직접 읽기 수행과 새 설계의 실행·자동 발견은 구분합니다. [과제 보고서·실제 사용·회고 초안](docs/course-harness-report.md)

TXT 제작 요구사항에 맞춘 **로컬 GUI·프로젝트 스킬·역할/아키텍처 문서·로컬 모델 연결 모의 어댑터**를 추가했습니다. 실행은 `.\.venv\Scripts\python.exe -X utf8 shorts_web.py` 후 `http://127.0.0.1:8765`입니다. 기획·제작 승인은 별도 버튼이며 기존 CLI도 유지합니다. [제작 요구와 재사용 목록](docs/harness.md) · [시연·종료 안내](docs/shorts-production.md) · [역할과 그림](docs/architecture.md)

수정 요청 후 **명시적 기획 수정 → 별도 기획 재승인 → 새 모의 견적 → 별도 제작 재승인 → 새 로컬 합성 결과**도 연결했습니다. 각 승인 대기에서 멈추며 마지막 제작은 사용자의 명시 CLI 호출로만 진행합니다. [실행 예시](#수정-요청--재승인--모의-재제작)

현재 구현은 **기획·수정·승인 → 연출·프롬프트 → 모의 견적·승인 → 로컬 합성 MP4/SRT와 결과 검사**까지입니다. 기획만 명시적으로 실제 로컬 AI를 선택할 수 있으며 `local_template`·`openai_mock` 기획과 색상 카드·무음 오디오는 AI 생성물이 아닙니다. 승인된 로컬 모델의 CLI·GUI 기획/대본 생성 외에 CrewAI, AI 영상 생성과 TTS는 아직 연결하지 않았습니다. 프롬프트의 `cost_estimate`는 `null`이고 모의 승인은 외부 서비스·결제·유료 제작 권한이 아닙니다.

OpenAI SDK의 **모의 응답 경로**는 CLI `draft-mock`과 GUI의 **API 연결 모의 테스트 · OpenAI SDK** 선택에서 사용합니다. 실제 Python SDK가 요청을 직렬화하지만 고정 dummy 자격 증명과 `httpx.MockTransport`가 메모리 안에서 합성 응답을 반환합니다. API 키를 발급·설정할 필요가 없으며 기존 키·비밀 환경을 읽지 않습니다. `openai_mock`은 Codex나 실제 AI가 생성한 대본이 아니고 실제 서버·유료 API로 전환하는 옵션도 없습니다. 잘못된 응답은 승인·저장 전에 거부하고 두 승인은 사용자가 별도로 진행합니다. [API 모의 연결 결정과 원리](docs/decisions/0016-gui-api-mock.md)

기획의 **명시적 수정과 재승인**도 지원합니다. 수정 사유와 `hook`, `story`, `scenes`의 교체 값을 JSON으로 전달하면 원본을 보존하고 새 초안을 저장합니다. 자연어 사유를 AI가 해석하는 기능은 아니며, 입력 조건·출처·비용·승인은 수정 요청으로 바꿀 수 없습니다.

## 준비

기획 전 **모의 자료 조사 사용**을 선택하면 **모의 자료 검색**으로 고정된 합성 자료의 제목·모의 주소·요약을 확인할 수 있습니다. 조사 없이도 기존대로 생성합니다. 조사한 경우 자료를 기획 문맥과 승인 내용에 포함하며 저장된 기획에서도 출처를 다시 보여줍니다. 조건을 바꾸면 재검색해야 하고 자료 자체를 바꾸려면 새 기획으로 시작합니다. 실제 인터넷 검색·사실 확인·RAG 벡터 DB는 연결하지 않습니다. API 모의/템플릿은 실제 AI 생성물이 아니며 로컬 AI의 새 자료 반영은 이번에는 모의 요청으로만 검증합니다. [선택 범위와 승인 원리](docs/decisions/0017-optional-mock-research.md)

확정한 환경은 Python 3.12, `venv` + `pip`입니다. [requirements.txt](requirements.txt)에 `openai==3.41.0`, `httpx==0.28.1`을 고정했습니다. 패키지 설치에는 PyPI 다운로드가 필요하지만 모의 실행에는 API 키와 네트워크가 필요하지 않습니다. PowerShell에서 저장소 루트에서 실행합니다.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --index-url https://pypi.org/simple --only-binary=:all: -r requirements.txt
```

첫 명령이 Python 3.12를 표시하는지 확인하세요. `.venv`, `.env` 계열 파일과 `workspace/` 출력은 Git에서 제외됩니다. 초기 검증에는 합성·공개 예제만 사용합니다.

## 실행

로컬 모델 사용은 별도로 실행한 승인 portable 서버가 필요합니다. 서버가 없거나 버전·모델 digest가 다르면 오류로 끝나며 자동 설치/다운로드/시작하지 않습니다. 다음은 저장소 루트에서 격리 환경으로 서버를 명시 실행하는 PowerShell 안내입니다. 실행 전 11434가 비어 있는지 확인하고, 이미 사용 중이면 해당 프로세스를 임의 종료하지 마세요. 실행 파일·모델은 Git 제외 경로 workspace/local-model에 있습니다.

```powershell
$localModelRoot = Join-Path (Get-Location) 'workspace\local-model'
$localModelLaunch = [System.Diagnostics.ProcessStartInfo]::new()
$localModelLaunch.FileName = Join-Path $localModelRoot 'ollama-v0.40.16\ollama.exe'
$localModelLaunch.Arguments = 'serve'
$localModelLaunch.WorkingDirectory = Split-Path $localModelLaunch.FileName
$localModelLaunch.UseShellExecute = $false
$localModelLaunch.CreateNoWindow = $true
$localModelLaunch.Environment.Clear()
foreach ($runtimeName in @('PATH','SystemRoot','WINDIR')) {
    $localModelLaunch.Environment[$runtimeName] = [Environment]::GetEnvironmentVariable($runtimeName)
}
$privateModelHome = Join-Path $localModelRoot 'private-home'
$runtimeSettings = @{
    USERPROFILE=$privateModelHome
    APPDATA=(Join-Path $privateModelHome 'AppData\Roaming')
    LOCALAPPDATA=(Join-Path $privateModelHome 'AppData\Local')
    TEMP=(Join-Path $privateModelHome 'tmp')
    TMP=(Join-Path $privateModelHome 'tmp')
    OLLAMA_MODELS=(Join-Path $localModelRoot 'models')
    OLLAMA_HOST='127.0.0.1:11434'
    OLLAMA_NO_CLOUD='1'
    OLLAMA_NUM_PARALLEL='1'
    OLLAMA_MAX_LOADED_MODELS='1'
    OLLAMA_CONTEXT_LENGTH='4096'
    OLLAMA_KEEP_ALIVE='0'
    OLLAMA_NOPRUNE='1'
}
foreach ($runtimeName in $runtimeSettings.Keys) {
    $localModelLaunch.Environment[$runtimeName] = $runtimeSettings[$runtimeName]
}
$ownedLocalModelServer = [System.Diagnostics.Process]::Start($localModelLaunch)
```

서버의 초기 GPU 탐색이 끝난 뒤 같은 PowerShell에서 기획 생성 명령을 별도로 실행합니다. 기존 출력 경로는 덮어쓰지 않으므로 새 경로를 사용하세요.

```powershell
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py draft-local examples/shorts_brief.json workspace/local-draft.json
```

작업을 마치면 이 PowerShell에서 시작한 서버 객체만 종료하고 종료를 기다립니다.

```powershell
$ownedLocalModelServer.Kill()
$ownedLocalModelServer.WaitForExit()
```

첫 기동의 GPU 탐색이 끝난 뒤 draft-local을 호출합니다. 위 안내는 실제 검증에 쓴 자식 프로세스 환경을 옮긴 것이며 PowerShell 안내 전체를 복사해 별도 실행한 검사는 하지 않았습니다. Python으로 실행한 실제 서버·CLI·정리 근거는 [검사 기록](docs/testing.md)에 있습니다. 내용 확인 뒤에만 기존 `approve`를 별도 호출하며 모의 제작 승인은 다시 별도로 필요합니다. 자동 시작·전역 PATH/환경 변경은 등록하지 않았고 작업 서버는 검증 후 종료했습니다.

아래는 **현재 오프라인 기획 CLI의 실행 방법**입니다. 2026-10-30에 Python 3.12.1에서 예제 입력으로 초안·승인 JSON을 생성하고, 저장 파일을 다시 읽어 승인 유효성을 확인했습니다. 출력 파일이 이미 있으면 덮어쓰지 않으므로 다른 경로를 사용하세요. 전체 영상 제작 명령은 미구성입니다.

```powershell
.\.venv\Scripts\python.exe shorts_cli.py draft examples/shorts_brief.json workspace/shorts_draft.json
.\.venv\Scripts\python.exe shorts_cli.py approve workspace/shorts_draft.json workspace/shorts_approved.json
```

SDK 모의 경로의 정상 실행 예시입니다. 요청의 모델 문자열만 `gpt-6.1-sol`로 맞춘 것이며, 실제 모델을 호출하거나 접근 가능 여부·콘텐츠 품질을 검증한 결과가 아닙니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py draft-mock examples/shorts_brief.json workspace/mock_draft.json
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py approve workspace/mock_draft.json workspace/mock_approved.json
```

`draft-mock`에 `--mock-response examples/mock_refusal.json`을 붙이면 합성 거부 응답을 확인할 수 있습니다. 이때 종료 코드는 2이고 출력 파일은 생성하지 않습니다. 실제 API로 전환하는 옵션은 없습니다. SDK의 환경 설정 읽기를 모의 전용으로 격리하기 위해 고정 버전의 내부 모듈을 사용하므로 SDK 업데이트와 동시 실행은 별도 검증 대상입니다.

기획 수정 예시입니다. 유효한 승인 기획과 초안 모두 수정할 수 있으며, 수정 결과는 반드시 다시 승인해야 합니다. `scenes`를 수정할 때는 장면 배열 전체를 교체합니다. 빈 수정·실질적 변경 없음·변조된 승인 기획·잘못된 JSON은 거부합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py revise workspace/mock_approved.json examples/plan_revision.json workspace/revised_draft.json
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py approve workspace/revised_draft.json workspace/reapproved.json
```

수정본의 `revision`에는 버전·회차·부모 내용 해시·수정 사유·변경 필드를 기록합니다. 새 승인은 이 정보까지 결속하며, `revision`이 없는 기존 기획의 승인 해시는 그대로 유지합니다. 해시는 변경 감지용이며 사용자 인증이나 제작 허가가 아닙니다.

승인된 기획에서 로컬 연출과 범용 프롬프트를 만드는 예시입니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py direct workspace/reapproved.json workspace/direction.json
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py prompts workspace/reapproved.json workspace/direction.json workspace/prompts.json
```

연출은 승인된 조건·장면을 옮기고 조명·오디오의 미확정 부분을 `local_default`로 표시하는 고정 규칙입니다. `prompts`는 전체 훅·이야기 흐름과 장면 대본·행동·구도·길이·비율·스타일을 문자열로 묶습니다. 금지 요소는 긍정 프롬프트에 넣지 않고 `must_avoid`로 분리합니다. 생성된 `local_rule_template` 결과는 AI 연출물이 아니며 실제 영상 모델의 입력 규격이나 품질을 검증한 결과도 아닙니다.

미승인·변조된 기획, 다른 기획에 연결되거나 수동 변경된 연출은 거부합니다. 기획을 고치면 재승인 후 연출·프롬프트를 새로 생성하세요. 로컬 기본값이나 긍정 프롬프트가 금지어와 충돌해도 거부합니다. 프롬프트의 제공자·모델·견적·제작 승인은 모두 `null`이며, 실제 제작을 시작하는 명령은 없습니다.

## 모의 견적과 제작 승인 확인

아래 기능은 **가상 단위 `mock_credit`으로만** 동작합니다. [합성 단가 예제](examples/mock_pricing.json)는 임의 테스트 값이며 실제 서비스 요금·통화·환율이 아닙니다. 기획의 `max_budget` 숫자도 이 단계에서는 가상 단위 한도로만 비교합니다. 실제 예산이나 과금 한도를 설정하는 기능이 아닙니다.

산식은 장면마다 길이를 1초 단위로 올림한 값 × `video_per_second`, 대본의 Unicode 문자 수를 100자 단위로 올림한 값 × `narration_per_100_characters`, 프로젝트당 `assembly_fixed` 1회입니다. 합계·내역·예산 내 여부를 저장하고 승인 때 현재 입력으로 다시 계산합니다. 예산 초과 견적은 확인할 수 있지만 모의 승인은 거부합니다.

앞의 기획·연출·프롬프트 파일을 만든 다음 PowerShell에서 실행합니다. 모든 결과는 새 파일 경로여야 합니다.

```powershell
$mockInputs = @('workspace/reapproved.json', 'workspace/direction.json', 'workspace/prompts.json', 'examples/mock_pricing.json')
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py quote-mock @mockInputs workspace/mock_quote.json
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py approve-production-mock @mockInputs workspace/mock_quote.json workspace/mock_approval.json --approved-by 'local mock tester' --reason '모의 견적 확인'
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py check-production-mock @mockInputs workspace/mock_quote.json workspace/mock_approval.json
```

마지막 명령은 유효하면 종료 코드 0과 `mock approval valid; real execution is NOT authorized`를 출력합니다. 잘못되거나 만료된 승인은 종료 코드 2로 거부합니다. 모의 승인은 기획·연출·프롬프트·가격표·견적의 정확한 내용에 결속하고, 변경되면 다시 견적과 승인을 만들어야 합니다. 테스트용 유효기간은 승인 시점부터 1시간이며 실제 서비스의 승인 정책이 아닙니다.

승인 파일은 `scope: mock_only`, `real_execution_allowed: false`인 별도 기록입니다. 기획 승인과 원본 프롬프트의 `production_approval: null`은 그대로 보존합니다. 호출자 표기와 내용 해시는 신원 인증이나 전자서명이 아닙니다. 실행기·실제 API·키·결제·미디어 생성은 연결되어 있지 않습니다.

## 로컬 모의 제작과 결과 검사

FFmpeg와 FFprobe가 PATH에 있어야 합니다. 새 설치나 실제 API 전환 기능은 없습니다. 앞의 견적·모의 승인을 새로 만든 뒤 실행합니다. 테스트용 1시간 승인이 만료됐다면 기존 파일을 보존하고 새 경로로 다시 만드세요.

```powershell
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py produce-mock @mockInputs workspace/mock_quote.json workspace/mock_approval.json workspace/mock_result
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py validate-result-mock @mockInputs workspace/mock_quote.json workspace/mock_approval.json workspace/mock_result
```

`produce-mock`는 유효 승인과 입력을 확인한 다음 **프로젝트 `workspace/` 아래 새 폴더**에 `video.mp4`, `subtitles.srt`, `scenes.json`, `quality.json`, `manifest.json`을 저장합니다. 영상은 `MOCK / SCENE` 표시 색상 카드와 무음 AAC입니다. 대본은 별도 UTF-8 SRT에만 쓰며 셸·필터·외부 주소에 넣지 않습니다. `real_execution_allowed: false`는 유지하고 외부 AI·유료 제작은 하지 않습니다.

모의 프로필은 24fps, 비율에 맞는 짝수 96~640px, 최대 60장면입니다. 누적 길이를 가장 가까운 프레임으로 양자화하고 SRT 경계는 가장 가까운 밀리초로 기록합니다. 한 프레임보다 짧아 사라지는 장면, 극단 비율, SRT의 CR·빈 문단/가장자리 빈 줄은 거부하며 원문을 조용히 정규화하지 않습니다. 최종 길이는 목표의 ±10% 안이어야 합니다. 예제는 30초·360×640·720프레임입니다.

검사는 성공 플래그를 믿지 않고 경로·크기·SHA-256·입력 결속, FFprobe 길이/해상도/코덱/프레임, FFmpeg 전체 디코드·무음 샘플, SRT 순서/겹침/경계/대본과 장면 JSON을 다시 확인합니다. 승인 유효성은 **제작 시작 시점**을 기준으로 검사하므로 나중에 만료되어도 기존 영상의 기술 검사는 가능하며, 현재 입력이 달라지면 거부합니다.

결과 폴더를 덮어쓰지 않습니다. 렌더 중 실패하면 부분 결과와 `failure.json`을 보존하고 성공 manifest를 만들지 않습니다. 자동 재시도·삭제는 없으며 원인을 확인한 뒤 새 폴더로 실행합니다. `.work/`는 그 시도의 내부 합성 카드·클립입니다. 기술 검사 통과는 실제 AI 품질·내레이션 동기화·사용자 최종 채택을 뜻하지 않습니다.

2026-10-30 Python 3.12.1·FFmpeg/FFprobe 9.0.1에서 기존 58개와 신규 11개, 총 **69개 테스트**가 통과했습니다. 실물 30초 CLI 생성·재검사·파일 보존도 확인했습니다. [검증 범위와 한계](docs/testing.md#로컬-합성-제작과-결과-검사)

## 결과 검사와 명시적 확인 기록

기술 검사 결과와 사용자가 적은 수정 요청을 별도 JSON으로 보관합니다. 아래 각 명령의 `plan direction prompts pricing quote approval`은 현재 연결된 여섯 JSON 파일 경로입니다. 출력은 새 파일이어야 합니다.

```text
inspect-result-mock plan direction prompts pricing quote approval result_dir inspection.json
review-result-mock plan direction prompts pricing quote approval result_dir inspection.json examples/result_accept.json review.json
check-result-review-mock plan direction prompts pricing quote approval result_dir inspection.json review.json
```

실행은 `.venv\Scripts\python.exe shorts_cli.py` 뒤에 명령을 붙입니다. 수정 요청은 [예제](examples/result_changes.json)처럼 `request_changes`와 `content`·`visual`·`timing`·`subtitle` 항목을 적습니다. 기획, 연출/프롬프트, 제작/편집 중 돌아갈 단계와 필요한 재승인을 안내하며 자동으로 수정하거나 재생성하지 않습니다.

검사 실패도 보고서를 저장하고 종료 코드 2를 반환합니다. 기술 실패 상태의 `accept`는 거부합니다. 저장 기록을 확인할 때도 현재 입력·파일 해시와 실제 미디어 검사를 다시 수행합니다. `record_valid`는 기록의 결속이 유효하다는 뜻입니다. 예제의 합성 확인자는 실제 시청·신원 인증·최종 사용자 채택이 아니며, 원래 `quality.json`의 사람 확인 상태는 바꾸지 않습니다. 모든 기록은 모의 전용이며 실제 제작 허가는 계속 꺼져 있습니다.

2026-10-30 현재 파일 닫기 경고 회귀를 포함한 **80개 검사**와 보존된 30초 결과의 CLI 왕복이 통과했습니다. [근거와 한계](docs/testing.md#결과-검사보고와-수정-요청)

## 수정 요청 → 재승인 → 모의 재제작

`changes_requested` 확인 기록에 사용자가 작성한 [명시적 교체 JSON](examples/rework_revision.json)을 연결합니다. 자연어 문제를 해석하거나 해결됐다고 판단하지 않습니다. 원본 기획·영상·확인 기록은 보존하며 각 단계는 새 `workspace/` 폴더에 저장합니다. 저장 후 재개해도 원 여섯 입력·영상·검사·확인·교체 요청을 다시 검증합니다. `accepted` 결과나 차단·원인 불명 상태는 자동 처리하지 않습니다.

아래 `$oldInputs`에는 **보존된 원본** `plan direction prompts pricing quote approval`의 여섯 JSON 경로를 순서대로 넣습니다. `$source` 뒤의 네 경로도 해당 원본과 연결된 현재 파일이어야 합니다. 실제 확인한 합성 예제 경로는 다음과 같습니다. 기존 이름이 있으면 새 출력 경로를 선택하세요.

```powershell
$oldInputs = @('workspace/planning-revision-20261030/reapproved.json', 'workspace/direction-prompt-20261030/direction.json', 'workspace/direction-prompt-20261030/prompts.json', 'examples/mock_pricing.json', 'workspace/mock-media-20261030/quote.json', 'workspace/mock-media-20261030/approval.json')
$source = $oldInputs + @('workspace/mock-media-20261030/result-30s', 'workspace/quality-feedback-20261030/inspection.json', 'workspace/quality-feedback-20261030/changes-review.json', 'examples/rework_revision.json')
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py rework-plan-mock @source workspace/rework-example/draft
# awaiting_plan_approval: 내용을 확인한 사용자가 별도로 기획 승인
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py approve workspace/rework-example/draft/draft.json workspace/rework-example/reapproved.json
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py prepare-rework-mock @source workspace/rework-example/draft workspace/rework-example/reapproved.json workspace/rework-example/prepared
# awaiting_mock_production_approval: 새 프롬프트·견적을 확인한 사용자가 별도로 모의 제작 승인
$newInputs = @('workspace/rework-example/prepared/plan.json', 'workspace/rework-example/prepared/direction.json', 'workspace/rework-example/prepared/prompts.json', 'workspace/rework-example/prepared/pricing.json', 'workspace/rework-example/prepared/quote.json')
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py approve-production-mock @newInputs workspace/rework-example/new-approval.json --approved-by 'local mock tester' --reason '새 견적 모의 확인'
.\.venv\Scripts\python.exe -X utf8 shorts_cli.py produce-rework-mock @source workspace/rework-example/draft workspace/rework-example/reapproved.json workspace/rework-example/prepared workspace/rework-example/new-approval.json workspace/rework-example/result
```

첫 명령은 `draft.json`·`revision.json`·`handoff.json`만, 준비 명령은 새 기획·연출·프롬프트·가격표·견적과 handoff만 저장합니다. 승인 함수나 렌더를 자동 호출하지 않습니다. 마지막 명령도 새 승인이 없거나 다른 내용·만료·예산 초과이면 렌더를 거부합니다. 원본 재검증의 읽기 전용 미디어 검사와 새 영상 렌더는 구분합니다. 입력·bundle 변경, 상위 이동·링크, 기존 폴더 덮어쓰기도 거부합니다. handoff에는 실행할 경로나 명령을 넣지 않습니다.

재제작 결과는 기존 다섯 파일에 `inspection.json`과 `rework.json`을 더합니다. 최종 상태는 `technical_complete_mock_human_review_pending`, 원 문제 해결 여부는 `not_inferred`입니다. 새 영상의 `inspection.json`으로 기존 `review-result-mock` 명령에서 별도 확인을 기록하세요. 새 모의 승인도 `real_execution_allowed: false`이며 실제 AI·유료 제작 허가는 아닙니다. 합성 카드의 글자는 그대로일 수 있고 수정 대본은 **SRT·장면 JSON**에 반영됩니다. 예제의 6→7초/15→14초 교체는 명시적 합성 테스트 값입니다.

2026-10-30 기존82+신규8, 총90개 검사와 실제30초 재제작·별도두승인·7초 경계·원본13파일 보존을 확인했습니다. [검증 범위](docs/testing.md#수정-요청과-별도-재승인-모의-재제작)

## 검사

현재 단위·CLI 테스트 명령은 아래와 같습니다. 2026-10-30에 Python 3.12.1에서 기존 5개와 경계·거부 경로를 보완한 총 14개 테스트가 통과했습니다. 기존 출력 파일 보존, 중복 승인 거부와 승인 후 내용 변경 시 무효 판단도 확인했습니다. 기획의 내용 해시는 변경 감지용이며 사용자 신원 인증이나 유료 제작 허가를 뜻하지 않습니다. 전체 제작·미디어·외부 API 검사용 명령은 미구성입니다. 대상별 계획은 [테스트 계획](docs/testing.md)에 있습니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

SDK 모의 후보에서는 기존 14개와 신규 14개를 합친 28개 테스트가 통과했습니다. 소켓/DNS 및 키·프록시 환경변수 접근을 막은 상태에서도 SDK 직렬화·응답 검증·승인이 동작했습니다. 별도 CLI 확인에서 발견한 JSON `null` fixture의 잘못된 대체 동작은 사용자 승인 예외 수정 후 거부하도록 고쳤고 회귀 검사도 통과했습니다. 상세 범위와 수리 이력은 [테스트 기록](docs/testing.md#sdk-모의-응답-후보)을 참고하세요. 이는 실제 모델·유료 API 검증 결과가 아닙니다.

기획 수정 단계에서는 기존 28개와 신규 10개를 합친 **38개 테스트**가 통과했습니다. 실제 모의 기획 생성 → 승인 → 수정 → 재승인 → 재로딩, 원본 보존과 수정 정보 변조 시 승인 무효도 확인했습니다. 단계별 근거는 [테스트 기록](docs/testing.md#기획-수정과-재승인)에 있습니다.

연출·프롬프트 단계에서는 기존 38개와 신규 10개, 총 **48개 테스트**가 통과했습니다. 승인 게이트, 오래되거나 변경된 연출 거부, 금지 요소 분리, 원본·출력 보존과 네트워크·환경 읽기 차단 아래 동작을 확인했습니다. [검사 범위와 한계](docs/testing.md#로컬-연출과-범용-프롬프트)

모의 견적·제작 승인 단계에서는 기존 48개와 신규 10개, 총 **58개 테스트**가 첫 검사에서 통과했습니다. 산식·올림·예산 경계·입력 결속·변조·만료·통신/환경 차단과 CLI 저장·거부·파일 보존을 확인했습니다. [검사 범위와 한계](docs/testing.md#모의-견적과-제작-승인)

## 문서 탐색

- [제안서 원본](Video_Production_Project.md) · [프로젝트 브리프](docs/project-brief.md): 목표와 범위
- [프로젝트 규칙](AGENTS.md) · [작업 흐름](docs/workflow.md): 작업·검토 방식
- [테스트 계획](docs/testing.md): 확인 대상과 현재/후속 검사
- [ADR 결정 기록](docs/decisions/README.md): 확정된 선택과 개인 확인 기준
- [초기 질문과 답변](docs/open-questions.md) · [첫 구현 요구사항](requirements.md): 결정 당시 문맥과 기존 구현 범위
