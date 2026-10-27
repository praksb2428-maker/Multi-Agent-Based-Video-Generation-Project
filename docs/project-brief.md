# 프로젝트 브리프: 숏츠 제작 멀티 에이전트팀

## 근거와 상태 표기

요청된 `proposal.md`는 현재 저장소에 없다. 사용자는 [`Video_Production_Project.md`](../Video_Production_Project.md)를 이 작업의 제안서 원본으로 확정했다. 참고 프로젝트 분석 보고서는 별도 자료이며 이 프로젝트의 확정 요구사항으로 취급하지 않는다. 확정 선택의 기준 기록은 [ADR](decisions/README.md)이다.

- **명시된 사실**: 제안서에 직접 적힌 목표·계획·후보. 미래형 서술은 구현 완료를 뜻하지 않는다.
- **현재 상태**: 저장소 파일을 읽어 확인한 구현·구성.
- **확정 결정**: 제안서에 없는 사항에 대해 사용자가 이번 작업에서 선택한 방향.
- **제안**: 초기 개발 환경을 구성할 때 적용하면 좋을 방침. 승인된 요구사항은 아니다.
- **미정**: 제안서나 현재 파일로 결론 낼 수 없는 선택.

## 문제, 사용자, 기대 결과

| 구분 | 내용 | 근거 |
| --- | --- | --- |
| 명시된 사실 · 문제 | 시청자 분석부터 품질 검사까지 숏츠 제작의 단계가 많고, 따로 처리하면 오래 걸리며 영상마다 품질과 형식이 달라지기 쉽다. | [제안서 §2.1 「문제 정의」](../Video_Production_Project.md#L12) |
| 명시된 사실 · 사용 주체 | 주제·조건·금지 요소·예산을 입력하고 기획·프롬프트·예상 비용을 확인한 뒤 수정·제작을 승인하는 사용자다. 영상의 **대상 시청자**는 입력 항목이지만, 구체적인 사용자 직군이나 시청자 집단은 지정되지 않았다. | [§2.1 「제안 배경」](../Video_Production_Project.md#L13), [§3.3 「입력 형태」](../Video_Production_Project.md#L32) |
| 명시된 사실 · 기대 결과 | 에이전트가 기획 → 연출 → 프롬프트 → 승인 → 제작 → 검토를 연결해 주제 하나로 숏츠 한 편을 만들고, MP4·SRT·장면별 JSON·품질 검사 결과를 제공한다. 장면의 배경·행동·카메라·길이를 채우고 최종 길이를 목표의 ±10% 안에 둔다. | [§3.1 「정량적/정성적 달성 목표」](../Video_Production_Project.md#L23), [§3.2 「에이전트 워크플로우」](../Video_Production_Project.md#L28), [§3.3 「최종 형태」](../Video_Production_Project.md#L33) |

## 범위와 제외 범위

| 구분 | 내용 | 근거 |
| --- | --- | --- |
| 명시된 사실 · 목표 범위 | 첫 완성 목표는 **입력 주제 하나로 짧은 영상 한 편**이다. 사용자 기획 승인과 제작 승인, 수정 후 재검토, 자동 검사와 사람의 영상 확인을 포함한다. 이후 다른 주제로 반복 적용한다. | [§3.1 「달성 목표」](../Video_Production_Project.md#L23), [§3.2 「에이전트 워크플로우」](../Video_Production_Project.md#L28) |
| 명시된 사실 · 입력/참고 자료 | 주제, 목표 길이, 화면 비율, 스타일, 대상 시청자, 금지 요소, 최대 예산을 받는다. 참고 자료는 선택 사항이며 출처와 사용 가능 범위를 기록한다. 참고 자료 없이도 진행할 수 있어야 한다. | [§3.3 「입력 형태」](../Video_Production_Project.md#L32), [§3.2 「에이전트 워크플로우」](../Video_Production_Project.md#L28) |
| 명시된 사실 · 제외 | 제안서의 현재 범위에서 RAG와 벡터 데이터베이스를 쓰지 않는다. 참고 자료 검토도 자료가 제공된 경우에만 한다. | [§4.2 「모델 외 연계 기술」](../Video_Production_Project.md#L43), [§2.2 「기존 프로젝트와의 차별성」](../Video_Production_Project.md#L17) |
| 확정 결정 · 이번 단계 | 초기 개발 하네스는 Python 3.12 `venv`·`pip`와 명시적 의존성 파일을 쓰고, 기존 JSON 계약·승인 단계 및 합성 예제를 오프라인으로 검증한다. CrewAI 선택과 유료 API 호출은 이후 단계로 둔다. 앱 기능은 추가하지 않는다. | [확정 ADR](decisions/README.md) |

## 기술, 데이터, 외부 API, 실행 환경, 제약

| 구분 | 내용 | 근거 |
| --- | --- | --- |
| 명시된 사실 · 언어/도구 | Python 3.12 가상환경, Visual Studio Code, Git·GitHub를 계획한다. `openai`, `pydantic`, `python-dotenv`, FFmpeg를 사용할 계획이며 `crewai`는 CrewAI 채택 시에만 추가한다. | [§4.3 「개발 언어 및 환경」](../Video_Production_Project.md#L47), [「주요 라이브러리」](../Video_Production_Project.md#L48) |
| 명시된 사실 · 에이전트/데이터 | 역할 분리와 순차 전달을 설계하고, 에이전트 간 결과를 버전 있는 JSON 스키마로 전달한다. 작업 상태, 승인된 기획안·프롬프트, 예상 비용을 저장할 계획이다. CrewAI는 구현 **후보**이고 승인 후 재개 및 도구 호출을 시험한 뒤 확정한다. | [§3.2 「에이전트 워크플로우」](../Video_Production_Project.md#L28), [§4.2 「에이전트 프레임워크」](../Video_Production_Project.md#L42), [「모델 외 연계 기술」](../Video_Production_Project.md#L43) |
| 명시된 사실 · 외부 API/미디어 도구 | OpenAI API를 기획·대본·TTS에 사용할 계획이다. `gpt-4o-mini`는 기획·대본·프롬프트용 우선 검토 모델이다. 영상 생성 API와 모델은 기능·비용 비교 뒤 선정한다. FFmpeg로 장면·음성·배경음·자막을 결합한다. | [§4.1 「기반 LLM 모델」](../Video_Production_Project.md#L38), [§4.2 「외부 연동 도구 및 API」](../Video_Production_Project.md#L44) |
| 명시된 사실 · 비용/승인 | 구체적 개발 예산은 미정이다. 제작 전에 예상 비용과 입력된 최대 예산을 확인하고, 유료 영상·음성 재생성은 추가 비용 안내와 사용자 승인을 거쳐야 한다. | [§4.1 「예상 API 비용」](../Video_Production_Project.md#L39), [§3.2 「에이전트 워크플로우」](../Video_Production_Project.md#L28) |
| 명시된 사실 · 검사 | 영상 길이·해상도·자막 타이밍은 자동 검사하고, 인물·배경 일관성·음성 동기화·내용 적절성은 사용자 확인을 병행한다. 변경된 내용과 후속 단계는 재검토하고 제작 내용이 바뀌면 다시 승인받는다. | [§2.2 「기존 프로젝트와의 차별성」](../Video_Production_Project.md#L17), [§3.1 「핵심 에이전트 루프」](../Video_Production_Project.md#L24), [§3.2 「에이전트 워크플로우」](../Video_Production_Project.md#L28) |

## 데이터·키·개인정보에 관한 프로젝트별 주의

| 구분 | 내용 | 근거 |
| --- | --- | --- |
| 명시된 사실 | 선택적 참고 자료는 **출처와 사용 가능 범위**를 기록하고, 불명확하면 사용자에게 확인해야 한다. 입력에는 주제·대상 시청자·금지 요소 등이 포함되며 기획안과 승인·비용 상태를 저장할 계획이다. | [§3.2 「에이전트 워크플로우」](../Video_Production_Project.md#L28), [§3.3 「입력 형태」](../Video_Production_Project.md#L32), [§4.2 「모델 외 연계 기술」](../Video_Production_Project.md#L43) |
| 제안 | 실제 참고 자료나 프롬프트에 개인정보·초상·음성이 들어갈 수 있으므로, 초기 테스트는 합성 예제로 하고 외부 API 전송 전에 자료 사용권과 개인정보 포함 여부를 확인한다. API 키는 코드·JSON·로그·Git에 넣지 않고 로컬 환경 변수 또는 Git에서 제외된 비밀 파일로만 주입한다. 저장할 원본·중간 파일·승인 기록의 위치와 보존 기간을 먼저 정한다. | 위 입력·저장·외부 API 계획에서 도출한 하네스 운영 제안. `.gitignore`에는 현재 `.env`와 `workspace/` 제외 규칙이 있다. |
| 미정 | 향후 실제 참고 자료의 종류·사용권, 개인정보/음성/초상 포함 여부, 저장·삭제 기준, 키 주입 방식과 유료 API 시험 조건은 확정되지 않았다. 이번 단계의 합성 예제·오프라인 검증 선택은 [확정](decisions/README.md)됐다. | [§3.3 「입력 형태」](../Video_Production_Project.md#L32), [§4.1 「예상 API 비용」](../Video_Production_Project.md#L39) |

## 현재 저장소 상태와 간극

- **현재 상태**: [`src/shorts.py`](../src/shorts.py)는 Python 표준 라이브러리로 입력 검증, 3장면 로컬 템플릿, JSON 기획 검증, 승인 시각·내용 해시를 구현한다. [`shorts_cli.py`](../shorts_cli.py)는 `draft`/`approve` 명령으로 JSON 파일을 생성하며, [`tests/test_shorts.py`](../tests/test_shorts.py)에 단위·CLI 테스트가 있다. [`README.md`](../README.md)와 [`requirements.md`](../requirements.md)는 이 범위를 첫 구현으로 설명한다. 2026-10-27에 Python 3.12.7 가상환경에서 기존 테스트 5개가 통과했다.
- **현재 상태**: 모델·CrewAI·영상 생성·TTS·자막 생성·FFmpeg 조립은 연결되어 있지 않다. 현재 `cost_estimate`는 `null`이고 기획 승인은 유료 제작 실행 승인과 다르다. [README 「현재 범위」](../README.md#L5), [`src/shorts.py`](../src/shorts.py)
- **현재 상태**: `proposal.md`는 없으며 `requirements.txt`는 현재 오프라인 단계에 외부 Python 의존성이 없음을 명시한다. `.gitignore`는 `.env` 계열 비밀 파일, `.venv`, `workspace/`를 제외한다.
- **미정**: CrewAI 채택 여부, 영상 API 제공자·모델, 비용 상한과 실제 자료 취급 규칙은 후속 단계에서 정한다. [§4.1](../Video_Production_Project.md#L38), [§4.2](../Video_Production_Project.md#L42), [ADR](decisions/README.md)
