# 숏츠 제작 멀티 에이전트팀: 첫 구현

이 저장소는 [숏츠 제작 기획안](https://github.com/praksb2428-maker/Multi-Agent-Based-Video-Generation-Project/blob/main/Video_Production_Project.md)의 **콘텐츠 기획 단계**를 실행하는 첫 구현입니다. 현재는 입력 조건을 검증하고, 3장면짜리 로컬 템플릿 초안을 JSON으로 만들고, 검증된 초안을 승인할 수 있습니다. `source: local_template`은 AI가 작성한 기획안이 아니라는 뜻입니다.

## 실행

Python 3.12에서 추가 패키지나 API 키 없이 실행됩니다.

```bash
python shorts_cli.py draft examples/shorts_brief.json workspace/shorts_draft.json
python shorts_cli.py approve workspace/shorts_draft.json workspace/shorts_approved.json
python -m unittest discover -s tests -v
```

출력 경로에 파일이 이미 있으면 덮어쓰지 않습니다. 내용을 수정하려면 새 출력 경로를 지정하세요. `approved` 상태에는 승인 시점과 내용의 SHA-256 해시가 기록됩니다. 이후 기획 내용이 바뀌면 `is_approved()`가 거짓을 반환합니다.

초안에는 입력 조건, 훅, 이야기 구조, 장면별 대본·배경·행동·카메라·길이가 포함됩니다. 장면 길이 합계는 목표 길이의 ±10% 이내로 검사합니다. 금지어가 주제나 초안 문구에 있으면 승인이 거부됩니다.

## 현재 범위

이번 단계에는 LLM, CrewAI, 영상 생성, TTS, 자막 생성, FFmpeg 조립이 연결되지 않았습니다. `cost_estimate`는 `null`이며, 승인된 JSON은 **기획 승인 기록**일 뿐 유료 제작 실행 허가나 완성 영상이 아닙니다. 실제 모델과 영상 생성 서비스를 선택하고 비용 산정 및 별도의 제작 승인 단계를 구현한 뒤에 제작을 연결해야 합니다.

현재 기획 단계 이후의 제작 흐름은 사용자 제공 기획안의 후속 개발 범위입니다.
